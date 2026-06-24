"""POST /rag/insight — RAG 기반 AI 인사이트 (노션 ⑧ 명세).

처리 흐름: query 임베딩 → pgvector 검색 → (0건이면 404) → 추출형 생성 → 응답.
OpenAI·supabase 호출이 블로킹이므로 핸들러는 동기 def 로 작성한다
(FastAPI 가 스레드풀에서 실행 — async def 로 바꾸면 이벤트루프가 막힌다, #26 리뷰 참고).
"""

import logging
import re
from datetime import date, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.rag.generate import (
    ExtractiveGenerator,
    Generator,
    InsightSummaryGenerator,
    LLMGenerator,
    fallback_insight_summary,
)
from app.rag.retrieval import embed_query, search_chunks
from app.services.portfolio_insight import (
    fallback_portfolio_summary,
    summarize_portfolio_dashboard,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])

KST = ZoneInfo("Asia/Seoul")

# 기본 생성기는 LLM(gpt-4o). 실패(타임아웃·rate limit·키 미설정 등) 시 추출형으로
# 폴백해 답이라도 나오게 한다(Render Free·Azure 장애 대비 — 데모가 죽지 않게).
_generator: Generator = LLMGenerator()
_fallback_generator: Generator = ExtractiveGenerator()
_summary_generator = InsightSummaryGenerator()

_DASHBOARD_QUERY_PATTERNS = (
    r"(?:중앙)?대시보드.*(?:결과|요약|설명|다시)",
    r"분석(?:결과|겨로가).*(?:요약|설명|다시)",
    r"(?:분석|결과).*다시.*설명",
    r"(?:분석|결과).*요약",
    r"현재/?vs?a/?vs?b.*(?:결과|요약|설명)",
    r"(?:5년)?백테스트.*(?:결과|요약|다시)",
    r"절세(?:최적화|시뮬레이터).*(?:결과|요약|다시)",
)


def _generate_answer(query: str, chunks: list[dict]) -> str:
    """LLM 생성 시도 후 실패하면 추출형으로 폴백한다(폴백 발생 시 로그)."""
    try:
        return _generator.generate(query, chunks)
    except Exception:
        # 예외 메시지에 키·민감정보가 섞일 수 있으나 우리 RuntimeError 는 값을 담지
        # 않는다. exception() 으로 스택만 남기고 추출형으로 폴백한다.
        logger.exception("LLMGenerator 생성 실패 — ExtractiveGenerator 로 폴백합니다.")
        return _fallback_generator.generate(query, chunks)


def _generate_summary(answer: str) -> str:
    """gpt-4.1-mini 요약 시도 후 실패하면 answer 원문 기반 요약으로 폴백한다."""
    try:
        return _summary_generator.summarize(answer)
    except Exception:
        logger.exception("InsightSummaryGenerator 생성 실패 — fallback 요약으로 폴백합니다.")
        return fallback_insight_summary(answer)


def _normalize_intent_text(text: str) -> str:
    return "".join(text.lower().split())


def _is_dashboard_summary_query(query: str) -> bool:
    normalized = _normalize_intent_text(query)
    return any(re.search(pattern, normalized) for pattern in _DASHBOARD_QUERY_PATTERNS)


def _generate_dashboard_answer(dashboard: dict[str, Any]) -> str:
    """중앙 대시보드 스냅샷을 근거로 요약한다. 실패 시 템플릿으로 폴백한다."""
    try:
        return summarize_portfolio_dashboard(dashboard)
    except Exception:
        logger.exception("대시보드 인사이트 LLM 실패 — 템플릿 폴백으로 응답합니다.")
        return fallback_portfolio_summary(dashboard)


class DashboardContext(BaseModel):
    """프론트 중앙 대시보드 상태 스냅샷. 화면 추가 필드는 그대로 통과시킨다."""

    model_config = ConfigDict(extra="allow")


class InsightContext(BaseModel):
    risk_profile: str | None = None
    selected_portfolio: str | None = None
    dashboard: DashboardContext | None = None


class InsightRequest(BaseModel):
    consultation_id: UUID
    query: str
    context: InsightContext | None = None


class Citation(BaseModel):
    doc_id: UUID
    source_type: str
    title: str
    published_date: date | None = None
    chunk: str
    similarity: float | None = None


class InsightResponse(BaseModel):
    answer: str
    summary: str
    citations: list[Citation]
    as_of: datetime


@router.post("/insight", response_model=InsightResponse)
def create_insight(request: InsightRequest) -> InsightResponse:
    # TODO: consultation_id 존재 검증 — consultation 테이블 조회는 다음 단계에서 추가.
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query 는 빈 문자열일 수 없습니다.")

    dashboard_payload = (
        request.context.dashboard.model_dump(exclude_none=True)
        if request.context and request.context.dashboard
        else None
    )
    if _is_dashboard_summary_query(query):
        if not dashboard_payload:
            raise HTTPException(
                status_code=400,
                detail="중앙 대시보드 요약 질의에는 context.dashboard 가 필요합니다.",
            )
        answer = _generate_dashboard_answer(dashboard_payload)
        return InsightResponse(
            answer=answer,
            summary=_generate_summary(answer),
            citations=[],
            as_of=datetime.now(KST),
        )

    query_embedding = embed_query(query)
    chunks = search_chunks(query_embedding)
    if not chunks:
        raise HTTPException(status_code=404, detail="관련 문서 없음(임계값 미달)")

    answer = _generate_answer(query, chunks)
    summary = _generate_summary(answer)
    return InsightResponse(
        answer=answer,
        summary=summary,
        citations=[Citation(**chunk) for chunk in chunks],
        as_of=datetime.now(KST),
    )
