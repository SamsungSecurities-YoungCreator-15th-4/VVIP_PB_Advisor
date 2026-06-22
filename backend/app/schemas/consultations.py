from typing import Literal

from pydantic import BaseModel, ConfigDict


# 고객 SSOT 는 DB(client 테이블)다. 과거에는 페르소나 3명을 Literal 로 고정했으나,
# 고객 추가 기능 도입으로 임의 고객명이 들어올 수 있어 자유 문자열로 전환한다.
# 검증은 타입(Literal)이 아니라 "DB 에 존재하는 고객인가"로 한다(라우터에서 조회).
CustomerName = str


class ConsultationResponse(BaseModel):
    consultation_id: str
    customer_id: str
    customer_name: CustomerName
    consultation_date: str
    transcript_title: str
    ips_title: str
    transcript_json: list[dict]
    ips_json: dict
    ips_snapshot_id: str | None
    created_at: str

    model_config = ConfigDict(extra="forbid")


class ConsultationSummaryResponse(BaseModel):
    consultation_id: str
    customer_id: str
    customer_name: CustomerName
    consultation_date: str
    transcript_title: str
    ips_title: str
    created_at: str

    model_config = ConfigDict(extra="forbid")


class ConsultationListResponse(BaseModel):
    customer_id: str
    customer_name: CustomerName
    consultations: list[ConsultationSummaryResponse]

    model_config = ConfigDict(extra="forbid")


class InitialIpsResponse(BaseModel):
    ips_snapshot_id: str
    customer_id: str
    customer_name: CustomerName
    source_type: Literal["initial"]
    ips_json: dict
    created_at: str

    model_config = ConfigDict(extra="forbid")
