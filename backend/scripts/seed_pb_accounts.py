"""데모용 PB 계정 시드 스크립트.

Supabase Admin API 로 PB 계정 3개를 생성하고,
기존 데모 고객(페르소나 3명: 김성삼·이사조·박기업)을 PB001 에 배정한다.

실행 (backend/ 디렉터리에서):
    python scripts/seed_pb_accounts.py

필요 환경변수 (backend/.env):
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY  — Admin API 는 service_role 필요
"""

import sys  # noqa: E402
from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.db.supabase import get_supabase  # noqa: E402

# 데모용 PB 계정 3개. 비번은 데모 환경 전용이며 절대 운영계에 쓰지 않는다.
DEMO_PBS = [
    {"email": "pb1@samsung-sec.demo", "password": "PBDemo1234!", "name": "이준호 PB", "pb_code": "PB001"},  # noqa: E501
    {"email": "pb2@samsung-sec.demo", "password": "PBDemo1234!", "name": "김다경 PB", "pb_code": "PB002"},  # noqa: E501
    {"email": "pb3@samsung-sec.demo", "password": "PBDemo1234!", "name": "박지은 PB", "pb_code": "PB003"},  # noqa: E501
]


def _get_or_create_auth_user(supabase, email: str, password: str) -> str | None:
    """Supabase Admin API 로 사용자를 생성하거나, 이미 존재하면 조회해 UUID 반환."""
    try:
        result = supabase.auth.admin.create_user(
            {
                "email": email,
                "password": password,
                "email_confirm": True,  # 이메일 확인 건너뜀 (데모용)
            }
        )
        return str(result.user.id)
    except Exception as create_err:
        err_str = str(create_err)
        already_exists = (
            "already been registered" in err_str
            or "already exists" in err_str
            or "duplicate" in err_str.lower()
        )
        if already_exists:
            # 이미 존재하면 list_users 로 찾기
            try:
                page = supabase.auth.admin.list_users()
                users = page if isinstance(page, list) else getattr(page, "users", [])
                user = next((u for u in users if u.email == email), None)
                if user:
                    return str(user.id)
            except Exception as list_err:
                print(f"  list_users 실패: {list_err}")
            return None
        print(f"  create_user 실패: {create_err}")
        return None


def seed() -> None:
    supabase = get_supabase()
    pb_uuids: dict[str, str] = {}  # pb_code → uuid

    print("=== PB 계정 생성 ===")
    for pb in DEMO_PBS:
        print(f"\n[{pb['pb_code']}] {pb['email']} ...")
        user_id = _get_or_create_auth_user(supabase, pb["email"], pb["password"])
        if not user_id:
            print("  SKIP — auth user 생성/조회 실패")
            continue
        print(f"  auth.users id: {user_id}")

        try:
            supabase.table("pb_profile").upsert(
                {"id": user_id, "name": pb["name"], "pb_code": pb["pb_code"]},
                on_conflict="id",
            ).execute()
            print(f"  pb_profile upserted: {pb['name']}")
        except Exception as e:
            print(f"  pb_profile upsert 실패: {e}")

        pb_uuids[pb["pb_code"]] = user_id

    # 기존 데모 고객(페르소나) 3명을 PB001 에 배정
    pb1_id = pb_uuids.get("PB001")
    if pb1_id:
        print(f"\n=== 기존 데모 고객 → PB001 ({pb1_id}) 배정 ===")
        try:
            result = (
                supabase.table("client")
                .select("id,name,meta,pb_id")
                .execute()
            )
            persona_clients = [
                r for r in result.data
                if (r.get("meta") or {}).get("persona") is True and not r.get("pb_id")
            ]
            for client in persona_clients:
                supabase.table("client").update({"pb_id": pb1_id}).eq("id", client["id"]).execute()
                print(f"  {client['name']} ({client['id'][:8]}...) → PB001")
            print(f"  총 {len(persona_clients)}명 배정 완료")
        except Exception as e:
            print(f"  배정 실패: {e}")
    else:
        print("\nPB001 UUID 없음 — 데모 고객 배정 건너뜀")

    print("\n" + "=" * 48)
    print("시드 완료! 아래 계정으로 데모 로그인 가능합니다:")
    print("=" * 48)
    for pb in DEMO_PBS:
        print(f"  [{pb['pb_code']}] {pb['name']}")
        print(f"       이메일 : {pb['email']}")
        # 비밀번호는 평문 로깅을 피한다(CodeQL: clear-text logging). 데모 비밀번호는
        # 이 스크립트 상단 DEMO_PBS 상수에서 직접 확인한다.
        print("       비밀번호: (DEMO_PBS 상수 참조)")
    print("=" * 48)


if __name__ == "__main__":
    seed()
