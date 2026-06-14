# ruff: noqa: E501

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal, Tuple, Any
import uuid
import logging
import numpy as np
import pandas as pd
import yfinance as yf


router = APIRouter(tags=["portfolio"])
logger = logging.getLogger(__name__)


# ============================================================
# 0. 기본 설정
# ============================================================

TRADING_DAYS = 252
SORTINO_NO_DOWNSIDE_CAP = 3.0
MIN_COMMON_PRICE_OBSERVATIONS = 126
MAX_SESSION_REQUEST_STORE_SIZE = 100

# 기준 금리와 시나리오 금리는 분리한다.
# 검증된 사실: Sharpe/Sortino의 risk-free rate와 스트레스 시나리오 금리는 서로 다른 입력으로 둘 수 있다.
# 프로젝트용 가정: 기준 무위험이자율은 미국 기준 3.5%를 기본값으로 사용한다.
DEFAULT_RISK_FREE_RATE = 0.035
DEFAULT_CASH_RETURN = 0.025

# 금융소득종합과세 기준: 이자·배당 금융소득 2,000만 원 초과 여부
FINANCIAL_INCOME_COMPREHENSIVE_TAX_THRESHOLD = 20_000_000

# 해외주식 양도소득 기본공제 및 기본세율
OVERSEAS_STOCK_GAIN_DEDUCTION = 2_500_000
OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE = 0.22

# 국내 이자·배당 원천징수 기본세율
DEFAULT_WITHHOLDING_TAX_RATE = 0.154

# ISA 기본 세제 가정
ISA_GENERAL_TAX_FREE_LIMIT = 2_000_000
ISA_SEOGMIN_TAX_FREE_LIMIT = 4_000_000
ISA_LOW_TAX_RATE = 0.099
ISA_MANDATORY_HOLDING_YEARS = 3
ISA_ANNUAL_CONTRIBUTION_LIMIT = 20_000_000
ISA_TOTAL_CONTRIBUTION_LIMIT = 100_000_000

# IRP/연금계좌 기본 세액공제 가정
IRP_PENSION_COMBINED_TAX_CREDIT_LIMIT = 9_000_000
IRP_TAX_CREDIT_RATE_HIGH_INCOME = 0.132
IRP_TAX_CREDIT_RATE_LOW_INCOME = 0.165

TAX_RULE_TABLE_VERSION = "2026-06-13-v1"
TAX_RULE_EFFECTIVE_DATE = "2026-06-13"

# 세율/공제액은 코드 곳곳의 매직넘버로 흩뿌리지 않고 공통 rule table에도 함께 싣는다.
# 실제 서비스에서는 이 테이블을 baseline migration의 tax_rule 테이블에서 로드하면 된다.
TAX_RULE_TABLE = {
    "financial_income_comprehensive_tax_threshold": {
        "value": FINANCIAL_INCOME_COMPREHENSIVE_TAX_THRESHOLD,
        "unit": "KRW",
        "source": "금융소득종합과세 검토 기준",
    },
    "overseas_stock_gain_deduction": {
        "value": OVERSEAS_STOCK_GAIN_DEDUCTION,
        "unit": "KRW",
        "source": "해외주식 양도소득 기본공제",
    },
    "overseas_stock_capital_gains_tax_rate": {
        "value": OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE,
        "unit": "rate",
        "source": "해외주식 양도소득 기본세율",
    },
    "default_withholding_tax_rate": {
        "value": DEFAULT_WITHHOLDING_TAX_RATE,
        "unit": "rate",
        "source": "국내 이자·배당 원천징수 기본세율",
    },
    "isa_general_tax_free_limit": {
        "value": ISA_GENERAL_TAX_FREE_LIMIT,
        "unit": "KRW",
        "source": "ISA 일반형 비과세 한도",
    },
    "isa_seogmin_tax_free_limit": {
        "value": ISA_SEOGMIN_TAX_FREE_LIMIT,
        "unit": "KRW",
        "source": "ISA 서민형 비과세 한도",
    },
    "isa_low_tax_rate": {
        "value": ISA_LOW_TAX_RATE,
        "unit": "rate",
        "source": "ISA 비과세 한도 초과분 저율 분리과세율",
    },
    "isa_mandatory_holding_years": {
        "value": ISA_MANDATORY_HOLDING_YEARS,
        "unit": "year",
        "source": "ISA 의무보유기간",
    },
    "isa_annual_contribution_limit": {
        "value": ISA_ANNUAL_CONTRIBUTION_LIMIT,
        "unit": "KRW",
        "source": "ISA 연 납입한도",
    },
    "isa_total_contribution_limit": {
        "value": ISA_TOTAL_CONTRIBUTION_LIMIT,
        "unit": "KRW",
        "source": "ISA 총 납입한도",
    },
    "irp_tax_credit_limit": {
        "value": IRP_PENSION_COMBINED_TAX_CREDIT_LIMIT,
        "unit": "KRW",
        "source": "연금저축·IRP 합산 세액공제 한도",
    },
    "irp_tax_credit_rate_high_income": {
        "value": IRP_TAX_CREDIT_RATE_HIGH_INCOME,
        "unit": "rate",
        "source": "IRP 세액공제율 가정: 고소득 구간",
    },
    "irp_tax_credit_rate_low_income": {
        "value": IRP_TAX_CREDIT_RATE_LOW_INCOME,
        "unit": "rate",
        "source": "IRP 세액공제율 가정: 저소득 구간",
    },
}

# 추천 B 선별 기준
# 검증된 사실: 상관계수가 낮을수록 분산효과가 커질 수 있음.
# 프로젝트용 가정: 추천 A와 B가 너무 비슷하지 않도록 0.95 이하를 기준으로 둠.
SECOND_PORTFOLIO_MAX_CORRELATION = 0.95


# ============================================================
# 1. 자산군
# ============================================================
# 확정 자산 enum은 프론트·DB·응답 JSON에서 공통으로 사용할 키다.
# 사용자가 요청한 12종: 코스피, S&P500, 나스닥, 일반채, 분리과세채, 저쿠폰채,
# 해외배당(SCHD), 리츠, 금, 원자재, 달러, 현금.
#
# 검증된 사실:
# - DXY는 Yahoo Finance에서 DX-Y.NYB로 조회 가능.
# - 471230.KS는 한국 국채 proxy로 사용한다.
# - 484790.KS는 KODEX 미국30년국채액티브(H) proxy로, 환헤지형이므로 FX 민감자산에서 제외한다.
# - 439870.KS는 분리과세 장기채 전략의 가격 proxy로 사용한다.
#
# 프로젝트용 가정:
# - ETF proxy가 세법상 직접투자 상품과 완전히 동일하다는 뜻은 아니다.
# - 세금 계산에서 배당·이자 수익과 가격차익을 간이 분리하기 위해 아래 수익률 가정을 사용한다.

ASSET_TICKERS = {
    "domestic_equity": "^KS11",
    "overseas_blue_chip": "SPY",
    "overseas_growth": "QQQ",
    "overseas_dividend": "SCHD",
    "general_bond": "471230.KS",
    "separate_tax_bond": "439870.KS",
    "low_coupon_bond": "484790.KS",
    "reit": "VNQ",
    "gold": "GLD",
    "commodity": "DBC",
    "dollar": "DX-Y.NYB",
    "cash": "CASH",
}

ASSET_NAMES_KR = {
    "domestic_equity": "코스피",
    "overseas_blue_chip": "S&P500",
    "overseas_growth": "나스닥",
    "overseas_dividend": "해외배당 ETF(SCHD)",
    "general_bond": "일반채 proxy",
    "separate_tax_bond": "분리과세채 장기국고채 proxy",
    "low_coupon_bond": "저쿠폰채 proxy",
    "reit": "리츠",
    "gold": "금",
    "commodity": "원자재",
    "dollar": "달러",
    "cash": "현금",
}

# 기존 키로 들어온 요청도 한동안 받아주기 위한 호환 alias.
LEGACY_ASSET_ALIASES = {
    "domestic_stock": "domestic_equity",
    "sp500": "overseas_blue_chip",
    "nasdaq": "overseas_growth",
    "high_dividend": "overseas_dividend",
    "kr_treasury": "general_bond",
    "dxy": "dollar",
}

UNIQUE_ASSETS = ["cash", "general_bond", "low_coupon_bond", "separate_tax_bond"]

STOCK_ASSETS = ["domestic_equity", "overseas_blue_chip", "overseas_growth", "overseas_dividend"]
OVERSEAS_STOCK_CAPITAL_GAIN_ASSETS = [
    "overseas_blue_chip",
    "overseas_growth",
    "overseas_dividend",
    "reit",
]
# 기존 함수명 호환용 alias
OVERSEAS_STOCK_ASSETS = OVERSEAS_STOCK_CAPITAL_GAIN_ASSETS
BOND_ASSETS = ["general_bond", "separate_tax_bond", "low_coupon_bond"]
BOND_CASH_ASSETS = BOND_ASSETS + ["cash"]
ALTERNATIVE_ASSETS = ["reit", "gold", "commodity", "dollar"]
CASH_LIKE_ASSETS = ["cash", "general_bond", "low_coupon_bond", "separate_tax_bond"]

# 이자·배당 성격이 강해 금융소득종합과세 검토 대상에 넣을 자산.
# 해외배당·리츠는 전체 기대수익률 전부가 아니라 아래 income yield 가정 범위까지만 금융소득으로 본다.
INCOME_TAXABLE_ASSETS = [
    "cash",
    "general_bond",
    "low_coupon_bond",
    "separate_tax_bond",
    "overseas_dividend",
    "reit",
]

# 배당·이자 수익률 간이 가정. 기대수익률 중 이 수준까지만 이자·배당성 금융소득으로 본다.
ASSET_INCOME_YIELD_ASSUMPTIONS = {
    "cash": DEFAULT_CASH_RETURN,
    "general_bond": 0.030,
    "low_coupon_bond": 0.015,
    "separate_tax_bond": 0.025,
    "overseas_dividend": 0.035,
    "reit": 0.040,
}

ISA_PRIORITY_ASSETS = [
    "overseas_dividend",
    "reit",
    "general_bond",
    "low_coupon_bond",
    "separate_tax_bond",
    "cash",
]

IRP_PRIORITY_ASSETS = [
    "general_bond",
    "low_coupon_bond",
    "separate_tax_bond",
    "overseas_blue_chip",
    "overseas_dividend",
]

# 듀레이션은 점수화에만 사용. 차트 하단 6종 지표에는 포함하지 않음.
# 검증된 사실: 듀레이션은 금리 변화에 대한 채권 가격 민감도 지표.
# 프로젝트용 가정: 아래 수치는 ETF/전략별 대표 근사치.
ASSET_DURATION_YEARS = {
    "domestic_equity": 0.0,
    "overseas_blue_chip": 0.0,
    "overseas_growth": 0.0,
    "overseas_dividend": 0.0,
    "reit": 0.0,
    "gold": 0.0,
    "commodity": 0.0,
    "dollar": 0.0,
    "general_bond": 7.99,
    "separate_tax_bond": 19.53,
    "low_coupon_bond": 15.39,
    "cash": 0.0,
}

INTEREST_RATE_SENSITIVE_ASSETS = BOND_ASSETS
FX_SENSITIVE_ASSETS = [
    "overseas_blue_chip",
    "overseas_growth",
    "overseas_dividend",
    "reit",
    "gold",
    "commodity",
    "dollar",
    # low_coupon_bond는 환헤지(H) proxy이므로 환율 충격에서 제외한다.
]

CLIENT_RISK_LEVEL = {
    "conservative": 1,
    "balanced": 2,
    "aggressive": 3,
}

RISK_LEVEL_NAME = {
    1: "안정형",
    2: "균형형",
    3: "공격형",
}

# ============================================================
# 2. 기준표 및 리스크 관리 기준
# ============================================================
# 검증된 사실:
# - 투자위험 판단에는 변동성, 최대 손실 가능성, 기초자산 구성, 유동성, 만기, 환율 변동성 등이 고려될 수 있음.
# - 투자자 성향보다 높은 위험도의 상품 권유는 제한됨.
# - 금융소득 2,000만 원, ISA 3년, 해외주식 양도차익 250만 원 공제 등은 세법/제도상 기본 기준.
#
# 프로젝트용 가정:
# - 안정형/균형형/공격형의 변동성, MDD, 자산비중 한도
# - VaR/ERC 리스크 관리 기준
# - 추천 B 상관계수 0.95 기준

GUIDELINE_RULES = {
    "conservative": {
        "level": 1,
        "label": "안정형",
        "volatility_max": 0.10,
        "mdd_min": -0.10,
        "liquidity_coverage_min": 1.0,
        "stock_weight_max": 0.30,
        "alternative_weight_max": 0.10,
        "bond_cash_weight_min": 0.60,
        "expected_return_min": 0.030,
        "expected_return_max": 0.055,
        "sharpe_min": 0.6,
        "sortino_min": 0.8,
        "tax_gap_max": 0.006,
        "taxable_income_max": FINANCIAL_INCOME_COMPREHENSIVE_TAX_THRESHOLD,
        "after_tax_retention_min": None,
    },
    "balanced": {
        "level": 2,
        "label": "균형형",
        "volatility_max": 0.20,
        "mdd_min": -0.20,
        "liquidity_coverage_min": 1.0,
        "stock_weight_max": 0.60,
        "alternative_weight_max": 0.25,
        "bond_cash_weight_min": 0.25,
        "expected_return_min": 0.045,
        "expected_return_max": 0.105,
        "sharpe_min": 0.4,
        "sortino_min": 0.6,
        "tax_gap_max": None,
        "taxable_income_max": FINANCIAL_INCOME_COMPREHENSIVE_TAX_THRESHOLD,
        "after_tax_retention_min": None,
    },
    "aggressive": {
        "level": 3,
        "label": "공격형",
        "volatility_max": 0.32,
        "mdd_min": -0.50,
        "liquidity_coverage_min": 0.0,
        "stock_weight_max": 0.85,
        "alternative_weight_max": 0.40,
        "bond_cash_weight_min": 0.00,
        "expected_return_min": 0.070,
        "expected_return_max": None,
        "sharpe_min": 0.25,
        "sortino_min": None,
        "tax_gap_max": None,
        "taxable_income_max": None,
        "after_tax_retention_min": 0.78,
    },
}

SELECTION_RISK_CONTROLS = {
    "conservative": {
        "historical_var_95_daily_max_loss": 0.010,
        "risk_contribution_max_share": 0.45,
    },
    "balanced": {
        "historical_var_95_daily_max_loss": 0.018,
        "risk_contribution_max_share": 0.55,
    },
    "aggressive": {
        "historical_var_95_daily_max_loss": 0.030,
        "risk_contribution_max_share": 0.70,
    },
}

SELECTION_RANKING_BASIS = [
    "suitability_filter",
    "historical_var_95_filter",
    "risk_contribution_filter",
    "after_tax_return_desc",
    "expected_return_desc",
    "historical_var_95_asc",
    "risk_contribution_max_share_asc",
]



# ============================================================
# 3. Request Models
# ============================================================


class IPSRequest(BaseModel):
    total_asset: float = Field(..., gt=0)
    unique_need_amount: float = Field(..., ge=0)
    unique_asset: str = Field(...)

    risk_profile: Literal["conservative", "balanced", "aggressive"] = Field(...)
    investment_horizon_years: int = Field(..., ge=1, le=50)
    tax_sensitivity: Literal["low", "medium", "high"] = Field(...)
    liquidity_need: Literal["low", "medium", "high"] = Field(...)

    current_weights: Optional[Dict[str, float]] = Field(None)

    risk_free_rate: float = Field(DEFAULT_RISK_FREE_RATE)
    cash_return: float = Field(DEFAULT_CASH_RETURN)
    period: str = Field("5y")

    num_simulations: int = Field(5000, ge=500, le=100000)
    expected_return_haircut: float = Field(0.75, ge=0.0, le=1.0)
    random_seed: int = Field(42, ge=0)

    enable_black_litterman: bool = Field(False)
    view_expected_returns: Optional[Dict[str, float]] = Field(None)
    view_weight: float = Field(0.35, ge=0.0, le=1.0)

    marginal_income_tax_rate: float = Field(0.24, ge=0.06, le=0.495)
    overseas_stock_realized_gain_rate: float = Field(0.0, ge=0.0, le=1.0)

    isa_enabled: bool = Field(True)
    isa_type: Literal["general", "seogmin"] = Field("general")
    isa_account_exists: bool = Field(False)
    isa_account_age_years: float = Field(0.0, ge=0, le=50)
    isa_cumulative_contribution: float = Field(0.0, ge=0)
    isa_recent_3yr_comprehensive_taxed: bool = Field(False)
    isa_existing_account_usable: bool = Field(True)
    isa_remaining_capacity: float = Field(ISA_TOTAL_CONTRIBUTION_LIMIT, ge=0)
    isa_remaining_capacity_override: Optional[float] = Field(None, ge=0)
    isa_years_until_liquid: float = Field(ISA_MANDATORY_HOLDING_YEARS, ge=0, le=50)

    irp_enabled: bool = Field(True)
    irp_eligible: bool = Field(True)
    irp_current_year_contribution: float = Field(0.0, ge=0)
    irp_remaining_tax_credit_capacity: float = Field(
        IRP_PENSION_COMBINED_TAX_CREDIT_LIMIT, ge=0
    )
    irp_remaining_tax_credit_capacity_override: Optional[float] = Field(None, ge=0)
    irp_tax_credit_rate: float = Field(
        IRP_TAX_CREDIT_RATE_HIGH_INCOME, ge=0.0, le=IRP_TAX_CREDIT_RATE_LOW_INCOME
    )
    irp_years_until_access: float = Field(0.0, ge=0, le=80)


class ScenarioRequest(BaseModel):
    base_interest_rate: float = Field(...)
    base_fx_rate_krw_per_usd: float = Field(..., gt=0)

    stress_interest_rate_shock: float = Field(...)
    stress_fx_shock: float = Field(...)

    # 다경님 쪽 시나리오 테스트에서 넘어오는 값.
    # 구조가 아직 확정되지 않았으므로 dict로 받아 프론트/타 팀과 유연하게 연결.
    rrttllu: Dict[str, Any] = Field(...)

    # false: 스트레스 결과는 표시만 하고 추천 점수에는 미반영
    # true: 스트레스 손실이 큰 포트폴리오를 점수에서 감점
    stress_affects_scoring: bool = Field(False)


class AnalysisRequest(BaseModel):
    ips: IPSRequest = Field(...)
    scenario: ScenarioRequest = Field(...)


# 기존 /analyze 호환용
class PortfolioRequest(BaseModel):
    total_asset: float = Field(..., gt=0)
    unique_need_amount: float = Field(0, ge=0)
    unique_asset: str = Field("general_bond")
    risk_profile: Literal["conservative", "balanced", "aggressive"] = Field(...)
    investment_horizon_years: int = Field(10, ge=1, le=50)
    tax_sensitivity: Literal["low", "medium", "high"] = Field("medium")
    liquidity_need: Literal["low", "medium", "high"] = Field("medium")
    current_weights: Optional[Dict[str, float]] = Field(None)

    risk_free_rate: float = Field(DEFAULT_RISK_FREE_RATE)
    cash_return: float = Field(DEFAULT_CASH_RETURN)
    period: str = Field("5y")
    num_simulations: int = Field(5000, ge=500, le=100000)
    expected_return_haircut: float = Field(0.75, ge=0.0, le=1.0)
    random_seed: int = Field(42, ge=0)

    enable_black_litterman: bool = Field(False)
    view_expected_returns: Optional[Dict[str, float]] = Field(None)
    view_weight: float = Field(0.35, ge=0.0, le=1.0)

    stress_interest_rate_shock: float = Field(0.01)
    stress_fx_shock: float = Field(0.10)
    stress_affects_scoring: bool = Field(False)

    marginal_income_tax_rate: float = Field(0.24, ge=0.06, le=0.495)
    overseas_stock_realized_gain_rate: float = Field(0.0, ge=0.0, le=1.0)

    isa_enabled: bool = Field(True)
    isa_type: Literal["general", "seogmin"] = Field("general")
    isa_account_exists: bool = Field(False)
    isa_account_age_years: float = Field(0.0, ge=0, le=50)
    isa_cumulative_contribution: float = Field(0.0, ge=0)
    isa_recent_3yr_comprehensive_taxed: bool = Field(False)
    isa_existing_account_usable: bool = Field(True)
    isa_remaining_capacity: float = Field(ISA_TOTAL_CONTRIBUTION_LIMIT, ge=0)
    isa_remaining_capacity_override: Optional[float] = Field(None, ge=0)
    isa_years_until_liquid: float = Field(ISA_MANDATORY_HOLDING_YEARS, ge=0, le=50)

    irp_enabled: bool = Field(True)
    irp_eligible: bool = Field(True)
    irp_current_year_contribution: float = Field(0.0, ge=0)
    irp_remaining_tax_credit_capacity: float = Field(
        IRP_PENSION_COMBINED_TAX_CREDIT_LIMIT, ge=0
    )
    irp_remaining_tax_credit_capacity_override: Optional[float] = Field(None, ge=0)
    irp_tax_credit_rate: float = Field(
        IRP_TAX_CREDIT_RATE_HIGH_INCOME, ge=0.0, le=IRP_TAX_CREDIT_RATE_LOW_INCOME
    )
    irp_years_until_access: float = Field(0.0, ge=0, le=80)


# ============================================================
# 4. 기본 유틸
# ============================================================

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


def save_session_request(session_id: str, payload: Dict[str, Any]) -> None:
    SESSION_REQUEST_STORE[session_id] = payload
    while len(SESSION_REQUEST_STORE) > MAX_SESSION_REQUEST_STORE_SIZE:
        oldest_key = next(iter(SESSION_REQUEST_STORE))
        SESSION_REQUEST_STORE.pop(oldest_key, None)


def public_http_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=503, detail=str(exc))

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
        risk_profile=ips.risk_profile,
        investment_horizon_years=ips.investment_horizon_years,
        tax_sensitivity=ips.tax_sensitivity,
        liquidity_need=ips.liquidity_need,
        current_weights=canonicalize_weights(ips.current_weights),
        # Sharpe/Sortino 기준 금리는 미국 무위험이자율 기준으로 별도 관리한다.
        # scenario.base_interest_rate는 스트레스 테스트 표시용 기준금리이며 여기에 덮어쓰지 않는다.
        risk_free_rate=ips.risk_free_rate,
        cash_return=ips.cash_return,
        period=ips.period,
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
        isa_enabled=ips.isa_enabled,
        isa_type=ips.isa_type,
        isa_account_exists=ips.isa_account_exists,
        isa_account_age_years=ips.isa_account_age_years,
        isa_cumulative_contribution=ips.isa_cumulative_contribution,
        isa_recent_3yr_comprehensive_taxed=ips.isa_recent_3yr_comprehensive_taxed,
        isa_existing_account_usable=ips.isa_existing_account_usable,
        isa_remaining_capacity=ips.isa_remaining_capacity,
        isa_remaining_capacity_override=ips.isa_remaining_capacity_override,
        isa_years_until_liquid=ips.isa_years_until_liquid,
        irp_enabled=ips.irp_enabled,
        irp_eligible=ips.irp_eligible,
        irp_current_year_contribution=ips.irp_current_year_contribution,
        irp_remaining_tax_credit_capacity=ips.irp_remaining_tax_credit_capacity,
        irp_remaining_tax_credit_capacity_override=(
            ips.irp_remaining_tax_credit_capacity_override
        ),
        irp_tax_credit_rate=ips.irp_tax_credit_rate,
        irp_years_until_access=ips.irp_years_until_access,
    )


# ============================================================
# 5. 가격 데이터
# ============================================================


def download_price_data(period: str, cash_return: float) -> pd.DataFrame:
    tickers = {asset: ticker for asset, ticker in ASSET_TICKERS.items() if ticker != "CASH"}

    raw = yf.download(
        list(tickers.values()),
        period=period,
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=True,
    )

    if raw.empty:
        raise RuntimeError("yfinance에서 데이터를 가져오지 못했습니다.")

    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" not in raw.columns.get_level_values(0):
            raise RuntimeError("yfinance 응답에서 Close 가격을 찾지 못했습니다.")
        prices = raw["Close"].copy()
    else:
        prices = raw[["Close"]].copy()

    reverse_map = {ticker: asset for asset, ticker in tickers.items()}
    prices = prices.rename(columns=reverse_map)
    prices = prices.dropna(how="all").sort_index()

    available_assets = [
        asset
        for asset in ASSET_TICKERS.keys()
        if asset != "cash" and asset in prices.columns and prices[asset].notna().any()
    ]
    excluded_assets = [
        asset
        for asset in ASSET_TICKERS.keys()
        if asset != "cash" and asset not in available_assets
    ]

    if excluded_assets:
        raise RuntimeError(
            "확정 자산군 중 가격 데이터를 가져오지 못한 자산이 있습니다. "
            f"excluded_assets={excluded_assets}. 티커, 상장일, yfinance 다운로드 상태를 확인해 주세요."
        )

    first_valid_dates = {asset: prices[asset].first_valid_index() for asset in available_assets}
    common_start = max(first_valid_dates.values())
    limiting_assets = [
        asset for asset, start_date in first_valid_dates.items() if start_date == common_start
    ]

    # 신규 상장 ETF가 섞여 있을 때 .dropna()가 5년치 대부분을 조용히 날리는 문제를 방지한다.
    # 공통 시작일을 명시적으로 잡고, 너무 짧으면 왜 실패했는지 설명한다.
    common_prices = prices.loc[common_start:, available_assets].ffill().dropna(how="any")

    if len(common_prices) < MIN_COMMON_PRICE_OBSERVATIONS:
        raise RuntimeError(
            "공통 가격 데이터 구간이 너무 짧습니다. "
            f"observations={len(common_prices)}, min_required={MIN_COMMON_PRICE_OBSERVATIONS}, "
            f"common_start={common_start.date() if common_start is not None else None}, "
            f"limiting_assets={limiting_assets}. 최근 상장 ETF proxy를 더 긴 이력 proxy로 바꾸는지 검토해 주세요."
        )

    daily_cash_return = (1 + cash_return) ** (1 / TRADING_DAYS) - 1
    common_prices["cash"] = (1 + daily_cash_return) ** np.arange(len(common_prices))

    ordered_assets = [asset for asset in ASSET_TICKERS.keys() if asset in common_prices.columns]
    common_prices = common_prices[ordered_assets]

    common_prices.attrs["data_snapshot"] = {
        "period_requested": period,
        "as_of": common_prices.index[-1].strftime("%Y-%m-%d"),
        "data_start": common_prices.index[0].strftime("%Y-%m-%d"),
        "data_end": common_prices.index[-1].strftime("%Y-%m-%d"),
        "observations": int(len(common_prices)),
        "available_assets": ordered_assets,
        "excluded_assets": excluded_assets,
        "first_valid_dates": {
            asset: date.strftime("%Y-%m-%d") for asset, date in first_valid_dates.items()
        },
        "limiting_assets": limiting_assets,
        "note": "전체 자산의 공통 가격 구간만 사용. 신규 상장 proxy가 있으면 data_start가 짧아질 수 있음.",
    }

    return common_prices


def calculate_daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    returns = prices.pct_change().replace([np.inf, -np.inf], np.nan).dropna(how="any")
    if returns.empty:
        raise RuntimeError("수익률 계산 결과가 비어 있습니다.")
    returns.attrs["data_snapshot"] = prices.attrs.get("data_snapshot", {})
    return returns



# ============================================================
# 6. 기대수익률
# ============================================================


def calculate_expected_returns(
    returns: pd.DataFrame,
    expected_return_haircut: float,
    enable_black_litterman: bool,
    view_expected_returns: Optional[Dict[str, float]],
    view_weight: float,
) -> pd.Series:
    historical_annual_returns = returns.mean() * TRADING_DAYS
    adjusted_returns = historical_annual_returns * expected_return_haircut

    if "cash" in historical_annual_returns.index:
        adjusted_returns["cash"] = historical_annual_returns["cash"]

    view_expected_returns = canonicalize_asset_return_map(view_expected_returns)

    if not enable_black_litterman or not view_expected_returns:
        return adjusted_returns

    final_returns = adjusted_returns.copy()
    for asset, view_return in view_expected_returns.items():
        if asset in final_returns.index:
            final_returns[asset] = (
                final_returns[asset] * (1 - view_weight) + float(view_return) * view_weight
            )

    return final_returns


# ============================================================
# 7. 세금 / 계좌
# ============================================================


def get_common_tax_rules() -> Dict[str, Any]:
    return {
        "version": TAX_RULE_TABLE_VERSION,
        "effective_date": TAX_RULE_EFFECTIVE_DATE,
        "rules": TAX_RULE_TABLE,
    }


def estimate_income_profit_for_asset(
    asset: str,
    weight: float,
    expected_return: float,
    total_asset: float,
) -> float:
    if asset not in INCOME_TAXABLE_ASSETS:
        return 0.0

    positive_return = max(safe_float(expected_return), 0.0)
    income_yield = ASSET_INCOME_YIELD_ASSUMPTIONS.get(asset, positive_return)
    income_return = min(positive_return, max(income_yield, 0.0))
    return float(max(weight, 0.0) * total_asset * income_return)


def estimate_overseas_capital_gain_profit_for_asset(
    asset: str,
    weight: float,
    expected_return: float,
    total_asset: float,
) -> float:
    if asset not in OVERSEAS_STOCK_CAPITAL_GAIN_ASSETS:
        return 0.0

    total_positive_profit = max(weight, 0.0) * total_asset * max(safe_float(expected_return), 0.0)
    income_profit = estimate_income_profit_for_asset(
        asset=asset,
        weight=weight,
        expected_return=expected_return,
        total_asset=total_asset,
    )
    return float(max(total_positive_profit - income_profit, 0.0))


def estimate_taxable_financial_income(
    weights: Dict[str, float],
    expected_returns: pd.Series,
    total_asset: float,
) -> float:
    estimated_income = 0.0
    weights = normalize_weights(weights)

    for asset in INCOME_TAXABLE_ASSETS:
        if asset in expected_returns.index:
            estimated_income += estimate_income_profit_for_asset(
                asset=asset,
                weight=weights.get(asset, 0.0),
                expected_return=float(expected_returns[asset]),
                total_asset=total_asset,
            )

    return float(estimated_income)


def calculate_financial_income_comprehensive_tax_status(
    taxable_financial_income: float,
) -> Dict[str, Any]:
    taxable_financial_income = safe_float(taxable_financial_income)
    excess = max(taxable_financial_income - FINANCIAL_INCOME_COMPREHENSIVE_TAX_THRESHOLD, 0.0)

    return {
        "taxable_financial_income": safe_round(taxable_financial_income, 0),
        "threshold": FINANCIAL_INCOME_COMPREHENSIVE_TAX_THRESHOLD,
        "excess_over_threshold": safe_round(excess, 0),
        "is_over_threshold": taxable_financial_income
        > FINANCIAL_INCOME_COMPREHENSIVE_TAX_THRESHOLD,
        "rule_key": "financial_income_comprehensive_tax_threshold",
        "basis": "금융소득종합과세 검토 기준 2,000만 원. 세부 적용은 고객 전체 소득과 세법 확인 필요.",
    }


def estimate_overseas_stock_capital_gains_tax(
    weights: Dict[str, float],
    expected_returns: pd.Series,
    total_asset: float,
    realized_gain_rate: float,
) -> Dict[str, Any]:
    gross_realized_gain = 0.0
    weights = normalize_weights(weights)

    for asset in OVERSEAS_STOCK_CAPITAL_GAIN_ASSETS:
        if asset in expected_returns.index:
            asset_capital_gain = estimate_overseas_capital_gain_profit_for_asset(
                asset=asset,
                weight=weights.get(asset, 0.0),
                expected_return=float(expected_returns[asset]),
                total_asset=total_asset,
            )
            gross_realized_gain += asset_capital_gain * realized_gain_rate

    taxable_gain = max(gross_realized_gain - OVERSEAS_STOCK_GAIN_DEDUCTION, 0.0)
    estimated_tax = taxable_gain * OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE

    return {
        "gross_realized_gain": safe_round(gross_realized_gain, 0),
        "basic_deduction": OVERSEAS_STOCK_GAIN_DEDUCTION,
        "taxable_gain": safe_round(taxable_gain, 0),
        "tax_rate": OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE,
        "estimated_tax": safe_round(estimated_tax, 0),
        "rule_keys": [
            "overseas_stock_gain_deduction",
            "overseas_stock_capital_gains_tax_rate",
        ],
        "basis": (
            "해외상장 주식/ETF의 가격차익 부분에 기본공제 250만 원과 "
            "기본세율 22%를 적용한 간이 추정. 배당·이자성 수익과 "
            "가격차익은 중복 과세하지 않도록 분리 추정."
        ),
    }


def calculate_isa_status(request: PortfolioRequest) -> Dict[str, Any]:
    can_open_new = not request.isa_recent_3yr_comprehensive_taxed
    account_year_count = max(int(np.floor(request.isa_account_age_years)) + 1, 1)

    if request.isa_account_exists:
        earned_capacity = min(
            ISA_ANNUAL_CONTRIBUTION_LIMIT * account_year_count,
            ISA_TOTAL_CONTRIBUTION_LIMIT,
        )
        account_usable = request.isa_existing_account_usable
    else:
        earned_capacity = ISA_ANNUAL_CONTRIBUTION_LIMIT
        account_usable = can_open_new

    calculated_capacity = max(
        earned_capacity - request.isa_cumulative_contribution,
        0.0,
    )
    manual_capacity = request.isa_remaining_capacity
    if request.isa_remaining_capacity_override is not None:
        manual_capacity = request.isa_remaining_capacity_override

    remaining_capacity = min(calculated_capacity, manual_capacity)
    isa_usable = request.isa_enabled and account_usable and remaining_capacity > 0

    calculated_years_until_liquid = max(
        ISA_MANDATORY_HOLDING_YEARS - request.isa_account_age_years,
        0.0,
    )
    years_until_liquid = min(
        request.isa_years_until_liquid,
        calculated_years_until_liquid,
    )

    if not isa_usable:
        remaining_capacity = 0.0

    if isa_usable and request.isa_account_exists:
        reason = "existing_isa_account_usable"
    elif isa_usable:
        reason = "new_isa_opening_allowed"
    elif not request.isa_enabled:
        reason = "isa_disabled_by_input"
    elif not account_usable:
        reason = "isa_account_or_eligibility_not_usable"
    else:
        reason = "isa_remaining_capacity_zero"

    return {
        "enabled": request.isa_enabled,
        "usable": isa_usable,
        "type": request.isa_type,
        "account_exists": request.isa_account_exists,
        "account_age_years": safe_round(request.isa_account_age_years, 2),
        "can_open_new": can_open_new,
        "existing_account_usable": request.isa_existing_account_usable,
        "recent_3yr_comprehensive_taxed": (
            request.isa_recent_3yr_comprehensive_taxed
        ),
        "annual_contribution_limit": ISA_ANNUAL_CONTRIBUTION_LIMIT,
        "total_contribution_limit": ISA_TOTAL_CONTRIBUTION_LIMIT,
        "earned_capacity": safe_round(earned_capacity, 0),
        "cumulative_contribution": safe_round(
            request.isa_cumulative_contribution, 0
        ),
        "calculated_remaining_capacity": safe_round(calculated_capacity, 0),
        "remaining_capacity_input": safe_round(request.isa_remaining_capacity, 0),
        "remaining_capacity_override": safe_round(
            request.isa_remaining_capacity_override, 0
        )
        if request.isa_remaining_capacity_override is not None
        else None,
        "remaining_capacity": safe_round(remaining_capacity, 0),
        "years_until_liquid": safe_round(years_until_liquid, 2),
        "reason": reason,
    }


def calculate_irp_status(request: PortfolioRequest) -> Dict[str, Any]:
    calculated_capacity = max(
        IRP_PENSION_COMBINED_TAX_CREDIT_LIMIT
        - request.irp_current_year_contribution,
        0.0,
    )
    manual_capacity = request.irp_remaining_tax_credit_capacity
    if request.irp_remaining_tax_credit_capacity_override is not None:
        manual_capacity = request.irp_remaining_tax_credit_capacity_override

    remaining_capacity = min(calculated_capacity, manual_capacity)
    irp_usable = request.irp_enabled and request.irp_eligible and remaining_capacity > 0

    if not irp_usable:
        remaining_capacity = 0.0

    if irp_usable:
        reason = "irp_tax_credit_capacity_available"
    elif not request.irp_enabled:
        reason = "irp_disabled_by_input"
    elif not request.irp_eligible:
        reason = "irp_not_eligible"
    else:
        reason = "irp_remaining_capacity_zero"

    return {
        "enabled": request.irp_enabled,
        "eligible": request.irp_eligible,
        "usable": irp_usable,
        "annual_tax_credit_limit": IRP_PENSION_COMBINED_TAX_CREDIT_LIMIT,
        "current_year_contribution": safe_round(
            request.irp_current_year_contribution, 0
        ),
        "calculated_remaining_capacity": safe_round(calculated_capacity, 0),
        "remaining_tax_credit_capacity_input": safe_round(
            request.irp_remaining_tax_credit_capacity, 0
        ),
        "remaining_capacity_override": safe_round(
            request.irp_remaining_tax_credit_capacity_override, 0
        )
        if request.irp_remaining_tax_credit_capacity_override is not None
        else None,
        "remaining_tax_credit_capacity": safe_round(remaining_capacity, 0),
        "tax_credit_rate": request.irp_tax_credit_rate,
        "years_until_access": safe_round(request.irp_years_until_access, 2),
        "reason": reason,
    }


def allocate_account_buckets(
    weights: Dict[str, float],
    total_asset: float,
    request: PortfolioRequest,
) -> Dict[str, Any]:
    weights = normalize_weights(weights)
    remaining_amounts = {
        asset: weights.get(asset, 0.0) * total_asset for asset in ASSET_TICKERS.keys()
    }

    isa_status = calculate_isa_status(request)
    irp_status = calculate_irp_status(request)

    isa_alloc = {asset: 0.0 for asset in ASSET_TICKERS.keys()}
    irp_alloc = {asset: 0.0 for asset in ASSET_TICKERS.keys()}
    taxable_alloc = {asset: 0.0 for asset in ASSET_TICKERS.keys()}

    if isa_status["usable"]:
        remaining_isa_capacity = isa_status["remaining_capacity"]
        for asset in ISA_PRIORITY_ASSETS:
            amount = min(remaining_amounts.get(asset, 0.0), remaining_isa_capacity)
            if amount > 0:
                isa_alloc[asset] += amount
                remaining_amounts[asset] -= amount
                remaining_isa_capacity -= amount
            if remaining_isa_capacity <= 0:
                break

    if irp_status["usable"]:
        remaining_irp_capacity = irp_status["remaining_tax_credit_capacity"]
        for asset in IRP_PRIORITY_ASSETS:
            amount = min(remaining_amounts.get(asset, 0.0), remaining_irp_capacity)
            if amount > 0:
                irp_alloc[asset] += amount
                remaining_amounts[asset] -= amount
                remaining_irp_capacity -= amount
            if remaining_irp_capacity <= 0:
                break

    for asset, amount in remaining_amounts.items():
        taxable_alloc[asset] = max(amount, 0.0)

    isa_total = sum(isa_alloc.values())
    irp_total = sum(irp_alloc.values())
    taxable_total = sum(taxable_alloc.values())

    isa_locked_amount = isa_total if isa_status["years_until_liquid"] > 0 else 0.0
    irp_tax_credit = min(
        irp_total,
        irp_status["remaining_tax_credit_capacity"],
    ) * request.irp_tax_credit_rate

    isa_tax_free_limit = (
        ISA_GENERAL_TAX_FREE_LIMIT
        if request.isa_type == "general"
        else ISA_SEOGMIN_TAX_FREE_LIMIT
    )

    return {
        "isa": {
            **isa_status,
            "allocated_amount": safe_round(isa_total, 0),
            "used_capacity": safe_round(isa_total, 0),
            "utilization_ratio": safe_round(
                isa_total / isa_status["remaining_capacity"], 6
            )
            if isa_status["remaining_capacity"] > 0
            else 0.0,
            "locked_amount_for_liquidity": safe_round(isa_locked_amount, 0),
            "tax_free_limit": isa_tax_free_limit,
            "low_tax_rate_after_tax_free_limit": ISA_LOW_TAX_RATE,
            "rule_keys": [
                "isa_general_tax_free_limit",
                "isa_seogmin_tax_free_limit",
                "isa_low_tax_rate",
                "isa_mandatory_holding_years",
                "isa_annual_contribution_limit",
                "isa_total_contribution_limit",
            ],
            "allocations": {
                asset: {
                    "label": ASSET_NAMES_KR[asset],
                    "amount": safe_round(amount, 0),
                    "weight_in_total_asset": safe_round(amount / total_asset, 6),
                }
                for asset, amount in isa_alloc.items()
                if amount > 0
            },
        },
        "irp": {
            **irp_status,
            "allocated_amount": safe_round(irp_total, 0),
            "used_capacity": safe_round(irp_total, 0),
            "utilization_ratio": safe_round(
                irp_total / irp_status["remaining_tax_credit_capacity"], 6
            )
            if irp_status["remaining_tax_credit_capacity"] > 0
            else 0.0,
            "estimated_tax_credit": safe_round(irp_tax_credit, 0),
            "rule_keys": [
                "irp_tax_credit_limit",
                "irp_tax_credit_rate_high_income",
                "irp_tax_credit_rate_low_income",
            ],
            "allocations": {
                asset: {
                    "label": ASSET_NAMES_KR[asset],
                    "amount": safe_round(amount, 0),
                    "weight_in_total_asset": safe_round(amount / total_asset, 6),
                }
                for asset, amount in irp_alloc.items()
                if amount > 0
            },
        },
        "taxable_account": {
            "allocated_amount": safe_round(taxable_total, 0),
            "allocations": {
                asset: {
                    "label": ASSET_NAMES_KR[asset],
                    "amount": safe_round(amount, 0),
                    "weight_in_total_asset": safe_round(amount / total_asset, 6),
                }
                for asset, amount in taxable_alloc.items()
                if amount > 0
            },
        },
    }

def estimate_tax_saving_effect(
    weights: Dict[str, float],
    expected_returns: pd.Series,
    total_asset: float,
    request: PortfolioRequest,
    account_buckets: Dict[str, Any],
) -> Dict[str, Any]:
    weights = normalize_weights(weights)
    taxable_income_before = estimate_taxable_financial_income(
        weights, expected_returns, total_asset
    )

    irp_tax_credit = account_buckets["irp"]["estimated_tax_credit"]

    income_shifted_to_isa = 0.0
    for asset, info in account_buckets["isa"]["allocations"].items():
        if asset not in expected_returns.index:
            continue
        asset_amount = safe_float(info["amount"])
        asset_weight = asset_amount / total_asset if total_asset > 0 else 0.0
        income_shifted_to_isa += estimate_income_profit_for_asset(
            asset=asset,
            weight=asset_weight,
            expected_return=float(expected_returns[asset]),
            total_asset=total_asset,
        )

    isa_tax_free_limit = (
        ISA_GENERAL_TAX_FREE_LIMIT if request.isa_type == "general" else ISA_SEOGMIN_TAX_FREE_LIMIT
    )
    isa_tax_free_income = min(income_shifted_to_isa, isa_tax_free_limit)
    isa_low_tax_income = max(income_shifted_to_isa - isa_tax_free_limit, 0.0)

    isa_tax_saving = isa_tax_free_income * DEFAULT_WITHHOLDING_TAX_RATE + isa_low_tax_income * max(
        DEFAULT_WITHHOLDING_TAX_RATE - ISA_LOW_TAX_RATE, 0.0
    )

    estimated_total_tax_saving = isa_tax_saving + irp_tax_credit

    return {
        "taxable_financial_income_before_account_allocation": safe_round(
            taxable_income_before, 0
        ),
        "estimated_income_shifted_to_isa": safe_round(income_shifted_to_isa, 0),
        "isa_tax_free_income_used": safe_round(isa_tax_free_income, 0),
        "isa_low_tax_income_used": safe_round(isa_low_tax_income, 0),
        "estimated_isa_tax_saving": safe_round(isa_tax_saving, 0),
        "estimated_irp_tax_credit": safe_round(irp_tax_credit, 0),
        "estimated_total_tax_saving": safe_round(estimated_total_tax_saving, 0),
        "note": "절세제안은 제외하고, 세후수익률 반영을 위한 간이 절세효과만 계산.",
    }


def calculate_after_tax_return(
    weights: Dict[str, float],
    expected_returns: pd.Series,
    total_asset: float,
    request: PortfolioRequest,
) -> Tuple[float, Dict[str, Any]]:
    weights = normalize_weights(weights)
    gross_profit = 0.0
    withholding_tax = 0.0

    for asset, weight in weights.items():
        if asset not in expected_returns.index:
            continue

        asset_expected_return = safe_float(expected_returns[asset])
        asset_profit = weight * total_asset * asset_expected_return
        gross_profit += asset_profit

        income_profit = estimate_income_profit_for_asset(
            asset=asset,
            weight=weight,
            expected_return=asset_expected_return,
            total_asset=total_asset,
        )
        if income_profit > 0:
            withholding_tax += income_profit * DEFAULT_WITHHOLDING_TAX_RATE

    taxable_financial_income = estimate_taxable_financial_income(
        weights, expected_returns, total_asset
    )
    comprehensive_tax_status = calculate_financial_income_comprehensive_tax_status(
        taxable_financial_income
    )

    overseas_tax = estimate_overseas_stock_capital_gains_tax(
        weights=weights,
        expected_returns=expected_returns,
        total_asset=total_asset,
        realized_gain_rate=request.overseas_stock_realized_gain_rate,
    )

    account_buckets = allocate_account_buckets(weights, total_asset, request)
    tax_saving_effect = estimate_tax_saving_effect(
        weights=weights,
        expected_returns=expected_returns,
        total_asset=total_asset,
        request=request,
        account_buckets=account_buckets,
    )

    # 금융소득종합과세 초과분에 대한 추가 부담 간이 추정
    excess_financial_income = comprehensive_tax_status["excess_over_threshold"]
    additional_comprehensive_tax = excess_financial_income * max(
        request.marginal_income_tax_rate - DEFAULT_WITHHOLDING_TAX_RATE,
        0.0,
    )

    total_tax_before_saving = (
        withholding_tax + overseas_tax["estimated_tax"] + additional_comprehensive_tax
    )
    total_tax_after_saving = max(
        total_tax_before_saving - tax_saving_effect["estimated_total_tax_saving"], 0.0
    )

    after_tax_profit = gross_profit - total_tax_after_saving
    after_tax_return = after_tax_profit / total_asset if total_asset > 0 else 0.0

    tax_breakdown = {
        "gross_profit": safe_round(gross_profit, 0),
        "withholding_tax_estimate": safe_round(withholding_tax, 0),
        "financial_income_comprehensive_tax": comprehensive_tax_status,
        "additional_comprehensive_tax_estimate": safe_round(additional_comprehensive_tax, 0),
        "overseas_stock_capital_gains_tax": overseas_tax,
        "account_buckets": account_buckets,
        "tax_saving_effect": tax_saving_effect,
        "total_tax_before_saving": safe_round(total_tax_before_saving, 0),
        "total_tax_after_saving": safe_round(total_tax_after_saving, 0),
        "after_tax_profit": safe_round(after_tax_profit, 0),
        "after_tax_return": safe_round(after_tax_return, 6),
        "tax_disclaimer": "세금 계산은 프로젝트용 간이 추정. 실제 세액은 전체 소득, 실현손익, 상품별 요건에 따라 달라짐.",
    }

    return float(after_tax_return), tax_breakdown

# ============================================================
# 8. 지표 계산
# ============================================================


def calculate_mdd(portfolio_daily_returns: pd.Series) -> float:
    cumulative = (1 + portfolio_daily_returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    return float(drawdown.min())


def calculate_sortino(
    portfolio_daily_returns: pd.Series,
    annual_return: float,
    risk_free_rate: float,
) -> float:
    daily_target = (1 + risk_free_rate) ** (1 / TRADING_DAYS) - 1
    downside_returns = portfolio_daily_returns[portfolio_daily_returns < daily_target]

    if len(downside_returns) == 0:
        return SORTINO_NO_DOWNSIDE_CAP

    downside_deviation = downside_returns.std() * np.sqrt(TRADING_DAYS)

    if downside_deviation < 1e-8 or np.isnan(downside_deviation):
        return SORTINO_NO_DOWNSIDE_CAP if annual_return > risk_free_rate else 0.0

    return float((annual_return - risk_free_rate) / downside_deviation)


def calculate_historical_var(
    portfolio_daily_returns: pd.Series,
    confidence_level: float = 0.95,
) -> Dict[str, Any]:
    if portfolio_daily_returns.empty:
        return {
            "confidence_level": confidence_level,
            "daily_return_quantile": 0.0,
            "daily_loss": 0.0,
            "annualized_loss_approx": 0.0,
            "method": "historical",
        }

    q = 1.0 - confidence_level
    daily_quantile = float(portfolio_daily_returns.quantile(q))
    daily_loss = max(-daily_quantile, 0.0)
    annualized_loss = daily_loss * np.sqrt(TRADING_DAYS)

    return {
        "confidence_level": confidence_level,
        "daily_return_quantile": safe_round(daily_quantile, 6),
        "daily_loss": safe_round(daily_loss, 6),
        "annualized_loss_approx": safe_round(annualized_loss, 6),
        "method": "historical_5_percentile",
    }


def calculate_risk_contribution(
    assets: List[str],
    weights_array: np.ndarray,
    cov_matrix: pd.DataFrame,
) -> Dict[str, Any]:
    if len(assets) == 0:
        return {
            "by_asset": {},
            "max_share": 0.0,
            "hhi": 0.0,
            "method": "variance_contribution",
        }

    selected_cov = cov_matrix.reindex(index=assets, columns=assets).fillna(0.0)
    cov_values = selected_cov.values
    variance = float(weights_array.T @ cov_values @ weights_array)

    if variance <= 1e-12 or not np.isfinite(variance):
        zero_map = {asset: 0.0 for asset in assets}
        return {
            "by_asset": zero_map,
            "max_share": 0.0,
            "hhi": 0.0,
            "method": "variance_contribution",
        }

    marginal = cov_values @ weights_array
    raw_contribution = weights_array * marginal
    shares = raw_contribution / variance
    positive_shares = np.maximum(shares, 0.0)

    return {
        "by_asset": {
            asset: safe_round(value, 6) for asset, value in zip(assets, shares)
        },
        "max_share": safe_round(float(positive_shares.max()), 6),
        "hhi": safe_round(float(np.square(positive_shares).sum()), 6),
        "method": "variance_contribution",
    }


def evaluate_selection_risk_controls(
    metrics: Dict[str, Any],
    client_risk_profile: str,
) -> Dict[str, Any]:
    rule = SELECTION_RISK_CONTROLS[client_risk_profile]
    var_loss = metrics["historical_var_95_daily_loss"]
    max_risk_share = metrics["risk_contribution_max_share"]

    checks = {
        "historical_var_95": (
            var_loss <= rule["historical_var_95_daily_max_loss"]
        ),
        "risk_contribution": (
            max_risk_share <= rule["risk_contribution_max_share"]
        ),
    }

    return {
        "profile": client_risk_profile,
        "passed": all(checks.values()),
        "checks": checks,
        "thresholds": rule,
    }


def calculate_asset_group_weights(weights: Dict[str, float]) -> Dict[str, float]:
    stock_weight = sum(weights.get(asset, 0.0) for asset in STOCK_ASSETS)
    bond_cash_weight = sum(weights.get(asset, 0.0) for asset in BOND_CASH_ASSETS)
    alternative_weight = sum(weights.get(asset, 0.0) for asset in ALTERNATIVE_ASSETS)

    return {
        "stock_weight": float(stock_weight),
        "bond_cash_weight": float(bond_cash_weight),
        "alternative_weight": float(alternative_weight),
    }


def calculate_portfolio_duration(weights: Dict[str, float]) -> float:
    bond_weight = sum(weights.get(asset, 0.0) for asset in BOND_ASSETS)
    if bond_weight <= 1e-8:
        return 0.0

    weighted_duration = sum(
        weights.get(asset, 0.0) * ASSET_DURATION_YEARS.get(asset, 0.0)
        for asset in BOND_ASSETS
    )

    return float(weighted_duration / bond_weight)


def target_duration_by_horizon(investment_horizon_years: int) -> float:
    if investment_horizon_years <= 3:
        return 1.5
    if investment_horizon_years <= 7:
        return 4.0
    return 7.0


def calculate_duration_fit_score(portfolio_duration: float, target_duration: float) -> float:
    if target_duration <= 0:
        return 1.0
    diff_ratio = abs(portfolio_duration - target_duration) / target_duration
    return cap01(1 - diff_ratio)


def calculate_isa_locked_amount(
    weights: Dict[str, float],
    total_asset: float,
    request: PortfolioRequest,
) -> float:
    if not request.isa_enabled or request.isa_years_until_liquid <= 0:
        return 0.0

    account_buckets = allocate_account_buckets(weights, total_asset, request)
    return float(account_buckets["isa"]["locked_amount_for_liquidity"])


def calculate_liquidity_coverage(
    weights: Dict[str, float],
    total_asset: float,
    unique_need_amount: float,
    request: PortfolioRequest,
) -> float:
    if unique_need_amount <= 0:
        return 1.0

    liquid_weight = sum(weights.get(asset, 0.0) for asset in CASH_LIKE_ASSETS)
    liquid_amount = liquid_weight * total_asset

    isa_locked_amount = calculate_isa_locked_amount(weights, total_asset, request)
    usable_liquid_amount = max(liquid_amount - isa_locked_amount, 0.0)

    return float(usable_liquid_amount / unique_need_amount)


def calculate_stress_test(
    weights: Dict[str, float],
    request: PortfolioRequest,
) -> Dict[str, Any]:
    interest_rate_effect = 0.0

    for asset in INTEREST_RATE_SENSITIVE_ASSETS:
        asset_weight = weights.get(asset, 0.0)
        duration = ASSET_DURATION_YEARS.get(asset, 0.0)
        interest_rate_effect += asset_weight * (-duration * request.stress_interest_rate_shock)

    fx_effect = (
        sum(weights.get(asset, 0.0) for asset in FX_SENSITIVE_ASSETS) * request.stress_fx_shock
    )

    total_stress_return = interest_rate_effect + fx_effect
    estimated_loss_ratio = min(total_stress_return, 0.0)

    return {
        "interest_rate_shock": request.stress_interest_rate_shock,
        "fx_shock": request.stress_fx_shock,
        "interest_rate_effect": round(float(interest_rate_effect), 6),
        "fx_effect": round(float(fx_effect), 6),
        "total_stress_return": round(float(total_stress_return), 6),
        "estimated_loss_ratio": round(float(estimated_loss_ratio), 6),
        "method": "금리효과는 -듀레이션×금리변화, 환율효과는 외화노출자산비중×환율변화로 단순 추정.",
    }


def calculate_metrics(
    weights: Dict[str, float],
    returns: pd.DataFrame,
    expected_returns: pd.Series,
    request: PortfolioRequest,
    cov_matrix: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    weights = normalize_weights(weights)
    validate_required_assets_available(weights, list(returns.columns), "portfolio_weights")

    assets = [
        asset
        for asset in weights.keys()
        if asset in returns.columns and weights[asset] > 1e-12
    ]
    if not assets:
        raise ValueError("수익률 데이터에 포함된 자산의 비중이 없습니다.")

    w = np.array([weights[asset] for asset in assets], dtype=float)
    w = w / w.sum()

    selected_returns = returns[assets]
    selected_expected_returns = expected_returns.reindex(assets).fillna(0.0)

    if cov_matrix is None:
        selected_cov_matrix = selected_returns.cov() * TRADING_DAYS
    else:
        selected_cov_matrix = cov_matrix.reindex(index=assets, columns=assets).fillna(0.0)

    portfolio_return = float(np.dot(w, selected_expected_returns))
    variance = float(np.dot(w.T, np.dot(selected_cov_matrix.values, w)))
    portfolio_volatility = float(np.sqrt(max(variance, 0.0)))

    portfolio_daily_returns = selected_returns.dot(w)

    if portfolio_volatility < 1e-8 or np.isnan(portfolio_volatility):
        sharpe = 0.0
    else:
        sharpe = float((portfolio_return - request.risk_free_rate) / portfolio_volatility)

    sortino = calculate_sortino(
        portfolio_daily_returns=portfolio_daily_returns,
        annual_return=portfolio_return,
        risk_free_rate=request.risk_free_rate,
    )

    mdd = calculate_mdd(portfolio_daily_returns)

    after_tax_return, tax_breakdown = calculate_after_tax_return(
        weights=weights,
        expected_returns=expected_returns,
        total_asset=request.total_asset,
        request=request,
    )

    taxable_financial_income = estimate_taxable_financial_income(
        weights=weights,
        expected_returns=expected_returns,
        total_asset=request.total_asset,
    )

    liquidity_coverage = calculate_liquidity_coverage(
        weights=weights,
        total_asset=request.total_asset,
        unique_need_amount=request.unique_need_amount,
        request=request,
    )

    group_weights = calculate_asset_group_weights(weights)

    portfolio_duration = calculate_portfolio_duration(weights)
    target_duration = target_duration_by_horizon(request.investment_horizon_years)
    duration_fit_score = calculate_duration_fit_score(portfolio_duration, target_duration)

    stress_test = calculate_stress_test(weights, request)
    historical_var = calculate_historical_var(portfolio_daily_returns)
    risk_contribution = calculate_risk_contribution(
        assets=assets,
        weights_array=w,
        cov_matrix=selected_cov_matrix,
    )

    temp_metrics = {
        "expected_return": portfolio_return,
        "after_tax_return": after_tax_return,
        "volatility": portfolio_volatility,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "mdd": mdd,
        "taxable_financial_income": taxable_financial_income,
        "liquidity_coverage": liquidity_coverage,
        "stock_weight": group_weights["stock_weight"],
        "bond_cash_weight": group_weights["bond_cash_weight"],
        "alternative_weight": group_weights["alternative_weight"],
        "historical_var_95_daily_loss": historical_var["daily_loss"],
        "risk_contribution_max_share": risk_contribution["max_share"],
    }

    risk_level = classify_portfolio_by_guidelines(temp_metrics)
    selection_risk_control = evaluate_selection_risk_controls(
        temp_metrics,
        request.risk_profile,
    )

    return {
        "expected_return": safe_round(portfolio_return, 6),
        "after_tax_return": safe_round(after_tax_return, 6),
        "volatility": safe_round(portfolio_volatility, 6),
        "sharpe_ratio": safe_round(sharpe, 6),
        "sortino_ratio": safe_round(sortino, 6),
        "mdd": safe_round(mdd, 6),
        "taxable_financial_income": safe_round(taxable_financial_income, 0),
        "liquidity_coverage": safe_round(liquidity_coverage, 6),
        "stock_weight": safe_round(group_weights["stock_weight"], 6),
        "bond_cash_weight": safe_round(group_weights["bond_cash_weight"], 6),
        "alternative_weight": safe_round(group_weights["alternative_weight"], 6),
        "portfolio_duration": safe_round(portfolio_duration, 6),
        "target_duration": safe_round(target_duration, 6),
        "duration_fit_score": safe_round(duration_fit_score, 6),
        "historical_var_95": historical_var,
        "historical_var_95_daily_loss": historical_var["daily_loss"],
        "risk_contribution": risk_contribution,
        "risk_contribution_max_share": risk_contribution["max_share"],
        "selection_risk_control": selection_risk_control,
        "stress_test": stress_test,
        "risk_level": risk_level,
        "risk_level_label": RISK_LEVEL_NAME.get(risk_level, "기준 미충족"),
        "tax_breakdown": tax_breakdown,
    }


def calculate_cumulative_returns(
    weights: Dict[str, float],
    returns: pd.DataFrame,
) -> List[Dict[str, Any]]:
    weights = normalize_weights(weights)
    validate_required_assets_available(weights, list(returns.columns), "portfolio_weights")

    assets = [
        asset
        for asset in weights.keys()
        if asset in returns.columns and weights[asset] > 1e-12
    ]
    w = np.array([weights[asset] for asset in assets], dtype=float)
    w = w / w.sum()

    portfolio_daily_returns = returns[assets].dot(w)
    cumulative = (1 + portfolio_daily_returns).cumprod() - 1

    return [
        {
            "date": date.strftime("%Y-%m-%d"),
            "value": safe_round(value, 6),
        }
        for date, value in cumulative.items()
    ]


# ============================================================
# 9. 기준표 평가
# ============================================================


def evaluate_guideline_detail(metrics: Dict[str, Any], profile: str) -> Dict[str, Any]:
    rule = GUIDELINE_RULES[profile]

    expected_return = metrics["expected_return"]
    after_tax_return = metrics["after_tax_return"]
    volatility = metrics["volatility"]
    sharpe = metrics["sharpe_ratio"]
    sortino = metrics["sortino_ratio"]
    mdd = metrics["mdd"]
    taxable_income = metrics["taxable_financial_income"]
    liquidity_coverage = metrics["liquidity_coverage"]
    stock_weight = metrics["stock_weight"]
    bond_cash_weight = metrics["bond_cash_weight"]
    alternative_weight = metrics["alternative_weight"]

    tax_gap = expected_return - after_tax_return

    hard_checks = {}
    soft_checks = {}

    hard_checks["volatility"] = volatility <= rule["volatility_max"]
    hard_checks["mdd"] = mdd >= rule["mdd_min"]
    hard_checks["liquidity_coverage"] = liquidity_coverage >= rule["liquidity_coverage_min"]
    hard_checks["stock_weight"] = stock_weight <= rule["stock_weight_max"]
    hard_checks["alternative_weight"] = alternative_weight <= rule["alternative_weight_max"]
    hard_checks["bond_cash_weight"] = bond_cash_weight >= rule["bond_cash_weight_min"]

    soft_checks["expected_return_min"] = expected_return >= rule["expected_return_min"]

    if rule["expected_return_max"] is not None:
        soft_checks["expected_return_max"] = expected_return <= rule["expected_return_max"]
    else:
        soft_checks["expected_return_max"] = True

    soft_checks["sharpe"] = sharpe >= rule["sharpe_min"]

    if rule["sortino_min"] is not None:
        soft_checks["sortino"] = sortino >= rule["sortino_min"]
    else:
        soft_checks["sortino"] = True

    if rule["tax_gap_max"] is not None:
        soft_checks["tax_gap"] = tax_gap <= rule["tax_gap_max"]
    else:
        soft_checks["tax_gap"] = True

    if rule["taxable_income_max"] is not None:
        soft_checks["taxable_financial_income"] = taxable_income <= rule["taxable_income_max"]
    else:
        soft_checks["taxable_financial_income"] = True

    if rule["after_tax_retention_min"] is not None:
        if expected_return <= 0:
            soft_checks["after_tax_retention"] = False
        else:
            soft_checks["after_tax_retention"] = (
                after_tax_return / expected_return >= rule["after_tax_retention_min"]
            )
    else:
        soft_checks["after_tax_retention"] = True

    hard_passed = all(hard_checks.values())
    soft_passed_count = sum(1 for passed in soft_checks.values() if passed)
    soft_total_count = len(soft_checks)
    soft_pass_ratio = soft_passed_count / soft_total_count if soft_total_count > 0 else 1.0

    return {
        "profile": profile,
        "level": rule["level"],
        "label": rule["label"],
        "passed": hard_passed,
        "hard_checks": hard_checks,
        "soft_checks": soft_checks,
        "soft_pass_ratio": round(float(soft_pass_ratio), 4),
    }


def check_guideline(metrics: Dict[str, Any], profile: str) -> bool:
    return evaluate_guideline_detail(metrics, profile)["passed"]


def classify_portfolio_by_guidelines(metrics: Dict[str, Any]) -> Optional[int]:
    if check_guideline(metrics, "conservative"):
        return 1
    if check_guideline(metrics, "balanced"):
        return 2
    if check_guideline(metrics, "aggressive"):
        return 3
    return None


def is_suitable_for_client(metrics: Dict[str, Any], client_risk_profile: str) -> bool:
    client_level = CLIENT_RISK_LEVEL[client_risk_profile]
    portfolio_level = metrics["risk_level"]

    if portfolio_level is None:
        return False

    return portfolio_level <= client_level


# ============================================================
# 10. 포트폴리오 생성 / 점수화
# ============================================================


def generate_random_weights(
    assets: Optional[List[str]] = None,
    rng: Optional[np.random.Generator] = None,
) -> Dict[str, float]:
    assets = assets or list(ASSET_TICKERS.keys())
    if not assets:
        raise ValueError("랜덤 포트폴리오를 생성할 자산 목록이 비어 있습니다.")

    rng = rng or np.random.default_rng()
    alpha = np.ones(len(assets))
    sampled = rng.dirichlet(alpha)
    return {asset: float(weight) for asset, weight in zip(assets, sampled)}


def apply_unique_constraint(
    base_weights: Dict[str, float],
    total_asset: float,
    unique_need_amount: float,
    unique_asset: str,
) -> Dict[str, float]:
    unique_asset = validate_unique_asset(unique_asset)
    unique_ratio = min(max(unique_need_amount / total_asset, 0.0), 1.0)
    investable_ratio = 1.0 - unique_ratio

    final_weights = {asset: 0.0 for asset in ASSET_TICKERS.keys()}
    final_weights[unique_asset] += unique_ratio

    normalized_base = normalize_weights(base_weights)

    for asset, weight in normalized_base.items():
        final_weights[asset] += weight * investable_ratio

    return normalize_weights(final_weights)


def build_selection_rank_tuple(metrics: Dict[str, Any]) -> Tuple[Any, ...]:
    risk_control = metrics.get("selection_risk_control", {})
    risk_control_passed = bool(risk_control.get("passed", False))
    var_loss = safe_float(metrics.get("historical_var_95_daily_loss"))
    rc_max = safe_float(metrics.get("risk_contribution_max_share"))

    return (
        1 if risk_control_passed else 0,
        safe_float(metrics.get("after_tax_return")),
        safe_float(metrics.get("expected_return")),
        safe_float(metrics.get("sharpe_ratio")),
        -var_loss,
        -rc_max,
        safe_float(metrics.get("mdd")),
    )


def build_selection_summary(metrics: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ranking_basis": SELECTION_RANKING_BASIS,
        "risk_control": metrics.get("selection_risk_control", {}),
        "primary_objective": "after_tax_return_desc",
        "tie_breakers": [
            "expected_return_desc",
            "sharpe_ratio_desc",
            "historical_var_95_asc",
            "risk_contribution_max_share_asc",
            "mdd_desc",
        ],
        "note": (
            "8th는 임의 scoring weight 합산식을 쓰지 않고, "
            "적합성·VaR·ERC 필터를 통과한 후보를 "
            "세후수익률 중심의 우선순위로 정렬한다."
        ),
    }


def calculate_portfolio_return_series(
    weights: Dict[str, float],
    returns: pd.DataFrame,
) -> pd.Series:
    weights = normalize_weights(weights)
    validate_required_assets_available(weights, list(returns.columns), "portfolio_weights")
    assets = [
        asset
        for asset in weights.keys()
        if asset in returns.columns and weights[asset] > 1e-12
    ]
    w = np.array([weights[asset] for asset in assets], dtype=float)
    w = w / w.sum()
    return returns[assets].dot(w)


def calculate_portfolio_return_correlation(
    weights_a: Dict[str, float],
    weights_b: Dict[str, float],
    returns: pd.DataFrame,
    series_a: Optional[pd.Series] = None,
) -> float:
    if series_a is None:
        series_a = calculate_portfolio_return_series(weights_a, returns)
    series_b = calculate_portfolio_return_series(weights_b, returns)
    corr = series_a.corr(series_b)

    if corr is None or np.isnan(corr):
        return 1.0

    return float(corr)


def find_recommended_portfolios(
    returns: pd.DataFrame,
    expected_returns: pd.Series,
    request: PortfolioRequest,
    cov_matrix: Optional[pd.DataFrame] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    rng = np.random.default_rng(request.random_seed)

    candidates = []
    generated_count = request.num_simulations
    guideline_pass_count = 0
    suitable_count = 0
    risk_control_pass_count = 0

    available_assets = [asset for asset in ASSET_TICKERS.keys() if asset in returns.columns]
    validate_required_assets_available(
        {request.unique_asset: 1.0},
        available_assets,
        "unique_asset",
    )

    for _ in range(request.num_simulations):
        base_weights = generate_random_weights(assets=available_assets, rng=rng)

        final_weights = apply_unique_constraint(
            base_weights=base_weights,
            total_asset=request.total_asset,
            unique_need_amount=request.unique_need_amount,
            unique_asset=request.unique_asset,
        )

        metrics = calculate_metrics(
            weights=final_weights,
            returns=returns,
            expected_returns=expected_returns,
            request=request,
            cov_matrix=cov_matrix,
        )

        if metrics["risk_level"] is not None:
            guideline_pass_count += 1

        if not is_suitable_for_client(metrics, request.risk_profile):
            continue

        suitable_count += 1
        if metrics["selection_risk_control"]["passed"]:
            risk_control_pass_count += 1

        selection_rank = build_selection_rank_tuple(metrics)

        candidates.append(
            {
                "weights": final_weights,
                "metrics": metrics,
                "selection_rank": selection_rank,
                "selection_summary": build_selection_summary(metrics),
            }
        )

    if len(candidates) == 0:
        raise RuntimeError(
            "기준표와 고객 위험성향 기준을 통과한 포트폴리오가 없습니다. "
            "num_simulations를 늘리거나 기준표를 재검토해야 합니다."
        )

    candidates = sorted(candidates, key=lambda x: x["selection_rank"], reverse=True)

    recommendation_1 = candidates[0]
    recommendation_2 = None
    recommendation_1_series = calculate_portfolio_return_series(
        recommendation_1["weights"],
        returns,
    )

    for candidate in candidates[1:]:
        corr = calculate_portfolio_return_correlation(
            recommendation_1["weights"],
            candidate["weights"],
            returns,
            series_a=recommendation_1_series,
        )

        if corr <= SECOND_PORTFOLIO_MAX_CORRELATION:
            candidate["correlation_with_recommended_1"] = corr
            recommendation_2 = candidate
            break

    if recommendation_2 is None:
        recommendation_2 = candidates[1] if len(candidates) > 1 else candidates[0]
        recommendation_2["correlation_with_recommended_1"] = calculate_portfolio_return_correlation(
            recommendation_1["weights"],
            recommendation_2["weights"],
            returns,
            series_a=recommendation_1_series,
        )

    search_summary = {
        "generated_portfolios": generated_count,
        "guideline_pass_portfolios": guideline_pass_count,
        "suitable_portfolios": suitable_count,
        "risk_control_pass_portfolios": risk_control_pass_count,
        "filtered_out_portfolios": generated_count - suitable_count,
        "selection_method": "suitability_filter_var_erc_after_tax_ranking",
        "random_seed": request.random_seed,
    }

    return [recommendation_1, recommendation_2], search_summary

# ============================================================
# 11. 응답 생성
# ============================================================


def build_guideline_report(metrics: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "conservative": evaluate_guideline_detail(metrics, "conservative"),
        "balanced": evaluate_guideline_detail(metrics, "balanced"),
        "aggressive": evaluate_guideline_detail(metrics, "aggressive"),
    }


def build_portfolio_response(
    name: str,
    api_key: str,
    weights: Dict[str, float],
    returns: pd.DataFrame,
    expected_returns: pd.Series,
    request: PortfolioRequest,
    score: Optional[float] = None,
    selection_summary: Optional[Dict[str, Any]] = None,
    correlation_with_recommended_1: Optional[float] = None,
    cov_matrix: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    metrics = calculate_metrics(
        weights=weights,
        returns=returns,
        expected_returns=expected_returns,
        request=request,
        cov_matrix=cov_matrix,
    )

    cumulative_returns = calculate_cumulative_returns(weights, returns)

    response = {
        "api_key": api_key,
        "name": name,
        "weights": {
            asset: {
                "label": ASSET_NAMES_KR.get(asset, asset),
                "ticker": ASSET_TICKERS.get(asset, asset),
                "weight": round(float(weight), 6),
                "amount": round(float(weight) * request.total_asset, 0),
            }
            for asset, weight in weights.items()
        },
        "metrics": {
            # 원형 차트와 5대 지표에서 주로 쓸 값
            "expected_return": metrics["expected_return"],
            "volatility": metrics["volatility"],
            "sharpe_ratio": metrics["sharpe_ratio"],
            "sortino_ratio": metrics["sortino_ratio"],
            "mdd": metrics["mdd"],
            "liquidity_coverage": metrics["liquidity_coverage"],
            # 세후수익률은 절세 최적화 계산 이후 반영되는 값
            "after_tax_return": metrics["after_tax_return"],
            # 포트폴리오 위험/세금/스트레스 정보
            "taxable_financial_income": metrics["taxable_financial_income"],
            "financial_income_comprehensive_tax_status": metrics["tax_breakdown"][
                "financial_income_comprehensive_tax"
            ],
            "risk_level": metrics["risk_level"],
            "risk_level_label": metrics["risk_level_label"],
            "stock_weight": metrics["stock_weight"],
            "bond_cash_weight": metrics["bond_cash_weight"],
            "alternative_weight": metrics["alternative_weight"],
            # 듀레이션은 표시용 6종 지표가 아니라 점수화/내부 설명용
            "portfolio_duration": metrics["portfolio_duration"],
            "target_duration": metrics["target_duration"],
            "duration_fit_score": metrics["duration_fit_score"],
            "historical_var_95": metrics["historical_var_95"],
            "historical_var_95_daily_loss": (
                metrics["historical_var_95_daily_loss"]
            ),
            "risk_contribution": metrics["risk_contribution"],
            "risk_contribution_max_share": metrics["risk_contribution_max_share"],
            "selection_risk_control": metrics["selection_risk_control"],
            "stress_test": metrics["stress_test"],
        },
        "tax_breakdown": metrics["tax_breakdown"],
        "selection_summary": selection_summary
        if selection_summary is not None
        else build_selection_summary(metrics),
        "guideline_report": build_guideline_report(metrics),
        "cumulative_returns": cumulative_returns,
    }

    if score is not None:
        response["score"] = round(float(score), 6)

    if correlation_with_recommended_1 is not None:
        response["correlation_with_recommended_1"] = round(float(correlation_with_recommended_1), 6)

    return response


def build_asset_summary(
    returns: pd.DataFrame,
    expected_returns: pd.Series,
) -> Dict[str, Any]:
    summary = {}

    for asset in returns.columns:
        annual_volatility = returns[asset].std() * np.sqrt(TRADING_DAYS)

        summary[asset] = {
            "label": ASSET_NAMES_KR.get(asset, asset),
            "ticker": ASSET_TICKERS.get(asset, asset),
            "expected_return": safe_round(float(expected_returns[asset]), 6),
            "annual_volatility": safe_round(float(annual_volatility), 6),
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

    return summary


def get_guideline_definition() -> Dict[str, Any]:
    return {
        "verified_basis": {
            "financial_income_threshold": "금융소득종합과세 검토 기준 2,000만 원",
            "overseas_stock_deduction": "해외주식 양도소득 기본공제 250만 원",
            "isa": "ISA 의무보유기간 3년, 일반형 비과세 200만 원, 서민형 비과세 400만 원, 초과분 저율 분리과세 가정",
            "risk_suitability": "투자자성향보다 높은 위험도의 투자성 상품 권유 제한 원칙 반영",
            "risk_factors": "변동성, 최대손실가능성, 기초자산 구성, 유동성, 만기, 환율 변동성 등을 위험 판단 요소로 반영",
        },
        "project_assumptions": {
            "risk_profile_thresholds": "안정형/균형형/공격형별 변동성, MDD, 자산군 비중 한도는 프로젝트용 수치화 기준",
            "selection_risk_controls": SELECTION_RISK_CONTROLS,
            "selection_ranking_basis": SELECTION_RANKING_BASIS,
            "second_portfolio_max_correlation": SECOND_PORTFOLIO_MAX_CORRELATION,
            "duration_source_note": (
                "듀레이션은 채권형 ETF proxy 기준으로만 적용. "
                "주식·리츠·현금·대체자산에는 0년을 적용."
            ),
            "duration_targets": {
                "short_horizon_1_to_3_years": 1.5,
                "middle_horizon_4_to_7_years": 4.0,
                "long_horizon_8_plus_years": 7.0,
            },
            "low_coupon_bond_proxy": "484790.KS를 저쿠폰 장기채 price proxy로 사용",
            "separate_tax_bond_proxy": "439870.KS를 분리과세 장기채 price proxy로 사용",
        },
        "guideline_rules": GUIDELINE_RULES,
    }


def extract_backtest_payload(full_response: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "session_id": full_response["session_id"],
        "backtest": {
            "current": full_response["portfolios"]["current"]["cumulative_returns"],
            "portfolio_a": full_response["portfolios"]["recommended_1"]["cumulative_returns"],
            "portfolio_b": full_response["portfolios"]["recommended_2"]["cumulative_returns"],
        },
        "summary_metrics": {
            "current": full_response["portfolios"]["current"]["metrics"],
            "portfolio_a": full_response["portfolios"]["recommended_1"]["metrics"],
            "portfolio_b": full_response["portfolios"]["recommended_2"]["metrics"],
        },
    }


def build_isa_tax_card(
    account_buckets: Dict[str, Any],
    tax_saving_effect: Dict[str, Any],
) -> Dict[str, Any]:
    isa = account_buckets["isa"]
    remaining_capacity = safe_float(isa.get("remaining_capacity"))
    used_capacity = safe_float(isa.get("used_capacity"))

    return {
        "enabled": isa["enabled"],
        "usable": isa["usable"],
        "account_type": isa["type"],
        "account_exists": isa["account_exists"],
        "account_age_years": isa["account_age_years"],
        "cumulative_contribution": isa["cumulative_contribution"],
        "remaining_capacity": safe_round(remaining_capacity, 0),
        "used_capacity": safe_round(used_capacity, 0),
        "utilization_ratio": isa["utilization_ratio"],
        "tax_free_limit": isa["tax_free_limit"],
        "low_tax_rate": isa["low_tax_rate_after_tax_free_limit"],
        "estimated_tax_saving": tax_saving_effect["estimated_isa_tax_saving"],
        "income_shifted_to_isa": (
            tax_saving_effect["estimated_income_shifted_to_isa"]
        ),
        "status_label": (
            "일반형 ISA 활용" if isa["usable"] else "ISA 활용 불가"
        ),
        "description": "비과세 한도와 초과분 9.9% 분리과세 간이 반영",
        "rule_keys": isa["rule_keys"],
    }


def build_irp_tax_card(
    account_buckets: Dict[str, Any],
    tax_saving_effect: Dict[str, Any],
) -> Dict[str, Any]:
    irp = account_buckets["irp"]

    return {
        "enabled": irp["enabled"],
        "eligible": irp["eligible"],
        "usable": irp["usable"],
        "current_year_contribution": irp["current_year_contribution"],
        "annual_tax_credit_limit": irp["annual_tax_credit_limit"],
        "remaining_tax_credit_capacity": irp["remaining_tax_credit_capacity"],
        "used_capacity": irp["used_capacity"],
        "utilization_ratio": irp["utilization_ratio"],
        "tax_credit_rate": irp["tax_credit_rate"],
        "estimated_tax_credit": tax_saving_effect["estimated_irp_tax_credit"],
        "years_until_access": irp["years_until_access"],
        "status_label": (
            "연금저축·IRP 세액공제 활용"
            if irp["usable"]
            else "IRP 세액공제 활용 불가"
        ),
        "description": "연금계좌 세액공제 한도 내 납입액에 공제율 적용",
        "rule_keys": irp["rule_keys"],
    }


def build_taxable_account_card(
    account_buckets: Dict[str, Any],
    tax_breakdown: Dict[str, Any],
) -> Dict[str, Any]:
    taxable = account_buckets["taxable_account"]

    return {
        "allocated_amount": taxable["allocated_amount"],
        "estimated_tax_after_strategy": tax_breakdown["total_tax_after_saving"],
        "status_label": "잔여 자산 일반계좌 배치",
        "description": "ISA·IRP 한도 적용 후 남은 자산을 일반계좌에 배치",
        "allocations": taxable["allocations"],
    }


def build_tax_optimizer_payload(
    portfolio_key: str,
    portfolio_response: Dict[str, Any],
    request: PortfolioRequest,
) -> Dict[str, Any]:
    tax_breakdown = portfolio_response["tax_breakdown"]
    account_buckets = tax_breakdown["account_buckets"]
    tax_saving_effect = tax_breakdown["tax_saving_effect"]

    gross_profit = safe_float(tax_breakdown["gross_profit"])
    tax_before = safe_float(tax_breakdown["total_tax_before_saving"])
    tax_after = safe_float(tax_breakdown["total_tax_after_saving"])
    tax_saving = max(tax_before - tax_after, 0.0)

    before_after_tax_profit = gross_profit - tax_before
    after_strategy_profit = gross_profit - tax_after
    before_after_tax_return = before_after_tax_profit / request.total_asset
    after_strategy_return = after_strategy_profit / request.total_asset

    return {
        "portfolio_key": portfolio_key,
        "portfolio_name": portfolio_response["name"],
        "total_asset": safe_round(request.total_asset, 0),
        "headline": {
            "annual_tax_saving": safe_round(tax_saving, 0),
            "tax_amount_before": safe_round(tax_before, 0),
            "tax_amount_after": safe_round(tax_after, 0),
            "after_tax_return_before": safe_round(before_after_tax_return, 6),
            "after_tax_return_after": safe_round(after_strategy_return, 6),
            "after_tax_return_improvement_p": safe_round(
                after_strategy_return - before_after_tax_return, 6
            ),
        },
        "account_cards": {
            "isa": build_isa_tax_card(account_buckets, tax_saving_effect),
            "irp": build_irp_tax_card(account_buckets, tax_saving_effect),
            "taxable_account": build_taxable_account_card(
                account_buckets,
                tax_breakdown,
            ),
        },
        "tax_flow": {
            "general_tax_before_strategy": {
                "after_tax_profit": safe_round(before_after_tax_profit, 0),
                "tax_amount": safe_round(tax_before, 0),
            },
            "after_tax_strategy": {
                "after_tax_profit": safe_round(after_strategy_profit, 0),
                "tax_amount": safe_round(tax_after, 0),
                "tax_saving": safe_round(tax_saving, 0),
            },
        },
        "common_tax_rules": get_common_tax_rules(),
        "notes": [
            "세금 계산은 프로젝트용 간이 추정입니다.",
            "실제 세액은 전체 소득·실현손익·상품 요건에 따라 달라집니다.",
        ],
    }


def build_tax_optimizer_map(
    full_response: Dict[str, Any],
    request: PortfolioRequest,
) -> Dict[str, Any]:
    portfolios = full_response["portfolios"]

    return {
        "current": build_tax_optimizer_payload(
            "current",
            portfolios["current"],
            request,
        ),
        "portfolio_a": build_tax_optimizer_payload(
            "portfolio_a",
            portfolios["recommended_1"],
            request,
        ),
        "portfolio_b": build_tax_optimizer_payload(
            "portfolio_b",
            portfolios["recommended_2"],
            request,
        ),
    }


def extract_tax_inputs_payload(full_response: Dict[str, Any]) -> Dict[str, Any]:
    portfolios = full_response["portfolios"]

    return {
        "session_id": full_response["session_id"],
        "tax_inputs": {
            "current": {
                "name": portfolios["current"]["name"],
                "tax_breakdown": portfolios["current"]["tax_breakdown"],
            },
            "portfolio_a": {
                "name": portfolios["recommended_1"]["name"],
                "tax_breakdown": portfolios["recommended_1"]["tax_breakdown"],
            },
            "portfolio_b": {
                "name": portfolios["recommended_2"]["name"],
                "tax_breakdown": portfolios["recommended_2"]["tax_breakdown"],
            },
        },
        "tax_optimizer": full_response.get("tax_optimizer", {}),
        "common_tax_rules": get_common_tax_rules(),
        "note": "절세 화면용 계좌별 카드와 세금 흐름을 함께 반환.",
    }


# ============================================================
# 12. 전체 분석 실행
# ============================================================


def run_analysis_core(request: PortfolioRequest) -> Dict[str, Any]:
    if request.unique_need_amount > request.total_asset:
        raise ValueError("Unique 필요금액은 총자산보다 클 수 없습니다.")

    request.unique_asset = validate_unique_asset(request.unique_asset)
    request.current_weights = canonicalize_weights(request.current_weights)
    request.view_expected_returns = canonicalize_asset_return_map(request.view_expected_returns)

    prices = download_price_data(
        period=request.period,
        cash_return=request.cash_return,
    )
    data_snapshot = prices.attrs.get("data_snapshot", {})

    returns = calculate_daily_returns(prices)
    cov_matrix = returns.cov() * TRADING_DAYS

    expected_returns = calculate_expected_returns(
        returns=returns,
        expected_return_haircut=request.expected_return_haircut,
        enable_black_litterman=request.enable_black_litterman,
        view_expected_returns=request.view_expected_returns,
        view_weight=request.view_weight,
    )

    validate_required_assets_available(
        {request.unique_asset: 1.0},
        list(returns.columns),
        "unique_asset",
    )

    if request.current_weights is None:
        current_weights = get_default_current_weights()
    else:
        validate_weights(request.current_weights)
        validate_required_assets_available(
            request.current_weights,
            list(returns.columns),
            "current_weights",
        )
        current_weights = normalize_weights(request.current_weights)

    recommendations, search_summary = find_recommended_portfolios(
        returns=returns,
        expected_returns=expected_returns,
        request=request,
        cov_matrix=cov_matrix,
    )

    current_response = build_portfolio_response(
        name="현재 포트폴리오",
        api_key="current",
        weights=current_weights,
        returns=returns,
        expected_returns=expected_returns,
        request=request,
        cov_matrix=cov_matrix,
    )

    rec_1_response = build_portfolio_response(
        name="포트폴리오 A",
        api_key="portfolio_a",
        weights=recommendations[0]["weights"],
        returns=returns,
        expected_returns=expected_returns,
        request=request,
        selection_summary=recommendations[0]["selection_summary"],
        cov_matrix=cov_matrix,
    )

    rec_2_response = build_portfolio_response(
        name="포트폴리오 B",
        api_key="portfolio_b",
        weights=recommendations[1]["weights"],
        returns=returns,
        expected_returns=expected_returns,
        request=request,
        selection_summary=recommendations[1]["selection_summary"],
        correlation_with_recommended_1=recommendations[1].get("correlation_with_recommended_1"),
        cov_matrix=cov_matrix,
    )

    correlation_matrix = returns.corr().round(4).to_dict()
    asset_summary = build_asset_summary(returns, expected_returns)

    unique_ratio = request.unique_need_amount / request.total_asset

    return {
        "input_summary": {
            "total_asset": request.total_asset,
            "unique_need_amount": request.unique_need_amount,
            "unique_ratio": safe_round(unique_ratio, 6),
            "unique_asset": request.unique_asset,
            "unique_asset_label": ASSET_NAMES_KR[request.unique_asset],
            "risk_profile": request.risk_profile,
            "client_risk_level": CLIENT_RISK_LEVEL[request.risk_profile],
            "investment_horizon_years": request.investment_horizon_years,
            "tax_sensitivity": request.tax_sensitivity,
            "liquidity_need": request.liquidity_need,
            "risk_free_rate": request.risk_free_rate,
            "risk_free_rate_basis": "미국 기준 무위험이자율. 시나리오 테스트 금리와 분리.",
            "cash_return": request.cash_return,
            "period": request.period,
            "num_simulations": request.num_simulations,
            "random_seed": request.random_seed,
            "expected_return_haircut": request.expected_return_haircut,
            "enable_black_litterman": request.enable_black_litterman,
            "view_expected_returns": request.view_expected_returns,
            "view_weight": request.view_weight,
            "stress_interest_rate_shock": request.stress_interest_rate_shock,
            "stress_fx_shock": request.stress_fx_shock,
            "stress_affects_scoring": request.stress_affects_scoring,
            "marginal_income_tax_rate": request.marginal_income_tax_rate,
            "overseas_stock_realized_gain_rate": request.overseas_stock_realized_gain_rate,
            "isa_enabled": request.isa_enabled,
            "isa_type": request.isa_type,
            "isa_account_exists": request.isa_account_exists,
            "isa_account_age_years": request.isa_account_age_years,
            "isa_cumulative_contribution": request.isa_cumulative_contribution,
            "isa_recent_3yr_comprehensive_taxed": (
                request.isa_recent_3yr_comprehensive_taxed
            ),
            "isa_remaining_capacity": request.isa_remaining_capacity,
            "isa_remaining_capacity_override": request.isa_remaining_capacity_override,
            "isa_years_until_liquid": request.isa_years_until_liquid,
            "irp_enabled": request.irp_enabled,
            "irp_eligible": request.irp_eligible,
            "irp_current_year_contribution": request.irp_current_year_contribution,
            "irp_remaining_tax_credit_capacity": (
                request.irp_remaining_tax_credit_capacity
            ),
            "irp_remaining_tax_credit_capacity_override": (
                request.irp_remaining_tax_credit_capacity_override
            ),
            "irp_tax_credit_rate": request.irp_tax_credit_rate,
            "irp_years_until_access": request.irp_years_until_access,
            "data_snapshot": data_snapshot,
        },
        "search_summary": search_summary,
        "portfolios": {
            "current": current_response,
            "recommended_1": rec_1_response,
            "recommended_2": rec_2_response,
        },
        "correlation_matrix": correlation_matrix,
        "asset_summary": asset_summary,
        "guideline_definition": get_guideline_definition(),
        "methodology": {
            "portfolio_generation": (
                "Monte Carlo 방식으로 후보 포트폴리오 생성. "
                "8th 기본값은 5,000개이며 request.random_seed로 재현 가능."
            ),
            "optimization_basis": "Mean-Variance 기반: 기대수익률, 공분산 기반 변동성, Sharpe Ratio 계산.",
            "risk_classification": "변동성, MDD, 유동성 커버리지, 자산구성비중을 hard filter로 사용.",
            "selection_logic": "임의 점수 가중치 없이 적합성, VaR, ERC 통과 후보를 세후수익률 중심으로 정렬.",
            "duration_logic": "듀레이션은 채권형 자산에만 적용하고 ETF proxy 기준 수치를 사용.",
            "suitability_filter": "포트폴리오 위험등급이 고객 위험성향 이하인 경우만 추천.",
            "liquidity_metric": "현금+일반채/저쿠폰채/분리과세채 금액에서 ISA 의무기간 잠김 금액을 제외한 값 / 단기 필요금액.",
            "tax_logic": (
                "금융소득종합과세 검토액, 해외주식 양도세 추정액, "
                "ISA/IRP 효과를 포트폴리오별로 계산. 배당·이자성 수익과 "
                "가격차익은 간이 분리하여 중복 과세를 피함."
            ),
            "second_portfolio_logic": (
                "포트폴리오 B는 포트폴리오 A와 수익률 상관계수 "
                f"{SECOND_PORTFOLIO_MAX_CORRELATION} 이하인 후보 중 우선순위가 높은 후보."
            ),
            "stress_test_logic": "금리 충격은 채권형 자산에만 -듀레이션×금리변화를 적용.",
            "var_erc_logic": "95% historical VaR와 공분산 기반 위험기여도 집중도를 리스크 관리에 반영.",
            "backtest_caution": (
                "동일 다운로드 구간의 수익률·공분산으로 추천을 만들고 "
                "같은 구간 누적수익률을 그림. 백테스트 차트는 설명용 "
                "in-sample chart이며 독립 검증 성과로 해석하면 안 됨."
            ),
        },
        "notes": [
            "본 결과는 정보제공 목적이며 투자 판단과 책임은 투자자 본인에게 있습니다.",
            "기대수익률은 과거 일별 수익률을 연율화한 뒤 보수 조정한 추정값입니다.",
            (
                "세금 계산은 간이 추정입니다. 실제 세액은 전체 소득, "
                "실현손익, 보유계좌, 상품별 요건에 따라 달라집니다."
            ),
            "8th는 임의 scoring weight 합산식을 제거하고 VaR·ERC 기반 리스크 통제를 사용합니다.",
        ],
    }


def run_full_analysis(request: AnalysisRequest) -> Dict[str, Any]:
    session_id = str(uuid.uuid4())

    save_session_request(
        session_id,
        {
            "ips": model_to_dict(request.ips),
            "scenario": model_to_dict(request.scenario),
        },
    )

    portfolio_request = convert_analysis_to_portfolio_request(request)
    core = run_analysis_core(portfolio_request)

    core["session_id"] = session_id
    core["scenario_summary"] = {
        "base_interest_rate": request.scenario.base_interest_rate,
        "base_fx_rate_krw_per_usd": request.scenario.base_fx_rate_krw_per_usd,
        "stressed_interest_rate": request.scenario.base_interest_rate
        + request.scenario.stress_interest_rate_shock,
        "stressed_fx_rate_krw_per_usd": request.scenario.base_fx_rate_krw_per_usd
        * (1 + request.scenario.stress_fx_shock),
        "stress_interest_rate_shock": request.scenario.stress_interest_rate_shock,
        "stress_fx_shock": request.scenario.stress_fx_shock,
        "stress_affects_scoring": request.scenario.stress_affects_scoring,
        "risk_free_rate_used_for_sharpe_sortino": core["input_summary"]["risk_free_rate"],
        "risk_free_rate_note": "Sharpe/Sortino 기준 금리는 scenario.base_interest_rate와 분리됨.",
        "rrttllu": request.scenario.rrttllu,
    }

    core["backtest"] = extract_backtest_payload(core)
    core["tax_optimizer"] = build_tax_optimizer_map(core, portfolio_request)
    core["tax_inputs"] = extract_tax_inputs_payload(core)

    return core


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


@router.post("/api/portfolio/all")
def api_portfolio_all(request: AnalysisRequest):
    """
    최초 대시보드용 전체 API.
    현재 포트폴리오 / 포트폴리오 A / 포트폴리오 B / 백테스트 / 절세 입력값을 한 번에 반환.
    """
    try:
        return run_full_analysis(request)
    except Exception as e:
        raise public_http_exception(e)


@router.post("/api/portfolio/current")
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


@router.post("/api/portfolio/a")
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


@router.post("/api/portfolio/b")
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


@router.post("/api/portfolio/bundle")
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


@router.post("/api/backtest")
def api_backtest(request: AnalysisRequest):
    """
    현재 / 포트폴리오 A / 포트폴리오 B 백테스트 데이터만 반환.
    """
    try:
        full = run_full_analysis(request)
        return extract_backtest_payload(full)
    except Exception as e:
        raise public_http_exception(e)


@router.post("/api/tax-inputs")
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


@router.post("/api/tax-optimizer")
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


@router.get("/api/sessions/{session_id}/request")
def api_get_saved_request(session_id: str):
    """
    1회차 상담 request 조회.
    현재는 서버 메모리 저장이라 서버 재시작 시 사라짐.
    """
    saved = SESSION_REQUEST_STORE.get(session_id)
    if saved is None:
        raise HTTPException(status_code=404, detail="해당 session_id의 저장된 request가 없습니다.")

    return {
        "session_id": session_id,
        "request": saved,
    }


# ============================================================
# 14. Legacy Analyze API
# ============================================================
# 기존 프론트나 테스트 코드와의 호환을 위해 남김.
# 새 프론트는 /api/portfolio/all 등 분리 API를 사용하면 됨.


@router.post("/analyze")
def analyze_portfolio(request: PortfolioRequest):
    try:
        return run_analysis_core(request)
    except Exception as e:
        raise public_http_exception(e)



