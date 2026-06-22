"""오프라인 단위 테스트: canonical portfolio API 보조 로직.

외부 yfinance/Azure OpenAI 호출 없이 실행된다.
"""

from __future__ import annotations

from app.services.portfolio_orchestration import (
    _a_rank,
    _b_rank,
    get_benchmark_catalog,
    normalize_benchmark_key,
)
from app.services.semantic_mapping import (
    _validate_and_attach_coverage,
    empty_insight_mapping,
    split_source_segments,
)


def _metrics(
    *,
    after_tax: float,
    hhi: float,
    max_share: float,
    var_loss: float,
) -> dict:
    return {
        "after_tax_return": after_tax,
        "expected_return": after_tax + 0.01,
        "sharpe_ratio": 0.5,
        "historical_var_95_daily_loss": var_loss,
        "risk_contribution_max_share": max_share,
        "risk_contribution": {"hhi": hhi},
        "mdd": -0.12,
    }


def test_benchmark_catalog_is_display_only() -> None:
    catalog = get_benchmark_catalog()
    assert catalog["default_key"] == "msci_acwi"
    assert catalog["affects_portfolio_recommendation"] is False
    assert {item["key"] for item in catalog["items"]} == {
        "kospi",
        "sp500",
        "msci_acwi",
    }


def test_invalid_benchmark_falls_back_to_acwi() -> None:
    assert normalize_benchmark_key("kospi") == "kospi"
    assert normalize_benchmark_key("unknown") == "msci_acwi"


def test_a_prefers_highest_after_tax_return() -> None:
    lower = _metrics(
        after_tax=0.06,
        hhi=0.20,
        max_share=0.30,
        var_loss=0.01,
    )
    higher = _metrics(
        after_tax=0.07,
        hhi=0.40,
        max_share=0.45,
        var_loss=0.015,
    )
    assert _a_rank(higher) > _a_rank(lower)


def test_b_meets_target_then_prefers_lower_risk_concentration() -> None:
    target = 0.06
    concentrated = _metrics(
        after_tax=0.065,
        hhi=0.42,
        max_share=0.55,
        var_loss=0.012,
    )
    diversified = _metrics(
        after_tax=0.061,
        hhi=0.22,
        max_share=0.35,
        var_loss=0.010,
    )
    assert _b_rank(diversified, target) > _b_rank(concentrated, target)


def test_b_prefers_smaller_shortfall_when_target_not_met() -> None:
    target = 0.08
    near = _metrics(
        after_tax=0.075,
        hhi=0.40,
        max_share=0.50,
        var_loss=0.012,
    )
    far_but_diversified = _metrics(
        after_tax=0.06,
        hhi=0.15,
        max_share=0.25,
        var_loss=0.008,
    )
    assert _b_rank(near, target) > _b_rank(far_but_diversified, target)


def test_semantic_mapping_never_silently_drops_segments() -> None:
    segments = split_source_segments(
        "내년 전세자금 3억 필요. 미국 배당주를 선호. 특정 종목은 제외."
    )
    result = {
        "summary": None,
        "mappings": [
            {
                "source_segment_ids": [1],
                "source_text": segments[0]["text"],
            }
        ],
        "coverage_complete": True,
    }
    checked = _validate_and_attach_coverage(
        segments=segments,
        result=result,
        item_key="mappings",
    )
    assert checked["coverage_complete"] is False
    assert {item["id"] for item in checked["unmapped_segments"]} == {2, 3}


def test_ai_insight_mapping_is_advisory_only() -> None:
    result = empty_insight_mapping("금리 상승 가능성이 있습니다.")
    assert result["advisory_only"] is True
    assert result["calculation_applied"] is False
