"""POST /dart/insight — DART 재무 기반 AI 인사이트 (stage-2).

/rag/insight 와 별도 라우터·별도 스키마다(스키마 충돌 회피, 기존 결정).
처리 흐름: 요청(corp_name|corp_code) → resolve_corp_code → (제외/수동확인이면 그 상태를
응답에 명확히) → 재무 fetch → gpt-4o 요약 → 응답.

OpenAI·supabase·DART 호출이 블로킹이므로 핸들러는 동기 def 로 작성한다(FastAPI 가
스레드풀에서 실행 — async def 로 바꾸면 이벤트루프가 막힌다, rag.py 와 동일).

LLM 은 요약·설명만 생성하고, 수치·사실은 fetch 결과를 그대로 응답에 싣는다(숫자를
LLM 이 지어내지 않게 — 할루시네이션 금지). 출처(보고서 연도·접수번호·연결/별도)와
조회 시점을 응답에 포함해 감사추적성을 보장한다.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_pb_id
from pydantic import BaseModel, model_validator

from app.core.azure_openai import get_llm_client, get_llm_deployment
from app.services.dart_finance import FINANCE_FIELDS, FinancialResult, fetch_financials
from app.services.dart_resolve import resolve_corp_code

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dart", tags=["dart"])

KST = ZoneInfo("Asia/Seoul")

# 수치 지어내기를 막는 시스템 프롬프트. 제공된 값만 쓰게 강제한다.
_SYSTEM_PROMPT = (
    "당신은 삼성증권 PB를 돕는 재무 분석 보조자입니다. "
    "반드시 아래에 '제공된 재무 수치'만 사용해 한국어로 간결히 요약·해설하세요. "
    "제공되지 않은 값은 추정하거나 새로 만들지 마세요(없으면 '제공되지 않음'이라고 하세요). "
    "수치를 임의로 반올림하거나 변형하지 말고, 의미(수익성·재무안정성 등) 해석에 집중하세요. "
    "투자 권유나 단정적 전망은 하지 마세요."
)


class DartInsightRequest(BaseModel):
    corp_name: str | None = None
    corp_code: str | None = None
    bsns_year: int | None = None  # 재현용: 특정 사업연도 지정(미지정 시 최신)

    @model_validator(mode="after")
    def _need_one(self) -> "DartInsightRequest":
        if not (self.corp_name or self.corp_code):
            raise ValueError("corp_name 또는 corp_code 중 하나는 필요합니다.")
        return self


class FinancialsPayload(BaseModel):
    # FINANCE_FIELDS 키(영문) → 금액(원). 누락은 None.
    revenue: int | None = None
    operating_income: int | None = None
    net_income: int | None = None
    total_assets: int | None = None
    total_liabilities: int | None = None
    total_equity: int | None = None


class DartSource(BaseModel):
    corp_code: str
    bsns_year: int
    reprt_code: str
    rcept_no: str        # 공시 원문 접수번호(감사추적)
    fs_label: str        # 연결/별도
    currency: str
    note: str


class DartInsightResponse(BaseModel):
    query: str
    resolve_status: str          # matched/disambiguated/excluded_delisted/manual_review/not_found
    resolve_reason: str
    corp_code: str | None
    corp_name: str | None
    financials: FinancialsPayload | None
    source: DartSource | None
    summary: str
    as_of: datetime


def _format_financials_for_prompt(corp_name: str, fin: FinancialResult) -> str:
    lines = [f"회사: {corp_name}", f"기준: {fin.source_note} (단위 {fin.currency}, 원)"]
    for key, label in FINANCE_FIELDS.items():
        v = fin.values.get(key)
        lines.append(f"- {label}: {'제공되지 않음' if v is None else format(v, ',')}원")
    return "\n".join(lines)


def _summarize(corp_name: str, fin: FinancialResult) -> str:
    """gpt-4o 요약(temperature=0). 실패 시 결정적 템플릿으로 폴백(데모가 죽지 않게)."""
    facts = _format_financials_for_prompt(corp_name, fin)
    user_msg = f"다음 재무 수치를 PB 관점에서 요약해 주세요.\n\n{facts}"
    try:
        resp = get_llm_client().chat.completions.create(
            model=get_llm_deployment(),
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0,
        )
        if resp.choices and resp.choices[0].message.content:
            return resp.choices[0].message.content.strip()
        raise RuntimeError("LLM 응답이 비어 있음")
    except Exception:
        # 키·민감정보가 섞일 수 있으나 우리 RuntimeError 는 값을 담지 않는다. 스택만 남김.
        logger.exception("DART 인사이트 LLM 생성 실패 — 템플릿 요약으로 폴백합니다.")
        return f"[자동요약 폴백] {facts}"


@router.post("/insight", response_model=DartInsightResponse)
def create_dart_insight(
    request: DartInsightRequest,
    pb_id: str = Depends(get_current_pb_id),
) -> DartInsightResponse:
    query = (request.corp_code or request.corp_name or "").strip()

    resolved = resolve_corp_code(query)
    now = datetime.now(KST)

    # 채택/확정이 아니면(제외·수동확인·미발견) 재무 fetch 없이 상태를 명확히 응답.
    if not resolved.usable:
        return DartInsightResponse(
            query=query,
            resolve_status=resolved.status,
            resolve_reason=resolved.reason,
            corp_code=resolved.corp_code,
            corp_name=resolved.corp_name,
            financials=None,
            source=None,
            summary=f"재무 조회를 진행하지 않았습니다: {resolved.reason}",
            as_of=now,
        )

    fin = fetch_financials(resolved.corp_code, bsns_year=request.bsns_year)
    if fin is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"{resolved.corp_name}({resolved.corp_code}) 의 "
                "확정 사업보고서 재무를 찾지 못했습니다."
            ),
        )

    summary = _summarize(resolved.corp_name or query, fin)

    return DartInsightResponse(
        query=query,
        resolve_status=resolved.status,
        resolve_reason=resolved.reason,
        corp_code=resolved.corp_code,
        corp_name=resolved.corp_name,
        financials=FinancialsPayload(**fin.values),
        source=DartSource(
            corp_code=fin.corp_code,
            bsns_year=fin.bsns_year,
            reprt_code=fin.reprt_code,
            rcept_no=fin.rcept_no,
            fs_label=fin.fs_label,
            currency=fin.currency,
            note=fin.source_note,
        ),
        summary=summary,
        as_of=now,
    )
