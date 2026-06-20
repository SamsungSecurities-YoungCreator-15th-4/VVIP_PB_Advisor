"""DART 회사명→corp_code 매핑 적재 스크립트 — corpCode.xml 을 dart_corp_code 에 캐싱.

DART 재무 조회(향후 /dart/insight)의 1단계. 사용자 질의에서 뽑은 회사명을
DART 고유번호(corp_code)로 바꾸기 위한 식별자 매핑을 Supabase 에 적재한다.
시세가 아니라 식별자 캐싱이라 RAG 임베딩 금지 원칙과 무관하다.

이 스크립트는 로컬에서 일회성으로 실행한다(ingest_documents.py 와 같은 운영 패턴).
corpCode.xml 전체(약 10만 건)는 메모리 부담이 있어 Render 런타임에서 적재하지
않는다 — 런타임은 dart_corp_code 조회만 한다.

처리 흐름
  1) DART corpCode.xml 다운로드 (zip 바이너리)
  2) zip 해제 → CORPCODE.xml 단일 파일
  3) xml.etree 로 파싱
  4) stock_code 가 있는 상장사만 필터 (비상장 ~9만 건은 재무 조회 대상 아님)
  5) corp_name_normalized 계산 (app.services.dart_corp.normalize_corp_name)
  6) supabase-py .upsert(on_conflict="corp_code") 로 배치 적재

실행법
  cd backend && source .venv/bin/activate
  python scripts/ingest_corp_code.py --dry-run     # 다운로드·파싱·필터만(DB 미적재)
  python scripts/ingest_corp_code.py               # 상장사 전체 적재

요구 환경변수(backend/.env): DART_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
  · DART_API_KEY 는 https://opendart.fss.or.kr 에서 발급(.env.example 참고).
  · 키는 코드·로그·출력 어디에도 노출하지 않는다(요청 URL 도 출력 금지).
"""

import argparse
import io
import os
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.supabase import get_supabase  # noqa: E402
from app.services.dart_corp import normalize_corp_name  # noqa: E402

# DART corpCode API. 키는 환경변수에서만 읽고 URL 을 출력하지 않는다(키 노출 방지).
DART_CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"

# 다운로드 타임아웃(초). corpCode.xml zip 은 수 MB라 넉넉히 둔다.
DOWNLOAD_TIMEOUT = 60.0

# supabase upsert 배치 크기. 상장사는 수천 건 규모라 한 번에 다 보내도 되지만,
# 요청 본문이 과도하게 커지지 않게 적당히 나눈다(ingest_documents.py 의 배치 패턴 준용).
UPSERT_BATCH_SIZE = 500


def fetch_corp_code_xml(api_key: str) -> bytes:
    """DART corpCode.xml(zip)을 받아 내부 CORPCODE.xml 바이트를 반환한다.

    인증 실패 등에서는 zip 이 아니라 에러 XML(<result><status><message>)이 오므로,
    BadZipFile 이면 그 본문을 파싱해 status·message 만 표면화한다(키는 노출 안 함).
    """
    try:
        resp = httpx.get(
            DART_CORP_CODE_URL,
            params={"crtfc_key": api_key},
            timeout=DOWNLOAD_TIMEOUT,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        # 예외 메시지에 요청 URL(키 포함)이 섞일 수 있어 타입만 표면화한다.
        raise SystemExit(f"DART corpCode 다운로드 실패: {type(exc).__name__}")

    body = resp.content
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            names = zf.namelist()
            if not names:
                raise SystemExit("corpCode zip 이 비어 있습니다.")
            # zip 안에는 CORPCODE.xml 단일 파일이 들어온다.
            return zf.read(names[0])
    except zipfile.BadZipFile:
        # zip 이 아니면 DART 에러 응답(XML). status/message 만 뽑아 안내한다.
        status = message = None
        try:
            root = ET.fromstring(body)
            status = (root.findtext("status") or "").strip()
            message = (root.findtext("message") or "").strip()
        except ET.ParseError:
            # 에러 본문 파싱은 보조 정보(status/message) 추출용이다.
            # 파싱에 실패해도 아래에서 일반 오류 메시지로 안전하게 폴백한다.
            pass
        detail = f"status={status}, message={message}" if status else "응답이 zip 이 아님"
        raise SystemExit(f"DART corpCode 응답 오류({detail}). DART_API_KEY 를 확인하세요.")


def parse_listed_rows(xml_bytes: bytes) -> list[dict]:
    """CORPCODE.xml 에서 상장사(stock_code 존재) 행만 dart_corp_code 레코드로 만든다."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        # 다운로드 손상·예기치 못한 형식이면 트레이스백 대신 친절히 종료한다.
        raise SystemExit(f"CORPCODE.xml 파싱 실패(올바르지 않은 XML 형식): {exc}")
    rows: list[dict] = []
    # corpCode.xml 은 <result> 바로 아래 <list> 가 평면으로 나열된 구조라, 트리 전체를
    # 재귀 탐색하는 iter() 대신 직계 자식만 도는 iterfind() 가 효율적이다(대용량 대응).
    for item in root.iterfind("list"):
        corp_code = (item.findtext("corp_code") or "").strip()
        corp_name = (item.findtext("corp_name") or "").strip()
        stock_code = (item.findtext("stock_code") or "").strip()
        modify_date = (item.findtext("modify_date") or "").strip()

        # 비상장사는 stock_code 가 빈 값(또는 공백)이라 건너뛴다(재무 조회 대상 아님).
        if not stock_code:
            continue
        # corp_code/corp_name 결손 행은 적재 대상에서 제외(PK·NOT NULL 보호).
        if not corp_code or not corp_name:
            continue

        rows.append(
            {
                "corp_code": corp_code,
                "corp_name": corp_name,
                "corp_name_normalized": normalize_corp_name(corp_name),
                "stock_code": stock_code,
                "modify_date": modify_date or None,
            }
        )
    return rows


def summarize_collisions(rows: list[dict]) -> dict[str, list[str]]:
    """정규화명이 겹치는 그룹을 {정규화명: [원본 corp_name, ...]} 으로 반환한다.

    서로 다른 회사가 같은 corp_name_normalized 로 뭉치면(예: "한국전력공사" vs
    "한국전력(주)") 조회 시 .eq(corp_name_normalized) 가 여러 행을 돌려줘 "어느
    회사 재무냐"가 모호해진다. 적재 없이 파싱 데이터만으로 미리 알 수 있어, 2단계
    조회 설계(종목코드 보조 구분 필요 여부)의 입력으로 dry-run 에서 출력한다.
    """
    groups: dict[str, list[str]] = {}
    for row in rows:
        groups.setdefault(row["corp_name_normalized"], []).append(row["corp_name"])
    return {name: names for name, names in groups.items() if len(names) > 1}


def print_collision_summary(rows: list[dict]) -> None:
    """정규화명 충돌 요약을 출력한다(상위 5종 예시 포함). DB 접근 없음."""
    dups = summarize_collisions(rows)
    if not dups:
        print("[충돌] 정규화명 중복 0종 — 정규화 매칭 안전")
        return
    total = sum(len(names) for names in dups.values())
    print(
        f"[충돌] 정규화명 중복 {len(dups)}종 / {total}건 — 조회 모호성 주의"
        " (2단계에서 종목코드 보조 구분 필요)"
    )
    for name, names in sorted(dups.items(), key=lambda kv: -len(kv[1]))[:5]:
        print(f"  · '{name}' ×{len(names)}: {names}")


def upsert_rows(rows: list[dict]) -> None:
    """dart_corp_code 에 corp_code 기준으로 배치 upsert 한다(재실행 시 갱신)."""
    supabase = get_supabase()
    for start in range(0, len(rows), UPSERT_BATCH_SIZE):
        batch = rows[start : start + UPSERT_BATCH_SIZE]
        supabase.table("dart_corp_code").upsert(
            batch, on_conflict="corp_code"
        ).execute()
        print(f"  · {start + len(batch)}/{len(rows)} 적재")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DART corpCode.xml → dart_corp_code(상장사) 적재"
    )
    parser.add_argument(
        "--limit", type=int, help="앞에서부터 N개만 적재(소량 검증용)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB 미적재 — 다운로드·파싱·필터만 하고 상장사 건수·샘플만 출력",
    )
    args = parser.parse_args()

    api_key = os.getenv("DART_API_KEY")
    if not api_key:
        raise SystemExit(
            "DART_API_KEY 환경변수가 설정되지 않았습니다. "
            "backend/.env 에 추가하세요 (.env.example 참고)."
        )

    # 실제 적재 모드면 무거운(쿼터 소모) DART 다운로드 전에 Supabase 환경변수를 먼저
    # 검증한다. 누락 시 다운로드·파싱 다 한 뒤 upsert 단계에서야 실패하면 쿼터 낭비다.
    if not args.dry_run and (
        not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    ):
        raise SystemExit(
            "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 환경변수가 설정되지 않았습니다. "
            "backend/.env 를 확인하세요 (.env.example 참고)."
        )

    print("[DART] corpCode.xml 다운로드 중…")
    xml_bytes = fetch_corp_code_xml(api_key)
    rows = parse_listed_rows(xml_bytes)
    print(f"[파싱] 상장사(stock_code 존재) {len(rows)}건 추출")

    if args.limit is not None:
        rows = rows[: args.limit]
        print(f"[limit] 앞 {len(rows)}건만 처리")

    if not rows:
        raise SystemExit("적재 대상 상장사가 없습니다.")

    # 충돌 요약은 적재 없이도 산출 가능하므로 항상 먼저 출력한다(2단계 설계 입력).
    print_collision_summary(rows)

    if args.dry_run:
        print("[DRY-RUN] DB 미적재. 샘플 3건:")
        for row in rows[:3]:
            print(
                f"  · {row['corp_name']} → 정규화 '{row['corp_name_normalized']}' "
                f"(stock_code={row['stock_code']}, corp_code={row['corp_code']})"
            )
        return

    print(f"[적재] dart_corp_code upsert 시작 (배치 {UPSERT_BATCH_SIZE})")
    upsert_rows(rows)
    print(f"\n완료: 상장사 {len(rows)}건 적재")


if __name__ == "__main__":
    main()
