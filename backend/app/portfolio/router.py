# ruff: noqa: E501
"""§13-14. API 엔드포인트 — FastAPI 라우터."""

import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Optional, Literal, Any, Union

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.market.cache import TTLCache

from .assets import (
    ASSET_TICKERS,
    ASSET_NAMES_KR,
    ASSET_DURATION_YEARS,
    INCOME_TAXABLE_ASSETS,
    CASH_LIKE_ASSETS,
    STOCK_ASSETS,
    BOND_CASH_ASSETS,
    ALTERNATIVE_ASSETS,
    FX_SENSITIVE_ASSETS,
    OVERSEAS_STOCK_CAPITAL_GAIN_ASSETS,
    ASSET_INCOME_YIELD_ASSUMPTIONS,
)
from .models import (
    AnalysisRequest,
    PortfolioRequest,
)
from .api_contracts import (
    PortfolioCalculateRequest,
    PortfolioCalculateResponseContract,
    PortfolioStressTestResponseContract,
)
from .utils import (
    canonicalize_weights,
    normalize_weights,
    get_default_current_weights,
    safe_round,
    get_benchmark_catalog,
    attach_benchmark_returns,
    public_http_exception,
)
from .prices import (
    download_price_data,
    download_benchmark_returns,
    calculate_daily_returns,
)
from .expected_returns import calculate_expected_returns
from .tax_accounts import get_common_tax_rules
from .metrics import (
    build_stress_drawdown_series,
    calculate_cumulative_returns,
    calculate_metrics,
    derive_asset_shocks_from_macro,
    resolve_scenario_shocks,
)
from .responses import (
    build_tax_optimizer_payload,
    get_guideline_definition,
    extract_backtest_payload,
    extract_tax_inputs_payload,
)
from .analysis import run_analysis_core, run_full_analysis
from .adapters import normalize_analysis_request_payload
from .formatters import build_metrics_payload, build_portfolio_calculate_response

router = APIRouter(tags=["portfolio"])
KST = ZoneInfo("Asia/Seoul")


# ============================================================
# 13. API Endpoints
# ============================================================


@router.get("/")
def root():
    return {
        "message": "AI IPS Portfolio Analysis API - 8.0.0",
        "swagger": "/docs",
    }


@router.get("/assets")
def get_assets():
    return {
        asset: {
            "label": ASSET_NAMES_KR[asset],
            "ticker": ASSET_TICKERS[asset],
            "duration_years": ASSET_DURATION_YEARS.get(asset, 0.0),
            "income_taxable_asset": asset in INCOME_TAXABLE_ASSETS,
            "cash_like_asset": asset in CASH_LIKE_ASSETS,
            "stock_asset": asset in STOCK_ASSETS,
            "bond_cash_asset": asset in BOND_CASH_ASSETS,
            "alternative_asset": asset in ALTERNATIVE_ASSETS,
            "fx_sensitive_asset": asset in FX_SENSITIVE_ASSETS,
            "overseas_capital_gain_asset": asset in OVERSEAS_STOCK_CAPITAL_GAIN_ASSETS,
            "income_yield_assumption": ASSET_INCOME_YIELD_ASSUMPTIONS.get(asset),
        }
        for asset in ASSET_TICKERS
    }


@router.get("/guidelines")
def get_guidelines():
    return get_guideline_definition()


@router.get("/benchmarks", response_model=Dict[str, Any])
def get_benchmarks():
    """PB가 선택할 수 있는 비교용 벤치마크 메타데이터."""
    return get_benchmark_catalog()


# calculate는 결정론(seed 고정·now/random 미사용)이라 동일 입력이면 동일 출력이다.
# 5000→3000회로 줄여도 무거운(약한 CPU에서 수십 초) CPU 작업이라, 동일 입력 재호출과
# 화면 재진입을 캐시로 즉시 응답한다. 시세는 일중 변하므로 TTL을 짧게(10분) 둔다.
_CALCULATE_TTL_SECONDS = 600
_calculate_cache: TTLCache[Dict[str, Any]] = TTLCache(ttl_seconds=_CALCULATE_TTL_SECONDS)


def _calculate_cache_key(payload: Dict[str, Any]) -> str:
    # 캐시된 응답에 요청자의 client_id·consultation_id가 그대로 담기므로(formatters
    # build_portfolio_calculate_response), 이 식별자를 키에서 빼면 동일 파라미터의 다른
    # 고객/세션이 남의 식별자를 받는 정보 유출이 된다. 데이터 격리를 위해 식별자를 키에 포함한다.
    serialized = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@router.post(
    "/portfolio/calculate",
    response_model=PortfolioCalculateResponseContract,
)
def portfolio_calculate(
    request: Union[PortfolioCalculateRequest, AnalysisRequest],
):
    """STT ips_json 또는 내부 AnalysisRequest로 포트폴리오를 계산한다."""
    try:
        payload = request.model_dump(exclude_none=True)
        cache_key = _calculate_cache_key(payload)
        cached = _calculate_cache.get(cache_key)
        if cached is not None:
            return cached
        normalized_request, adapter_info = normalize_analysis_request_payload(payload)
        full = run_full_analysis(normalized_request)
        response = build_portfolio_calculate_response(full, adapter_info)
        _calculate_cache.set(cache_key, response)
        return response
    except Exception as e:
        raise public_http_exception(e)


@router.post(
    "/portfolio/stress-test",
    response_model=PortfolioStressTestResponseContract,
)
def portfolio_stress_test(
    request: Union[PortfolioCalculateRequest, AnalysisRequest],
):
    """calculate와 동일한 입력 계약으로 스트레스 결과를 반환한다."""
    try:
        payload = request.model_dump(exclude_none=True)
        normalized_request, adapter_info = normalize_analysis_request_payload(payload)
        full = run_full_analysis(normalized_request)
        response = build_portfolio_calculate_response(full, adapter_info)
        return {
            "consultation_id": response["consultation_id"],
            "calculation_session_id": response["calculation_session_id"],
            "as_of": response["as_of"],
            "risk_profile": response["risk_profile"],
            "risk_profile_label": response["risk_profile_label"],
            "portfolios": response["portfolios"],
            "scenario_summary": response["scenario_summary"],
            "data_snapshot": response.get("data_snapshot", {}),
            "input_adapter": response["input_adapter"],
        }
    except Exception as e:
        raise public_http_exception(e)


class StressMetricsRequest(BaseModel):
    """충격 후 전체 지표 재계산용 입력. weights가 없으면 기본 현재 비중을 사용한다."""

    weights: Optional[Dict[str, float]] = Field(None)
    portfolio: PortfolioRequest
    # 위기 시나리오 버튼용. 지정 시 금리·환율 슬라이더 대신 해당 위기 충격 벡터를 주입한다.
    # None이면 슬라이더(금리·환율) 기반. Literal로 두어 Pydantic이 입구에서 값 검증·문서화.
    scenario: Optional[Literal["crisis_2008", "crisis_ru_war"]] = Field(None)


@router.post("/portfolio/stress-metrics", response_model=Dict[str, Any])
def portfolio_stress_metrics(request: StressMetricsRequest):
    """금리·환율 충격을 시계열에 주입해 기준/스트레스 지표를 함께 반환한다."""
    try:
        req = request.portfolio
        weights = canonicalize_weights(request.weights) or get_default_current_weights()
        weights = normalize_weights(weights)

        prices = download_price_data(period=req.period, cash_return=req.cash_return)
        returns = calculate_daily_returns(prices)
        benchmark_returns, _ = download_benchmark_returns(
            period=req.period,
        )
        analysis_returns = attach_benchmark_returns(
            returns,
            benchmark_returns,
        )
        expected_returns = calculate_expected_returns(
            returns=returns,
            expected_return_haircut=req.expected_return_haircut,
            enable_black_litterman=req.enable_black_litterman,
            view_expected_returns=req.view_expected_returns,
            view_weight=req.view_weight,
        )

        base = calculate_metrics(
            weights, analysis_returns, expected_returns, req, include_benchmark_metrics=True
        )
        assets = [
            asset
            for asset in weights
            if asset in returns.columns and weights[asset] > 1e-12
        ]
        # 위기 시나리오 버튼이면 해당 위기 충격 벡터, 아니면 금리·환율 슬라이더 충격.
        if request.scenario:
            asset_shocks = resolve_scenario_shocks(request.scenario, assets)
        else:
            asset_shocks = derive_asset_shocks_from_macro(assets, req)
        stressed = calculate_metrics(
            weights,
            analysis_returns,
            expected_returns,
            req,
            include_benchmark_metrics=True,
            shocks=asset_shocks,
        )

        # ── 백테스트: 위기 시점 급락 포인트(A 합의) ─────────────────────────
        # 과거 누적곡선(base)은 그대로 두고, 끝에 위기 급락 한 칸을 덧붙인다.
        # portfolio_shock = Σ wᵢ·shockᵢ (포트폴리오 단위 연간 충격; 위기 땐 음수).
        portfolio_shock = sum(
            weights.get(asset, 0.0) * shock for asset, shock in asset_shocks.items()
        )
        base_backtest = calculate_cumulative_returns(weights, returns)
        stressed_backtest = build_stress_drawdown_series(base_backtest, portfolio_shock)

        # ── 절세: base/stressed 최적화 페이로드 ────────────────────────────
        # calculate_metrics가 충격 반영(shift_expected_returns) tax_breakdown을 이미
        # 만들어 주므로, 그 결과를 절세 최적화 페이로드로 변환만 한다(세금 재계산 없음).
        # 절대 세액(원)은 req.total_asset 단위에 비례 — base/stressed가 같은
        # total_asset을 쓰므로 둘의 차이(절세 방향)는 단위와 무관하게 일관적이다.
        # portfolio_key는 프런트가 상태 정규화·캐싱 식별자로 쓸 수 있으므로
        # base/stressed를 구분되는 키로 둔다(동일 키 → 덮어쓰기·오동작 방지).
        base_tax = build_tax_optimizer_payload(
            "base_tax",
            {"name": "현재 포트폴리오", "tax_breakdown": base["tax_breakdown"]},
            req,
        )
        stressed_tax = build_tax_optimizer_payload(
            "stressed_tax",
            {"name": "현재 포트폴리오", "tax_breakdown": stressed["tax_breakdown"]},
            req,
        )

        return {
            "as_of": datetime.now(KST).isoformat(timespec="seconds"),
            "scenario": request.scenario,
            # 위기 시나리오일 땐 슬라이더 충격이 무시되므로 None으로 명시(오해 방지).
            "stress_interest_rate_shock": (
                None if request.scenario else req.stress_interest_rate_shock
            ),
            "stress_fx_shock": None if request.scenario else req.stress_fx_shock,
            "asset_shocks": {k: safe_round(v, 6) for k, v in asset_shocks.items()},
            "portfolio_shock": safe_round(portfolio_shock, 6),
            # 단위 통일: calculate(/portfolio/calculate)는 metrics를
            # build_metrics_payload로 퍼센트 변환해 내보낸다(0.05 비율 → 5.00%).
            # stress-metrics도 같은 포매터를 태워 calculate의 metrics
            # (PortfolioMetricsResponse)와 키·단위를 일치시킨다. 필드별 변환이라
            # 세후수익률·변동성·MDD만 ×100이고 샤프·소르티노·베타는 비율 유지.
            # 내부 계산값(base/stressed)은 0.05 비율 그대로라 세금·백테스트에 영향 없음.
            "base": build_metrics_payload({"metrics": base}),
            "stressed": build_metrics_payload({"metrics": stressed}),
            "base_backtest": base_backtest,
            "stressed_backtest": stressed_backtest,
            "base_tax": base_tax,
            "stressed_tax": stressed_tax,
        }
    except Exception as e:
        raise public_http_exception(e)


@router.post(
    "/api/portfolio/all",
    response_model=Dict[str, Any],
    deprecated=True,
)
def api_portfolio_all(request: AnalysisRequest):
    """
    최초 대시보드용 전체 API.
    현재 포트폴리오 / 포트폴리오 A / 포트폴리오 B / 백테스트 / 절세 입력값을 한 번에 반환.
    """
    try:
        return run_full_analysis(request)
    except Exception as e:
        raise public_http_exception(e)


@router.post(
    "/api/portfolio/current",
    response_model=Dict[str, Any],
    deprecated=True,
)
def api_portfolio_current(request: AnalysisRequest):
    """
    현재 포트폴리오만 반환.
    """
    try:
        full = run_full_analysis(request)
        return {
            "session_id": full["session_id"],
            "portfolio": full["portfolios"]["current"],
        }
    except Exception as e:
        raise public_http_exception(e)


@router.post(
    "/api/portfolio/a",
    response_model=Dict[str, Any],
    deprecated=True,
)
def api_portfolio_a(request: AnalysisRequest):
    """
    포트폴리오 A만 반환.
    """
    try:
        full = run_full_analysis(request)
        return {
            "session_id": full["session_id"],
            "portfolio": full["portfolios"]["recommended_1"],
        }
    except Exception as e:
        raise public_http_exception(e)


@router.post(
    "/api/portfolio/b",
    response_model=Dict[str, Any],
    deprecated=True,
)
def api_portfolio_b(request: AnalysisRequest):
    """
    포트폴리오 B만 반환.
    """
    try:
        full = run_full_analysis(request)
        return {
            "session_id": full["session_id"],
            "portfolio": full["portfolios"]["recommended_2"],
        }
    except Exception as e:
        raise public_http_exception(e)


@router.post(
    "/api/portfolio/bundle",
    response_model=Dict[str, Any],
    deprecated=True,
)
def api_portfolio_bundle(request: AnalysisRequest):
    """
    현재 / 포트폴리오 A / 포트폴리오 B 묶음만 반환.
    차트 카드 갱신용.
    """
    try:
        full = run_full_analysis(request)
        return {
            "session_id": full["session_id"],
            "portfolios": full["portfolios"],
            "search_summary": full["search_summary"],
            "scenario_summary": full["scenario_summary"],
        }
    except Exception as e:
        raise public_http_exception(e)


@router.post(
    "/api/backtest",
    response_model=Dict[str, Any],
    deprecated=True,
)
def api_backtest(request: AnalysisRequest):
    """
    현재 / 포트폴리오 A / 포트폴리오 B 백테스트 데이터만 반환.
    """
    try:
        full = run_full_analysis(request)
        return extract_backtest_payload(full)
    except Exception as e:
        raise public_http_exception(e)


@router.post(
    "/api/tax-inputs",
    response_model=Dict[str, Any],
    deprecated=True,
)
def api_tax_inputs(request: AnalysisRequest):
    """
    절세 최적화 파트에 넘길 값만 반환.
    절세제안 문구는 제외하고, 종합과세 임계점/해외주식 양도세/ISA·IRP·일반계좌 정보만 반환.
    """
    try:
        full = run_full_analysis(request)
        return extract_tax_inputs_payload(full)
    except Exception as e:
        raise public_http_exception(e)


@router.post(
    "/api/tax-optimizer",
    response_model=Dict[str, Any],
    deprecated=True,
)
def api_tax_optimizer(request: AnalysisRequest):
    """
    절세 최적화 화면 전용 payload만 반환.
    ISA·IRP·일반계좌 카드와 최종 절세효과를 포함한다.
    """
    try:
        full = run_full_analysis(request)
        return {
            "session_id": full["session_id"],
            "tax_optimizer": full["tax_optimizer"],
            "common_tax_rules": get_common_tax_rules(),
        }
    except Exception as e:
        raise public_http_exception(e)




# ============================================================
# 14. Legacy Analyze API
# ============================================================
# 기존 프론트나 테스트 코드와의 호환을 위해 남김.
# 새 프론트는 /api/portfolio/all 등 분리 API를 사용하면 됨.


@router.post(
    "/analyze",
    response_model=Dict[str, Any],
    deprecated=True,
)
def analyze_portfolio(request: PortfolioRequest):
    try:
        return run_analysis_core(request)
    except Exception as e:
        raise public_http_exception(e)
