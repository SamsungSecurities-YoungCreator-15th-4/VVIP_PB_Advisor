"""벤치마크 3선택형(KOSPI·S&P500·ACWI) 단위 테스트.

외부 API(yfinance) 없이 실행 가능한 순수 로직 테스트.
    python backend/tests/test_benchmark_choice.py
    pytest backend/tests/test_benchmark_choice.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "portfolio_logic"))
import portfolio_logic as PL  # noqa: E402


# ── 공통 픽스처 ────────────────────────────────────────────────────────────────

def _make_returns(seed: int = 42) -> pd.DataFrame:
    """가상 일간 수익률 DataFrame — 실제 자산 컬럼 + 벤치마크 컬럼 포함."""
    rng = np.random.default_rng(seed)
    n = 252
    idx = pd.date_range("2020-01-02", periods=n, freq="B")

    df = pd.DataFrame(index=idx)
    # 실제 자산 (일부만)
    for asset in ["domestic_equity", "overseas_blue_chip", "overseas_growth",
                  "overseas_dividend", "general_bond", "cash"]:
        df[asset] = rng.normal(0.0003, 0.01, n)

    # ACWI 전용 벤치마크 컬럼 (acwi 선택 시 extra download)
    df[PL.BENCHMARK_SERIES_KEY] = rng.normal(0.0003, 0.012, n)
    return df


SAMPLE_WEIGHTS = {"domestic_equity": 0.4, "overseas_blue_chip": 0.3, "general_bond": 0.3}


# ── AVAILABLE_BENCHMARKS 구조 ──────────────────────────────────────────────────

def test_available_benchmarks_keys():
    assert set(PL.AVAILABLE_BENCHMARKS.keys()) == {"kospi", "sp500", "acwi"}
    print("✅ AVAILABLE_BENCHMARKS 키: kospi·sp500·acwi 3개")


def test_available_benchmarks_required_fields():
    for key, cfg in PL.AVAILABLE_BENCHMARKS.items():
        for field in ("series_key", "needs_extra_ticker", "ticker", "label", "policy", "mode"):
            assert field in cfg, f"{key} 설정에 '{field}' 없음"
    print("✅ AVAILABLE_BENCHMARKS 필수 필드 모두 존재")


def test_acwi_needs_extra_ticker():
    assert PL.AVAILABLE_BENCHMARKS["acwi"]["needs_extra_ticker"] is True
    assert PL.AVAILABLE_BENCHMARKS["kospi"]["needs_extra_ticker"] is False
    assert PL.AVAILABLE_BENCHMARKS["sp500"]["needs_extra_ticker"] is False
    print("✅ acwi만 extra ticker 필요, kospi·sp500은 기존 컬럼 재사용")


# ── PortfolioRequest benchmark 필드 ───────────────────────────────────────────

def test_portfolio_request_benchmark_default():
    req = PL.PortfolioRequest(total_asset=1_000_000_000, risk_profile="balanced")
    assert req.benchmark == "acwi"
    print(f"✅ PortfolioRequest.benchmark 기본값: {req.benchmark}")


def test_portfolio_request_benchmark_kospi():
    req = PL.PortfolioRequest(total_asset=1_000_000_000, risk_profile="balanced", benchmark="kospi")
    assert req.benchmark == "kospi"
    print("✅ PortfolioRequest.benchmark = kospi 설정 가능")


def test_portfolio_request_benchmark_sp500():
    req = PL.PortfolioRequest(total_asset=1_000_000_000, risk_profile="balanced", benchmark="sp500")
    assert req.benchmark == "sp500"
    print("✅ PortfolioRequest.benchmark = sp500 설정 가능")


# ── build_portfolio_benchmark ─────────────────────────────────────────────────

def test_benchmark_acwi_uses_acwi_column():
    returns = _make_returns()
    series, meta = PL.build_portfolio_benchmark(SAMPLE_WEIGHTS, returns, "acwi")
    assert series is not None and not series.empty
    assert meta["benchmark_key"] == PL.BENCHMARK_SERIES_KEY
    assert meta["choice"] == "acwi"
    assert meta["mode"] == "msci_acwi_proxy"
    print(f"✅ acwi 벤치마크: series len={len(series)}, key={meta['benchmark_key']}")


def test_benchmark_kospi_uses_domestic_equity():
    returns = _make_returns()
    series, meta = PL.build_portfolio_benchmark(SAMPLE_WEIGHTS, returns, "kospi")
    assert series is not None and not series.empty
    assert meta["benchmark_key"] == "domestic_equity"
    assert meta["choice"] == "kospi"
    assert meta["mode"] == "kospi_proxy"
    # domestic_equity 컬럼 값과 동일해야 함
    assert series.equals(
        returns["domestic_equity"].replace([float("inf"), float("-inf")], float("nan")).dropna()
    )
    print(f"✅ kospi 벤치마크: domestic_equity 컬럼 재사용, series len={len(series)}")


def test_benchmark_sp500_uses_overseas_blue_chip():
    returns = _make_returns()
    series, meta = PL.build_portfolio_benchmark(SAMPLE_WEIGHTS, returns, "sp500")
    assert series is not None and not series.empty
    assert meta["benchmark_key"] == "overseas_blue_chip"
    assert meta["choice"] == "sp500"
    assert meta["mode"] == "sp500_proxy"
    print(f"✅ sp500 벤치마크: overseas_blue_chip 컬럼 재사용, series len={len(series)}")


def test_benchmark_missing_acwi_column():
    returns = _make_returns()
    returns_no_acwi = returns.drop(columns=[PL.BENCHMARK_SERIES_KEY])
    series, meta = PL.build_portfolio_benchmark(SAMPLE_WEIGHTS, returns_no_acwi, "acwi")
    assert series is None
    assert meta["applicable"] is False
    assert meta["reason"] == "benchmark_data_missing"
    print("✅ acwi 컬럼 없을 때 applicable=False, reason=benchmark_data_missing")


def test_benchmark_default_is_acwi_compat():
    """benchmark_choice 미지정 시 기존 동작(acwi) 유지 — 하위호환."""
    returns = _make_returns()
    series_default, _ = PL.build_portfolio_benchmark(SAMPLE_WEIGHTS, returns)
    series_acwi, _ = PL.build_portfolio_benchmark(SAMPLE_WEIGHTS, returns, "acwi")
    assert series_default.equals(series_acwi)
    print("✅ benchmark_choice 기본값 = acwi, 기존 동작과 동일")


# ── 3개 선택지가 서로 다른 시리즈를 반환하는지 확인 ─────────────────────────

def test_three_benchmarks_are_distinct():
    returns = _make_returns()
    s_kospi, _ = PL.build_portfolio_benchmark(SAMPLE_WEIGHTS, returns, "kospi")
    s_sp500, _ = PL.build_portfolio_benchmark(SAMPLE_WEIGHTS, returns, "sp500")
    s_acwi, _ = PL.build_portfolio_benchmark(SAMPLE_WEIGHTS, returns, "acwi")

    assert s_kospi is not None and s_sp500 is not None and s_acwi is not None
    # 각기 다른 컬럼 데이터이므로 동일하지 않아야 함
    assert not s_kospi.equals(s_sp500), "kospi와 sp500이 동일 시리즈"
    assert not s_kospi.equals(s_acwi), "kospi와 acwi가 동일 시리즈"
    assert not s_sp500.equals(s_acwi), "sp500과 acwi가 동일 시리즈"
    print("✅ 3개 벤치마크가 서로 다른 시리즈 반환")


if __name__ == "__main__":
    test_available_benchmarks_keys()
    test_available_benchmarks_required_fields()
    test_acwi_needs_extra_ticker()
    test_portfolio_request_benchmark_default()
    test_portfolio_request_benchmark_kospi()
    test_portfolio_request_benchmark_sp500()
    test_benchmark_acwi_uses_acwi_column()
    test_benchmark_kospi_uses_domestic_equity()
    test_benchmark_sp500_uses_overseas_blue_chip()
    test_benchmark_missing_acwi_column()
    test_benchmark_default_is_acwi_compat()
    test_three_benchmarks_are_distinct()
    print("\n모든 테스트 통과 ✅")
