import logging
from datetime import datetime, timezone
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.db.supabase import get_supabase
from app.schemas.consultations import (
    ConsultationListResponse,
    ConsultationResponse,
    CustomerName,
    InitialIpsResponse,
)
from app.services.ips import (
    build_ips_snapshot_payload,
    flatten_ips_json,
)
from app.services.stt_pipeline import run_uploaded_wav_pipeline
from app.services.transcript import transcript_to_raw_note

router = APIRouter(prefix="/consultations", tags=["consultations"])
logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")


@router.post(
    "/stt",
    response_model=ConsultationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_stt_consultation(
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
        logger.exception("STT consultation pipeline failed")
        raise HTTPException(
            status_code=500,
            detail="STT 상담 처리 중 오류가 발생했습니다.",
        ) from exc

    try:
        raw_note = transcript_to_raw_note(pipeline_result.transcript_json)
        ips_json = flatten_ips_json(pipeline_result.ips_json)
    except ValueError as exc:
        logger.exception("Invalid IPS extraction result")
        raise HTTPException(
            status_code=500,
            detail="IPS 구조화 결과 검증 중 오류가 발생했습니다.",
        ) from exc

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
    try:
        snapshot_result = (
            supabase.table("ips_snapshot")
            .insert(snapshot_payload)
            .execute()
        )
        snapshot = _first_row(snapshot_result.data)
    except Exception as exc:
        _delete_consultation(supabase, consultation["id"])
        logger.exception("IPS snapshot insert failed")
        raise HTTPException(
            status_code=500,
            detail="상담 결과 저장 중 오류가 발생했습니다.",
        ) from exc

    if not snapshot:
        _delete_consultation(supabase, consultation["id"])
        raise HTTPException(
            status_code=500,
            detail="상담 결과 저장 중 오류가 발생했습니다.",
        )

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
        created_at=_to_kst_iso(consultation["created_at"]),
    )


@router.get("/initial-ips", response_model=InitialIpsResponse)
def get_initial_ips(customer_name: CustomerName) -> InitialIpsResponse:
    supabase = get_supabase()
    client = _get_client_by_name(supabase, customer_name)
    if not client:
        raise HTTPException(
            status_code=404,
            detail=f"고객 정보를 찾을 수 없습니다: {customer_name}",
        )

    result = (
        supabase.table("ips_snapshot")
        .select("id,client_id,source_type,raw_ips_json,created_at")
        .eq("client_id", client["id"])
        .eq("source_type", "initial")
        .limit(1)
        .execute()
    )
    snapshot = _first_row(result.data)
    if not snapshot:
        raise HTTPException(
            status_code=404,
            detail=f"최초 IPS 정보를 찾을 수 없습니다: {customer_name}",
        )

    try:
        ips_json = flatten_ips_json(snapshot.get("raw_ips_json") or {})
    except ValueError as exc:
        logger.exception("Invalid initial IPS snapshot")
        raise HTTPException(
            status_code=500,
            detail="최초 IPS 구조 검증 중 오류가 발생했습니다.",
        ) from exc

    return InitialIpsResponse(
        ips_snapshot_id=snapshot["id"],
        customer_id=snapshot["client_id"],
        customer_name=customer_name,
        source_type="initial",
        ips_json=ips_json,
        created_at=_to_kst_iso(snapshot["created_at"]),
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
            created_at=_to_kst_iso(row["created_at"]),
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
    return _parse_datetime(created_at).astimezone(KST).date().isoformat()


def _to_kst_iso(created_at: str) -> str:
    return _parse_datetime(created_at).astimezone(KST).isoformat()


def _parse_datetime(datetime_text: str) -> datetime:
    normalized = datetime_text.replace("Z", "+00:00")
    created_datetime = datetime.fromisoformat(normalized)
    if created_datetime.tzinfo is None:
        created_datetime = created_datetime.replace(tzinfo=timezone.utc)

    return created_datetime


def _delete_consultation(supabase, consultation_id: str) -> None:
    try:
        supabase.table("consultation").delete().eq("id", consultation_id).execute()
    except Exception:
        logger.exception("Failed to delete orphan consultation: %s", consultation_id)
