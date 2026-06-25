# ruff: noqa: E501
"""POST /portfolio/stress-metrics 의 base/stressed 단위 계약 회귀 테스트.

배경:
    /portfolio/calculate 는 metrics 를 build_metrics_payload 로 퍼센트 변환해
    내보낸다(내부 비율 0.05 → 응답 5.00). 과거 stress-metrics 는 calculate_metrics
    내부 결과(0.05 비율)를 그대로 반환해, 프런트가 같은 필드를 같은 단위로 보면
    평상시 5.00% ↔ 스트레스 0.05% 처럼 100배 어긋났다.

    수정: stress-metrics 도 base/stressed 를 build_metrics_payload 로 태워
    calculate 와 동일한 키·단위(PortfolioMetricsResponse)로 맞춘다. 이 테스트는
    그 단위 계약(필드별 변환)을 고정한다 — 통째 ×100 이 아니라 수익률 계열만
    퍼센트, 샤프/소르티노/베타는 비율 유지여야 한다.
"""
from __future__ import annotations

from app.portfolio.formatters import build_metrics_payload


def _raw_metrics() -> dict:
    """calculate_metrics() 가 내부적으로 돌려주는 비율(ratio) 형태 샘플."""
    return {
        "expected_return": 0.05,       # 5.00%
        "after_tax_return": 0.0432,    # 4.32%
        "volatility": 0.1234,          # 12.34%
        "mdd": -0.1567,                # -15.67%
        "sharpe_ratio": 1.2345,        # 무차원 → 비율 유지
        "sortino_ratio": 1.5678,       # 무차원 → 비율 유지
        "beta": 0.9876,                # 무차원 → 비율 유지
        "selected_benchmark_key": "kospi",
        "benchmark_comparisons": {},
    }


def test_stress_metrics_return_fields_are_percent_like_calculate():
    """수익률 계열은 ×100(퍼센트)로 나와 calculate 와 단위가 같아야 한다."""
    out = build_metrics_payload({"metrics": _raw_metrics()})

    assert out["expected_return"] == 5.0
    assert out["after_tax_return"] == 4.32
    assert out["volatility"] == 12.34
    assert out["mdd"] == -15.67


def test_stress_metrics_dimensionless_fields_stay_ratio():
    """샤프·소르티노·베타는 무차원이라 ×100 하면 안 된다(비율 유지)."""
    out = build_metrics_payload({"metrics": _raw_metrics()})

    assert out["sharpe"] == 1.2345
    assert out["sortino"] == 1.5678
    assert out["beta"] == 0.9876


def test_stress_metrics_key_shape_matches_calculate_contract():
    """calculate 의 metrics(PortfolioMetricsResponse) 키와 동일해야 프런트가 같은 코드로 렌더한다."""
    out = build_metrics_payload({"metrics": _raw_metrics()})

    for key in (
        "expected_return",
        "volatility",
        "sharpe",
        "sortino",
        "mdd",
        "after_tax_return",
    ):
        assert key in out

    # 내부 원본 키(sharpe_ratio 등)가 그대로 새어나가면 안 된다.
    assert "sharpe_ratio" not in out
    assert "sortino_ratio" not in out
