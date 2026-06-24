"""스트레스 → 백테스트 급락 포인트 + 절세 재계산 단위 테스트.

원칙(AGENTS.md): 더미값이 아니라 불변식을 검증한다. 네트워크(yfinance) 없이
합성 시계열로, /portfolio/stress-metrics 가 쓰는 빌딩블록을 직접 검증한다.
  1) 백테스트: 과거 곡선은 보존되고, 끝에 위기 급락 포인트 한 칸만 덧붙는다.
  2) 절세: 충격이 반영된 tax_breakdown → 절세 페이로드의 세후수익률/세액이 달라진다.
  3) 재현성: 같은 입력 → 항상 같은 출력(now/random 없음).
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.portfolio.metrics import (  # noqa: E402
    TRADING_DAYS,
    build_stress_drawdown_series,
    calculate_cumulative_returns,
    calculate_metrics,
    resolve_scenario_shocks,
)
from app.portfolio.models import PortfolioRequest  # noqa: E402
from app.portfolio.responses import build_tax_optimizer_payload  # noqa: E402

WEIGHTS = {
    "domestic_equity": 0.3,
    "overseas_growth": 0.3,
    "general_bond": 0.3,
    "overseas_dividend": 0.1,
}


def _synthetic_returns(seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = 600
    data = {
        "domestic_equity": rng.normal(0.0004, 0.011, n),
        "overseas_growth": rng.normal(0.0006, 0.014, n),
        "general_bond": rng.normal(0.0001, 0.003, n),
        "overseas_dividend": rng.normal(0.0003, 0.009, n),
    }
    idx = pd.date_range("2021-01-01", periods=n, freq="B")
    return pd.DataFrame(data, index=idx)


def _expected_returns(returns: pd.DataFrame) -> pd.Series:
    return returns.mean() * TRADING_DAYS


def _request(**kw) -> PortfolioRequest:
    base = dict(total_asset=50.0, risk_profile="balanced")
    base.update(kw)
    return PortfolioRequest(**base)


def _shocks() -> dict:
    return resolve_scenario_shocks("crisis_2008", list(WEIGHTS))


# ── 1. 백테스트 급락 포인트 ────────────────────────────────────────────────


def test_drawdown_preserves_history_and_appends_one_point():
    base_bt = calculate_cumulative_returns(WEIGHTS, _synthetic_returns())
    out = build_stress_drawdown_series(base_bt, -0.30)
    assert len(out) == len(base_bt) + 1
    for original, kept in zip(base_bt, out[:-1]):
        assert original["value"] == kept["value"]
        assert original["date"] == kept["date"]
        assert "stress_event" not in kept
    print("✅ 과거 곡선 보존 + 위기 포인트 1칸만 추가")


def test_drawdown_point_marked_and_drops_on_negative_shock():
    base_bt = calculate_cumulative_returns(WEIGHTS, _synthetic_returns())
    out = build_stress_drawdown_series(base_bt, -0.30)
    crisis = out[-1]
    assert crisis["stress_event"] is True
    assert crisis["label"] == "위기"
    assert crisis["value"] < base_bt[-1]["value"]
    assert crisis["date"] == base_bt[-1]["date"]
    print("✅ 음의 충격 → 위기 포인트 급락 + 마커 표시")


def test_drawdown_positive_shock_rises_and_empty_is_empty():
    base_bt = calculate_cumulative_returns(WEIGHTS, _synthetic_returns())
    up = build_stress_drawdown_series(base_bt, 0.10)
    assert up[-1]["value"] > base_bt[-1]["value"]
    assert build_stress_drawdown_series([], -0.30) == []
    print("✅ 양의 충격 상승 / 빈 시계열 방어")


def test_drawdown_value_floored_at_minus_one():
    """극단 충격(예: -200%)에도 누적수익률은 -1.0(자산가치 0) 미만으로 안 떨어진다."""
    base_bt = calculate_cumulative_returns(WEIGHTS, _synthetic_returns())
    out = build_stress_drawdown_series(base_bt, -2.0)
    crisis = out[-1]
    assert crisis["value"] == -1.0
    assert crisis["index_value"] == 0.0  # (1 + -1.0) * base_index
    print("✅ 극단 충격 시 누적수익률 -1.0 하한 방어")


def test_crisis_2008_portfolio_shock_is_negative_drop():
    shocks = _shocks()
    portfolio_shock = sum(WEIGHTS.get(a, 0.0) * s for a, s in shocks.items())
    base_bt = calculate_cumulative_returns(WEIGHTS, _synthetic_returns())
    out = build_stress_drawdown_series(base_bt, portfolio_shock)
    assert portfolio_shock < 0
    assert out[-1]["value"] < base_bt[-1]["value"]
    print(f"✅ 2008 포트폴리오 충격 {portfolio_shock:.3f} → 백테스트 급락")


# ── 2. 절세 재계산 ─────────────────────────────────────────────────────────


def _tax_payload(shocks=None) -> dict:
    returns = _synthetic_returns()
    expected = _expected_returns(returns)
    req = _request()
    metrics = calculate_metrics(WEIGHTS, returns, expected, req, shocks=shocks)
    return build_tax_optimizer_payload(
        "stress",
        {"name": "현재 포트폴리오", "tax_breakdown": metrics["tax_breakdown"]},
        req,
    )


def test_stress_tax_differs_from_base():
    base_tax = _tax_payload(shocks=None)
    stressed_tax = _tax_payload(shocks=_shocks())
    assert (
        stressed_tax["headline"]["after_tax_return_before"]
        < base_tax["headline"]["after_tax_return_before"]
    )
    assert set(stressed_tax) == set(base_tax)
    print("✅ 위기 시 절세 페이로드의 세후수익률(before) 하락 + 구조 보존")


# ── 3. 재현성 ──────────────────────────────────────────────────────────────


def test_reproducible_outputs():
    base_bt1 = calculate_cumulative_returns(WEIGHTS, _synthetic_returns())
    base_bt2 = calculate_cumulative_returns(WEIGHTS, _synthetic_returns())
    assert build_stress_drawdown_series(base_bt1, -0.3) == build_stress_drawdown_series(
        base_bt2, -0.3
    )
    assert _tax_payload(shocks=_shocks()) == _tax_payload(shocks=_shocks())
    print("✅ 동일 입력 → 동일 출력(재현성)")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\n전체 통과 ✅")
