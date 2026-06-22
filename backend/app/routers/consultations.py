import asyncio
import json
import logging
import re
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Annotated, get_args
from zoneinfo import ZoneInfo

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from app.db.supabase import get_supabase
from app.schemas.consultations import (
    ConsultationListResponse,
    ConsultationResponse,
    ConsultationSummaryResponse,
    CustomerName,
    InitialIpsResponse,
)
from app.services.ips import (
    build_ips_snapshot_payload,
    flatten_ips_json,
)
from app.services.stt_pipeline import SttPipelineResult, run_uploaded_wav_pipeline
from app.services.transcript import transcript_to_raw_note
from app.stt.stt_realtime import (
    DEFAULT_BITS_PER_SAMPLE,
    DEFAULT_CHANNELS,
    DEFAULT_SAMPLE_RATE,
    RealtimeConversationTranscriber,
    build_realtime_pipeline_result,
)

router = APIRouter(prefix="/consultations", tags=["consultations"])
logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")
STT_TEST_PAGE = Path(__file__).resolve().parents[1] / "stt" / "realtime_test.html"


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

    return _save_stt_consultation_result(
        supabase=supabase,
        client=client,
        customer_name=customer_name,
        pipeline_result=pipeline_result,
    )


@router.get("/stt/realtime/spec")
def get_realtime_stt_spec() -> dict:
    """Swagger 문서용 실시간 STT WebSocket 프로토콜 명세."""
    return {
        "transport": "websocket",
        "path": "/consultations/stt/realtime",
        "local_url": "ws://127.0.0.1:8000/consultations/stt/realtime",
        "production_url": "wss://{render-backend-domain}/consultations/stt/realtime",
        "audio_format": {
            "content_type": "binary",
            "encoding": "PCM signed 16-bit little-endian",
            "sample_rate": DEFAULT_SAMPLE_RATE,
            "bits_per_sample": DEFAULT_BITS_PER_SAMPLE,
            "channels": DEFAULT_CHANNELS,
        },
        "client_messages": [
            {
                "step": "start",
                "type": "text/json",
                "example": {
                    "customer_name": "김성삼",
                    "sample_rate": DEFAULT_SAMPLE_RATE,
                    "bits_per_sample": DEFAULT_BITS_PER_SAMPLE,
                    "channels": DEFAULT_CHANNELS,
                },
            },
            {
                "step": "audio",
                "type": "binary",
                "description": "재생 중인 마이크 PCM audio chunk를 반복 전송합니다.",
            },
            {
                "step": "pause",
                "type": "text/json",
                "example": {"event": "pause"},
            },
            {
                "step": "resume",
                "type": "text/json",
                "example": {"event": "play"},
                "aliases": [{"event": "resume"}],
            },
            {
                "step": "finish",
                "type": "text/json",
                "example": {"event": "finish"},
                "aliases": [{"event": "stop"}],
            },
        ],
        "server_events": [
            {"event": "started"},
            {"event": "partial_transcript", "payload": {"transcript": "Raw STT segment"}},
            {"event": "paused"},
            {"event": "resumed"},
            {"event": "ignored"},
            {"event": "completed", "payload": {"consultation": "ConsultationResponse"}},
            {"event": "error"},
        ],
        "notes": [
            "Swagger UI는 WebSocket을 직접 실행하지 못하므로 이 엔드포인트는 문서용입니다.",
            "프론트는 사용자 기기 마이크 권한을 받고 PCM chunk를 WebSocket으로 전송해야 합니다.",
            "finish 이후 기존 STT 파이프라인과 동일하게 상담 스크립트와 IPS를 DB에 저장합니다.",
        ],
    }


@router.get("/stt/realtime/test", response_class=FileResponse)
def get_realtime_stt_test_page() -> FileResponse:
    """로컬 개발용 실시간 STT WebSocket 테스트 페이지."""
    return FileResponse(STT_TEST_PAGE)


@router.websocket("/stt/realtime")
async def create_realtime_stt_consultation(websocket: WebSocket) -> None:
    """실시간 STT WebSocket.

    프로토콜:
    1) 최초 text JSON:
       {"customer_name":"김성삼","sample_rate":16000,"bits_per_sample":16,"channels":1}
    2) 재생 중에는 binary PCM chunk 전송
    3) 일시정지 text JSON: {"event":"pause"}
    4) 재개 text JSON: {"event":"play"} 또는 {"event":"resume"}
    5) 완료 text JSON: {"event":"finish"} 또는 {"event":"stop"}
    6) 서버가 partial_transcript 이벤트와 completed 이벤트를 JSON으로 반환
    """
    await websocket.accept()
    transcriber: RealtimeConversationTranscriber | None = None
    transcript_task: asyncio.Task[None] | None = None
    transcript_queue: asyncio.Queue[dict] = asyncio.Queue()
    send_lock = asyncio.Lock()
    loop = asyncio.get_running_loop()

    def queue_transcript(item: dict) -> None:
        loop.call_soon_threadsafe(transcript_queue.put_nowait, item)

    try:
        start_payload = await websocket.receive_json()
        customer_name = _parse_realtime_customer_name(start_payload)
        sample_rate = _parse_positive_int(
            start_payload.get("sample_rate"),
            default=DEFAULT_SAMPLE_RATE,
            field_name="sample_rate",
        )
        bits_per_sample = _parse_positive_int(
            start_payload.get("bits_per_sample"),
            default=DEFAULT_BITS_PER_SAMPLE,
            field_name="bits_per_sample",
        )
        channels = _parse_positive_int(
            start_payload.get("channels"),
            default=DEFAULT_CHANNELS,
            field_name="channels",
        )

        supabase = get_supabase()
        client = await run_in_threadpool(_get_client_by_name, supabase, customer_name)
        if not client:
            await _send_realtime_json(
                websocket,
                {
                    "event": "error",
                    "detail": f"고객 정보를 찾을 수 없습니다: {customer_name}",
                },
                send_lock,
            )
            await websocket.close(code=1008)
            return

        transcriber = await run_in_threadpool(
            RealtimeConversationTranscriber,
            sample_rate=sample_rate,
            bits_per_sample=bits_per_sample,
            channels=channels,
            on_transcript=queue_transcript,
        )
        await run_in_threadpool(transcriber.start)
        await _send_realtime_json(websocket, {"event": "started"}, send_lock)
        transcript_task = asyncio.create_task(
            _stream_realtime_transcripts(websocket, transcript_queue, send_lock)
        )
        paused = False

        try:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    raise WebSocketDisconnect()

                audio_chunk = message.get("bytes")
                if audio_chunk is not None:
                    if not paused:
                        await run_in_threadpool(transcriber.write, audio_chunk)
                    continue

                text_payload = message.get("text")
                if text_payload is None:
                    continue
                control = _parse_realtime_control_message(text_payload)
                event = _normalize_realtime_control_event(control)
                if event == "pause":
                    paused = True
                    await _send_realtime_json(websocket, {"event": "paused"}, send_lock)
                    continue
                if event in {"play", "resume"}:
                    paused = False
                    await _send_realtime_json(websocket, {"event": "resumed"}, send_lock)
                    continue
                if event in {"finish", "stop"}:
                    break
                await _send_realtime_json(
                    websocket,
                    {
                        "event": "ignored",
                        "detail": f"지원하지 않는 제어 이벤트입니다: {event}",
                    },
                    send_lock,
                )
        finally:
            if transcript_task and transcript_task.done():
                await transcript_task

        transcript = await run_in_threadpool(transcriber.stop)
        await _stop_realtime_transcript_task(transcript_task)
        transcript_task = None
        mapped_transcript, ips_json = await run_in_threadpool(
            build_realtime_pipeline_result,
            transcript,
        )
        response = await run_in_threadpool(
            _save_stt_consultation_result,
            supabase=supabase,
            client=client,
            customer_name=customer_name,
            pipeline_result=SttPipelineResult(
                transcript_json=mapped_transcript,
                ips_json=ips_json,
            ),
        )
        await _send_realtime_json(
            websocket,
            {
                "event": "completed",
                "consultation": response.model_dump(),
            },
            send_lock,
        )
        await websocket.close(code=1000)
    except WebSocketDisconnect:
        logger.info("Realtime STT websocket disconnected")
        await _stop_realtime_transcript_task(transcript_task)
        if transcriber:
            await run_in_threadpool(transcriber.stop)
    except ValueError as exc:
        await _stop_realtime_transcript_task(transcript_task)
        if transcriber:
            await _stop_realtime_transcriber(transcriber)
        await _send_realtime_json(
            websocket,
            {"event": "error", "detail": str(exc)},
            send_lock,
        )
        await websocket.close(code=1003)
    except HTTPException as exc:
        logger.error("Realtime STT consultation HTTP error: %s", exc.detail)
        await _stop_realtime_transcript_task(transcript_task)
        if transcriber:
            await _stop_realtime_transcriber(transcriber)
        await _send_realtime_json(
            websocket,
            {"event": "error", "detail": exc.detail},
            send_lock,
        )
        await websocket.close(code=1011)
    except Exception:
        logger.exception("Realtime STT consultation pipeline failed")
        await _stop_realtime_transcript_task(transcript_task)
        if transcriber:
            await _stop_realtime_transcriber(transcriber)
        await _send_realtime_json(
            websocket,
            {
                "event": "error",
                "detail": "실시간 STT 상담 처리 중 오류가 발생했습니다.",
            },
            send_lock,
        )
        await websocket.close(code=1011)


def _save_stt_consultation_result(
    *,
    supabase,
    client: dict,
    customer_name: CustomerName,
    pipeline_result: SttPipelineResult,
) -> ConsultationResponse:
    try:
        raw_note = transcript_to_raw_note(pipeline_result.transcript_json)
        ips_json = flatten_ips_json(pipeline_result.ips_json)
    except ValueError as exc:
        logger.exception("Invalid IPS extraction result")
        raise HTTPException(
            status_code=500,
            detail="IPS 구조화 결과 검증 중 오류가 발생했습니다.",
        ) from exc

    snapshot_payload = build_ips_snapshot_payload(
        client_id=client["id"],
        consultation_id=None,
        source_type="consultation",
        raw_ips_json=ips_json,
    )
    transcript_title, ips_title = _build_stt_titles(
        supabase=supabase,
        client_id=client["id"],
        customer_name=customer_name,
    )

    rpc_payload = {
        "p_client_id": client["id"],
        "p_raw_note": raw_note,
        "p_transcript_json": pipeline_result.transcript_json,
        "p_ips_json": ips_json,
        "p_goal": snapshot_payload["goal"],
        "p_asset": snapshot_payload["asset"],
        "p_return": snapshot_payload["return"],
        "p_risk": snapshot_payload["risk"],
        "p_time": snapshot_payload["time"],
        "p_tax": snapshot_payload["tax"],
        "p_liquidity": snapshot_payload["liquidity"],
        "p_legal": snapshot_payload["legal"],
        "p_unique": snapshot_payload["unique"],
        "p_raw_ips_json": snapshot_payload["raw_ips_json"],
    }
    titled_rpc_payload = {
        **rpc_payload,
        "p_transcript_title": transcript_title,
        "p_ips_title": ips_title,
    }

    try:
        created = _execute_stt_consultation_rpc(supabase, rpc_payload)
    except Exception as exc:
        if not _is_missing_stt_rpc_signature_error(exc):
            logger.exception("STT consultation RPC failed")
            raise HTTPException(
                status_code=500,
                detail="상담 결과 저장 중 오류가 발생했습니다.",
            ) from exc

        logger.warning(
            "STT consultation RPC current signature missing; "
            "retrying title-parameter signature."
        )
        try:
            created = _execute_stt_consultation_rpc(supabase, titled_rpc_payload)
        except Exception as fallback_exc:
            logger.exception("Title-parameter STT consultation RPC failed")
            raise HTTPException(
                status_code=500,
                detail="상담 결과 저장 중 오류가 발생했습니다.",
            ) from fallback_exc

    if not created:
        raise HTTPException(
            status_code=500,
            detail="상담 결과 저장 중 오류가 발생했습니다.",
        )

    return ConsultationResponse(
        consultation_id=created["consultation_id"],
        customer_id=created.get("customer_id") or client["id"],
        customer_name=customer_name,
        consultation_date=_consultation_date(created["created_at"]),
        transcript_title=created.get("transcript_title") or transcript_title,
        ips_title=created.get("ips_title") or ips_title,
        transcript_json=pipeline_result.transcript_json,
        ips_json=ips_json,
        ips_snapshot_id=created.get("ips_snapshot_id"),
        created_at=_to_kst_iso(created["created_at"]),
    )


def _execute_stt_consultation_rpc(supabase, payload: dict) -> dict | None:
    result = (
        supabase.rpc(
            "create_stt_consultation_with_snapshot",
            payload,
        )
        .execute()
    )
    return _first_row(result.data)


def _is_missing_stt_rpc_signature_error(exc: Exception) -> bool:
    message = str(exc)
    return (
        "PGRST202" in message
        and "create_stt_consultation_with_snapshot" in message
    )


def _parse_realtime_customer_name(payload: dict) -> CustomerName:
    if not isinstance(payload, dict):
        raise ValueError("첫 메시지는 JSON object 여야 합니다.")
    customer_name = payload.get("customer_name")
    if customer_name not in get_args(CustomerName):
        allowed = ", ".join(get_args(CustomerName))
        raise ValueError(f"customer_name 은 다음 중 하나여야 합니다: {allowed}")
    return customer_name


def _parse_positive_int(value, *, default: int, field_name: str) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} 은 정수여야 합니다.") from exc
    if parsed <= 0:
        raise ValueError(f"{field_name} 은 1 이상이어야 합니다.")
    return parsed


def _parse_realtime_control_message(text_payload: str) -> dict:
    try:
        control = json.loads(text_payload)
    except json.JSONDecodeError as exc:
        raise ValueError("제어 메시지는 JSON 형식이어야 합니다.") from exc
    if not isinstance(control, dict):
        raise ValueError("제어 메시지는 JSON object 여야 합니다.")
    return control


def _normalize_realtime_control_event(control: dict) -> str:
    event = control.get("event")
    if event is None:
        return ""
    return str(event).strip().lower()


async def _send_realtime_json(
    websocket: WebSocket,
    payload: dict,
    send_lock: asyncio.Lock,
) -> None:
    async with send_lock:
        await websocket.send_json(payload)


async def _stream_realtime_transcripts(
    websocket: WebSocket,
    transcript_queue: asyncio.Queue[dict],
    send_lock: asyncio.Lock,
) -> None:
    try:
        while True:
            transcript = await transcript_queue.get()
            await _send_realtime_transcript(websocket, transcript, send_lock)
    except asyncio.CancelledError:
        while not transcript_queue.empty():
            transcript = transcript_queue.get_nowait()
            await _send_realtime_transcript(websocket, transcript, send_lock)
        raise


async def _send_realtime_transcript(
    websocket: WebSocket,
    transcript: dict,
    send_lock: asyncio.Lock,
) -> None:
    await _send_realtime_json(
        websocket,
        {
            "event": "partial_transcript",
            "transcript": transcript,
        },
        send_lock,
    )


async def _stop_realtime_transcript_task(
    transcript_task: asyncio.Task[None] | None,
) -> None:
    if not transcript_task:
        return
    if not transcript_task.done():
        transcript_task.cancel()
    try:
        await transcript_task
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.warning("Realtime STT transcript sender stopped with error: %s", exc)


async def _stop_realtime_transcriber(
    transcriber: RealtimeConversationTranscriber,
) -> None:
    try:
        await run_in_threadpool(transcriber.stop)
    except Exception as cleanup_error:
        logger.warning("Realtime STT websocket cleanup failed: %s", cleanup_error)


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


@router.get("/detail", response_model=ConsultationResponse)
def get_consultation_detail(
    customer_name: CustomerName,
    consultation_id: Annotated[str | None, Query()] = None,
    transcript_title: Annotated[str | None, Query()] = None,
) -> ConsultationResponse:
    if not consultation_id and not transcript_title:
        raise HTTPException(
            status_code=400,
            detail="consultation_id 또는 transcript_title 중 하나가 필요합니다.",
        )

    supabase = get_supabase()
    client = _get_client_by_name(supabase, customer_name)
    if not client:
        raise HTTPException(
            status_code=404,
            detail=f"고객 정보를 찾을 수 없습니다: {customer_name}",
        )

    query = (
        supabase.table("consultation")
        .select(
            "id,client_id,transcript_title,ips_title,"
            "transcript_json,ips_json,created_at"
        )
        .eq("client_id", client["id"])
    )
    if consultation_id:
        query = query.eq("id", consultation_id)
    else:
        query = query.eq("transcript_title", transcript_title)

    result = query.order("created_at", desc=True).limit(1).execute()
    consultation = _first_row(result.data)
    if not consultation:
        raise HTTPException(
            status_code=404,
            detail="상담 내역을 찾을 수 없습니다.",
        )

    return _build_consultation_response(
        consultation=consultation,
        customer_name=customer_name,
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
        .select("id,client_id,transcript_title,ips_title,created_at")
        .eq("client_id", client["id"])
        .order("created_at", desc=True)
        .execute()
    )

    consultations = [
        ConsultationSummaryResponse(
            consultation_id=row["id"],
            customer_id=row["client_id"],
            customer_name=customer_name,
            consultation_date=_consultation_date(row["created_at"]),
            transcript_title=row.get("transcript_title") or "",
            ips_title=row.get("ips_title") or "",
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


def _build_stt_titles(
    *,
    supabase,
    client_id: str,
    customer_name: str,
    now: datetime | None = None,
) -> tuple[str, str]:
    now_kst = (now or datetime.now(KST)).astimezone(KST)
    start_kst = datetime.combine(now_kst.date(), time.min, tzinfo=KST)
    end_kst = start_kst + timedelta(days=1)

    result = (
        supabase.table("consultation")
        .select("id", count="exact")
        .eq("client_id", client_id)
        .gte("created_at", start_kst.astimezone(timezone.utc).isoformat())
        .lt("created_at", end_kst.astimezone(timezone.utc).isoformat())
        .execute()
    )
    existing_count = result.count
    if existing_count is None:
        existing_count = len(result.data or [])

    sequence = existing_count + 1
    title_prefix = f"{now_kst:%y%m%d}_{customer_name}"

    return (
        f"{title_prefix}_상담 스크립트({sequence})",
        f"{title_prefix}_ips({sequence})",
    )


def _first_row(rows: list[dict] | None) -> dict | None:
    if not rows:
        return None
    return rows[0]


def _build_consultation_response(
    *,
    consultation: dict,
    customer_name: CustomerName,
) -> ConsultationResponse:
    return ConsultationResponse(
        consultation_id=consultation["id"],
        customer_id=consultation["client_id"],
        customer_name=customer_name,
        consultation_date=_consultation_date(consultation["created_at"]),
        transcript_title=consultation.get("transcript_title") or "",
        ips_title=consultation.get("ips_title") or "",
        transcript_json=consultation.get("transcript_json") or [],
        ips_json=consultation.get("ips_json") or {},
        ips_snapshot_id=None,
        created_at=_to_kst_iso(consultation["created_at"]),
    )


def _consultation_date(created_at: str) -> str:
    return _parse_datetime(created_at).astimezone(KST).date().isoformat()


def _to_kst_iso(created_at: str) -> str:
    return _parse_datetime(created_at).astimezone(KST).isoformat()


def _parse_datetime(datetime_text: str) -> datetime:
    normalized = _normalize_datetime_text(datetime_text)
    created_datetime = datetime.fromisoformat(normalized)
    if created_datetime.tzinfo is None:
        created_datetime = created_datetime.replace(tzinfo=timezone.utc)

    return created_datetime


def _normalize_datetime_text(datetime_text: str) -> str:
    normalized = str(datetime_text).strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"

    match = re.match(
        r"^(?P<head>.+?\.)(?P<fraction>\d+)(?P<tail>(?:[+-]\d{2}:?\d{2})?)$",
        normalized,
    )
    if match:
        fraction = f"{match.group('fraction')}000000"[:6]
        normalized = f"{match.group('head')}{fraction}{match.group('tail')}"

    offset_match = re.match(r"^(?P<head>.+)(?P<offset>[+-]\d{2})(?P<minute>\d{2})$", normalized)
    if offset_match:
        normalized = (
            f"{offset_match.group('head')}"
            f"{offset_match.group('offset')}:{offset_match.group('minute')}"
        )

    return normalized
