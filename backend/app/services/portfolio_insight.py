"""포트폴리오 전체 대시보드 결과 요약 — 계산은 portfolio_logic이 끝내고, 여기선 설명만.

원칙:
- AI는 주어진 계산 결과(숫자)를 설명·비교·요약하는 역할만 한다.
- 아래 두 가드레일은 절대 위반 금지:
  [1] 입력에 없는 숫자를 새로 생성하지 않는다 (6지표·세금·벤치마크 재계산 금지).
  [2] "X 자산을 늘리세요"와 같은 새로운 자산배분 추천을 하지 않는다.
      (이는 절세요약 AI와 같은 설명 레이어이지, 추천 산출 레이어가 아니다.)
- temperature=0으로 재현성을 지향한다.
- 실패 시 fallback_portfolio_summary()로 템플릿 문장을 반환한다.
"""

import json
import math
from typing import Any

from app.core.azure_openai import get_llm_client, get_llm_deployment

_SYSTEM_PROMPT = (
    "너는 삼성증권 PB가 VVIP 고객에게 포트폴리오 전체 분석 결과를 설명할 때 쓰는 "
    "요약을 작성하는 보조자다.\n\n"
    "【절대 금지 — 위반 시 전체 응답 무효】\n"
    "1. 입력 JSON에 없는 숫자를 생성하지 않는다. "
    "샤프지수, MDD, 변동성, 베타, 세율, 절세액 등 모든 지표는 이미 계산되어 있다. "
    "재계산하거나 새 수치를 만들어내지 않는다.\n"
    "2. '○○ 자산 비중을 늘리세요', '△△에 투자하세요' 등 새로운 자산배분을 "
    "추천하거나 제안하지 않는다. 포트폴리오 A·B는 이미 추천된 결과이며, "
    "너의 역할은 그 결과를 설명하는 것이다.\n\n"
    "【허용 사항】\n"
    "- 입력에 있는 숫자와 지표를 인용하면서 의미를 설명한다.\n"
    "- 현재 포트폴리오와 포트폴리오 A·B의 차이점을 비교한다.\n"
    "- 절세 전략의 예상 효과를 쉬운 말로 풀어 설명한다.\n"
    "- 스트레스 테스트 결과가 의미하는 위험 수준을 설명한다.\n"
    "- 벤치마크 대비 성과를 설명한다(베타, 수익률 차이 등).\n\n"
    "응답은 PB가 고객 앞에서 읽을 수 있는 자연스러운 한국어 문단으로 작성한다. "
    "불릿 포인트 최소화, 핵심 위주로 간결하게."
)


def _format_dashboard_for_prompt(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def summarize_portfolio_dashboard(payload: dict[str, Any]) -> str:
    """포트폴리오 전체 대시보드 결과를 gpt-4o로 요약한다.

    실패 시 예외를 올린다(라우터가 fallback 처리).
    payload 키 구조: current·portfolio_a·portfolio_b·stress·benchmark·tax_optimizer
    """
    if not payload:
        raise ValueError("대시보드 결과가 비어 있어 요약할 수 없습니다.")

    context = _format_dashboard_for_prompt(payload)
    user_prompt = (
        f"[포트폴리오 전체 분석 결과(JSON)]\n{context}\n\n"
        "위 계산 결과의 숫자만 사용해, PB가 고객에게 설명하듯 한국어로 요약하라. "
        "새 숫자 생성과 자산배분 추천은 절대 금지다."
    )
    response = get_llm_client().chat.completions.create(
        model=get_llm_deployment(),
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        timeout=30.0,
    )
    if not response.choices:
        raise ValueError("LLM 응답에 choices가 없습니다.")
    summary = response.choices[0].message.content
    if not summary or not summary.strip():
        raise ValueError("LLM이 빈 요약을 반환했습니다.")
    return summary.strip()


def _is_real_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _percent(value: Any) -> str | None:
    if _is_real_number(value):
        return f"{value * 100:.2f}%"
    return None


def _won(value: Any) -> str | None:
    if _is_real_number(value):
        return f"{round(value):,}원"
    return None


def fallback_portfolio_summary(payload: dict[str, Any]) -> str:
    """LLM 실패 시 계산 결과를 그대로 끼워 넣는 템플릿 요약(숫자 생성/변형 없음)."""
    if not payload:
        return "포트폴리오 분석 결과가 없어 요약을 생성할 수 없습니다."

    lines = ["[포트폴리오 분석 요약(자동 임시본)]"]

    for key, label in [
        ("current", "현재 포트폴리오"),
        ("portfolio_a", "포트폴리오 A"),
        ("portfolio_b", "포트폴리오 B"),
    ]:
        p = payload.get(key) or {}
        metrics = p.get("metrics") or {}
        er = _percent(metrics.get("expected_return"))
        vol = _percent(metrics.get("volatility"))
        sharpe = metrics.get("sharpe_ratio")
        beta = metrics.get("beta")
        mdd = _percent(metrics.get("mdd"))

        parts = []
        if er:
            parts.append(f"기대수익률 {er}")
        if vol:
            parts.append(f"변동성 {vol}")
        if _is_real_number(sharpe):
            parts.append(f"샤프 {sharpe:.2f}")
        if _is_real_number(beta):
            parts.append(f"베타 {beta:.2f}")
        if mdd:
            parts.append(f"MDD {mdd}")

        if parts:
            lines.append(f"- {label}: {', '.join(parts)}")

    stress = (payload.get("stress") or {}).get("stressed") or {}
    stress_metrics = stress.get("metrics") or {}
    stress_er = _percent(stress_metrics.get("expected_return"))
    if stress_er:
        lines.append(f"- 스트레스 시나리오 기대수익률: {stress_er}")

    tax = payload.get("tax_optimizer") or {}
    current_tax = tax.get("current") or {}
    headline = current_tax.get("headline") or {}
    saving = _won(headline.get("annual_tax_saving"))
    if saving:
        lines.append(f"- 절세 전략 적용 시 연간 약 {saving} 절감 추정")

    if len(lines) == 1:
        lines.append("- 표시할 분석 수치가 없습니다.")

    lines.append(
        "※ 요약 생성이 일시적으로 실패해 계산 결과를 그대로 표기했습니다. "
        "수치는 프로젝트용 간이 추정입니다."
    )
    return "\n".join(lines)
