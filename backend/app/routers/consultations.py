from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.db.supabase import get_supabase
from app.schemas.consultations import (
    ConsultationListResponse,
    ConsultationResponse,
    CustomerName,
)
from app.services.ips import (
    build_ips_snapshot_payload,
    flatten_ips_json,
)
from app.services.stt_pipeline import run_uploaded_wav_pipeline
from app.services.transcript import transcript_to_raw_note

router = APIRouter(prefix="/consultations", tags=["consultations"])


@router.post(
    "/stt",
    response_model=ConsultationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_stt_consultation(
    customer_name: Annotated[CustomerName, Form()],
    audio_file: Annotated[UploadFile, File()],
) -> ConsultationResponse:
    supabase = get_supabase()
    client = _get_client_by_name(supabase, customer_name)
    if not client:
        raise HTTPException(
            status_code=404,
            detail=f"고객 정보를 찾을 수 없습니다: {customer_name}",
        )

    try:
        pipeline_result = run_uploaded_wav_pipeline(
            customer_name=customer_name,
            audio_file=audio_file,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    raw_note = transcript_to_raw_note(pipeline_result.transcript_json)
    ips_json = flatten_ips_json(pipeline_result.ips_json)

    consultation_payload = {
        "client_id": client["id"],
        "raw_note": raw_note,
        "transcript_title": pipeline_result.transcript_title,
        "ips_title": pipeline_result.ips_title,
        "transcript_json": pipeline_result.transcript_json,
        "ips_json": ips_json,
    }

    consultation_result = (
        supabase.table("consultation")
        .insert(consultation_payload)
        .execute()
    )
    consultation = _first_row(consultation_result.data)
    if not consultation:
        raise HTTPException(status_code=500, detail="상담 내역 저장에 실패했습니다.")

    snapshot_payload = build_ips_snapshot_payload(
        client_id=client["id"],
        consultation_id=consultation["id"],
        source_type="consultation",
        raw_ips_json=ips_json,
    )
    snapshot_result = (
        supabase.table("ips_snapshot")
        .insert(snapshot_payload)
        .execute()
    )
    snapshot = _first_row(snapshot_result.data)
    if not snapshot:
        raise HTTPException(status_code=500, detail="IPS 스냅샷 저장에 실패했습니다.")

    return ConsultationResponse(
        consultation_id=consultation["id"],
        customer_id=client["id"],
        customer_name=customer_name,
        consultation_date=_consultation_date(consultation["created_at"]),
        transcript_title=consultation["transcript_title"],
        ips_title=consultation["ips_title"],
        transcript_json=pipeline_result.transcript_json,
        ips_json=ips_json,
        ips_snapshot_id=snapshot["id"],
        created_at=consultation["created_at"],
    )


@router.get("", response_model=ConsultationListResponse)
def list_consultations(customer_name: CustomerName) -> ConsultationListResponse:
    supabase = get_supabase()
    client = _get_client_by_name(supabase, customer_name)
    if not client:
        raise HTTPException(
            status_code=404,
            detail=f"고객 정보를 찾을 수 없습니다: {customer_name}",
        )

    result = (
        supabase.table("consultation")
        .select(
            "id,client_id,transcript_title,ips_title,"
            "transcript_json,ips_json,created_at"
        )
        .eq("client_id", client["id"])
        .order("created_at", desc=True)
        .execute()
    )

    consultations = [
        ConsultationResponse(
            consultation_id=row["id"],
            customer_id=row["client_id"],
            customer_name=customer_name,
            consultation_date=_consultation_date(row["created_at"]),
            transcript_title=row.get("transcript_title") or "",
            ips_title=row.get("ips_title") or "",
            transcript_json=row.get("transcript_json") or [],
            ips_json=row.get("ips_json") or {},
            ips_snapshot_id=None,
            created_at=row["created_at"],
        )
        for row in result.data
    ]

    return ConsultationListResponse(customer_name=customer_name, consultations=consultations)


def _get_client_by_name(supabase, customer_name: str) -> dict | None:
    result = (
        supabase.table("client")
        .select("id,name")
        .eq("name", customer_name)
        .limit(1)
        .execute()
    )
    return _first_row(result.data)


def _first_row(rows: list[dict] | None) -> dict | None:
    if not rows:
        return None
    return rows[0]


def _consultation_date(created_at: str) -> str:
    return created_at[:10]
