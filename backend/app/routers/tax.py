"""POST /tax/insight — 절세 시뮬레이터 결과를 gpt-4o 로 요약.

방향(준호님 확정): "계산은 지은·승민님 로직(#30), AI는 요약만".
계산 결과를 입력으로 받아 LLM 이 PB 설명조로 요약한다. LLM 실패 시 템플릿 폴백.

입력 계약(tax_result)은 #30(portfolio_logic)의 build_tax_optimizer_payload
출력(포트폴리오 1건분)과 호환되도록 설계했다. 회의에서 필드가 바뀔 수 있어
extra='allow' 로 유연하게 두고, 요약을 만드는 핵심 필드만 명시한다.

TODO(#30 머지 후): portfolio_logic.build_tax_optimizer_payload 출력을 그대로
tax_result 로 넘겨 실연결한다. 현재는 더미 입력으로 동작만 확인한다.

OpenAI 호출이 블로킹이므로 핸들러는 동기 def 로 둔다(rag.py 와 동일, #26 리뷰 참고).
"""

import logging
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from app.services.tax_insight import fallback_summary, summarize_tax_result

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tax", tags=["tax"])

KST = ZoneInfo("Asia/Seoul")


class TaxHeadline(BaseModel):
    # build_tax_optimizer_payload["headline"] 호환. 비율은 0.0432 = 4.32% 형태.
    model_config = ConfigDict(extra="allow")
    annual_tax_saving: float | None = None
    tax_amount_before: float | None = None
    tax_amount_after: float | None = None
    after_tax_return_before: float | None = None
    after_tax_return_after: float | None = None
    after_tax_return_improvement_p: float | None = None


class AccountCard(BaseModel):
    # ISA/IRP/일반계좌 카드 공통 형태. 계좌별로 채워지는 키가 달라 모두 optional.
    model_config = ConfigDict(extra="allow")
    status_label: str | None = None
    description: str | None = None
    estimated_tax_saving: float | None = None  # ISA
    estimated_tax_credit: float | None = None  # IRP
    estimated_tax_after_strategy: float | None = None  # 일반계좌


class TaxCalculationResult(BaseModel):
    """#30 절세 계산 결과(포트폴리오 1건분). 미확정이라 extra 허용·핵심만 명시."""

    model_config = ConfigDict(extra="allow")
    portfolio_key: str | None = None
    portfolio_name: str | None = None
    total_asset: float | None = None
    headline: TaxHeadline | None = None
    account_cards: dict[str, AccountCard] | None = None
    notes: list[str] | None = None


class TaxInsightRequest(BaseModel):
    consultation_id: UUID
    tax_result: TaxCalculationResult


class TaxInsightResponse(BaseModel):
    summary: str
    as_of: datetime


@router.post("/insight", response_model=TaxInsightResponse)
def create_tax_insight(request: TaxInsightRequest) -> TaxInsightResponse:
    # TODO: consultation_id 존재 검증 — consultation 테이블 조회는 다음 단계(rag.py 와 동일).
    # extra='allow' 로 들어온 #30 의 나머지 필드까지 보존해 LLM 근거로 넘긴다.
    tax_result = request.tax_result.model_dump(exclude_none=True)
    try:
        summary = summarize_tax_result(tax_result)
    except Exception:
        # 우리 RuntimeError 는 키 값을 담지 않는다. 스택만 남기고 템플릿으로 폴백한다.
        logger.exception("절세 요약 LLM 실패 — 템플릿 폴백으로 응답합니다.")
        summary = fallback_summary(tax_result)
    return TaxInsightResponse(summary=summary, as_of=datetime.now(KST))
