"""인메모리 TTL 캐시 — 프론트엔드 yfinance-cache.ts의 캐시 레이어를 백엔드로 이식."""
import time
from typing import Generic, TypeVar

T = TypeVar("T")

CACHE_TTL_SECONDS = 5 * 60  # 5분


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: float = CACHE_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, T]] = {}

    def get(self, key: str) -> T | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: T) -> None:
        self._store[key] = (time.monotonic() + self._ttl, value)
