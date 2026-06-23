"""포트폴리오 인사이트 서비스 단위 테스트 — 가드레일 검증.

핵심 검증:
1. mock LLM 응답에 입력에 없는 숫자가 들어 있으면 가드레일 테스트가 이를 탐지한다.
2. fallback_portfolio_summary()는 입력 필드 밖의 숫자를 생성하지 않는다.
3. 엔드포인트 스키마(PortfolioInsightRequest) 직렬화 정상 동작.

LLM 실제 호출 없이 실행 가능:
    python backend/tests/test_portfolio_insight.py
    pytest backend/tests/test_portfolio_insight.py
"""
import os
import re
import sys
import types
from unittest.mock import MagicMock

_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# app 패키지는 실제 경로로 로드하되, azure_openai 모듈만 mock으로 대체한다.
# build_azure_client도 포함해 모든 공개 함수를 stub으로 등록한다(다른 테스트 오염 방지).
_mock_azure = types.ModuleType("app.core.azure_openai")
_mock_azure.get_llm_client = MagicMock(return_value=MagicMock())
_mock_azure.get_llm_deployment = MagicMock(return_value="gpt-4o")
_mock_azure.build_azure_client = MagicMock(return_value=MagicMock())
# 이미 실제 모듈이 로드된 경우에는 mock으로 덮어쓰지 않는다.
if "app.core.azure_openai" not in sys.modules:
    sys.modules["app.core.azure_openai"] = _mock_azure

import app.services.portfolio_insight as PI  # noqa: E402

# ── 공통 픽스처 ────────────────────────────────────────────────────────────────

SAMPLE_PAYLOAD = {
    "benchmark_choice": "acwi",
    "current": {
        "api_key": "current",
        "name": "현재 포트폴리오",
        "metrics": {
            "expected_return": 0.058,
            "volatility": 0.112,
            "sharpe_ratio": 0.21,
            "sortino_ratio": 0.29,
            "mdd": -0.175,
            "beta": 0.81,
            "after_tax_return": 0.052,
        },
    },
    "portfolio_a": {
        "api_key": "portfolio_a",
        "name": "포트폴리오 A",
        "metrics": {
            "expected_return": 0.072,
            "volatility": 0.135,
            "sharpe_ratio": 0.34,
            "sortino_ratio": 0.45,
            "mdd": -0.198,
            "beta": 0.92,
            "after_tax_return": 0.064,
        },
    },
    "portfolio_b": {
        "api_key": "portfolio_b",
        "name": "포트폴리오 B",
        "metrics": {
            "expected_return": 0.065,
            "volatility": 0.098,
            "sharpe_ratio": 0.40,
            "sortino_ratio": 0.52,
            "mdd": -0.142,
            "beta": 0.70,
            "after_tax_return": 0.059,
        },
    },
    "tax_optimizer": {
        "current": {
            "headline": {
                "annual_tax_saving": 3_200_000,
                "after_tax_return_before": 0.052,
                "after_tax_return_after": 0.064,
            }
        }
    },
}


def _extract_numbers_from_text(text: str) -> list[float]:
    """텍스트에서 숫자(정수/소수 포함)를 추출한다."""
    raw = re.findall(r"-?\d+(?:[,_]\d+)*(?:\.\d+)?", text.replace(",", ""))
    result = []
    for tok in raw:
        try:
            result.append(float(tok))
        except ValueError:
            # 숫자로 변환되지 않는 토큰은 무시하고 다음 토큰으로 진행한다.
            continue
    return result


def _collect_leaf_numbers(obj, acc: set[float] | None = None) -> set[float]:
    """dict/list 재귀로 모든 숫자 리프를 수집한다."""
    if acc is None:
        acc = set()
    if isinstance(obj, dict):
        for v in obj.values():
            _collect_leaf_numbers(v, acc)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect_leaf_numbers(v, acc)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        import math
        if math.isfinite(obj):
            acc.add(float(obj))
    return acc


# ── 가드레일 테스트: 입력에 없는 숫자가 응답에 나타나는지 탐지 ────────────────

def test_guardrail_detector_catches_new_number():
    """가드레일 탐지기 자체가 올바르게 동작하는지 검증.

    입력에 없는 숫자(99999.99)가 LLM 응답에 나타나면 탐지해야 한다.
    """
    input_numbers = _collect_leaf_numbers(SAMPLE_PAYLOAD)
    fake_llm_output = "포트폴리오 기대수익률은 99999.99%입니다."
    output_numbers = set(_extract_numbers_from_text(fake_llm_output))
    new_numbers = output_numbers - {round(n, 6) for n in input_numbers} - {100.0}  # % 변환 허용
    assert 99999.99 in output_numbers, "탐지기가 99999.99를 파싱하지 못함"
    # 99999.99는 입력에 없으므로 new_numbers에 있어야 함
    assert any(abs(n - 99999.99) < 0.01 for n in new_numbers), "탐지기가 새 숫자를 잡아내지 못함"
    print("✅ 가드레일 탐지기: 입력에 없는 숫자 99999.99 정상 감지")


def test_guardrail_detector_allows_input_numbers():
    """입력 숫자(변환 후 %)를 인용한 응답은 가드레일을 통과해야 한다."""
    input_numbers = _collect_leaf_numbers(SAMPLE_PAYLOAD)
    # 0.058 → "5.80%" 형태로 표현되는 것은 정상 인용
    valid_output = "현재 포트폴리오의 기대수익률은 5.80%이며 샤프지수는 0.21입니다."
    output_numbers = set(_extract_numbers_from_text(valid_output))
    # 입력 숫자(원본 + 100배 변환)
    allowed = {round(n, 6) for n in input_numbers}
    allowed |= {round(n * 100, 6) for n in input_numbers}
    allowed |= {round(n * 100, 2) for n in input_numbers}
    unexpected = [n for n in output_numbers if not any(abs(n - a) < 0.01 for a in allowed)]
    assert unexpected == [], f"허용된 숫자를 새 숫자로 잘못 분류: {unexpected}"
    print("✅ 가드레일 탐지기: 입력 기반 숫자 인용은 정상 통과")


# ── fallback_portfolio_summary 테스트 ─────────────────────────────────────────

def test_fallback_contains_no_invented_numbers():
    """fallback 템플릿이 입력 밖의 숫자를 생성하지 않는다."""
    input_numbers = _collect_leaf_numbers(SAMPLE_PAYLOAD)
    summary = PI.fallback_portfolio_summary(SAMPLE_PAYLOAD)

    assert isinstance(summary, str) and len(summary) > 0
    # 테스트: 출력 숫자가 모두 입력 숫자(또는 그 변환)에서 왔는지
    output_numbers = _extract_numbers_from_text(summary)
    allowed = {round(n, 6) for n in input_numbers}
    allowed |= {round(n * 100, 6) for n in input_numbers}   # % 변환
    allowed |= {round(n * 100, 2) for n in input_numbers}
    allowed |= {round(n / 10_000, 6) for n in input_numbers}  # 만원 변환

    invented = []
    for num in output_numbers:
        if not any(abs(num - a) < 1.0 for a in allowed):
            # 연도·순번 같은 큰 정수(≥1900)는 제외
            if num < 1900:
                invented.append(num)

    assert invented == [], f"fallback이 입력에 없는 숫자를 생성했습니다: {invented}"
    print(
        "✅ fallback_portfolio_summary: 입력 외 숫자 생성 없음 "
        f"(출력 수치 수: {len(output_numbers)})"
    )


def test_fallback_empty_payload():
    summary = PI.fallback_portfolio_summary({})
    assert "없어" in summary or "결과가 없" in summary
    print(f"✅ fallback 빈 payload 처리: '{summary[:40]}...'")


def test_fallback_returns_string():
    summary = PI.fallback_portfolio_summary(SAMPLE_PAYLOAD)
    assert isinstance(summary, str)
    assert len(summary) > 10
    print(f"✅ fallback 정상 문자열 반환: {len(summary)}자")


def test_fallback_includes_portfolio_labels():
    summary = PI.fallback_portfolio_summary(SAMPLE_PAYLOAD)
    assert "현재 포트폴리오" in summary or "포트폴리오 A" in summary or "포트폴리오 B" in summary
    print("✅ fallback: 포트폴리오 레이블 포함")


# ── 스키마 직렬화 테스트 ──────────────────────────────────────────────────────

def test_portfolio_insight_request_schema():
    """PortfolioInsightRequest가 SAMPLE_PAYLOAD 구조를 정상 파싱한다."""
    import importlib  # noqa: PLC0415
    mod = importlib.import_module("app.routers.portfolio_insight")
    PortfolioInsightRequest = mod.PortfolioInsightRequest
    req = PortfolioInsightRequest(**SAMPLE_PAYLOAD)
    dumped = req.model_dump(exclude_none=True)
    assert "benchmark_choice" in dumped
    assert dumped["benchmark_choice"] == "acwi"
    current_metrics = dumped.get("current", {}).get("metrics", {})
    assert current_metrics.get("expected_return") == 0.058
    print("✅ PortfolioInsightRequest 스키마 파싱·직렬화 정상")


def test_rag_dashboard_query_intent_detection():
    """RAG 인사이트가 대시보드 요약성 질의를 별도 분기로 감지한다."""
    import importlib  # noqa: PLC0415
    mod = importlib.import_module("app.routers.rag")

    assert mod._is_dashboard_summary_query("중앙대시보드 결과 요약해줘")
    assert mod._is_dashboard_summary_query("분석 겨로가 요약해줘")
    assert mod._is_dashboard_summary_query("분석결과 다시 설명해줘")
    assert mod._is_dashboard_summary_query("백테스트 요약해줘")
    assert mod._is_dashboard_summary_query("절세 최적화 결과 요약해줘")
    assert not mod._is_dashboard_summary_query("ISA 절세 효과는?")
    assert not mod._is_dashboard_summary_query("백테스트가 무엇인가요?")
    assert not mod._is_dashboard_summary_query("절세 최적화의 작동 원리는?")


def test_rag_insight_context_accepts_dashboard_payload():
    """RAG 요청 context.dashboard 가 중앙 대시보드 스냅샷 extra 필드를 보존한다."""
    import importlib  # noqa: PLC0415
    mod = importlib.import_module("app.routers.rag")

    req = mod.InsightRequest(
        consultation_id="00000000-0000-0000-0000-000000000000",
        query="중앙대시보드 결과 요약해줘",
        context={
            "risk_profile": "균형형",
            "dashboard": {
                "schema_version": "dashboard_context_v1",
                "current": {"metrics": {"expected_return": 0.048}},
            },
        },
    )
    dashboard = req.context.dashboard.model_dump()
    assert dashboard["schema_version"] == "dashboard_context_v1"
    assert dashboard["current"]["metrics"]["expected_return"] == 0.048
    print("✅ Rag InsightRequest: dashboard context extra 필드 보존")


if __name__ == "__main__":
    test_guardrail_detector_catches_new_number()
    test_guardrail_detector_allows_input_numbers()
    test_fallback_contains_no_invented_numbers()
    test_fallback_empty_payload()
    test_fallback_returns_string()
    test_fallback_includes_portfolio_labels()
    test_portfolio_insight_request_schema()
    test_rag_dashboard_query_intent_detection()
    test_rag_insight_context_accepts_dashboard_payload()
    print("\n모든 테스트 통과 ✅")
