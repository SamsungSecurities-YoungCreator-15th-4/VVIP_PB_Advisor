from typing import Literal

from pydantic import BaseModel, ConfigDict


CustomerName = Literal["김성삼", "이사조", "박기업"]


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


class ConsultationListResponse(BaseModel):
    customer_name: CustomerName
    consultations: list[ConsultationResponse]

    model_config = ConfigDict(extra="forbid")


class InitialIpsResponse(BaseModel):
    ips_snapshot_id: str
    customer_id: str
    customer_name: CustomerName
    source_type: Literal["initial"]
    ips_json: dict
    created_at: str

    model_config = ConfigDict(extra="forbid")
