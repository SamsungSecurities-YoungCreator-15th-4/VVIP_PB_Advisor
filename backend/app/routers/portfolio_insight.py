"""POST /portfolio/insight — 포트폴리오 전체 대시보드 결과를 gpt-4o로 요약.

설계:
- 입력: 이미 계산된 포트폴리오(current·A·B 6지표, 스트레스, 벤치마크, 절세 결과)
- AI 역할: 계산 결과 설명·비교만. 숫자 생성·자산배분 추천 절대 금지(시스템 프롬프트 강제).
- 기존 POST /tax/insight(포트폴리오 1건 절세 요약)와 직교 관계 — 이 엔드포인트는
  전체 대시보드 컨텍스트(3개 포트폴리오 + 스트레스 + 벤치마크 + 절세)를 한번에 받음.
- LLM 실패 시 fallback_portfolio_summary() 템플릿으로 응답 (데모가 죽지 않도록).
- 동기 def: OpenAI 호출이 블로킹이므로 tax.py·rag.py 패턴과 동일.
"""

import logging
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from app.services.portfolio_insight import (
    fallback_portfolio_summary,
    summarize_portfolio_dashboard,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolio", tags=["portfolio-insight"])

KST = ZoneInfo("Asia/Seoul")


class PortfolioMetrics(BaseModel):
    """6지표 + 베타 + 세후수익률 등 calculate_metrics 출력 호환. extra 허용."""

    model_config = ConfigDict(extra="allow")
    expected_return: float | None = None
    volatility: float | None = None
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    mdd: float | None = None
    beta: float | None = None
    after_tax_return: float | None = None


class PortfolioSummary(BaseModel):
    """포트폴리오 1건(current/A/B) 핵심 필드. extra 허용으로 weights 등 부가 필드도 통과."""

    model_config = ConfigDict(extra="allow")
    api_key: str | None = None
    name: str | None = None
    metrics: PortfolioMetrics | None = None


class StressResult(BaseModel):
    """스트레스 테스트 결과. extra 허용."""

    model_config = ConfigDict(extra="allow")


class TaxOptimizerResult(BaseModel):
    """절세 최적화 결과 맵. extra 허용 — build_tax_optimizer_map 출력과 호환."""

    model_config = ConfigDict(extra="allow")


class PortfolioInsightRequest(BaseModel):
    """전체 대시보드 요약 요청.

    consultation_id는 선택(미등록 고객 상담 지원). 나머지 필드는 run_full_analysis
    / run_analysis_core 출력에서 그대로 잘라 넣을 수 있도록 구조를 맞췄다.
    extra='allow'로 미래 필드 추가를 수용한다.
    """

    model_config = ConfigDict(extra="allow")
    consultation_id: UUID | None = None
    benchmark_choice: str | None = None
    current: PortfolioSummary | None = None
    portfolio_a: PortfolioSummary | None = None
    portfolio_b: PortfolioSummary | None = None
    stress: StressResult | None = None
    tax_optimizer: TaxOptimizerResult | None = None


class PortfolioInsightResponse(BaseModel):
    summary: str
    source: str  # "llm" | "fallback"
    as_of: datetime


@router.post("/insight", response_model=PortfolioInsightResponse)
def create_portfolio_insight(request: PortfolioInsightRequest) -> PortfolioInsightResponse:
    # extra='allow'로 들어온 모든 필드까지 LLM 근거로 넘긴다.
    payload = request.model_dump(exclude_none=True)
    # consultation_id는 UUID 직렬화 시 str로 변환
    if "consultation_id" in payload:
        payload["consultation_id"] = str(payload["consultation_id"])

    source = "llm"
    try:
        summary = summarize_portfolio_dashboard(payload)
    except Exception:
        logger.exception("포트폴리오 인사이트 LLM 실패 — 템플릿 폴백으로 응답합니다.")
        summary = fallback_portfolio_summary(payload)
        source = "fallback"

    return PortfolioInsightResponse(summary=summary, source=source, as_of=datetime.now(KST))
