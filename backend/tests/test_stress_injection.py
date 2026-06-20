"""calculate_metrics(shocks=...) 시계열 충격 주입 단위 테스트.

원칙(AGENTS.md): 더미값이 아니라 불변식·하위호환을 검증한다.
  1) 하위호환: shocks=None/{}이면 기존 동작과 '완전히' 동일.
  2) 비변형: 충격 계산이 입력 returns/expected_returns를 in-place로 바꾸지 않는다.
  3) 단조성: 음(-)의 금리/환율 충격이 커질수록 기대수익률이 낮아지고 변동성은 커진다.
  4) 충격 환산: derive_asset_shocks_from_macro가 듀레이션/환노출 가정과 일치.

네트워크(yfinance) 없이 합성 시계열로 검증한다.
"""
import numpy as np
import pandas as pd
import pytest

from app.portfolio_logic.portfolio_logic import (
    ASSET_DURATION_YEARS,
    TRADING_DAYS,
    PortfolioRequest,
    apply_return_shocks,
    calculate_metrics,
    derive_asset_shocks_from_macro,
)


def _synthetic_returns(seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = 600
    data = {
        "domestic_equity": rng.normal(0.0004, 0.011, n),
        "overseas_growth": rng.normal(0.0006, 0.014, n),
        "general_bond": rng.normal(0.0001, 0.003, n),
        "overseas_dividend": rng.normal(0.0003, 0.009, n),
    }
    return pd.DataFrame(data)


def _expected_returns(returns: pd.DataFrame) -> pd.Series:
    return returns.mean() * TRADING_DAYS


def _request(**kw) -> PortfolioRequest:
    base = dict(total_asset=50.0, risk_profile="balanced")
    base.update(kw)
    return PortfolioRequest(**base)


WEIGHTS = {
    "domestic_equity": 0.3,
    "overseas_growth": 0.3,
    "general_bond": 0.3,
    "overseas_dividend": 0.1,
}


def test_no_shocks_is_identical_to_baseline():
    """shocks=None과 shocks={}는 기존 경로와 완전히 동일해야 한다(하위호환)."""
    returns = _synthetic_returns()
    expected = _expected_returns(returns)
    req = _request()

    base = calculate_metrics(WEIGHTS, returns, expected, req)
    none_explicit = calculate_metrics(WEIGHTS, returns, expected, req, shocks=None)
    empty = calculate_metrics(WEIGHTS, returns, expected, req, shocks={})

    for key in ("expected_return", "volatility", "sharpe_ratio", "sortino_ratio", "mdd",
                "after_tax_return", "taxable_financial_income"):
        assert base[key] == none_explicit[key] == empty[key]


def test_inputs_not_mutated():
    """충격 주입이 입력 returns/expected_returns를 in-place로 바꾸면 안 된다."""
    returns = _synthetic_returns()
    expected = _expected_returns(returns)
    returns_snapshot = returns.copy()
    expected_snapshot = expected.copy()

    shocks = {"general_bond": -0.10, "overseas_growth": -0.05}
    calculate_metrics(WEIGHTS, returns, expected, _request(), shocks=shocks)

    pd.testing.assert_frame_equal(returns, returns_snapshot)
    pd.testing.assert_series_equal(expected, expected_snapshot)


def test_negative_shock_lowers_return_and_raises_vol():
    """음의 충격이 커질수록 기대수익률↓·변동성↑ (단조성)."""
    returns = _synthetic_returns()
    expected = _expected_returns(returns)
    req = _request()

    base = calculate_metrics(WEIGHTS, returns, expected, req)
    mild = calculate_metrics(
        WEIGHTS, returns, expected, req, shocks={"overseas_growth": -0.05}
    )
    severe = calculate_metrics(
        WEIGHTS, returns, expected, req, shocks={"overseas_growth": -0.15}
    )

    assert severe["expected_return"] < mild["expected_return"] < base["expected_return"]
    assert severe["volatility"] > base["volatility"]


def test_expected_return_shift_matches_weighted_shock():
    """기대수익률 변화 ≈ Σ(정규화 비중 × 자산 충격). 드리프트가 기대수익률에 그대로 반영."""
    returns = _synthetic_returns()
    expected = _expected_returns(returns)
    req = _request()
    shocks = {"general_bond": -0.08, "domestic_equity": -0.03}

    base = calculate_metrics(WEIGHTS, returns, expected, req)
    stressed = calculate_metrics(WEIGHTS, returns, expected, req, shocks=shocks)

    total_w = sum(WEIGHTS.values())
    expected_delta = sum(
        (WEIGHTS[a] / total_w) * s for a, s in shocks.items()
    )
    actual_delta = stressed["expected_return"] - base["expected_return"]
    assert actual_delta == pytest.approx(expected_delta, abs=1e-9)


def test_apply_return_shocks_preserves_drift_and_expands_vol():
    """주입 공식 r' = mean + (r-mean)*vm + s/252 의 평균·분산 변화를 직접 검증."""
    returns = _synthetic_returns()
    selected = returns[["overseas_growth"]]
    selected_expected = _expected_returns(returns).reindex(["overseas_growth"])
    s = -0.12

    stressed, stressed_expected = apply_return_shocks(
        selected, selected_expected, {"overseas_growth": s}
    )
    col0 = selected["overseas_growth"]
    col1 = stressed["overseas_growth"]

    # 평균은 원평균 + s/252 만큼 이동
    assert col1.mean() == pytest.approx(col0.mean() + s / TRADING_DAYS, abs=1e-12)
    # 표준편차는 vol_mult(|s|=0.12 → 1+2*0.12=1.24)배 확대
    assert col1.std() == pytest.approx(col0.std() * 1.24, rel=1e-9)
    # 기대수익률 시리즈에는 s 그대로 가산
    assert stressed_expected["overseas_growth"] == pytest.approx(
        selected_expected["overseas_growth"] + s, abs=1e-12
    )


def test_derive_asset_shocks_matches_sensitivities():
    """슬라이더→자산별 충격 환산이 듀레이션/환노출 가정과 일치."""
    req = _request(stress_interest_rate_shock=0.01, stress_fx_shock=0.10)
    shocks = derive_asset_shocks_from_macro(list(WEIGHTS), req)

    # 채권: -듀레이션 × 금리충격
    assert shocks["general_bond"] == pytest.approx(
        -ASSET_DURATION_YEARS["general_bond"] * 0.01, abs=1e-12
    )
    # 환노출 자산: + 환율충격 (해외성장주는 듀레이션 0이라 환충격만)
    assert shocks["overseas_growth"] == pytest.approx(0.10, abs=1e-12)
    # 국내주식: 금리·환율 민감 자산이 아니므로 충격 없음(키 부재)
    assert "domestic_equity" not in shocks
