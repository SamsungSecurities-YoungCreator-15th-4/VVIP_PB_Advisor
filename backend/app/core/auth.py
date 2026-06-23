"""FastAPI auth dependency — Supabase JWT 로컬 검증 후 pb_id(auth.users UUID) 반환.

PyJWT(HS256)로 로컬 검증해 네트워크 왕복을 제거한다.
SUPABASE_JWT_SECRET 이 비어있으면 supabase.auth.get_user() 폴백.

사용 방법:
    from app.core.auth import get_current_pb_id
    from fastapi import Depends

    @router.get("/...")
    def my_endpoint(pb_id: str = Depends(get_current_pb_id)):
        ...
"""

import logging

import jwt  # PyJWT
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import DecodeError, ExpiredSignatureError, InvalidTokenError

from app.core.config import settings
from app.db.supabase import get_supabase

logger = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)

# Supabase Auth JWT audience (Supabase 발급 JWT 표준값)
_JWT_AUDIENCE = "authenticated"
_JWT_ALGORITHM = "HS256"


def get_current_pb_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Authorization: Bearer <token> 헤더에서 pb_id(UUID)를 추출·반환한다.

    검증 전략:
    1) SUPABASE_JWT_SECRET 이 설정돼 있으면 PyJWT 로 로컬 검증(네트워크 0회)
    2) 시크릿이 없으면 supabase.auth.get_user(token) 으로 서버 사이드 검증(폴백)
    두 경우 모두 실패 시 401 반환.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 토큰이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    pb_id = _verify_jwt_local(token) if settings.supabase_jwt_secret else _verify_jwt_remote(token)
    if pb_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return pb_id


def _verify_jwt_local(token: str) -> str | None:
    """PyJWT 로 HS256 서명·만료시간·audience 를 로컬에서 검증하고 sub(UUID)를 반환."""
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=[_JWT_ALGORITHM],
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
