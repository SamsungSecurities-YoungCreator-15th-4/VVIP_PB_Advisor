"""CORS 허용 origin 회귀 테스트.

배경:
    allow_origins(고정 목록)만으로는 배포마다 바뀌는 Vercel 프리뷰 URL
    (vvip-pb-advisor-<hash>-...vercel.app)을 매번 막아(프리플라이트 400) 프런트가
    백엔드를 호출하지 못했다. allow_origin_regex 로 이 프로젝트의 vercel 배포를
    허용한다. 이 테스트는 그 규칙을 고정한다(프로젝트 도메인만, 임의 *.vercel.app 금지).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from starlette.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)

PREVIEW = "https://vvip-pb-advisor-okwi68dzc-choi-jung-hyeon-s-projects.vercel.app"
PROD = "https://vvip-pb-advisor.vercel.app"
EVIL = "https://evil.vercel.app"


def _preflight(origin: str):
    return client.options(
        "/clients",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )


def test_vercel_preview_origin_allowed():
    res = _preflight(PREVIEW)
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == PREVIEW


def test_vercel_production_origin_allowed():
    res = _preflight(PROD)
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == PROD


def test_unrelated_vercel_origin_rejected():
    # 다른 vercel.app 사이트는 거부해야 한다(자격증명 허용 상태라 더 중요).
    assert _preflight(EVIL).status_code == 400


def test_lookalike_vercel_projects_rejected():
    # 타인이 같은 접두사로 만든 프로젝트는 우리 계정 접미사가 없으므로 거부돼야 한다.
    # (Vercel은 누구나 프로젝트 생성 가능 → CORS origin 우회 방지)
    assert _preflight("https://vvip-pb-advisor-attacker.vercel.app").status_code == 400
    assert (
        _preflight(
            "https://vvip-pb-advisor-xyz-attacker-s-projects.vercel.app"
        ).status_code
        == 400
    )


def test_branch_preview_origin_allowed():
    # 브랜치 프리뷰 URL은 가운데 식별자에 하이픈이 들어가도 허용돼야 한다.
    res = _preflight(
        "https://vvip-pb-advisor-git-feat-cors-choi-jung-hyeon-s-projects.vercel.app"
    )
    assert res.status_code == 200


def test_localhost_origin_allowed():
    # 로컬 개발 origin은 기본 허용 목록에 있다.
    res = _preflight("http://localhost:3000")
    assert res.status_code == 200
