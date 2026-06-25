"""clients 라우터 — PB 인증 기반 고객 관리.

- POST /clients : 신규 고객 등록 (인증된 PB 에 자동 배정)
- GET  /clients : 본인 담당 고객 목록 조회 (타 PB 고객 노출 방지)

고객 SSOT 는 DB(client 테이블)다. STT 는 프론트가 넘긴 client_id(DB client.id)를
검증해 상담을 저장한다. 고객명은 표시값일 뿐 조회 키로 쓰지 않는다. 동명이인은
허용하며, 고유성은 PK(id uuid)가 보장한다.

운용자산(AUM)은 client 테이블에 전용 컬럼이 없어 meta.aum_eokwon(억원)으로 저장한다.
Supabase 호출이 블로킹이라 핸들러는 동기 def 로 둔다(rag.py·tax.py 와 동일).
"""

import logging
import math
from datetime import datetime, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.core.auth import get_current_pb_id
from app.db.supabase import get_supabase
from app.services.ips import build_ips_snapshot_payload

router = APIRouter(prefix="/clients", tags=["clients"])
logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")

MAX_NAME_LEN = 50
MAX_AUM_EOKWON = 100_000  # 비현실적 입력 방지 상한(억원).

# 신규 고객의 "미상담 기본 IPS" — 고정 상수 1세트(준호님 확정).
# 고객 생성마다 LLM 호출/난수로 흔들지 않는다(재현성·비용 — 절세규칙·상품매핑과 같은
# 하드코딩 규칙표 패턴). Asset 만 고객이 입력한 운용자산(억원)으로 채우고, 나머지는
# 보수적 중립값. 기존 페르소나 3명의 사전조사 IPS 값 범위를 참고했다(Return 3~25 →
# 중립 5, Risk 안정/균형/공격 → 균형형, Time → 10년, Liquidity → 중간).
# 추후 STT 상담이 들어오면 source_type='consultation' 스냅샷이 "별도로" 쌓이며,
# 이 initial 스냅샷을 덮어쓰지 않는다(기존 구조 유지).
DEFAULT_IPS_TEMPLATE: dict = {
    "Goal": "안정적 자산 운용 및 장기 수익 추구",
    "Return": 5,  # 중립적 목표 수익률(%)
    "Risk": "균형형",
    "Time": 10,  # 중장기 기본(년)
    "Tax": "금융소득종합과세 대비",
    "Liquidity": "중간",
    "Legal": "특이사항 없음",
    "Unique": "사전 상담 전 기본 프로파일",
}


def _default_ips_raw(aum_eokwon: float) -> dict:
    """고정 디폴트 IPS + 고객이 입력한 운용자산(Asset, 억원). 결정적(난수·시각 없음)."""
    return {**DEFAULT_IPS_TEMPLATE, "Asset": aum_eokwon}


class ClientCreateRequest(BaseModel):
    name: str
    aum_eokwon: float = Field(ge=0)  # 운용자산(억원). meta.aum_eokwon 으로 저장.

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("고객명은 비어 있을 수 없습니다.")
        if len(stripped) > MAX_NAME_LEN:
            raise ValueError(f"고객명은 {MAX_NAME_LEN}자 이내여야 합니다.")
        return stripped

    @field_validator("aum_eokwon")
    @classmethod
    def _validate_aum(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("운용자산은 유효한 숫자여야 합니다.")
        if value > MAX_AUM_EOKWON:
            raise ValueError(f"운용자산은 {MAX_AUM_EOKWON}억원 이내여야 합니다.")
        return value


class ClientCreateResponse(BaseModel):
    client_id: str
    name: str
    aum_eokwon: float
    ips_snapshot_id: str  # 함께 생성된 디폴트 initial IPS 스냅샷(추적용)
    created_at: str


class ClientListItem(BaseModel):
    client_id: str
    name: str
    aum_eokwon: float | None
    is_persona: bool
    created_at: str


class ClientListResponse(BaseModel):
    pb_id: str
    clients: list[ClientListItem]


class DashboardSnapshotSaveRequest(BaseModel):
    """상담 중 발생한 분석 결과 저장 요청.

    같은 consultation_id로 여러 번 호출해도 첫 번째 분석만 저장한다.
    """

    consultation_id: str = Field(..., min_length=1)
    calculation_session_id: str = Field(..., min_length=1)
    dashboard_result: dict[str, Any] = Field(
        ...,
        description="POST /portfolio/calculate 응답 전체",
    )
    stress_test_result: dict[str, Any] = Field(
        default_factory=dict,
        description="첫 분석 시점의 스트레스 테스트 결과. 없으면 빈 객체",
    )


class DashboardSnapshotResponse(BaseModel):
    saved: bool
    client_id: str
    consultation_id: str
    calculation_session_id: str
    dashboard_result: dict[str, Any]
    stress_test_result: dict[str, Any] = Field(default_factory=dict)
    saved_at: str
    message: str


# 기존 ips_snapshot.raw_ips_json 안에 넣는 내부 예약 키.
# IPS 파서는 Goal/Asset/Return/... 9개 키만 추려 쓰므로 계산 입력에는 영향을 주지 않는다.
FIRST_DASHBOARD_SNAPSHOT_KEY = "__first_dashboard_snapshot_v1"


def _validate_uuid(value: str, field_label: str) -> None:
    try:
        UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=400,
            detail=f"올바르지 않은 {field_label} 형식입니다.",
        ) from None


def _validate_client_id(client_id: str) -> None:
    _validate_uuid(client_id, "고객 ID")


def _get_owned_client_with_meta(
    supabase,
    client_id: str,
    pb_id: str,
) -> dict | None:
    result = (
        supabase.table("client")
        .select("id,meta")
        .eq("id", client_id)
        .eq("pb_id", pb_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def _get_consultation_ips_snapshot(
    supabase,
    client_id: str,
    consultation_id: str,
) -> dict | None:
    """해당 고객·상담의 consultation IPS 스냅샷 1행을 조회한다."""
    result = (
        supabase.table("ips_snapshot")
        .select("id,client_id,consultation_id,raw_ips_json,created_at")
        .eq("client_id", client_id)
        .eq("consultation_id", consultation_id)
        .eq("source_type", "consultation")
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def _validate_embedded_ids(
    payload: dict[str, Any],
    *,
    payload_name: str,
    client_id: str,
    consultation_id: str,
    calculation_session_id: str,
) -> None:
    """응답 객체 안에 식별자가 들어 있다면 바깥 요청 식별자와 일치해야 한다."""
    expected_ids = {
        "client_id": client_id,
        "consultation_id": consultation_id,
        "calculation_session_id": calculation_session_id,
    }
    for key, expected in expected_ids.items():
        actual = payload.get(key)
        if actual is not None and str(actual) != expected:
            raise HTTPException(
                status_code=400,
                detail=f"{payload_name}.{key}와 요청의 {key}가 일치하지 않습니다.",
            )


def _pick_first_dashboard_snapshot(
    rows: list[dict[str, Any]] | None,
    *,
    consultation_id: str | None,
    current_consultation_id: str | None,
) -> dict[str, Any] | None:
    """ips_snapshot 행들(created_at 내림차순)에서 첫 분석 스냅샷을 고른다.

    - consultation_id 지정: 그 회차의 스냅샷만 인정한다('지난 상담 불러오기'에서
      선택한 회차의 대시보드를 복원하기 위함).
    - 미지정: 현재 진행 중인 회차(current_consultation_id)는 제외하고 가장 최근 것.
    스냅샷이 없으면 None.
    """
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        row_consultation_id = str(row.get("consultation_id") or "")
        if consultation_id is not None:
            # 특정 회차 조회: 그 회차만 본다. current 제외 규칙보다 우선한다
            # (명시적으로 그 회차를 요청한 것이므로).
            if row_consultation_id != consultation_id:
                continue
        elif (
            current_consultation_id is not None
            and row_consultation_id == current_consultation_id
        ):
            # 최신 조회: 현재 진행 중인 회차는 제외한다.
            continue

        raw_ips_json = (
            row.get("raw_ips_json")
            if isinstance(row.get("raw_ips_json"), dict)
            else {}
        )
        snapshot = raw_ips_json.get(FIRST_DASHBOARD_SNAPSHOT_KEY)
        if isinstance(snapshot, dict):
            return snapshot
    return None


def _response_from_stored_snapshot(
    snapshot: dict[str, Any],
    *,
    saved: bool,
    message: str,
) -> DashboardSnapshotResponse:
    try:
        return DashboardSnapshotResponse(
            **{
                **snapshot,
                "saved": saved,
                "message": message,
            }
        )
    except Exception as exc:
        logger.exception("invalid stored first dashboard snapshot")
        raise HTTPException(
            status_code=500,
            detail="저장된 상담 첫 분석 결과 형식이 올바르지 않습니다.",
        ) from exc


@router.post(
    "/{client_id}/dashboard-snapshot",
    response_model=DashboardSnapshotResponse,
)
def save_client_dashboard_snapshot(
    client_id: str,
    request: DashboardSnapshotSaveRequest,
    pb_id: str = Depends(get_current_pb_id),
) -> DashboardSnapshotResponse:
    """상담별 첫 분석(1-1, 2-1, 3-1...)만 저장한다.

    같은 consultation_id로 1-2, 1-3처럼 다시 호출되면 기존 1-1을 반환하고
    DB 값은 덮어쓰지 않는다.
    """
    _validate_client_id(client_id)
    _validate_uuid(request.consultation_id, "상담 ID")
    _validate_uuid(request.calculation_session_id, "계산 세션 ID")

    if not request.dashboard_result:
        raise HTTPException(
            status_code=422,
            detail="dashboard_result는 비어 있을 수 없습니다.",
        )

    _validate_embedded_ids(
        request.dashboard_result,
        payload_name="dashboard_result",
        client_id=client_id,
        consultation_id=request.consultation_id,
        calculation_session_id=request.calculation_session_id,
    )
    _validate_embedded_ids(
        request.stress_test_result,
        payload_name="stress_test_result",
        client_id=client_id,
        consultation_id=request.consultation_id,
        calculation_session_id=request.calculation_session_id,
    )

    supabase = get_supabase()

    try:
        client = _get_owned_client_with_meta(supabase, client_id, pb_id)
    except Exception as exc:
        logger.exception("client dashboard owner lookup failed")
        raise HTTPException(
            status_code=500,
            detail="고객 정보 조회 중 오류가 발생했습니다.",
        ) from exc

    if not client:
        raise HTTPException(
            status_code=404,
            detail="담당 고객을 찾을 수 없습니다.",
        )

    try:
        ips_snapshot = _get_consultation_ips_snapshot(
            supabase,
            client_id,
            request.consultation_id,
        )
    except Exception as exc:
        logger.exception("consultation ips snapshot lookup failed")
        raise HTTPException(
            status_code=500,
            detail="상담 정보 조회 중 오류가 발생했습니다.",
        ) from exc

    if not ips_snapshot:
        raise HTTPException(
            status_code=404,
            detail=(
                "해당 고객의 상담 IPS 스냅샷을 찾을 수 없습니다. "
                "실제 consultations API가 반환한 consultation_id를 사용해야 합니다."
            ),
        )

    raw_ips_json = (
        ips_snapshot.get("raw_ips_json")
        if isinstance(ips_snapshot.get("raw_ips_json"), dict)
        else {}
    )
    existing_snapshot = raw_ips_json.get(FIRST_DASHBOARD_SNAPSHOT_KEY)

    # first-write-wins: 동일 상담의 두 번째 이후 분석은 절대 덮어쓰지 않는다.
    if isinstance(existing_snapshot, dict):
        return _response_from_stored_snapshot(
            existing_snapshot,
            saved=False,
            message=(
                "이 상담의 첫 분석 결과가 이미 저장되어 있어 "
                "후속 분석 결과로 덮어쓰지 않았습니다."
            ),
        )

    saved_at = datetime.now(KST).isoformat(timespec="seconds")
    snapshot = {
        "saved": True,
        "client_id": client_id,
        "consultation_id": request.consultation_id,
        "calculation_session_id": request.calculation_session_id,
        "dashboard_result": request.dashboard_result,
        "stress_test_result": request.stress_test_result,
        "saved_at": saved_at,
        "message": "이 상담의 첫 분석 결과가 저장되었습니다.",
    }

    updated_raw_ips_json = {
        **raw_ips_json,
        FIRST_DASHBOARD_SNAPSHOT_KEY: snapshot,
    }

    try:
        result = (
            supabase.table("ips_snapshot")
            .update({"raw_ips_json": updated_raw_ips_json})
            .eq("id", ips_snapshot["id"])
            .eq("client_id", client_id)
            .eq("consultation_id", request.consultation_id)
            .execute()
        )
    except Exception as exc:
        logger.exception("first dashboard snapshot update failed")
        raise HTTPException(
            status_code=500,
            detail="상담 첫 분석 결과 저장 중 오류가 발생했습니다.",
        ) from exc

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="저장 대상 상담 IPS 스냅샷을 찾을 수 없습니다.",
        )

    return DashboardSnapshotResponse(**snapshot)


@router.get(
    "/{client_id}/previous-dashboard",
    response_model=DashboardSnapshotResponse,
)
def get_client_previous_dashboard(
    client_id: str,
    current_consultation_id: str | None = None,
    consultation_id: str | None = None,
    pb_id: str = Depends(get_current_pb_id),
) -> DashboardSnapshotResponse:
    """상담의 첫 분석 결과(대시보드 스냅샷)를 반환한다.

    - consultation_id 지정: 그 상담의 스냅샷을 반환한다('지난 상담 불러오기'에서
      선택한 회차의 대시보드를 그대로 복원하기 위함). 없으면 404.
    - consultation_id 미지정: 가장 최근에 저장된 첫 분석을 반환한다(고객 선택 직후
      자동 복원용). current_consultation_id를 넘기면 그 회차는 제외한다.
    """
    _validate_client_id(client_id)
    if current_consultation_id is not None:
        _validate_uuid(current_consultation_id, "현재 상담 ID")
    if consultation_id is not None:
        _validate_uuid(consultation_id, "상담 ID")

    supabase = get_supabase()

    try:
        client = _get_owned_client_with_meta(supabase, client_id, pb_id)
    except Exception as exc:
        logger.exception("client previous dashboard owner lookup failed")
        raise HTTPException(
            status_code=500,
            detail="고객 정보 조회 중 오류가 발생했습니다.",
        ) from exc

    if not client:
        raise HTTPException(
            status_code=404,
            detail="담당 고객을 찾을 수 없습니다.",
        )

    try:
        result = (
            supabase.table("ips_snapshot")
            .select("consultation_id,raw_ips_json,created_at")
            .eq("client_id", client_id)
            .eq("source_type", "consultation")
            .order("created_at", desc=True)
            .execute()
        )
    except Exception as exc:
        logger.exception("previous first dashboard lookup failed")
        raise HTTPException(
            status_code=500,
            detail="이전 상담 첫 분석 결과 조회 중 오류가 발생했습니다.",
        ) from exc

    snapshot = _pick_first_dashboard_snapshot(
        result.data,
        consultation_id=consultation_id,
        current_consultation_id=current_consultation_id,
    )
    if snapshot is not None:
        return _response_from_stored_snapshot(
            snapshot,
            saved=True,
            message=(
                "선택한 상담의 첫 분석 결과입니다."
                if consultation_id is not None
                else "가장 최근 이전 상담의 첫 분석 결과입니다."
            ),
        )

    # PR #126 방식으로 이미 저장된 데이터가 있다면 한시적으로 읽기 호환한다.
    meta = client.get("meta") if isinstance(client.get("meta"), dict) else {}
    legacy_snapshot = meta.get("previous_dashboard")
    if isinstance(legacy_snapshot, dict):
        legacy_consultation_id = str(legacy_snapshot.get("consultation_id") or "")
        if consultation_id is not None:
            # 특정 회차 조회 시에는 그 회차의 legacy 스냅샷만 인정한다.
            legacy_matches = legacy_consultation_id == consultation_id
        else:
            legacy_matches = (
                current_consultation_id is None
                or legacy_consultation_id != current_consultation_id
            )
        if legacy_matches:
            return _response_from_stored_snapshot(
                legacy_snapshot,
                saved=True,
                message="기존 방식으로 저장된 상담 결과입니다.",
            )

    raise HTTPException(
        status_code=404,
        detail="이 고객의 저장된 이전 상담 첫 분석 결과가 없습니다.",
    )


@router.get("", response_model=ClientListResponse)
def list_clients(pb_id: str = Depends(get_current_pb_id)) -> ClientListResponse:
    """인증된 PB 의 담당 고객 목록을 반환한다. 타 PB 고객은 포함되지 않는다."""
    supabase = get_supabase()
    try:
        rows = _list_clients_for_pb(supabase, pb_id)
    except Exception as exc:
        logger.exception("client list failed")
        raise HTTPException(
            status_code=500,
            detail="고객 목록 조회 중 오류가 발생했습니다.",
        ) from exc
    items = [_to_list_item(r) for r in rows]
    return ClientListResponse(pb_id=pb_id, clients=items)


def _list_clients_for_pb(supabase, pb_id: str) -> list[dict]:
    """pb_id 로 필터링한 고객 목록 반환. 백엔드 2차 방어선."""
    result = (
        supabase.table("client")
        .select("id,name,meta,created_at")
        .eq("pb_id", pb_id)
        .order("created_at", desc=False)
        .execute()
    )
    return result.data or []


def _to_list_item(row: dict) -> ClientListItem:
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    raw_aum = (meta or {}).get("aum_eokwon")
    try:
        aum_eokwon: float | None = float(raw_aum) if raw_aum is not None else None
    except (TypeError, ValueError):
        aum_eokwon = None

    created_at_raw = row.get("created_at")
    created_at = _to_kst_iso(created_at_raw) if created_at_raw else ""

    return ClientListItem(
        client_id=row.get("id") or "",
        name=row.get("name") or "Unknown",
        aum_eokwon=aum_eokwon,
        is_persona=bool((meta or {}).get("persona", False)),
        created_at=created_at,
    )


@router.post("", response_model=ClientCreateResponse, status_code=status.HTTP_201_CREATED)
def create_client(
    request: ClientCreateRequest,
    pb_id: str = Depends(get_current_pb_id),
) -> ClientCreateResponse:
    supabase = get_supabase()

    try:
        result = (
            supabase.table("client")
            .insert(
                {
                    "name": request.name,
                    # AUM 전용 컬럼이 없어 meta 에 보관. persona=False 로 페르소나 3명과 구분.
                    "meta": {"aum_eokwon": request.aum_eokwon, "persona": False},
                    # 인증된 PB 에 자동 배정 (RLS 1차 방어선 + 백엔드 2차 방어선).
                    "pb_id": pb_id,
                }
            )
            .execute()
        )
        created = result.data[0] if result.data else None
    except Exception as exc:
        logger.exception("client insert failed")
        raise HTTPException(
            status_code=500,
            detail="고객 저장 중 오류가 발생했습니다.",
        ) from exc

    if not created:
        raise HTTPException(status_code=500, detail="고객 저장 중 오류가 발생했습니다.")

    # 신규 고객은 사전조사 IPS 가 없으므로 디폴트 initial 스냅샷을 함께 저장한다
    # (consultation_id=NULL — CHECK 제약상 initial 은 NULL 이어야 함).
    # supabase-py(REST)는 다중문 트랜잭션이 어려워, 스냅샷 insert 실패 시 방금 만든
    # client 를 보상 삭제(compensating rollback)해 고아 client 가 남지 않게 한다.
    snapshot_payload = build_ips_snapshot_payload(
        client_id=created["id"],
        consultation_id=None,
        source_type="initial",
        raw_ips_json=_default_ips_raw(request.aum_eokwon),
    )
    try:
        snapshot_result = (
            supabase.table("ips_snapshot").insert(snapshot_payload).execute()
        )
        snapshot = snapshot_result.data[0] if snapshot_result.data else None
    except Exception as exc:
        logger.exception("default ips_snapshot insert failed — rolling back client")
        _rollback_client(supabase, created["id"])
        raise HTTPException(
            status_code=500,
            detail="고객 IPS 저장 중 오류가 발생했습니다.",
        ) from exc

    if not snapshot:
        _rollback_client(supabase, created["id"])
        raise HTTPException(
            status_code=500,
            detail="고객 IPS 저장 중 오류가 발생했습니다.",
        )

    return ClientCreateResponse(
        client_id=created["id"],
        name=created["name"],
        aum_eokwon=request.aum_eokwon,
        ips_snapshot_id=snapshot["id"],
        created_at=_to_kst_iso(created["created_at"]),
    )


def _rollback_client(supabase, client_id: str) -> None:
    """스냅샷 저장 실패 시 방금 만든 client 보상 삭제. 삭제까지 실패하면 로그만 남긴다."""
    try:
        supabase.table("client").delete().eq("id", client_id).execute()
    except Exception:
        logger.exception("client rollback delete failed (client_id=%s)", client_id)


def _to_kst_iso(created_at: str) -> str:
    normalized = created_at.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(KST).isoformat()
