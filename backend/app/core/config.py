import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[2]
STT_DIR = BACKEND_DIR / "app" / "stt"
STT_AUDIO_DIR = STT_DIR / "audio"

load_dotenv(BACKEND_DIR / ".env")
load_dotenv(STT_DIR / ".env")


class Settings:
    def __init__(self) -> None:
        self.supabase_url = os.getenv("SUPABASE_URL", "")
        self.supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        # JWT 로컬 검증용 시크릿(HS256 레거시) — Supabase Dashboard → Settings → API → JWT Secret
        self.supabase_jwt_secret = os.getenv("SUPABASE_JWT_SECRET", "")
        # 비대칭(ES256) 서명키 전환 후 공개키 출처 — Supabase JWKS 엔드포인트.
        # 미설정 시 SUPABASE_URL 에서 표준 경로로 유도한다.
        self.supabase_jwks_url = os.getenv("SUPABASE_JWKS_URL", "") or (
            f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
            if self.supabase_url
            else ""
        )
        self.allowed_origins_raw = os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        )
        # Vercel 프리뷰 URL은 배포마다 바뀌어(vvip-pb-advisor-<hash>-...vercel.app)
        # 고정 목록(ALLOWED_ORIGINS)으로는 매번 CORS 프리플라이트가 400으로 막힌다.
        # 이 프로젝트의 vercel.app 배포(프로덕션·프리뷰)를 정규식으로 허용한다.
        #
        # 보안: allow_credentials=True 라 origin 검증이 느슨하면 CORS 우회 위험이 있다.
        # Vercel은 누구나 프로젝트를 만들 수 있어 'vvip-pb-advisor-*'만 허용하면 타인이
        # 같은 접두사 프로젝트(vvip-pb-advisor-attacker)로 우회할 수 있다. 그래서 프리뷰는
        # 우리 계정 접미사(-choi-jung-hyeon-s-projects)를 '반드시' 포함하도록 강제한다
        # (계정 슬러그는 소유자만 만들 수 있는 신뢰 경계). 가운데 식별자는 브랜치 프리뷰
        # (예: -git-feat-cors-)처럼 하이픈을 포함할 수 있어 [a-z0-9-]+ 로 둔다.
        # 프로덕션 도메인(vvip-pb-advisor.vercel.app)은 접미사 없이 매칭.
        self.allowed_origin_regex = os.getenv(
            "ALLOWED_ORIGIN_REGEX",
            r"^https://vvip-pb-advisor(-[a-z0-9-]+-choi-jung-hyeon-s-projects)?\.vercel\.app$",
        )

    @property
    def allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.allowed_origins_raw.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
