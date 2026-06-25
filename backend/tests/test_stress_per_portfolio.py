"""POST /portfolio/stress-metrics 의 포트폴리오별 stressed 응답 회귀 테스트.

배경:
    과거 stress-metrics 는 '제출된 현재 포트폴리오' 한 개만 stressed 로 줘서,
    프런트가 A/B 를 선형근사하고 절세 패널은 어떤 포트폴리오를 골라도 현재값만
    봤다(자세한 경위는 PR 본문). 수정으로 build_portfolio_response 에 shocks /
    include_monte_carlo_ranges 를 더해, 포트폴리오별로 같은 충격 벡터를 적용한
    실제 stressed 지표를 calculate 와 같은 형태로 낼 수 있게 했다.

원칙(AGENTS.md): 더미값이 아니라 불변식을 검증한다. 네트워크(yfinance) 없이
합성 시계열·합성 벤치마크로 build_portfolio_response 의 두 신규 인자 동작만 고정한다.
  1) shocks 를 주면 stressed 세후수익률이 base 보다 낮아진다(음의 위기 충격).
  2) include_monte_carlo_ranges=False 면 Range 시뮬레이션을 건너뛰어
     after_tax_return_range·mdd_range 가 None 이 된다(프런트가 stressed 본값을 씀).
  3) 비중이 다르면 같은 충격에도 stressed 지표가 달라진다(포트폴리오별 분리).
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.portfolio.constants import TRADING_DAYS  # noqa: E402
from app.portfolio.metrics import resolve_scenario_shocks  # noqa: E402
from app.portfolio.models import PortfolioRequest  # noqa: E402
from app.portfolio.responses import build_portfolio_response  # noqa: E402
from app.portfolio.utils import attach_benchmark_returns  # noqa: E402

WEIGHTS_AGGRESSIVE = {
    "domestic_equity": 0.35,
    "overseas_growth": 0.35,
    "general_bond": 0.20,
    "overseas_dividend": 0.10,
}
WEIGHTS_CONSERVATIVE = {
    "domestic_equity": 0.10,
    "overseas_growth": 0.10,
    "general_bond": 0.70,
    "overseas_dividend": 0.10,
}


def _returns(seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = 600
    idx = pd.date_range("2021-01-01", periods=n, freq="B")
    investable = pd.DataFrame(
        {
            "domestic_equity": rng.normal(0.0004, 0.011, n),
            "overseas_growth": rng.normal(0.0006, 0.014, n),
            "general_bond": rng.normal(0.0001, 0.003, n),
            "overseas_dividend": rng.normal(0.0003, 0.009, n),
        },
        index=idx,
    )
    # 합성 벤치마크(3종) — build_portfolio_response 가 include_benchmark_metrics=True 로
    # 베타·벤치마크 백테스트를 계산하므로 컬럼이 있어야 한다.
    benchmarks = pd.DataFrame(
        {
            "kospi": rng.normal(0.0003, 0.012, n),
            "sp500": rng.normal(0.0005, 0.010, n),
            "msci_acwi": rng.normal(0.0004, 0.009, n),
        },
        index=idx,
    )
    return attach_benchmark_returns(investable, benchmarks)


def _expected(returns: pd.DataFrame) -> pd.Series:
    return returns.mean() * TRADING_DAYS


def _request(**kw) -> PortfolioRequest:
    base = dict(total_asset=5_000_000_000.0, risk_profile="balanced")
    base.update(kw)
    return PortfolioRequest(**base)


def _build(weights, shocks):
    returns = _returns()
    expected = _expected(returns)
    return build_portfolio_response(
        name="t",
        api_key="t",
        weights=weights,
        returns=returns,
        expected_returns=expected,
        request=_request(),
        shocks=shocks,
        include_monte_carlo_ranges=False,
    )


def _crisis_shocks(weights):
    return resolve_scenario_shocks("crisis_2008", list(weights))


def test_shocks_lower_after_tax_return():
    base = _build(WEIGHTS_AGGRESSIVE, None)
    stressed = _build(WEIGHTS_AGGRESSIVE, _crisis_shocks(WEIGHTS_AGGRESSIVE))
    assert (
        stressed["metrics"]["after_tax_return"]
        < base["metrics"]["after_tax_return"]
    )


def test_monte_carlo_ranges_skipped_under_stress():
    stressed = _build(WEIGHTS_AGGRESSIVE, _crisis_shocks(WEIGHTS_AGGRESSIVE))
    metrics = stressed["metrics"]
    assert metrics["after_tax_return_range"] is None
    assert metrics["mdd_range"] is None
    basis = metrics["monte_carlo_range_basis"]
    assert basis["available"] is False
    assert basis["reason"] == "skipped_under_stress"


def test_different_weights_yield_different_stressed_metrics():
    shocks = _crisis_shocks(WEIGHTS_AGGRESSIVE)
    aggressive = _build(WEIGHTS_AGGRESSIVE, shocks)["metrics"]
    conservative = _build(WEIGHTS_CONSERVATIVE, shocks)["metrics"]
    # 같은 충격이라도 비중이 다르면 stressed 지표가 달라야 한다(포트폴리오별 분리).
    assert aggressive["after_tax_return"] != conservative["after_tax_return"]
    assert aggressive["mdd"] != conservative["mdd"]
    # 위기엔 주식 비중이 큰 포트폴리오의 낙폭(MDD)이 더 깊다(더 음수).
    assert aggressive["mdd"] < conservative["mdd"]


def test_reproducible():
    shocks = _crisis_shocks(WEIGHTS_AGGRESSIVE)
    a = _build(WEIGHTS_AGGRESSIVE, shocks)["metrics"]["after_tax_return"]
    b = _build(WEIGHTS_AGGRESSIVE, shocks)["metrics"]["after_tax_return"]
    assert a == b


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("전체 통과 ✅")
