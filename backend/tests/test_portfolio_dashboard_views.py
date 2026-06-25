"""Regression tests for dashboard 8-group output."""

import pandas as pd
import pytest

from app.portfolio.dashboard_views import (
    DASHBOARD_ASSET_GROUPS,
    build_dashboard_allocation_payload,
    calculate_dashboard_group_correlation_matrix,
    calculate_portfolio_risk_contribution_heatmap,
)


GROUP_KEYS = [
    "domestic_equity",
    "overseas_equity",
    "bond",
    "gold",
    "reit",
    "commodity",
    "dollar",
    "cash",
]


def sample_returns():
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


def test_allocation_is_fixed_eight_groups_and_totals_100():
    raw = {
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
    portfolio = {
        "weights": {
            asset: {"weight": weight}
            for asset, weight in raw.items()
        }
    }
    payload = build_dashboard_allocation_payload(portfolio)
    assert [item["asset_class"] for item in payload] == GROUP_KEYS
    assert sum(item["weight"] for item in payload) == pytest.approx(100.0)
    assert {item["asset_class"]: item["weight"] for item in payload}["bond"] == 30.0


def test_common_correlation_is_eight_by_eight():
    matrix = calculate_dashboard_group_correlation_matrix(sample_returns())
    assert list(matrix) == GROUP_KEYS
    assert all(list(column) == GROUP_KEYS for column in matrix.values())


def test_portfolio_specific_heatmaps_change_with_weights():
    returns = sample_returns()
    growth = {
        "domestic_equity": 0.10,
        "overseas_blue_chip": 0.35,
        "overseas_growth": 0.30,
        "overseas_dividend": 0.05,
        "general_bond": 0.05,
        "low_coupon_bond": 0.03,
        "separate_tax_bond": 0.02,
        "gold": 0.03,
        "reit": 0.02,
        "commodity": 0.02,
        "dollar": 0.02,
        "cash": 0.01,
    }
    defensive = {
        "domestic_equity": 0.05,
        "overseas_blue_chip": 0.05,
        "overseas_growth": 0.03,
        "overseas_dividend": 0.02,
        "general_bond": 0.30,
        "low_coupon_bond": 0.20,
        "separate_tax_bond": 0.15,
        "gold": 0.05,
        "reit": 0.03,
        "commodity": 0.02,
        "dollar": 0.05,
        "cash": 0.05,
    }
    first = calculate_portfolio_risk_contribution_heatmap(growth, returns)
    second = calculate_portfolio_risk_contribution_heatmap(defensive, returns)
    assert first["matrix"] != second["matrix"]
    assert first["matrix_total"] == pytest.approx(100.0, abs=0.02)
    assert second["matrix_total"] == pytest.approx(100.0, abs=0.02)
