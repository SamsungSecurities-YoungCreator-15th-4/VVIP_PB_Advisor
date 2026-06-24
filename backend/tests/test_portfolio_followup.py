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

from app.portfolio_logic import portfolio_logic as portfolio_module  # noqa: E402
from app.portfolio_logic.portfolio_logic import (  # noqa: E402
    BENCHMARK_CONFIGS,
    DEFAULT_RANDOM_SEED,
    MIN_BETA_OBSERVATIONS,
    PORTFOLIO_B_MIN_WEIGHT_DISTANCE,
    PortfolioRequest,
    allocate_account_buckets,
    build_portfolio_benchmark,
    build_portfolio_response,
    build_tax_optimizer_payload,
    calculate_beta,
    calculate_financial_income_comprehensive_tax_status,
    calculate_irp_status,
    calculate_weight_distance,
    extract_unique_profile,
    generate_random_weights,
    resolve_external_financial_income_krw,
)
from app.portfolio_logic.tax_advice import calc_combined_tax_saving  # noqa: E402


def _returns(
    seed: int = 7,
    n: int = 600,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.bdate_range(
        "2023-01-02",
        periods=n,
    )
    data = {
        "domestic_equity": rng.normal(
            0.00035, 0.010, n
        ),
        "overseas_blue_chip": rng.normal(
            0.00045, 0.011, n
        ),
        "overseas_growth": rng.normal(
            0.00055, 0.014, n
        ),
        "overseas_dividend": rng.normal(
            0.00030, 0.009, n
        ),
        "reit": rng.normal(
            0.00025, 0.012, n
        ),
        "general_bond": rng.normal(
            0.00012, 0.003, n
        ),
        "separate_tax_bond": rng.normal(
            0.00010, 0.004, n
        ),
        "low_coupon_bond": rng.normal(
            0.00009, 0.004, n
        ),
        "gold": rng.normal(
            0.00020, 0.009, n
        ),
        "commodity": rng.normal(
            0.00010, 0.012, n
        ),
        "dollar": rng.normal(
            0.00005, 0.005, n
        ),
        "cash": np.full(
            n,
            0.00005,
        ),
    }
    for offset, config in enumerate(
        BENCHMARK_CONFIGS.values()
    ):
        data[config["series_key"]] = (
            rng.normal(
                0.00038
                + offset * 0.00001,
                0.0105,
                n,
            )
        )
    return pd.DataFrame(
        data,
        index=index,
    )


def _request(**overrides) -> PortfolioRequest:
    base = {
        "total_asset": 3_000_000_000,
        "risk_profile": "aggressive",
        "investment_horizon_years": 10,
        "unique_need_amount": 0,
        "target_after_tax_return": 0.05,
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


@pytest.mark.parametrize(
    "benchmark_key",
    list(BENCHMARK_CONFIGS.keys()),
)
def test_pb_selectable_benchmark_is_fixed_market_series(
    benchmark_key: str,
) -> None:
    returns = _returns()
    first, first_meta = (
        build_portfolio_benchmark(
            {
                "domestic_equity": 0.6,
                "cash": 0.4,
            },
            returns,
            benchmark_key,
        )
    )
    second, second_meta = (
        build_portfolio_benchmark(
            {
                "general_bond": 0.8,
                "cash": 0.2,
            },
            returns,
            benchmark_key,
        )
    )
    assert first is not None
    assert second is not None
    pd.testing.assert_series_equal(
        first,
        second,
    )
    config = BENCHMARK_CONFIGS[
        benchmark_key
    ]
    for metadata in (
        first_meta,
        second_meta,
    ):
        assert (
            metadata["benchmark_key"]
            == benchmark_key
        )
        assert (
            metadata["ticker"]
            == config["ticker"]
        )
        assert (
            metadata[
                "affects_portfolio_"
                "recommendation"
            ]
            is False
        )


def test_beta_uses_aligned_selected_benchmark() -> None:
    returns = _returns()
    benchmark, metadata = (
        build_portfolio_benchmark(
            {
                "domestic_equity": 0.4,
                "overseas_growth": 0.6,
            },
            returns,
            "msci_acwi",
        )
    )
    assert benchmark is not None
    assert (
        metadata["benchmark_key"]
        == "msci_acwi"
    )
    assert calculate_beta(
        benchmark,
        benchmark,
    ) == pytest.approx(1.0)
    assert calculate_beta(
        benchmark * 2.0,
        benchmark,
    ) == pytest.approx(2.0)


def test_beta_requires_minimum_common_observations() -> None:
    returns = _returns(
        n=MIN_BETA_OBSERVATIONS - 1
    )
    benchmark, _ = (
        build_portfolio_benchmark(
            {
                "domestic_equity": 1.0,
            },
            returns,
            "kospi",
        )
    )
    assert benchmark is not None
    assert calculate_beta(
        returns["domestic_equity"],
        benchmark,
    ) is None


def test_selected_benchmark_reports_missing_data() -> None:
    returns = _returns()
    series_key = BENCHMARK_CONFIGS[
        "sp500"
    ]["series_key"]
    returns = returns.drop(
        columns=[series_key]
    )
    benchmark, metadata = (
        build_portfolio_benchmark(
            {
                "domestic_equity": 0.6,
                "cash": 0.4,
            },
            returns,
            "sp500",
        )
    )
    assert benchmark is None
    assert metadata["applicable"] is False
    assert (
        metadata["reason"]
        == "benchmark_data_missing"
    )


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

    assert status["estimated_additional_tax_total"] == pytest.approx(
    20_000_000 * extra_rate
    )
    assert status["estimated_additional_tax_external_baseline"] == pytest.approx(
        10_000_000 * extra_rate
    )
    assert status[
        "estimated_additional_tax_attributable_to_portfolio"
    ] == pytest.approx(
        10_000_000 * extra_rate
    )


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


def test_weight_distance_means_minimum_reallocation() -> None:
    distance = calculate_weight_distance(
        {"cash": 1.0},
        {
            "cash": 0.8,
            "gold": 0.2,
        },
    )
    assert distance == pytest.approx(
        0.20
    )
    assert (
        PORTFOLIO_B_MIN_WEIGHT_DISTANCE
        == 0.10
    )


def test_non_liquid_assets_do_not_fund_liquidity_reserve() -> None:
    request = _request(
        age=60,
        unique_need_amount=500_000_000,
    )
    buckets = allocate_account_buckets(
        {
            "overseas_growth": 1.0,
        },
        request.total_asset,
        request,
    )
    taxable = buckets[
        "taxable_account"
    ]
    assert (
        taxable[
            "liquidity_reserve_allocated"
        ]
        == 0
    )
    assert (
        taxable[
            "liquidity_reserve_shortfall"
        ]
        == 500_000_000
    )
    assert (
        taxable[
            "liquidity_reserve_fully_funded"
        ]
        is False
    )


def test_missing_age_requires_manual_irp_review() -> None:
    status = calculate_irp_status(
        _request(age=None)
    )
    assert status["usable"] is False
    assert (
        status[
            "manual_review_required"
        ]
        is True
    )
    assert (
        status["reason"]
        == "age_missing_manual_"
        "review_required"
    )


def test_recommendation_and_tax_screen_use_same_after_tax_return() -> None:
    returns = _returns()
    asset_keys = list(
        portfolio_module
        .ASSET_TICKERS.keys()
    )
    expected = (
        returns[asset_keys].mean()
        * 252
    )
    weights = {
        "overseas_growth": 0.30,
        "overseas_dividend": 0.20,
        "general_bond": 0.25,
        "gold": 0.10,
        "cash": 0.15,
    }
    request = _request(
        age=62,
        marginal_income_tax_rate=0.385,
        external_financial_income_manwon=1000,
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
    payload = build_tax_optimizer_payload(
        "portfolio_a",
        response,
        request,
    )
    assert (
        response["metrics"][
            "after_tax_return"
        ]
        == payload["headline"][
            "after_tax_return_after"
        ]
    )
    assert (
        response["tax_breakdown"][
            "tax_saving_effect"
        ]["selection_model"]
        == "six_strategy_combined_v1"
    )


def test_price_data_uses_last_success_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        portfolio_module,
        "PRICE_SNAPSHOT_DIR",
        tmp_path,
    )
    monkeypatch.setattr(
        portfolio_module,
        "PRICE_SNAPSHOT_PATH",
        tmp_path
        / "price_frames.json",
    )

    index = pd.bdate_range(
        "2024-01-02",
        periods=130,
    )
    cached = pd.DataFrame(
        {
            "domestic_equity": (
                np.linspace(
                    100,
                    110,
                    len(index),
                )
            ),
            "cash": np.linspace(
                1.0,
                1.01,
                len(index),
            ),
        },
        index=index,
    )
    cached.attrs[
        "data_snapshot"
    ] = {
        "data_start": "2024-01-02",
        "data_end": (
            index[-1].strftime(
                "%Y-%m-%d"
            )
        ),
    }

    key = (
        portfolio_module
        ._price_snapshot_key(
            "analysis_prices",
            "5y",
            0.025,
        )
    )
    portfolio_module._save_price_frame_snapshot(
        key,
        cached,
    )

    def raise_network_error(
        period: str,
        cash_return: float,
    ) -> pd.DataFrame:
        raise RuntimeError(
            "network unavailable"
        )

    monkeypatch.setattr(
        portfolio_module,
        "_download_price_data_live",
        raise_network_error,
    )
    result = (
        portfolio_module
        .download_price_data(
            period="5y",
            cash_return=0.025,
        )
    )
    pd.testing.assert_frame_equal(
        result,
        cached,
        check_freq=False,
    )
    assert (
        result.attrs[
            "data_snapshot"
        ]["fallback_used"]
        is True
    )
    assert (
        result.attrs[
            "data_snapshot"
        ]["data_source"]
        == "disk_last_success_snapshot"
    )


def test_after_tax_and_mdd_ranges_share_scenario_basis() -> None:
    returns = _returns()
    asset_keys = list(
        portfolio_module.ASSET_TICKERS.keys()
    )
    expected = returns[asset_keys].mean() * 252
    weights = {
        "domestic_equity": 0.20,
        "overseas_blue_chip": 0.25,
        "overseas_growth": 0.15,
        "general_bond": 0.20,
        "gold": 0.10,
        "cash": 0.10,
    }
    request = _request(age=62)

    response = build_portfolio_response(
        "포트폴리오 A",
        "portfolio_a",
        weights,
        returns,
        expected,
        request,
        backtest_returns=returns,
    )
    metrics = response["metrics"]
    basis = metrics["monte_carlo_range_basis"]
    after_tax_range = metrics[
        "after_tax_return_range"
    ]
    mdd_range = metrics["mdd_range"]

    assert basis["available"] is True
    assert basis["rebalancing"] == "none_buy_and_hold"
    assert basis["display_range"] == {
        "lower_percentile": 20,
        "center_percentile": 50,
        "upper_percentile": 80,
        "central_coverage": 0.60,
        "label": "P20-P80",
    }
    assert after_tax_range == basis["after_tax_return"]
    assert mdd_range == basis["mdd"]

    assert (
        after_tax_range["p10"]
        <= after_tax_range["p20"]
        <= after_tax_range["p50"]
        <= after_tax_range["p80"]
        <= after_tax_range["p90"]
    )
    assert (
        mdd_range["p10"]
        <= mdd_range["p20"]
        <= mdd_range["p50"]
        <= mdd_range["p80"]
        <= mdd_range["p90"]
        <= 0
    )

    assert after_tax_range["lower"] == after_tax_range["p20"]
    assert after_tax_range["center"] == after_tax_range["p50"]
    assert after_tax_range["upper"] == after_tax_range["p80"]
    assert mdd_range["lower"] == mdd_range["p20"]
    assert mdd_range["center"] == mdd_range["p50"]
    assert mdd_range["upper"] == mdd_range["p80"]


def test_metric_range_calculation_is_reproducible() -> None:
    returns = _returns()
    asset_keys = list(
        portfolio_module.ASSET_TICKERS.keys()
    )
    expected = returns[asset_keys].mean() * 252
    weights = {
        "overseas_blue_chip": 0.30,
        "overseas_growth": 0.20,
        "general_bond": 0.25,
        "gold": 0.10,
        "cash": 0.15,
    }
    request = _request(age=62)
    response = build_portfolio_response(
        "포트폴리오 A",
        "portfolio_a",
        weights,
        returns,
        expected,
        request,
        backtest_returns=returns,
    )

    kwargs = {
        "weights": weights,
        "returns": returns,
        "expected_returns": expected,
        "total_asset": request.total_asset,
        "investment_horizon_years": (
            request.investment_horizon_years
        ),
        "tax_breakdown": response["tax_breakdown"],
        "random_seed": 42,
        "num_simulations": 1000,
    }
    first = (
        portfolio_module
        .calculate_monte_carlo_metric_ranges(
            **kwargs
        )
    )
    second = (
        portfolio_module
        .calculate_monte_carlo_metric_ranges(
            **kwargs
        )
    )

    assert first == second
    assert first["simulation_count"] == 1000
    assert first["horizon_years"] == 5
    assert (
        first["scenario_basis_id"]
        == second["scenario_basis_id"]
    )


def test_ranges_are_not_added_to_other_ratio_metrics() -> None:
    returns = _returns()
    asset_keys = list(
        portfolio_module.ASSET_TICKERS.keys()
    )
    expected = returns[asset_keys].mean() * 252
    response = build_portfolio_response(
        "포트폴리오 A",
        "portfolio_a",
        {
            "overseas_blue_chip": 0.30,
            "general_bond": 0.35,
            "gold": 0.15,
            "cash": 0.20,
        },
        returns,
        expected,
        _request(age=62),
        backtest_returns=returns,
    )
    metrics = response["metrics"]

    assert "after_tax_return_range" in metrics
    assert "mdd_range" in metrics
    assert "volatility_range" not in metrics
    assert "sharpe_ratio_range" not in metrics
    assert "sortino_ratio_range" not in metrics
    assert "beta_range" not in metrics


def test_pr106_gemini_review_defensive_tax_breakdown() -> None:
    assert (
        portfolio_module
        ._effective_tax_rate_from_breakdown(None)
        == 0.0
    )
    assert (
        portfolio_module
        ._effective_tax_rate_from_breakdown("invalid")
        == 0.0
    )


def test_pr106_gemini_review_accepts_string_index() -> None:
    returns = _returns(n=120)
    returns.index = returns.index.strftime(
        "%Y-%m-%d"
    )
    asset_keys = list(
        portfolio_module.ASSET_TICKERS.keys()
    )
    expected = returns[asset_keys].mean() * 252

    result = (
        portfolio_module
        .calculate_monte_carlo_metric_ranges(
            weights={
                "overseas_blue_chip": 0.5,
                "general_bond": 0.3,
                "cash": 0.2,
            },
            returns=returns,
            expected_returns=expected,
            total_asset=3_000_000_000,
            investment_horizon_years=1,
            tax_breakdown={},
            random_seed=42,
            num_simulations=100,
        )
    )

    assert result["available"] is True
    assert "2023-01-02" in result[
        "scenario_basis_id"
    ]


def test_pr106_gemini_review_range_failure_is_graceful(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    returns = _returns()
    asset_keys = list(
        portfolio_module.ASSET_TICKERS.keys()
    )
    expected = returns[asset_keys].mean() * 252

    def raise_simulation_error(*args, **kwargs):
        raise np.linalg.LinAlgError(
            "forced simulation failure"
        )

    monkeypatch.setattr(
        portfolio_module,
        "calculate_monte_carlo_metric_ranges",
        raise_simulation_error,
    )

    response = build_portfolio_response(
        "포트폴리오 A",
        "portfolio_a",
        {
            "overseas_blue_chip": 0.4,
            "general_bond": 0.4,
            "cash": 0.2,
        },
        returns,
        expected,
        _request(age=62),
        backtest_returns=returns,
    )

    metrics = response["metrics"]
    assert metrics[
        "monte_carlo_range_basis"
    ] == {
        "available": False,
        "reason": "unexpected_simulation_error",
    }
    assert metrics[
        "after_tax_return_range"
    ] is None
    assert metrics["mdd_range"] is None

