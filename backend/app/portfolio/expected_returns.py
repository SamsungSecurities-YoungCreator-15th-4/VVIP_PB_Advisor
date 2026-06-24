# ruff: noqa: E501
"""portfolio_logic.py 분할: expected_returns 모듈."""


import pandas as pd
from typing import Dict, Optional

from .constants import TRADING_DAYS
from .utils import canonicalize_asset_return_map

# ============================================================
# 6. 기대수익률
# ============================================================


def calculate_expected_returns(
    returns: pd.DataFrame,
    expected_return_haircut: float,
    enable_black_litterman: bool,
    view_expected_returns: Optional[Dict[str, float]],
    view_weight: float,
) -> pd.Series:
    historical_annual_returns = returns.mean() * TRADING_DAYS
    adjusted_returns = historical_annual_returns * expected_return_haircut

    if "cash" in historical_annual_returns.index:
        adjusted_returns["cash"] = historical_annual_returns["cash"]

    view_expected_returns = canonicalize_asset_return_map(view_expected_returns)

    if not enable_black_litterman or not view_expected_returns:
        return adjusted_returns

    final_returns = adjusted_returns.copy()
    for asset, view_return in view_expected_returns.items():
        if asset in final_returns.index:
            final_returns[asset] = (
                final_returns[asset] * (1 - view_weight) + float(view_return) * view_weight
            )

    return final_returns
