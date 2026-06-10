"""POST /rag/insight — RAG 기반 AI 인사이트 (노션 ⑧ 명세).

처리 흐름: query 임베딩 → pgvector 검색 → (0건이면 404) → 추출형 생성 → 응답.
OpenAI·supabase 호출이 블로킹이므로 핸들러는 동기 def 로 작성한다
(FastAPI 가 스레드풀에서 실행 — async def 로 바꾸면 이벤트루프가 막힌다, #26 리뷰 참고).
"""

from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.rag.generate import ExtractiveGenerator, Generator
from app.rag.retrieval import embed_query, search_chunks

router = APIRouter(prefix="/rag", tags=["rag"])

KST = ZoneInfo("Asia/Seoul")

# 생성기는 인터페이스로 추상화 — LLM 생성기 확정(6/14 회의) 시 여기만 교체한다.
_generator: Generator = ExtractiveGenerator()


class InsightContext(BaseModel):
    risk_profile: str | None = None
    selected_portfolio: str | None = None


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
    citations: list[Citation]
    as_of: datetime


@router.post("/insight", response_model=InsightResponse)
def create_insight(request: InsightRequest) -> InsightResponse:
    # TODO: consultation_id 존재 검증 — consultation 테이블 조회는 다음 단계에서 추가.
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="query 는 빈 문자열일 수 없습니다.")

    query_embedding = embed_query(request.query)
    chunks = search_chunks(query_embedding)
    if not chunks:
        raise HTTPException(status_code=404, detail="관련 문서 없음(임계값 미달)")

    answer = _generator.generate(request.query, chunks)
    return InsightResponse(
        answer=answer,
        citations=[Citation(**chunk) for chunk in chunks],
        as_of=datetime.now(KST),
    )
