"""Dashboard-only 8-group allocation and heatmap calculations.

The recommendation, tax, VaR, ERC and backtest engines continue to use the
original 12 investable assets. This module only transforms final dashboard
output and computes portfolio-specific variance-contribution heatmaps.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from .constants import TRADING_DAYS
from .utils import safe_float, safe_round


DASHBOARD_ASSET_GROUPS: Dict[str, Dict[str, Any]] = {
    "domestic_equity": {
        "label": "국내주식",
        "assets": ("domestic_equity",),
    },
    "overseas_equity": {
        "label": "해외주식",
        "assets": (
            "overseas_blue_chip",
            "overseas_growth",
            "overseas_dividend",
        ),
    },
    "bond": {
        "label": "채권",
        "assets": (
            "general_bond",
            "low_coupon_bond",
            "separate_tax_bond",
        ),
    },
    "gold": {
        "label": "금",
        "assets": ("gold",),
    },
    "reit": {
        "label": "리츠",
        "assets": ("reit",),
    },
    "commodity": {
        "label": "원자재",
        "assets": ("commodity",),
    },
    "dollar": {
        "label": "달러",
        "assets": ("dollar",),
    },
    "cash": {
        "label": "현금",
        "assets": ("cash",),
    },
}


def _extract_weight(raw: Any) -> float:
    if isinstance(raw, dict):
        raw = raw.get("weight", 0.0)
    return max(safe_float(raw), 0.0)


def _round_percentages(
    weighted_items: List[tuple[str, float]],
) -> Dict[str, float]:
    """Round to two decimals while keeping the displayed total at 100.00."""
    positive = [(key, max(float(value), 0.0)) for key, value in weighted_items]
    total = sum(value for _, value in positive)
    if total <= 1e-12:
        return {key: 0.0 for key, _ in positive}

    raw_units = [
        (key, value / total * 10_000.0, index)
        for index, (key, value) in enumerate(positive)
    ]
    floor_units = {
        key: int(math.floor(units + 1e-12))
        for key, units, _ in raw_units
    }
    remaining = 10_000 - sum(floor_units.values())
    ranked = sorted(
        raw_units,
        key=lambda item: (
            -(item[1] - math.floor(item[1] + 1e-12)),
            item[2],
        ),
    )
    for index in range(max(remaining, 0)):
        floor_units[ranked[index % len(ranked)][0]] += 1

    return {
        key: round(floor_units[key] / 100.0, 2)
        for key, _ in positive
    }


def build_dashboard_allocation_payload(
    portfolio: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Aggregate the internal 12 weights into the fixed 8 dashboard groups."""
    raw_weights = portfolio.get("weights") or {}
    grouped = [
        (
            group_key,
            sum(
                _extract_weight(raw_weights.get(asset))
                for asset in config["assets"]
            ),
        )
        for group_key, config in DASHBOARD_ASSET_GROUPS.items()
    ]
    rounded = _round_percentages(grouped)
    return [
        {
            "asset_class": group_key,
            "name": config["label"],
            "weight": rounded[group_key],
        }
        for group_key, config in DASHBOARD_ASSET_GROUPS.items()
    ]


def calculate_dashboard_group_correlation_matrix(
    returns: pd.DataFrame,
) -> Dict[str, Dict[str, float]]:
    """Calculate the common 8-group reference correlation matrix.

    Multi-asset groups use an equal-weighted constituent return series.
    Undefined correlations, such as constant cash returns, are represented
    as 0.0 so the existing response contract remains valid.
    """
    if returns.empty:
        return {
            column: {row: 0.0 for row in DASHBOARD_ASSET_GROUPS}
            for column in DASHBOARD_ASSET_GROUPS
        }

    grouped: Dict[str, pd.Series] = {}
    for group_key, config in DASHBOARD_ASSET_GROUPS.items():
        members = [asset for asset in config["assets"] if asset in returns.columns]
        if members:
            grouped[group_key] = (
                returns.loc[:, members]
                .mean(axis=1, skipna=True)
                .rename(group_key)
            )
        else:
            grouped[group_key] = pd.Series(
                0.0,
                index=returns.index,
                name=group_key,
            )

    frame = (
        pd.concat(
            [grouped[key] for key in DASHBOARD_ASSET_GROUPS],
            axis=1,
        )
        .replace([np.inf, -np.inf], np.nan)
        .dropna(how="any")
    )
    corr = (
        frame.corr()
        .reindex(
            index=list(DASHBOARD_ASSET_GROUPS),
            columns=list(DASHBOARD_ASSET_GROUPS),
        )
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )
    return {
        column: {
            row: safe_round(corr.loc[row, column], 4)
            for row in DASHBOARD_ASSET_GROUPS
        }
        for column in DASHBOARD_ASSET_GROUPS
    }


def build_common_correlation_heatmap_payload(
    full_response: Dict[str, Any],
) -> Dict[str, Any]:
    raw = full_response.get("correlation_matrix") or {}
    group_keys = list(DASHBOARD_ASSET_GROUPS)
    return {
        "assets": [
            {
                "asset_class": key,
                "name": DASHBOARD_ASSET_GROUPS[key]["label"],
            }
            for key in group_keys
        ],
        "matrix": [
            [
                safe_round(
                    (raw.get(column_key) or {}).get(row_key),
                    4,
                )
                for column_key in group_keys
            ]
            for row_key in group_keys
        ],
        "value_type": "correlation",
    }


def calculate_portfolio_risk_contribution_heatmap(
    weights: Dict[str, float],
    returns: pd.DataFrame,
) -> Dict[str, Any]:
    """Compute an 8x8 portfolio variance-contribution heatmap.

    Each group return preserves the portfolio's actual constituent weights.
    Cell (g, h) is Wg * Wh * Cov(Rg, Rh) / Var(portfolio) * 100.
    The complete matrix therefore sums to approximately 100 percent when
    portfolio variance is positive. Negative cells indicate diversification.
    """
    group_keys = list(DASHBOARD_ASSET_GROUPS)
    all_assets = [
        asset
        for config in DASHBOARD_ASSET_GROUPS.values()
        for asset in config["assets"]
    ]
    raw_weights = {
        asset: max(safe_float(weights.get(asset)), 0.0)
        for asset in all_assets
    }
    total_weight = sum(raw_weights.values())
    if total_weight <= 1e-12:
        normalized = {asset: 0.0 for asset in all_assets}
    else:
        normalized = {
            asset: value / total_weight
            for asset, value in raw_weights.items()
        }

    group_weights: Dict[str, float] = {}
    group_returns: Dict[str, pd.Series] = {}
    for group_key, config in DASHBOARD_ASSET_GROUPS.items():
        members = list(config["assets"])
        group_weight = sum(normalized[asset] for asset in members)
        group_weights[group_key] = group_weight

        active = [
            asset
            for asset in members
            if normalized[asset] > 1e-12
        ]
        missing = [asset for asset in active if asset not in returns.columns]
        if missing:
            raise ValueError(
                "대시보드 위험기여도 계산에 필요한 수익률이 없습니다: "
                f"{missing}"
            )

        if group_weight <= 1e-12 or not active:
            group_returns[group_key] = pd.Series(
                0.0,
                index=returns.index,
                name=group_key,
            )
            continue

        within_group = pd.Series(
            {
                asset: normalized[asset] / group_weight
                for asset in active
            },
            dtype=float,
        )
        group_returns[group_key] = (
            returns.loc[:, active]
            .mul(within_group, axis=1)
            .sum(axis=1, min_count=1)
            .rename(group_key)
        )

    frame = (
        pd.concat([group_returns[key] for key in group_keys], axis=1)
        .replace([np.inf, -np.inf], np.nan)
        .dropna(how="any")
    )
    covariance = (
        frame.cov()
        .reindex(index=group_keys, columns=group_keys)
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
        * TRADING_DAYS
    )
    weight_vector = np.array(
        [group_weights[key] for key in group_keys],
        dtype=float,
    )
    covariance_values = covariance.to_numpy(dtype=float)
    portfolio_variance = float(
        weight_vector.T @ covariance_values @ weight_vector
    )

    if portfolio_variance <= 1e-12 or not np.isfinite(portfolio_variance):
        contributions = np.zeros_like(covariance_values)
        portfolio_variance = 0.0
    else:
        contributions = (
            np.outer(weight_vector, weight_vector)
            * covariance_values
            / portfolio_variance
            * 100.0
        )

    return {
        "assets": [
            {
                "asset_class": key,
                "name": DASHBOARD_ASSET_GROUPS[key]["label"],
                "weight": safe_round(group_weights[key] * 100.0, 4),
            }
            for key in group_keys
        ],
        "matrix": [
            [safe_round(value, 4) for value in row]
            for row in contributions.tolist()
        ],
        "value_type": "portfolio_variance_contribution_percent",
        "matrix_total": safe_round(float(contributions.sum()), 4),
        "portfolio_variance": safe_round(portfolio_variance, 10),
        "portfolio_volatility": safe_round(
            math.sqrt(portfolio_variance),
            6,
        ),
        "method": "weighted_group_covariance_decomposition",
        "interpretation": (
            "양수는 전체 위험 확대 기여, 음수는 분산효과에 의한 "
            "위험 감소 기여이며 행렬 전체 합은 약 100%입니다."
        ),
    }
