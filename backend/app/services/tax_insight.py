"""절세 시뮬레이터 요약 생성 — 계산은 #30(portfolio_logic)이 끝내고, 여기선 요약만.

원칙(우리 거버넌스):
- 계산은 하지 않는다. 주어진 절세 계산 결과(숫자)만 사용한다.
- 숫자를 새로 만들거나 바꾸지 않고, PB가 고객에게 설명하듯 한국어로 요약한다.
- temperature=0 으로 재현성을 지향한다.

LLM 호출이 실패하면 라우터가 fallback_summary() 로 템플릿 문장을 반환한다
(rag 의 ExtractiveGenerator 폴백과 같은 철학 — 데모가 죽지 않게).

이 모듈은 비결정 호출(now/random/uuid 등)을 쓰지 않는다. as_of 같은 시각 주입은
라우터 책임이다(재현성 정적검사 대상이 되어도 안전하도록 순수하게 유지).
"""

import json
import math
from typing import Any

from app.core.azure_openai import get_llm_client, get_llm_deployment

_SYSTEM_PROMPT = (
    "너는 삼성증권 PB가 VVIP 고객에게 절세 시뮬레이션 결과를 설명할 때 쓰는 "
    "요약을 작성하는 보조자다.\n"
    "반드시 다음 규칙을 지킨다.\n"
    "1. 아래 '절세 계산 결과(JSON)'에 있는 숫자만 사용한다. 숫자를 새로 만들거나 "
    "바꾸지 않는다. 계산은 이미 끝났고 너는 설명·요약만 한다.\n"
    "2. 계좌별(ISA·IRP·일반계좌) 절세 효과와 세전·세후 비교를 PB가 고객에게 "
    "설명하듯 한국어로 자연스럽게 정리한다.\n"
    "3. 결과에 없는 항목은 지어내지 말고 언급하지 않는다.\n"
    "4. 단정적 수익 보장이나 투자 권유 표현은 피하고, 계산 결과 설명에 한정한다.\n"
    "5. 금액은 원 단위로 읽기 쉽게 표현하고, 수익률은 % 로 표현한다."
)


def _format_tax_result_for_prompt(tax_result: dict[str, Any]) -> str:
    """계산 결과 전체를 JSON 으로 직렬화해 근거로 제공한다(숫자 가공 없이 그대로)."""
    return json.dumps(tax_result, ensure_ascii=False, indent=2, default=str)


def summarize_tax_result(tax_result: dict[str, Any]) -> str:
    """절세 계산 결과를 gpt-4o 로 요약한다. 실패 시 예외를 그대로 올린다(라우터가 폴백)."""
    if not tax_result:
        raise ValueError("절세 계산 결과가 비어 있어 요약할 수 없습니다.")

    context = _format_tax_result_for_prompt(tax_result)
    user_prompt = (
        f"[절세 계산 결과(JSON)]\n{context}\n\n"
        "위 계산 결과의 숫자만 사용해, PB가 고객에게 설명하듯 한국어로 요약하라."
    )
    response = get_llm_client().chat.completions.create(
        model=get_llm_deployment(),
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )
    # content 필터·정책 등으로 choices 가 비어 올 수 있어 접근 전에 검증한다.
    if not response.choices:
        raise ValueError("LLM 응답에 choices 가 없습니다.")
    summary = response.choices[0].message.content
    if not summary or not summary.strip():
        raise ValueError("LLM 이 빈 요약을 반환했습니다.")
    return summary.strip()


def _is_real_number(value: Any) -> bool:
    """bool(=int 서브클래스) 제외, NaN/Infinity 제외한 유한 실수만 True.

    폴백은 어떤 입력에도 예외를 던지면 안 되는 안전장치라 비정상 수치는 걸러낸다.
    """
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _won(value: Any) -> str | None:
    """숫자면 천단위 콤마 원화 문자열로, 아니면 None(폴백 템플릿용, 계산 아님)."""
    if _is_real_number(value):
        return f"{round(value):,}원"
    return None


def _percent(value: Any) -> str | None:
    """비율(예: 0.0432)을 % 문자열로 변환한다(표시용 단위 변환, 새 값 생성 아님)."""
    if _is_real_number(value):
        return f"{value * 100:.2f}%"
    return None


def fallback_summary(tax_result: dict[str, Any]) -> str:
    """LLM 실패 시 계산 결과를 그대로 끼워 넣는 템플릿 요약(숫자 생성/변형 없음)."""
    if not tax_result:
        return "절세 계산 결과가 없어 요약을 생성할 수 없습니다."

    name = tax_result.get("portfolio_name") or "선택한 포트폴리오"
    headline = tax_result.get("headline") or {}
    lines = [f"[절세 요약(자동 임시본) · {name}]"]

    saving = _won(headline.get("annual_tax_saving"))
    if saving:
        lines.append(f"- 전략 적용 시 연간 약 {saving}의 세금 절감이 추정됩니다.")

    before = _percent(headline.get("after_tax_return_before"))
    after = _percent(headline.get("after_tax_return_after"))
    if before and after:
        lines.append(f"- 세후수익률(추정): 전략 전 {before} → 전략 후 {after}")

    cards = tax_result.get("account_cards") or {}
    isa_saving = _won((cards.get("isa") or {}).get("estimated_tax_saving"))
    if isa_saving:
        lines.append(f"- ISA 계좌 절세 효과(추정): {isa_saving}")
    irp_credit = _won((cards.get("irp") or {}).get("estimated_tax_credit"))
    if irp_credit:
        lines.append(f"- IRP 세액공제(추정): {irp_credit}")

    if len(lines) == 1:
        lines.append("- 표시할 절세 계산 수치가 없습니다.")

    lines.append(
        "※ 요약 생성이 일시적으로 실패해 계산 결과를 그대로 표기했습니다. "
        "수치는 프로젝트용 간이 추정입니다."
    )
    return "\n".join(lines)
