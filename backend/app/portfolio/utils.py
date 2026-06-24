# ruff: noqa: E501
"""포트폴리오 계산 엔진 기본 유틸(§4). 모듈 분할 2단계로 분리.

자산키 정규화·비중 검증·벤치마크 조회·세션 저장·요청 변환 등 순수 보조 로직.
"""

import logging
import re
import threading
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import HTTPException
from pydantic import BaseModel

from .assets import (
    ASSET_NAMES_KR,
    ASSET_TICKERS,
    LEGACY_ASSET_ALIASES,
    UNIQUE_ASSETS,
)
from .constants import (
    BENCHMARK_CONFIGS,
    BENCHMARK_POLICY_VERSION,
    DEFAULT_BENCHMARK_KEY,
    MAX_SESSION_REQUEST_STORE_SIZE,
)
from .models import AnalysisRequest, PortfolioRequest

logger = logging.getLogger(__name__)


# ============================================================
# 4. 기본 유틸
# ============================================================

# FastAPI 의 sync 엔드포인트는 스레드풀에서 병렬 실행되므로, 전역 가변 store 의
# 쓰기(추가·LRU 삭제)는 락으로 직렬화한다(dict changed size during iteration 방지).
_SESSION_STORE_LOCK = threading.Lock()
SESSION_REQUEST_STORE: Dict[str, Dict[str, Any]] = {}


def model_to_dict(model: BaseModel) -> Dict[str, Any]:
    try:
        return model.model_dump()
    except AttributeError:
        return model.dict()


def canonicalize_asset_key(asset: str) -> str:
    return LEGACY_ASSET_ALIASES.get(asset, asset)


def canonicalize_weights(weights: Optional[Dict[str, float]]) -> Optional[Dict[str, float]]:
    if weights is None:
        return None

    canonical: Dict[str, float] = {}
    for asset, weight in weights.items():
        key = canonicalize_asset_key(asset)
        canonical[key] = canonical.get(key, 0.0) + float(weight)
    return canonical


def canonicalize_asset_return_map(
    values: Optional[Dict[str, float]],
) -> Optional[Dict[str, float]]:
    if values is None:
        return None

    canonical: Dict[str, float] = {}
    for asset, value in values.items():
        key = canonicalize_asset_key(asset)
        canonical[key] = float(value)
    return canonical


def validate_unique_asset(unique_asset: str) -> str:
    canonical = canonicalize_asset_key(unique_asset)
    if canonical not in UNIQUE_ASSETS:
        raise ValueError(f"unique_asset은 {UNIQUE_ASSETS} 중 하나여야 합니다. 입력값: {unique_asset}")
    return canonical


def validate_weights(weights: Dict[str, float]) -> None:
    canonical = canonicalize_weights(weights) or {}
    unknown_assets = set(canonical.keys()) - set(ASSET_TICKERS.keys())
    if unknown_assets:
        raise ValueError(f"지원하지 않는 자산군입니다: {unknown_assets}")


def validate_required_assets_available(
    weights: Dict[str, float],
    available_assets: List[str],
    context: str,
) -> None:
    available = set(available_assets)
    missing = [
        asset
        for asset, weight in (canonicalize_weights(weights) or {}).items()
        if float(weight) > 1e-12 and asset not in available
    ]
    if missing:
        labels = {asset: ASSET_NAMES_KR.get(asset, asset) for asset in missing}
        raise ValueError(
            f"{context}에 포함된 자산 중 가격 데이터가 없는 자산이 있습니다: {labels}. "
            "해당 자산의 티커/상장일/yfinance 다운로드 여부를 확인해 주세요."
        )


def normalize_weights(weights: Dict[str, float]) -> Dict[str, float]:
    validate_weights(weights)
    canonical = canonicalize_weights(weights) or {}
    cleaned = {asset: max(float(weight), 0.0) for asset, weight in canonical.items()}
    total = sum(cleaned.values())
    if total <= 0:
        raise ValueError("포트폴리오 비중 합계가 0입니다.")
    return {asset: weight / total for asset, weight in cleaned.items()}


def get_default_current_weights() -> Dict[str, float]:
    return {asset: (1.0 if asset == "cash" else 0.0) for asset in ASSET_TICKERS.keys()}


def cap01(value: float) -> float:
    return float(max(0.0, min(1.0, value)))


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        converted = float(value)
    except (TypeError, ValueError, OverflowError):
        return default

    if not np.isfinite(converted):
        return default
    return converted


def safe_round(value: Any, digits: int = 6) -> float:
    return round(safe_float(value), digits)


def normalize_target_after_tax_return(
    value: Any,
    *,
    percent_input: bool,
) -> Optional[float]:
    """IPS/RRTTLLU 목표수익률을 내부 소수 단위로 정규화한다.

    RRTTLLU.Return과 상담 IPS Return은 퍼센트 단위다.
    예: 8, 8.0, "8%", {"value": 8.0} -> 0.08
    """
    if isinstance(value, dict):
        for key in ("value", "Return", "return_target", "target"):
            if key in value:
                value = value.get(key)
                break

    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, str):
        match = re.search(r"-?[0-9]+(?:\.[0-9]+)?", value.replace(",", ""))
        if match is None:
            raise ValueError("RRTTLLU.Return을 목표 세후수익률 숫자로 해석할 수 없습니다.")
        number = safe_float(match.group(0), default=np.nan)
    else:
        number = safe_float(value, default=np.nan)

    if not np.isfinite(number):
        raise ValueError("RRTTLLU.Return을 목표 세후수익률 숫자로 해석할 수 없습니다.")

    normalized = number / 100.0 if percent_input else number
    if normalized <= 0.0 or normalized > 1.0:
        raise ValueError("RRTTLLU.Return은 0보다 크고 100 이하인 퍼센트 값이어야 합니다.")

    return float(normalized)

def get_benchmark_config(benchmark_key: str) -> Dict[str, Any]:
    config = BENCHMARK_CONFIGS.get(benchmark_key)
    if config is None:
        raise ValueError(
            f"benchmark_key는 {list(BENCHMARK_CONFIGS.keys())} 중 하나여야 합니다. "
            f"입력값: {benchmark_key}"
        )
    return config


def get_benchmark_catalog() -> Dict[str, Any]:
    return {
        "policy": BENCHMARK_POLICY_VERSION,
        "default_key": DEFAULT_BENCHMARK_KEY,
        "selection_scope": ["beta", "backtest_chart"],
        "affects_portfolio_recommendation": False,
        "options": {
            key: {
                "key": key,
                "ticker": config["ticker"],
                "label": config["label"],
                "official_index_series": config["official_index_series"],
                "proxy_note": config["proxy_note"],
            }
            for key, config in BENCHMARK_CONFIGS.items()
        },
    }


def attach_benchmark_returns(
    investable_returns: pd.DataFrame,
    benchmark_returns: pd.DataFrame,
) -> pd.DataFrame:
    combined = investable_returns.copy()
    for column in benchmark_returns.columns:
        combined[column] = benchmark_returns[column].reindex(combined.index)
    combined.attrs.update(investable_returns.attrs)
    return combined


def save_session_request(session_id: str, payload: Dict[str, Any]) -> None:
    with _SESSION_STORE_LOCK:
        SESSION_REQUEST_STORE[session_id] = payload
        while len(SESSION_REQUEST_STORE) > MAX_SESSION_REQUEST_STORE_SIZE:
            oldest_key = next(iter(SESSION_REQUEST_STORE))
            SESSION_REQUEST_STORE.pop(oldest_key, None)


def public_http_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))

    if isinstance(exc, RuntimeError):
        message = str(exc)
        if "기준표와 고객 위험성향" in message:
            return HTTPException(status_code=422, detail=message)
        return HTTPException(status_code=503, detail=message)

    logger.exception("Unhandled portfolio API error", exc_info=True)
    return HTTPException(
        status_code=500,
        detail="서버 내부 오류가 발생했습니다. 관리자 로그를 확인해 주세요.",
    )

def convert_analysis_to_portfolio_request(request: AnalysisRequest) -> PortfolioRequest:
    ips = request.ips
    scenario = request.scenario

    return PortfolioRequest(
        total_asset=ips.total_asset,
        unique_need_amount=ips.unique_need_amount,
        unique_asset=validate_unique_asset(ips.unique_asset),
        unique_items=ips.unique_items,
        unique_profile=ips.unique_profile,
        age=ips.age,
        client_context=ips.client_context,
        target_after_tax_return=(
            ips.target_after_tax_return
            if ips.target_after_tax_return is not None
            else normalize_target_after_tax_return(
                scenario.rrttllu.get(
                    "Return",
                    scenario.rrttllu.get("return_target"),
                ),
                percent_input=True,
            )
        ),
        risk_profile=ips.risk_profile,
        investment_horizon_years=ips.investment_horizon_years,
        tax_text=ips.tax_text,
        tax_profile=ips.tax_profile,
        tax_sensitivity=ips.tax_sensitivity,
        liquidity_need=ips.liquidity_need,
        current_weights=canonicalize_weights(ips.current_weights),
        # Sharpe/Sortino 기준 금리는 미국 무위험이자율 기준으로 별도 관리한다.
        # scenario.base_interest_rate는 스트레스 테스트 표시용 기준금리이며 여기에 덮어쓰지 않는다.
        risk_free_rate=ips.risk_free_rate,
        cash_return=ips.cash_return,
        period=ips.period,
        benchmark_key=ips.benchmark_key,
        num_simulations=ips.num_simulations,
        expected_return_haircut=ips.expected_return_haircut,
        random_seed=ips.random_seed,
        enable_black_litterman=ips.enable_black_litterman,
        view_expected_returns=canonicalize_asset_return_map(ips.view_expected_returns),
        view_weight=ips.view_weight,
        stress_interest_rate_shock=scenario.stress_interest_rate_shock,
        stress_fx_shock=scenario.stress_fx_shock,
        stress_affects_scoring=scenario.stress_affects_scoring,
        marginal_income_tax_rate=ips.marginal_income_tax_rate,
        overseas_stock_realized_gain_rate=ips.overseas_stock_realized_gain_rate,
        overseas_realized_loss=ips.overseas_realized_loss,
        overseas_realized_gain_krw=ips.overseas_realized_gain_krw,
        other_financial_income=ips.other_financial_income,
        external_financial_income_krw=ips.external_financial_income_krw,
        external_financial_income_manwon=ips.external_financial_income_manwon,
        pension_tax_liability_sufficient=ips.pension_tax_liability_sufficient,
        isa_enabled=ips.isa_enabled,
        isa_type=ips.isa_type,
        isa_account_exists=ips.isa_account_exists,
        isa_account_age_years=ips.isa_account_age_years,
        isa_cumulative_contribution=ips.isa_cumulative_contribution,
        isa_current_year_contribution=ips.isa_current_year_contribution,
        isa_recent_3yr_comprehensive_taxed=ips.isa_recent_3yr_comprehensive_taxed,
        isa_existing_account_usable=ips.isa_existing_account_usable,
        isa_remaining_capacity=ips.isa_remaining_capacity,
        isa_remaining_capacity_override=ips.isa_remaining_capacity_override,
        isa_years_until_liquid=ips.isa_years_until_liquid,
        irp_enabled=ips.irp_enabled,
        irp_eligible=ips.irp_eligible,
        irp_account_exists=ips.irp_account_exists,
        irp_account_age_years=ips.irp_account_age_years,
        irp_cumulative_contribution=ips.irp_cumulative_contribution,
        irp_current_year_contribution=ips.irp_current_year_contribution,
        irp_remaining_tax_credit_capacity=ips.irp_remaining_tax_credit_capacity,
        irp_remaining_tax_credit_capacity_override=(
            ips.irp_remaining_tax_credit_capacity_override
        ),
        irp_tax_credit_rate=ips.irp_tax_credit_rate,
        irp_years_until_access=ips.irp_years_until_access,
    )
