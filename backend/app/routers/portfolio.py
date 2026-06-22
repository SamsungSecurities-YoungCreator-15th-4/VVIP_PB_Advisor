"""포트폴리오 외부 API의 단일 진입점.

규칙은 하나다.
- GET: 서버가 이미 가진 설정/목록 조회. request body 없음.
- POST: 고객 입력을 받아 새 계산 실행. JSON request body 있음.

포트폴리오 계산 결과를 GET으로 조회하거나, 설정을 POST로 조회하는 경로는 만들지 않는다.
"""

from fastapi import APIRouter

from app.portfolio_logic import portfolio_logic as legacy
from app.schemas.portfolio_api import (
    PortfolioCalculationRequest,
    PortfolioCalculationResponse,
    PortfolioConfigResponse,
)
from app.services.portfolio_api_service import calculate_portfolios
from app.services.portfolio_orchestration import get_benchmark_catalog

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get(
    "/config",
    response_model=PortfolioConfigResponse,
    summary="포트폴리오 계산 설정 조회",
)
def get_portfolio_config() -> PortfolioConfigResponse:
    """자산 목록, 가이드라인, 벤치마크 목록을 읽기 전용으로 반환한다."""
    return PortfolioConfigResponse(
        api_version="portfolio-api-v1",
        assets=legacy.get_assets(),
        guidelines=legacy.get_guideline_definition(),
        benchmarks=get_benchmark_catalog(),
        methods={
            "GET": ["/api/portfolio/config"],
            "POST": [
                "/api/portfolio/calculate",
                "/api/portfolio/stress-test",
            ],
        },
        units={
            "money": "KRW",
            "rates": "decimal",
            "weights": "decimal",
            "examples": {
                "six_percent": "0.06",
                "one_hundred_basis_points": "0.01",
                "thirty_percent_weight": "0.30",
            },
        },
    )


@router.post(
    "/calculate",
    response_model=PortfolioCalculationResponse,
    response_model_exclude_none=False,
    summary="현재/A/B 포트폴리오 신규 계산",
)
def calculate_portfolio(
    request: PortfolioCalculationRequest,
) -> PortfolioCalculationResponse:
    """고객 IPS와 현재 포트폴리오를 받아 계산 결과를 새로 생성한다."""
    try:
        return calculate_portfolios(request)
    except Exception as exc:
        raise legacy.public_http_exception(exc)


@router.post(
    "/stress-test",
    response_model=PortfolioCalculationResponse,
    response_model_exclude_none=False,
    summary="스트레스 조건을 반영한 포트폴리오 신규 계산",
)
def stress_test_portfolio(
    request: PortfolioCalculationRequest,
) -> PortfolioCalculationResponse:
    """동일 요청 계약을 사용하고 scenario의 충격값으로 스트레스 결과를 계산한다."""
    try:
        return calculate_portfolios(request)
    except Exception as exc:
        raise legacy.public_http_exception(exc)
