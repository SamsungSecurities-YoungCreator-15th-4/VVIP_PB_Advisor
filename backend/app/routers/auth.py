"""auth 라우터 — 로그아웃(서버측 Supabase 세션 폐기).

이 백엔드는 토큰을 발급하지 않는 무상태(stateless) JWT 검증자다(app/core/auth.py).
따라서 '로그아웃'의 실체는 우리 서버 세션을 지우는 게 아니라, Supabase 인증서버의
세션(리프레시 토큰)을 폐기하는 것이다. 프론트는 이 엔드포인트로 서버측 세션을 끊은
뒤, supabase-js 로 로컬 세션(localStorage)을 정리한다.

주의(무상태 검증의 한계): 이미 발급된 access token(JWT)은 만료시간(exp)까지는 서명
검증을 통과한다. 즉시 무효화가 필요하면 session_id denylist 가 별도로 필요하다.
여기서는 리프레시 토큰을 끊어 '세션 연장(재발급) 차단'까지를 보장한다.

참고: Supabase GoTrue 로그아웃 — POST {SUPABASE_URL}/auth/v1/logout
  https://supabase.com/docs/reference/javascript/auth-signout
"""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)

# GoTrue logout scope — global: 해당 사용자의 모든 세션/리프레시 토큰 폐기.
# 단일 세션 사용 전제라 local 과 사실상 동일하나, 보안상 전 세션을 끊는다.
# 다중 기기 세션을 따로 유지하려면 "local" 로 바꾸면 된다.
_LOGOUT_SCOPE = "global"
_REQUEST_TIMEOUT_S = 10.0


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """현재 사용자의 Supabase 세션을 서버측에서 폐기한다(멱등).

    - 토큰 없음 → 401
    - 유효 토큰 → GoTrue /logout 으로 세션 폐기 후 204
    - 이미 만료/무효 토큰 → 이미 로그아웃 상태로 간주해 204(멱등)
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 토큰이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not settings.supabase_url or not settings.supabase_service_role_key:
        # 키가 없으면 서버측 폐기가 불가능하다(껍데기 204 로 속이지 않는다).
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase 환경변수 미설정으로 로그아웃을 처리할 수 없습니다.",
        )

    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/logout"
    headers = {
        "Authorization": f"Bearer {credentials.credentials}",
        "apikey": settings.supabase_service_role_key,
    }
    try:
        resp = httpx.post(
            url,
            headers=headers,
            params={"scope": _LOGOUT_SCOPE},
            timeout=_REQUEST_TIMEOUT_S,
        )
    except httpx.HTTPError as exc:
        logger.warning("Supabase 로그아웃 요청 실패: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="인증 서버와 통신할 수 없습니다.",
        ) from exc

    # 2xx(204 표준, 일부 GoTrue 버전·설정은 200): 폐기 성공.
    # 401: 이미 만료/무효 토큰 → 멱등적으로 로그아웃 성공 취급.
    if resp.is_success or resp.status_code == status.HTTP_401_UNAUTHORIZED:
        return None

    logger.warning(
        "Supabase 로그아웃 비정상 응답: %s %s", resp.status_code, resp.text[:200]
    )
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="로그아웃 처리에 실패했습니다.",
    )
