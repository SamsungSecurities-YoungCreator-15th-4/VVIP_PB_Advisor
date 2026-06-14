from functools import lru_cache

from supabase import Client, create_client

from app.core.config import settings


@lru_cache
def get_supabase() -> Client:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError(
            "Supabase 환경변수가 없습니다: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY"
        )

    return create_client(settings.supabase_url, settings.supabase_service_role_key)
