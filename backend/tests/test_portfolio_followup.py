"""Offline invariants for the PR #65 follow-up integration.

No yfinance call or Supabase secret is used. Synthetic returns make the tests
reproducible and suitable for CI.
"""
from __future__ import annotations

import sys
import types

import numpy as np
import pandas as pd
import pytest

# The project dependency is available in production. CI environments that run
# only these unit tests do not need the network package itself.
sys.modules.setdefault("yfinance", types.SimpleNamespace(download=lambda *a, **k: None))

from app.portfolio_logic.portfolio_logic import (  # noqa: E402
    DEFAULT_RANDOM_SEED,
    PortfolioRequest,
    allocate_account_buckets,
    build_portfolio_benchmark,
    build_portfolio_response,
    build_tax_optimizer_payload,
    calculate_beta,
    calculate_irp_status,
    calculate_financial_income_comprehensive_tax_status,
    resolve_external_financial_income_krw,
    extract_unique_profile,
    generate_random_weights,
)
from app.portfolio_logic.tax_advice import calc_combined_tax_saving  # noqa: E402


def _returns(seed: int = 7, n: int = 600) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.bdate_range("2023-01-02", periods=n)
    return pd.DataFrame(
        {
            "domestic_equity": rng.normal(0.00035, 0.010, n),
            "overseas_blue_chip": rng.normal(0.00045, 0.011, n),
            "overseas_growth": rng.normal(0.00055, 0.014, n),
            "overseas_dividend": rng.normal(0.00030, 0.009, n),
            "reit": rng.normal(0.00025, 0.012, n),
            "general_bond": rng.normal(0.00012, 0.003, n),
            "separate_tax_bond": rng.normal(0.00010, 0.004, n),
            "low_coupon_bond": rng.normal(0.00009, 0.004, n),
            "gold": rng.normal(0.00020, 0.009, n),
            "commodity": rng.normal(0.00010, 0.012, n),
            "dollar": rng.normal(0.00005, 0.005, n),
            "cash": np.full(n, 0.00005),
        },
        index=index,
    )


def _request(**overrides) -> PortfolioRequest:
    base = {
        "total_asset": 3_000_000_000,
        "risk_profile": "aggressive",
        "investment_horizon_years": 10,
        "unique_need_amount": 0,
        "isa_account_exists": True,
        "isa_account_age_years": 3,
        "isa_years_until_liquid": 0,
    }
    base.update(overrides)
    return PortfolioRequest(**base)


def test_random_weight_fallback_is_deterministic() -> None:
    assets = ["domestic_equity", "overseas_blue_chip", "cash"]
    first = generate_random_weights(assets)
    second = generate_random_weights(assets)
    assert DEFAULT_RANDOM_SEED == 42
    assert first == second
    assert sum(first.values()) == pytest.approx(1.0)


def test_portfolio_specific_benchmark_modes() -> None:
    returns = _returns()

    _, domestic = build_portfolio_benchmark(
        {"domestic_equity": 0.6, "cash": 0.4}, returns
    )
    _, overseas = build_portfolio_benchmark(
        {"overseas_growth": 0.6, "cash": 0.4}, returns
    )
    _, blended = build_portfolio_benchmark(
        {"domestic_equity": 0.3, "overseas_growth": 0.6, "cash": 0.1},
        returns,
    )

    assert domestic["mode"] == "kospi"
    assert overseas["mode"] == "sp500"
    assert blended["mode"] == "blended"
    assert blended["domestic_share_in_equity_sleeve"] == pytest.approx(1 / 3)
    assert blended["us_share_in_equity_sleeve"] == pytest.approx(2 / 3)


def test_beta_uses_the_same_portfolio_specific_benchmark() -> None:
    returns = _returns()
    weights = {"domestic_equity": 0.4, "overseas_growth": 0.6}
    benchmark, _ = build_portfolio_benchmark(weights, returns)
    assert benchmark is not None
    assert calculate_beta(benchmark, benchmark) == pytest.approx(1.0)
    assert calculate_beta(benchmark * 2.0, benchmark) == pytest.approx(2.0)


def test_pension_gating_zeroes_irp_for_short_horizon_young_client() -> None:
    young = _request(age=33, investment_horizon_years=3)
    status = calculate_irp_status(young)
    assert status["usable"] is False
    assert status["years_until_access"] == 22
    assert status["reason"] == "investment_horizon_shorter_than_pension_access"

    buckets = allocate_account_buckets(
        {"general_bond": 0.5, "overseas_blue_chip": 0.5},
        young.total_asset,
        young,
    )
    assert buckets["irp"]["allocated_amount"] == 0

    older = _request(age=62, investment_horizon_years=3)
    assert calculate_irp_status(older)["usable"] is True


def test_taxable_account_reserves_liquidity_before_lockup_accounts() -> None:
    request = _request(unique_need_amount=500_000_000)
    buckets = allocate_account_buckets(
        {"cash": 0.2, "general_bond": 0.3, "overseas_blue_chip": 0.5},
        request.total_asset,
        request,
    )
    taxable = buckets["taxable_account"]
    assert taxable["display_name"] == "일반과세 자산 운용"
    assert taxable["liquidity_reserve_target"] == 500_000_000
    assert taxable["liquidity_reserve_allocated"] == 500_000_000
    assert taxable["liquidity_reserve_shortfall"] == 0


def test_six_card_total_equals_contributions_and_display_is_descending() -> None:
    returns = _returns()
    expected = returns.mean() * 252
    weights = {
        "overseas_growth": 0.35,
        "overseas_dividend": 0.20,
        "general_bond": 0.20,
        "separate_tax_bond": 0.10,
        "cash": 0.15,
    }
    request = _request(
        age=62,
        investment_horizon_years=10,
        marginal_income_tax_rate=0.462,
        other_financial_income=40_000_000,
        overseas_realized_loss=5_000_000,
    )
    response = build_portfolio_response(
        "포트폴리오 A",
        "portfolio_a",
        weights,
        returns,
        expected,
        request,
        backtest_returns=returns,
    )
    tax = build_tax_optimizer_payload("portfolio_a", response, request)
    strategy = tax["strategy_cards"]
    contributions = [card["combined_contribution"] for card in strategy["cards"]]

    assert sum(contributions) == pytest.approx(strategy["combined_total"], abs=6)
    assert [card["key"] for card in strategy["cards"]] == [
        "isa",
        "pension_credit",
        "separate_bond",
        "low_tax_dividend",
        "overseas_exemption",
        "tax_loss",
    ]
    assert strategy["display_order_basis"] == "fixed_strategy_order"
    assert [card["priority_rank"] for card in strategy["cards"]] == list(
        range(1, 7)
    )


def test_corporate_context_is_generic_and_does_not_create_corporate_tax() -> None:
    profile = extract_unique_profile(
        "법인 단기 운전자금 20억 원 유동성 필요, 가업 승계와 상속 준비. "
        "IRP 2016년 가입, 올해 900만 원 납입"
    )
    context = profile["client_context"]
    assert profile["liquidity_need_amount"] == 2_000_000_000
    assert context["has_corporation"] is True
    assert context["estate_succession_goal"] is True
    assert "corporate_finance_review_required" in context["advisory_flags"]
    assert "법인세" in context["calculation_scope"]


def test_financial_income_gauge_combines_external_and_portfolio_income() -> None:
    status = calculate_financial_income_comprehensive_tax_status(
        portfolio_financial_income=32_220_000,
        external_financial_income=10_000_000,
        marginal_income_tax_rate=0.495,
    )

    assert status["portfolio_financial_income"] == 32_220_000
    assert status["external_financial_income"] == 10_000_000
    assert status["total_financial_income"] == 42_220_000
    assert status["excess_over_threshold"] == 22_220_000
    assert status["is_over_threshold"] is True

    gauge = status["gauge"]
    assert gauge["external_financial_income_manwon"] == 1000
    assert gauge["portfolio_financial_income_manwon"] == 3222
    assert gauge["total_financial_income_manwon"] == 4222
    assert gauge["excess_over_threshold_manwon"] == 2222
    assert gauge["marginal_rate_pct"] == 49.5


def test_external_income_tax_is_not_fully_charged_to_portfolio_return() -> None:
    status = calculate_financial_income_comprehensive_tax_status(
        portfolio_financial_income=10_000_000,
        external_financial_income=30_000_000,
        marginal_income_tax_rate=0.385,
    )
    extra_rate = 0.385 - 0.154

    assert status["estimated_additional_tax_total"] == pytest.approx(20_000_000 * extra_rate)
    assert status[
    "estimated_additional_tax_external_baseline"
] == pytest.approx(10_000_000 * extra_rate)
    assert status[
    "estimated_additional_tax_attributable_to_portfolio"
] == pytest.approx(10_000_000 * extra_rate)

def test_external_financial_income_unit_priority() -> None:
    by_manwon = _request(
        other_financial_income=99_000_000,
        external_financial_income_manwon=1000,
    )
    assert resolve_external_financial_income_krw(by_manwon) == 10_000_000

    by_krw = _request(
        other_financial_income=99_000_000,
        external_financial_income_manwon=1000,
        external_financial_income_krw=12_340_000,
    )
    assert resolve_external_financial_income_krw(by_krw) == 12_340_000


def test_portfolio_response_exposes_financial_income_tax_gauge() -> None:
    returns = _returns()
    expected = returns.mean() * 252
    weights = {
        "overseas_dividend": 0.40,
        "general_bond": 0.30,
        "overseas_growth": 0.20,
        "cash": 0.10,
    }
    request = _request(
        external_financial_income_manwon=1000,
        marginal_income_tax_rate=0.495,
    )
    response = build_portfolio_response(
        "포트폴리오 A",
        "portfolio_a",
        weights,
        returns,
        expected,
        request,
        backtest_returns=returns,
    )

    gauge = response["financial_income_tax_gauge"]
    assert gauge == response["metrics"]["financial_income_tax_gauge"]
    assert gauge["external_financial_income_manwon"] == 1000
    assert gauge["total_financial_income_manwon"] == (
        gauge["external_financial_income_manwon"]
        + gauge["portfolio_financial_income_manwon"]
    )



def test_pension_gating_near_age_with_sufficient_horizon() -> None:
    """김성삼 페르소나: 54세/10년 → years_to_receive=1 < horizon=10 → usable=True."""
    near = _request(age=54, investment_horizon_years=10)
    status = calculate_irp_status(near)
    assert status["usable"] is True
    assert status["years_until_access"] == 1


def test_pension_gating_already_past_receive_age() -> None:
    """박기업 페르소나: 62세 → 이미 55세 초과 → usable=True, years_until_access=0."""
    past = _request(age=62, investment_horizon_years=10)
    status = calculate_irp_status(past)
    assert status["usable"] is True
    assert status["years_until_access"] == 0


def test_pension_credit_zeroed_when_tax_liability_insufficient() -> None:
    """pension_tax_liability_sufficient=False이면 결합 절감액에서 연금 기여분이 0."""
    portfolio = [
        {"asset_class": "general_bond", "weight": 0.5},
        {"asset_class": "overseas_growth", "weight": 0.3},
        {"asset_class": "cash", "weight": 0.2},
    ]
    result = calc_combined_tax_saving(
        portfolio,
        gross_return=0.07,
        total_assets=30.0,
        marginal_income_tax_rate=0.385,
        age=60,
        horizon_years=10,
        pension_tax_liability_sufficient=False,
    )
    assert result["contributionsWon"]["pension_credit"] == 0
    assert "pension_credit" in result["ineligible"]


# PR checks retrigger