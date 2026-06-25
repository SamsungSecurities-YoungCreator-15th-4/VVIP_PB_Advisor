"""Regression tests for dashboard 8-group output and API contracts."""

import pandas as pd
import pytest

from app.portfolio.api_contracts import PortfolioCalculateResponseContract
from app.portfolio.assets import DASHBOARD_ASSET_GROUPS
from app.portfolio.dashboard_views import (
    build_common_correlation_heatmap_payload,
    build_dashboard_allocation_payload,
    calculate_dashboard_group_correlation_matrix,
    calculate_portfolio_risk_contribution_heatmap,
)


GROUP_KEYS = list(DASHBOARD_ASSET_GROUPS)


def sample_returns() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "domestic_equity": [-0.02, -0.01, 0.00, 0.01, 0.02, 0.03],
            "overseas_blue_chip": [-0.018, -0.006, 0.002, 0.012, 0.018, 0.028],
            "overseas_growth": [-0.030, -0.012, 0.004, 0.018, 0.032, 0.040],
            "overseas_dividend": [-0.010, -0.004, 0.001, 0.007, 0.011, 0.016],
            "general_bond": [0.008, 0.006, 0.004, 0.002, 0.000, -0.002],
            "low_coupon_bond": [0.012, 0.009, 0.006, 0.003, 0.000, -0.003],
            "separate_tax_bond": [0.010, 0.008, 0.005, 0.003, 0.001, -0.001],
            "gold": [0.004, -0.003, 0.006, -0.002, 0.008, 0.001],
            "reit": [-0.012, -0.006, 0.001, 0.009, 0.015, 0.021],
            "commodity": [0.009, -0.002, 0.005, 0.011, -0.004, 0.007],
            "dollar": [0.006, 0.004, 0.002, 0.000, -0.002, -0.004],
            "cash": [0.0001] * 6,
        }
    )


def sample_weights() -> dict[str, float]:
    return {
        "domestic_equity": 0.10,
        "overseas_blue_chip": 0.10,
        "overseas_growth": 0.05,
        "overseas_dividend": 0.05,
        "general_bond": 0.10,
        "low_coupon_bond": 0.10,
        "separate_tax_bond": 0.10,
        "gold": 0.10,
        "reit": 0.05,
        "commodity": 0.05,
        "dollar": 0.10,
        "cash": 0.10,
    }


def test_allocation_is_fixed_eight_groups_and_totals_100():
    portfolio = {
        "weights": {
            asset: {"weight": weight}
            for asset, weight in sample_weights().items()
        }
    }
    payload = build_dashboard_allocation_payload(portfolio)
    assert [item["asset_class"] for item in payload] == GROUP_KEYS
    assert sum(item["weight"] for item in payload) == pytest.approx(100.0)
    by_key = {item["asset_class"]: item["weight"] for item in payload}
    assert by_key["bond"] == 30.0


def test_common_correlation_uses_zero_policy():
    matrix = calculate_dashboard_group_correlation_matrix(sample_returns())
    assert list(matrix) == GROUP_KEYS
    assert all(list(column) == GROUP_KEYS for column in matrix.values())
    assert all(value is not None for col in matrix.values() for value in col.values())
    assert all(matrix[column]["cash"] == 0.0 for column in GROUP_KEYS)
    assert all(matrix["cash"][row] == 0.0 for row in GROUP_KEYS)


def test_common_payload_contains_required_contract_fields():
    matrix = calculate_dashboard_group_correlation_matrix(sample_returns())
    payload = build_common_correlation_heatmap_payload(
        {"correlation_matrix": matrix}
    )
    assert payload["grouping_method"] == "equal_weighted_constituent_daily_returns"
    assert payload["null_value_reason"]
    assert all(isinstance(value, float) for row in payload["matrix"] for value in row)


def test_portfolio_specific_heatmaps_change_with_weights():
    returns = sample_returns()
    growth = sample_weights()
    growth.update({
        "overseas_blue_chip": 0.35,
        "overseas_growth": 0.30,
        "general_bond": 0.02,
        "low_coupon_bond": 0.01,
        "separate_tax_bond": 0.01,
    })
    defensive = sample_weights()
    defensive.update({
        "overseas_blue_chip": 0.03,
        "overseas_growth": 0.02,
        "general_bond": 0.30,
        "low_coupon_bond": 0.20,
        "separate_tax_bond": 0.15,
    })
    first = calculate_portfolio_risk_contribution_heatmap(growth, returns)
    second = calculate_portfolio_risk_contribution_heatmap(defensive, returns)
    assert first["matrix"] != second["matrix"]
    assert first["matrix_total"] == pytest.approx(100.0, abs=0.02)
    assert second["matrix_total"] == pytest.approx(100.0, abs=0.02)


def _portfolio_item() -> dict:
    weights = sample_weights()
    allocation = build_dashboard_allocation_payload(
        {"weights": {asset: {"weight": weight} for asset, weight in weights.items()}}
    )
    heatmap = calculate_portfolio_risk_contribution_heatmap(weights, sample_returns())
    return {
        "kind": "current",
        "rank": None,
        "label": "현재 포트폴리오",
        "badge": None,
        "allocation": allocation,
        "allocation_total": 100.0,
        "risk_contribution_heatmap": heatmap,
        "metrics": {
            "expected_return": 5.0,
            "volatility": 10.0,
            "sharpe": 0.5,
            "sortino": 0.6,
            "mdd": -8.0,
            "after_tax_return": 4.0,
        },
        "metrics_krw": {
            "basis": "portfolio_total_asset",
            "total_asset": 1_000_000_000.0,
            "expected_return": 50_000_000.0,
            "after_tax_return": 40_000_000.0,
            "mdd": -80_000_000.0,
            "volatility_band": 100_000_000.0,
            "note": "test",
        },
        "vs_current_krw": {
            "after_tax_return_delta": 0.0,
            "mdd_loss_improvement": 0.0,
            "basis": "portfolio_amount_minus_current_amount",
        },
        "backtest": [],
        "benchmark": {"metadata": {}, "backtest": []},
        "benchmarks": {},
        "tax": {
            "waterfall": {
                "gross_return": 0.0,
                "dividend_interest_tax": 0.0,
                "capital_gains_tax": 0.0,
                "transaction_cost": 0.0,
                "fx_cost": 0.0,
                "after_tax": 0.0,
            },
            "saved_vs_current": 0.0,
            "summary": "test",
            "calculation_notes": [],
        },
    }


def test_portfolio_calculate_response_contract_accepts_dashboard_payload():
    matrix = calculate_dashboard_group_correlation_matrix(sample_returns())
    payload = {
        "client_id": None,
        "consultation_id": "consultation-test",
        "calculation_session_id": "session-test",
        "as_of": "2026-06-25T12:00:00+09:00",
        "risk_profile": "balanced",
        "risk_profile_label": "균형형",
        "portfolios": [_portfolio_item()],
        "correlation_heatmap": build_common_correlation_heatmap_payload(
            {"correlation_matrix": matrix}
        ),
        "search_summary": {
            "generated_portfolios": 1,
            "guideline_pass_portfolios": 1,
            "suitable_portfolios": 1,
            "liquidity_pass_portfolios": 1,
            "risk_control_pass_portfolios": 1,
            "common_filter_pass_portfolios": 1,
            "filtered_out_portfolios": 0,
            "rejection_counts": {},
            "selection_method": "test",
            "portfolio_a_selection_mode": "test",
            "portfolio_b_selection_mode": "test",
            "portfolio_b_available": True,
            "target_after_tax_return": 0.05,
        },
        "scenario_summary": {
            "base_interest_rate": 0.03,
            "base_fx_rate_krw_per_usd": 1300.0,
            "stressed_interest_rate": 0.04,
            "stressed_fx_rate_krw_per_usd": 1430.0,
            "stress_interest_rate_shock": 0.01,
            "stress_fx_shock": 0.10,
            "stress_affects_scoring": False,
        },
        "data_snapshot": {},
        "input_adapter": {"source": "test"},
        "methodology": {
            "portfolio_generation": "test",
            "optimization_basis": "test",
            "risk_classification": "test",
            "selection_logic": "test",
            "duration_logic": "test",
            "suitability_filter": "test",
            "liquidity_metric": "test",
            "tax_logic": "test",
            "second_portfolio_logic": "test",
            "stress_test_logic": "test",
            "var_erc_logic": "test",
            "benchmark_beta_logic": "test",
            "corporate_context_logic": "test",
            "backtest_caution": "test",
        },
        "notes": [],
    }
    validated = PortfolioCalculateResponseContract.model_validate(payload)
    assert validated.correlation_heatmap.null_value_reason
    assert validated.correlation_heatmap.matrix[0][0] == pytest.approx(1.0)
    assert validated.portfolios[0].risk_contribution_heatmap.matrix_total == pytest.approx(
        100.0, abs=0.02
    )
