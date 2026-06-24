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
