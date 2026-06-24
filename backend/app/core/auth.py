"""FastAPI auth dependency — Supabase JWT 로컬 검증 후 pb_id(auth.users UUID) 반환.

PyJWT 로 로컬 검증해 네트워크 왕복을 (캐시된 공개키 기준) 제거한다. Supabase 가
서명키를 비대칭(ES256/JWKS)으로 전환하면서 토큰 헤더의 alg 에 따라 분기한다.
  - ES256/RS256 등 비대칭 → JWKS 공개키(SUPABASE_JWKS_URL)로 검증
  - HS256(레거시 공유 시크릿) → SUPABASE_JWT_SECRET 로 검증(전환기 토큰 호환)
둘 다 불가하면 supabase.auth.get_user() 원격 검증으로 폴백한다.

사용 방법:
    from app.core.auth import get_current_pb_id
    from fastapi import Depends

    @router.get("/...")
    def my_endpoint(pb_id: str = Depends(get_current_pb_id)):
        ...
"""

import logging
from functools import lru_cache

import jwt  # PyJWT
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import DecodeError, ExpiredSignatureError, InvalidTokenError, PyJWKClient

from app.core.config import settings
from app.db.supabase import get_supabase

logger = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)

# Supabase Auth JWT audience (Supabase 발급 JWT 표준값)
_JWT_AUDIENCE = "authenticated"
_HS_ALGORITHM = "HS256"
# JWKS 로 검증할 비대칭 알고리즘 허용 목록.
# 헤더 alg 를 그대로 신뢰하지 않고 이 목록으로 제한해 alg-confusion 공격을 막는다.
_ASYMMETRIC_ALGORITHMS = ("ES256", "RS256")


@lru_cache(maxsize=1)
def _jwks_client(url: str) -> PyJWKClient:
    """JWKS 공개키 클라이언트(내부적으로 키를 캐싱). url 별 단일 인스턴스."""
    return PyJWKClient(url)


def get_current_pb_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Authorization: Bearer <token> 헤더에서 pb_id(UUID)를 추출·반환한다.

    검증 전략(토큰 헤더 alg 기준 분기):
    1) ES256/RS256(비대칭) → JWKS 공개키로 로컬 검증
    2) HS256(레거시) → SUPABASE_JWT_SECRET 로 로컬 검증
    3) 위가 모두 불가/실패 → supabase.auth.get_user(token) 원격 검증 폴백
    최종 실패 시 401 반환.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 토큰이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    pb_id = resolve_pb_id(credentials.credentials)
    if pb_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return pb_id


def resolve_pb_id(token: str | None) -> str | None:
    """토큰 문자열에서 pb_id 를 검증·추출한다(실패 시 None, 예외 없음).

    get_current_pb_id 는 HTTP 의존성이라 실패 시 401 을 던지지만, WebSocket 등
    비-HTTP 경로는 예외 대신 None 으로 분기해야 하므로 이 함수를 직접 쓴다.
    검증 전략은 get_current_pb_id 와 동일(로컬 → 원격 폴백).
    """
    if not token:
        return None
    pb_id = _verify_jwt_local(token)
    if pb_id is None:
        pb_id = _verify_jwt_remote(token)
    return pb_id


def _verify_jwt_local(token: str) -> str | None:
    """토큰 헤더의 alg 에 따라 서명·만료·audience 를 로컬 검증하고 sub(UUID)를 반환."""
    try:
        alg = jwt.get_unverified_header(token).get("alg")
    except (DecodeError, InvalidTokenError) as exc:
        logger.debug("JWT header parse error: %s", exc)
        return None

    if alg in _ASYMMETRIC_ALGORITHMS:
        return _verify_jwt_asymmetric(token, alg)
    if alg == _HS_ALGORITHM and settings.supabase_jwt_secret:
        return _decode_sub(token, settings.supabase_jwt_secret, [_HS_ALGORITHM])
    # 검증 수단 없음(예: HS256 인데 시크릿 미설정) → 원격 폴백에 맡긴다.
    return None


def _verify_jwt_asymmetric(token: str, alg: str) -> str | None:
    """JWKS 공개키(kid 매칭)로 비대칭 서명 토큰을 검증한다."""
    if not settings.supabase_jwks_url:
        logger.debug("SUPABASE_JWKS_URL 미설정 — 비대칭 토큰 로컬 검증 불가")
        return None
    try:
        signing_key = _jwks_client(settings.supabase_jwks_url).get_signing_key_from_jwt(token)
        return _decode_sub(token, signing_key.key, [alg])
    except Exception as exc:  # PyJWKClientError 등 네트워크/키 조회 실패 포함
        logger.debug("JWKS verification failed: %s", exc)
        return None


def _decode_sub(token: str, key, algorithms: list[str]) -> str | None:
    """서명·만료·audience 를 검증하고 sub(UUID)를 반환. 실패 시 None."""
    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=_JWT_AUDIENCE,
        )
        sub = payload.get("sub")
        if not sub:
            return None
        return str(sub)
    except ExpiredSignatureError:
        logger.debug("JWT expired")
        return None
    except (DecodeError, InvalidTokenError) as exc:
        logger.debug("JWT decode error: %s", exc)
        return None


def _verify_jwt_remote(token: str) -> str | None:
    """SUPABASE_JWT_SECRET 미설정 시 폴백 — Supabase Auth 서버에 검증 요청."""
    try:
        response = get_supabase().auth.get_user(token)
        if response is None or response.user is None:
            return None
        return str(response.user.id)
    except Exception as exc:
        logger.debug("Remote JWT verification failed: %s", exc)
        return None
