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
            # 만료돼도 삭제하지 않는다 — 갱신 실패 시 get_stale()로
            # 마지막 성공값을 복구할 수 있어야 한다 (stale-while-error).
            return None
        return value

    def get_stale(self, key: str) -> T | None:
        """TTL 만료 여부와 무관하게 마지막으로 저장된 값을 반환한다.

        실시간 조회 실패 시 하드코딩 fallback 대신 직전 성공값을 쓰기 위한 용도.
        """
        entry = self._store.get(key)
        return entry[1] if entry is not None else None

    def set(self, key: str, value: T) -> None:
        self._store[key] = (time.monotonic() + self._ttl, value)
