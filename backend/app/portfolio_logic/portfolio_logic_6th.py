from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal, Tuple, Any
import uuid
import numpy as np
import pandas as pd
import yfinance as yf


app = FastAPI(
    title="AI IPS Portfolio Analysis API",
    description="PB 보조용 포트폴리오 추천 및 분석 API",
    version="6.0.0",
)


# ============================================================
# 0. 기본 설정
# ============================================================

TRADING_DAYS = 252

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

# IRP/연금계좌 기본 세액공제 가정
IRP_PENSION_COMBINED_TAX_CREDIT_LIMIT = 9_000_000
IRP_TAX_CREDIT_RATE_HIGH_INCOME = 0.132
IRP_TAX_CREDIT_RATE_LOW_INCOME = 0.165

# 추천 B 선별 기준
# 검증된 사실: 상관계수가 낮을수록 분산효과가 커질 수 있음.
# 프로젝트용 가정: 추천 A와 B가 너무 비슷하지 않도록 0.95 이하를 기준으로 둠.
SECOND_PORTFOLIO_MAX_CORRELATION = 0.95


# ============================================================
# 1. 자산군
# ============================================================
# 검증된 사실:
# - DXY는 Yahoo Finance에서 DX-Y.NYB로 조회 가능.
# - 471230.KS는 KODEX 국고채10년액티브 proxy.
# - 484790.KS는 KODEX 미국30년국채액티브(H) proxy.
# - 273130.KS는 KODEX 종합채권(AA-이상)액티브 proxy.
#
# 프로젝트용 가정:
# - 484790.KS를 저쿠폰채 가격 proxy로 사용.
# - 273130.KS를 분리과세 채권/상품 price proxy로 사용.
#   ETF 자체가 세법상 저쿠폰채 직접투자나 분리과세 상품과 완전히 동일하다는 뜻은 아님.

ASSET_TICKERS = {
    "domestic_stock": "^KS11",
    "sp500": "SPY",
    "nasdaq": "QQQ",
    "high_dividend": "SCHD",
    "reit": "VNQ",
    "gold": "GLD",
    "commodity": "DBC",
    "dxy": "DX-Y.NYB",
    "kr_treasury": "471230.KS",
    "low_coupon_bond": "484790.KS",
    "separate_tax_bond": "273130.KS",
    "cash": "CASH",
}

ASSET_NAMES_KR = {
    "domestic_stock": "국내주식",
    "sp500": "S&P500",
    "nasdaq": "NASDAQ",
    "high_dividend": "고배당 ETF",
    "reit": "리츠",
    "gold": "금",
    "commodity": "원자재",
    "dxy": "미국 달러 인덱스(DXY)",
    "kr_treasury": "한국 국채",
    "low_coupon_bond": "저쿠폰채 proxy",
    "separate_tax_bond": "분리과세 채권 proxy",
    "cash": "현금",
}

STOCK_ASSETS = ["domestic_stock", "sp500", "nasdaq", "high_dividend"]
OVERSEAS_STOCK_ASSETS = ["sp500", "nasdaq", "high_dividend", "reit"]
BOND_ASSETS = ["kr_treasury", "low_coupon_bond", "separate_tax_bond"]
BOND_CASH_ASSETS = BOND_ASSETS + ["cash"]
ALTERNATIVE_ASSETS = ["reit", "gold", "commodity", "dxy"]
CASH_LIKE_ASSETS = ["cash", "kr_treasury", "low_coupon_bond", "separate_tax_bond"]

# 이자·배당 성격이 강해 금융소득종합과세 검토 대상에 넣을 자산
INCOME_TAXABLE_ASSETS = [
    "cash",
    "kr_treasury",
    "low_coupon_bond",
    "separate_tax_bond",
    "high_dividend",
    "reit",
]

ISA_PRIORITY_ASSETS = [
    "high_dividend",
    "reit",
    "kr_treasury",
    "low_coupon_bond",
    "separate_tax_bond",
    "cash",
]

IRP_PRIORITY_ASSETS = [
    "kr_treasury",
    "low_coupon_bond",
    "separate_tax_bond",
    "sp500",
    "high_dividend",
]

# 듀레이션은 점수화에만 사용. 차트 하단 6종 지표에는 포함하지 않음.
# 검증된 사실: 듀레이션은 금리 변화에 대한 채권 가격 민감도 지표.
# 프로젝트용 가정: 아래 수치는 ETF/전략별 대표 근사치.
ASSET_DURATION_YEARS = {
    "domestic_stock": 0.0,
    "sp500": 0.0,
    "nasdaq": 0.0,
    "high_dividend": 0.0,
    "reit": 0.0,
    "gold": 0.0,
    "commodity": 0.0,
    "dxy": 0.0,
    "kr_treasury": 7.0,
    "low_coupon_bond": 15.56,
    "separate_tax_bond": 5.0,
    "cash": 0.1,
}

INTEREST_RATE_SENSITIVE_ASSETS = BOND_ASSETS + ["reit"]
FX_SENSITIVE_ASSETS = [
    "sp500",
    "nasdaq",
    "high_dividend",
    "reit",
    "gold",
    "commodity",
    "dxy",
    "low_coupon_bond",
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

TAX_RULES = {
    "low": 0.154,
    "medium": 0.22,
    "high": 0.30,
}


# ============================================================
# 2. 기준표 및 점수 가중치
# ============================================================
# 검증된 사실:
# - 투자위험 판단에는 변동성, 최대 손실 가능성, 기초자산 구성, 유동성, 만기, 환율 변동성 등이 고려될 수 있음.
# - 투자자 성향보다 높은 위험도의 상품 권유는 제한됨.
# - 금융소득 2,000만 원, ISA 3년, 해외주식 양도차익 250만 원 공제 등은 세법/제도상 기본 기준.
#
# 프로젝트용 가정:
# - 안정형/균형형/공격형의 변동성, MDD, 자산비중 한도
# - 점수화 가중치
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

SCORING_WEIGHTS = {
    "conservative": {
        "after_tax_return": 0.25,
        "sharpe": 0.18,
        "sortino": 0.17,
        "liquidity": 0.15,
        "duration_fit": 0.10,
        "soft_pass": 0.10,
        "volatility_penalty": 0.03,
        "mdd_penalty": 0.02,
    },
    "balanced": {
        "after_tax_return": 0.22,
        "expected_return": 0.20,
        "sharpe": 0.18,
        "sortino": 0.12,
        "liquidity": 0.08,
        "duration_fit": 0.08,
        "soft_pass": 0.07,
        "mdd_penalty": 0.05,
    },
    "aggressive": {
        "expected_return": 0.32,
        "after_tax_return": 0.22,
        "sharpe": 0.14,
        "sortino": 0.08,
        "tax_retention": 0.08,
        "duration_fit": 0.04,
        "soft_pass": 0.04,
        "volatility_penalty": 0.04,
        "mdd_penalty": 0.04,
    },
}


# ============================================================
# 3. Request Models
# ============================================================

class IPSRequest(BaseModel):
    total_asset: float = Field(..., gt=0)
    unique_need_amount: float = Field(..., ge=0)
    unique_asset: Literal["cash", "kr_treasury", "low_coupon_bond", "separate_tax_bond"] = Field(...)

    risk_profile: Literal["conservative", "balanced", "aggressive"] = Field(...)
    investment_horizon_years: int = Field(..., ge=1, le=50)
    tax_sensitivity: Literal["low", "medium", "high"] = Field(...)
    liquidity_need: Literal["low", "medium", "high"] = Field(...)

    current_weights: Optional[Dict[str, float]] = Field(None)

    cash_return: float = Field(DEFAULT_CASH_RETURN)
    period: str = Field("5y")

    num_simulations: int = Field(5000, ge=500, le=100000)
    expected_return_haircut: float = Field(0.75, ge=0.0, le=1.0)

    enable_black_litterman: bool = Field(False)
    view_expected_returns: Optional[Dict[str, float]] = Field(None)
    view_weight: float = Field(0.35, ge=0.0, le=1.0)

    marginal_income_tax_rate: float = Field(0.24, ge=0.06, le=0.495)
    overseas_stock_realized_gain_rate: float = Field(0.0, ge=0.0, le=1.0)

    isa_enabled: bool = Field(True)
    isa_type: Literal["general", "seogmin"] = Field("general")
    isa_remaining_capacity: float = Field(20_000_000, ge=0)
    isa_years_until_liquid: float = Field(ISA_MANDATORY_HOLDING_YEARS, ge=0, le=50)

    irp_enabled: bool = Field(True)
    irp_remaining_tax_credit_capacity: float = Field(IRP_PENSION_COMBINED_TAX_CREDIT_LIMIT, ge=0)
    irp_tax_credit_rate: float = Field(IRP_TAX_CREDIT_RATE_HIGH_INCOME, ge=0.0, le=IRP_TAX_CREDIT_RATE_LOW_INCOME)


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
    unique_asset: Literal["cash", "kr_treasury", "low_coupon_bond", "separate_tax_bond"] = Field("kr_treasury")
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
    isa_remaining_capacity: float = Field(20_000_000, ge=0)
    isa_years_until_liquid: float = Field(ISA_MANDATORY_HOLDING_YEARS, ge=0, le=50)

    irp_enabled: bool = Field(True)
    irp_remaining_tax_credit_capacity: float = Field(IRP_PENSION_COMBINED_TAX_CREDIT_LIMIT, ge=0)
    irp_tax_credit_rate: float = Field(IRP_TAX_CREDIT_RATE_HIGH_INCOME, ge=0.0, le=IRP_TAX_CREDIT_RATE_LOW_INCOME)


# ============================================================
# 4. 기본 유틸
# ============================================================

SESSION_REQUEST_STORE: Dict[str, Dict[str, Any]] = {}


def model_to_dict(model: BaseModel) -> Dict[str, Any]:
    try:
        return model.model_dump()
    except AttributeError:
        return model.dict()


def validate_weights(weights: Dict[str, float]) -> None:
    unknown_assets = set(weights.keys()) - set(ASSET_TICKERS.keys())
    if unknown_assets:
        raise ValueError(f"지원하지 않는 자산군입니다: {unknown_assets}")


def normalize_weights(weights: Dict[str, float]) -> Dict[str, float]:
    cleaned = {asset: max(float(weight), 0.0) for asset, weight in weights.items()}
    total = sum(cleaned.values())
    if total <= 0:
        raise ValueError("포트폴리오 비중 합계가 0입니다.")
    return {asset: weight / total for asset, weight in cleaned.items()}


def get_default_current_weights() -> Dict[str, float]:
    return {asset: (1.0 if asset == "cash" else 0.0) for asset in ASSET_TICKERS.keys()}


def cap01(value: float) -> float:
    return float(max(0.0, min(1.0, value)))


def safe_round(value: float, digits: int = 6) -> float:
    if value is None or np.isnan(value) or np.isinf(value):
        return 0.0
    return round(float(value), digits)


def convert_analysis_to_portfolio_request(request: AnalysisRequest) -> PortfolioRequest:
    ips = request.ips
    scenario = request.scenario

    return PortfolioRequest(
        total_asset=ips.total_asset,
        unique_need_amount=ips.unique_need_amount,
        unique_asset=ips.unique_asset,
        risk_profile=ips.risk_profile,
        investment_horizon_years=ips.investment_horizon_years,
        tax_sensitivity=ips.tax_sensitivity,
        liquidity_need=ips.liquidity_need,
        current_weights=ips.current_weights,
        risk_free_rate=scenario.base_interest_rate,
        cash_return=ips.cash_return,
        period=ips.period,
        num_simulations=ips.num_simulations,
        expected_return_haircut=ips.expected_return_haircut,
        enable_black_litterman=ips.enable_black_litterman,
        view_expected_returns=ips.view_expected_returns,
        view_weight=ips.view_weight,
        stress_interest_rate_shock=scenario.stress_interest_rate_shock,
        stress_fx_shock=scenario.stress_fx_shock,
        stress_affects_scoring=scenario.stress_affects_scoring,
        marginal_income_tax_rate=ips.marginal_income_tax_rate,
        overseas_stock_realized_gain_rate=ips.overseas_stock_realized_gain_rate,
        isa_enabled=ips.isa_enabled,
        isa_type=ips.isa_type,
        isa_remaining_capacity=ips.isa_remaining_capacity,
        isa_years_until_liquid=ips.isa_years_until_liquid,
        irp_enabled=ips.irp_enabled,
        irp_remaining_tax_credit_capacity=ips.irp_remaining_tax_credit_capacity,
        irp_tax_credit_rate=ips.irp_tax_credit_rate,
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
        prices = raw["Close"].copy()
    else:
        prices = raw[["Close"]].copy()

    reverse_map = {ticker: asset for asset, ticker in tickers.items()}
    prices = prices.rename(columns=reverse_map)

    prices = prices.dropna(how="all").ffill().dropna()

    daily_cash_return = (1 + cash_return) ** (1 / TRADING_DAYS) - 1
    prices["cash"] = (1 + daily_cash_return) ** np.arange(len(prices))

    available_assets = [asset for asset in ASSET_TICKERS.keys() if asset in prices.columns]
    prices = prices[available_assets]

    if len(prices.columns) < 5:
        raise RuntimeError("사용 가능한 자산 가격 데이터가 너무 적습니다.")

    return prices


def calculate_daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.pct_change().dropna()


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

    if not enable_black_litterman or not view_expected_returns:
        return adjusted_returns

    final_returns = adjusted_returns.copy()
    for asset, view_return in view_expected_returns.items():
        if asset in final_returns.index:
            final_returns[asset] = final_returns[asset] * (1 - view_weight) + float(view_return) * view_weight

    return final_returns


# ============================================================
# 7. 세금 / 계좌
# ============================================================

def estimate_taxable_financial_income(
    weights: Dict[str, float],
    expected_returns: pd.Series,
    total_asset: float,
) -> float:
    estimated_income = 0.0

    for asset in INCOME_TAXABLE_ASSETS:
        if asset in expected_returns.index:
            asset_weight = weights.get(asset, 0.0)
            asset_return = max(float(expected_returns[asset]), 0.0)
            estimated_income += asset_weight * total_asset * asset_return

    return float(estimated_income)


def calculate_financial_income_comprehensive_tax_status(taxable_financial_income: float) -> Dict[str, Any]:
    excess = max(taxable_financial_income - FINANCIAL_INCOME_COMPREHENSIVE_TAX_THRESHOLD, 0.0)

    return {
        "taxable_financial_income": round(float(taxable_financial_income), 0),
        "threshold": FINANCIAL_INCOME_COMPREHENSIVE_TAX_THRESHOLD,
        "excess_over_threshold": round(float(excess), 0),
        "is_over_threshold": taxable_financial_income > FINANCIAL_INCOME_COMPREHENSIVE_TAX_THRESHOLD,
        "basis": "금융소득종합과세 검토 기준 2,000만 원. 세부 적용은 고객 전체 소득과 세법 확인 필요.",
    }


def estimate_overseas_stock_capital_gains_tax(
    weights: Dict[str, float],
    expected_returns: pd.Series,
    total_asset: float,
    realized_gain_rate: float,
) -> Dict[str, Any]:
    gross_realized_gain = 0.0

    for asset in OVERSEAS_STOCK_ASSETS:
        if asset in expected_returns.index:
            asset_profit = weights.get(asset, 0.0) * total_asset * max(float(expected_returns[asset]), 0.0)
            gross_realized_gain += asset_profit * realized_gain_rate

    taxable_gain = max(gross_realized_gain - OVERSEAS_STOCK_GAIN_DEDUCTION, 0.0)
    estimated_tax = taxable_gain * OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE

    return {
        "gross_realized_gain": round(float(gross_realized_gain), 0),
        "basic_deduction": OVERSEAS_STOCK_GAIN_DEDUCTION,
        "taxable_gain": round(float(taxable_gain), 0),
        "tax_rate": OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE,
        "estimated_tax": round(float(estimated_tax), 0),
        "basis": "해외주식 양도소득 기본공제 250만 원 및 기본세율 22%를 적용한 간이 추정.",
    }


def allocate_account_buckets(
    weights: Dict[str, float],
    total_asset: float,
    request: PortfolioRequest,
) -> Dict[str, Any]:
    remaining_amounts = {
        asset: weights.get(asset, 0.0) * total_asset
        for asset in ASSET_TICKERS.keys()
    }

    isa_alloc = {asset: 0.0 for asset in ASSET_TICKERS.keys()}
    irp_alloc = {asset: 0.0 for asset in ASSET_TICKERS.keys()}
    taxable_alloc = {asset: 0.0 for asset in ASSET_TICKERS.keys()}

    if request.isa_enabled and request.isa_remaining_capacity > 0:
        remaining_isa_capacity = request.isa_remaining_capacity
        for asset in ISA_PRIORITY_ASSETS:
            amount = min(remaining_amounts.get(asset, 0.0), remaining_isa_capacity)
            if amount > 0:
                isa_alloc[asset] += amount
                remaining_amounts[asset] -= amount
                remaining_isa_capacity -= amount
            if remaining_isa_capacity <= 0:
                break

    if request.irp_enabled and request.irp_remaining_tax_credit_capacity > 0:
        remaining_irp_capacity = request.irp_remaining_tax_credit_capacity
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

    isa_locked_amount = isa_total if request.isa_years_until_liquid > 0 else 0.0
    irp_tax_credit = min(irp_total, request.irp_remaining_tax_credit_capacity) * request.irp_tax_credit_rate

    return {
        "isa": {
            "enabled": request.isa_enabled,
            "type": request.isa_type,
            "remaining_capacity_input": round(float(request.isa_remaining_capacity), 0),
            "allocated_amount": round(float(isa_total), 0),
            "locked_amount_for_liquidity": round(float(isa_locked_amount), 0),
            "years_until_liquid": request.isa_years_until_liquid,
            "tax_free_limit": ISA_GENERAL_TAX_FREE_LIMIT if request.isa_type == "general" else ISA_SEOGMIN_TAX_FREE_LIMIT,
            "low_tax_rate_after_tax_free_limit": ISA_LOW_TAX_RATE,
            "allocations": {
                asset: {
                    "label": ASSET_NAMES_KR[asset],
                    "amount": round(float(amount), 0),
                    "weight_in_total_asset": round(float(amount / total_asset), 6),
                }
                for asset, amount in isa_alloc.items()
                if amount > 0
            },
        },
        "irp": {
            "enabled": request.irp_enabled,
            "remaining_tax_credit_capacity_input": round(float(request.irp_remaining_tax_credit_capacity), 0),
            "allocated_amount": round(float(irp_total), 0),
            "estimated_tax_credit": round(float(irp_tax_credit), 0),
            "tax_credit_rate": request.irp_tax_credit_rate,
            "allocations": {
                asset: {
                    "label": ASSET_NAMES_KR[asset],
                    "amount": round(float(amount), 0),
                    "weight_in_total_asset": round(float(amount / total_asset), 6),
                }
                for asset, amount in irp_alloc.items()
                if amount > 0
            },
        },
        "taxable_account": {
            "allocated_amount": round(float(taxable_total), 0),
            "allocations": {
                asset: {
                    "label": ASSET_NAMES_KR[asset],
                    "amount": round(float(amount), 0),
                    "weight_in_total_asset": round(float(amount / total_asset), 6),
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
    taxable_income_before = estimate_taxable_financial_income(weights, expected_returns, total_asset)

    isa_amount = account_buckets["isa"]["allocated_amount"]
    irp_tax_credit = account_buckets["irp"]["estimated_tax_credit"]

    income_taxable_weight_in_isa = 0.0
    if total_asset > 0 and isa_amount > 0:
        for asset, info in account_buckets["isa"]["allocations"].items():
            if asset in INCOME_TAXABLE_ASSETS:
                income_taxable_weight_in_isa += info["amount"] / total_asset

    weighted_expected_income_return = 0.0
    for asset in INCOME_TAXABLE_ASSETS:
        if asset in expected_returns.index:
            weighted_expected_income_return += weights.get(asset, 0.0) * max(float(expected_returns[asset]), 0.0)

    if sum(weights.get(asset, 0.0) for asset in INCOME_TAXABLE_ASSETS) > 0:
        avg_income_return = weighted_expected_income_return / sum(weights.get(asset, 0.0) for asset in INCOME_TAXABLE_ASSETS)
    else:
        avg_income_return = 0.0

    income_shifted_to_isa = income_taxable_weight_in_isa * total_asset * avg_income_return

    isa_tax_free_limit = ISA_GENERAL_TAX_FREE_LIMIT if request.isa_type == "general" else ISA_SEOGMIN_TAX_FREE_LIMIT
    isa_tax_free_income = min(income_shifted_to_isa, isa_tax_free_limit)
    isa_low_tax_income = max(income_shifted_to_isa - isa_tax_free_limit, 0.0)

    isa_tax_saving = (
        isa_tax_free_income * DEFAULT_WITHHOLDING_TAX_RATE
        + isa_low_tax_income * max(DEFAULT_WITHHOLDING_TAX_RATE - ISA_LOW_TAX_RATE, 0.0)
    )

    estimated_total_tax_saving = isa_tax_saving + irp_tax_credit

    return {
        "taxable_financial_income_before_account_allocation": round(float(taxable_income_before), 0),
        "estimated_income_shifted_to_isa": round(float(income_shifted_to_isa), 0),
        "isa_tax_free_income_used": round(float(isa_tax_free_income), 0),
        "isa_low_tax_income_used": round(float(isa_low_tax_income), 0),
        "estimated_isa_tax_saving": round(float(isa_tax_saving), 0),
        "estimated_irp_tax_credit": round(float(irp_tax_credit), 0),
        "estimated_total_tax_saving": round(float(estimated_total_tax_saving), 0),
        "note": "절세제안은 제외하고, 세후수익률 반영을 위한 간이 절세효과만 계산.",
    }


def calculate_after_tax_return(
    weights: Dict[str, float],
    expected_returns: pd.Series,
    total_asset: float,
    request: PortfolioRequest,
) -> Tuple[float, Dict[str, Any]]:
    gross_profit = 0.0
    withholding_tax = 0.0

    for asset, weight in weights.items():
        if asset not in expected_returns.index:
            continue

        asset_profit = weight * total_asset * float(expected_returns[asset])
        gross_profit += asset_profit

        if asset in INCOME_TAXABLE_ASSETS and asset_profit > 0:
            withholding_tax += asset_profit * DEFAULT_WITHHOLDING_TAX_RATE

    taxable_financial_income = estimate_taxable_financial_income(weights, expected_returns, total_asset)
    comprehensive_tax_status = calculate_financial_income_comprehensive_tax_status(taxable_financial_income)

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

    total_tax_before_saving = withholding_tax + overseas_tax["estimated_tax"] + additional_comprehensive_tax
    total_tax_after_saving = max(total_tax_before_saving - tax_saving_effect["estimated_total_tax_saving"], 0.0)

    after_tax_profit = gross_profit - total_tax_after_saving
    after_tax_return = after_tax_profit / total_asset

    tax_breakdown = {
        "gross_profit": round(float(gross_profit), 0),
        "withholding_tax_estimate": round(float(withholding_tax), 0),
        "financial_income_comprehensive_tax": comprehensive_tax_status,
        "additional_comprehensive_tax_estimate": round(float(additional_comprehensive_tax), 0),
        "overseas_stock_capital_gains_tax": overseas_tax,
        "account_buckets": account_buckets,
        "tax_saving_effect": tax_saving_effect,
        "total_tax_before_saving": round(float(total_tax_before_saving), 0),
        "total_tax_after_saving": round(float(total_tax_after_saving), 0),
        "after_tax_profit": round(float(after_tax_profit), 0),
        "after_tax_return": round(float(after_tax_return), 6),
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
        return 0.0

    downside_deviation = downside_returns.std() * np.sqrt(TRADING_DAYS)

    if downside_deviation < 1e-8 or np.isnan(downside_deviation):
        return 0.0

    return float((annual_return - risk_free_rate) / downside_deviation)


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
    bond_cash_weight = sum(weights.get(asset, 0.0) for asset in BOND_CASH_ASSETS)
    if bond_cash_weight <= 1e-8:
        return 0.0

    weighted_duration = sum(
        weights.get(asset, 0.0) * ASSET_DURATION_YEARS.get(asset, 0.0)
        for asset in BOND_CASH_ASSETS
    )

    return float(weighted_duration / bond_cash_weight)


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

    fx_effect = sum(weights.get(asset, 0.0) for asset in FX_SENSITIVE_ASSETS) * request.stress_fx_shock

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
) -> Dict[str, Any]:
    weights = normalize_weights(weights)

    assets = [asset for asset in weights.keys() if asset in returns.columns]
    w = np.array([weights[asset] for asset in assets], dtype=float)
    w = w / w.sum()

    selected_returns = returns[assets]
    selected_expected_returns = expected_returns[assets]

    cov_matrix = selected_returns.cov() * TRADING_DAYS

    portfolio_return = float(np.dot(w, selected_expected_returns))
    portfolio_volatility = float(np.sqrt(np.dot(w.T, np.dot(cov_matrix, w))))

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
    }

    risk_level = classify_portfolio_by_guidelines(temp_metrics)

    return {
        "expected_return": safe_round(portfolio_return, 6),
        "after_tax_return": safe_round(after_tax_return, 6),
        "volatility": safe_round(portfolio_volatility, 6),
        "sharpe_ratio": safe_round(sharpe, 6),
        "sortino_ratio": safe_round(sortino, 6),
        "mdd": safe_round(mdd, 6),
        "taxable_financial_income": round(float(taxable_financial_income), 0),
        "liquidity_coverage": safe_round(liquidity_coverage, 6),
        "stock_weight": safe_round(group_weights["stock_weight"], 6),
        "bond_cash_weight": safe_round(group_weights["bond_cash_weight"], 6),
        "alternative_weight": safe_round(group_weights["alternative_weight"], 6),
        "portfolio_duration": safe_round(portfolio_duration, 6),
        "target_duration": safe_round(target_duration, 6),
        "duration_fit_score": safe_round(duration_fit_score, 6),
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

    assets = [asset for asset in weights.keys() if asset in returns.columns]
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
            soft_checks["after_tax_retention"] = after_tax_return / expected_return >= rule["after_tax_retention_min"]
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

def generate_random_weights() -> Dict[str, float]:
    assets = list(ASSET_TICKERS.keys())
    alpha = np.ones(len(assets))
    sampled = np.random.dirichlet(alpha)
    return {asset: float(weight) for asset, weight in zip(assets, sampled)}


def apply_unique_constraint(
    base_weights: Dict[str, float],
    total_asset: float,
    unique_need_amount: float,
    unique_asset: str,
) -> Dict[str, float]:
    unique_ratio = min(max(unique_need_amount / total_asset, 0.0), 1.0)
    investable_ratio = 1.0 - unique_ratio

    final_weights = {asset: 0.0 for asset in ASSET_TICKERS.keys()}
    final_weights[unique_asset] += unique_ratio

    normalized_base = normalize_weights(base_weights)

    for asset, weight in normalized_base.items():
        final_weights[asset] += weight * investable_ratio

    return normalize_weights(final_weights)


def score_portfolio(metrics: Dict[str, Any], client_risk_profile: str, stress_affects_scoring: bool) -> float:
    expected_return = metrics["expected_return"]
    after_tax_return = metrics["after_tax_return"]
    volatility = metrics["volatility"]
    sharpe = metrics["sharpe_ratio"]
    sortino = metrics["sortino_ratio"]
    mdd = abs(metrics["mdd"])
    liquidity_coverage = metrics["liquidity_coverage"]
    duration_fit_score = metrics["duration_fit_score"]

    sharpe_capped = max(min(sharpe, 3.0), -3.0)
    sortino_capped = max(min(sortino, 3.0), -3.0)
    liquidity_capped = min(liquidity_coverage, 2.0)

    report = evaluate_guideline_detail(metrics, client_risk_profile)
    soft_pass_ratio = report["soft_pass_ratio"]

    w = SCORING_WEIGHTS[client_risk_profile]

    if client_risk_profile == "conservative":
        score = (
            w["after_tax_return"] * after_tax_return * 100
            + w["sharpe"] * sharpe_capped
            + w["sortino"] * sortino_capped
            + w["liquidity"] * liquidity_capped
            + w["duration_fit"] * duration_fit_score
            + w["soft_pass"] * soft_pass_ratio
            - w["volatility_penalty"] * volatility * 100
            - w["mdd_penalty"] * mdd * 100
        )

    elif client_risk_profile == "balanced":
        score = (
            w["after_tax_return"] * after_tax_return * 100
            + w["expected_return"] * expected_return * 100
            + w["sharpe"] * sharpe_capped
            + w["sortino"] * sortino_capped
            + w["liquidity"] * liquidity_capped
            + w["duration_fit"] * duration_fit_score
            + w["soft_pass"] * soft_pass_ratio
            - w["mdd_penalty"] * mdd * 100
        )

        taxable_income = metrics["taxable_financial_income"]
        if taxable_income > FINANCIAL_INCOME_COMPREHENSIVE_TAX_THRESHOLD:
            excess_ratio = (taxable_income - FINANCIAL_INCOME_COMPREHENSIVE_TAX_THRESHOLD) / FINANCIAL_INCOME_COMPREHENSIVE_TAX_THRESHOLD
            score -= min(excess_ratio, 2.0)

    else:
        retention = after_tax_return / expected_return if expected_return > 0 else 0.0

        score = (
            w["expected_return"] * expected_return * 100
            + w["after_tax_return"] * after_tax_return * 100
            + w["sharpe"] * sharpe_capped
            + w["sortino"] * sortino_capped
            + w["tax_retention"] * retention
            + w["duration_fit"] * duration_fit_score
            + w["soft_pass"] * soft_pass_ratio
            - w["volatility_penalty"] * volatility * 100
            - w["mdd_penalty"] * mdd * 100
        )

    if stress_affects_scoring:
        stress_loss = abs(min(metrics["stress_test"]["estimated_loss_ratio"], 0.0))
        score -= stress_loss * 100 * 0.10

    return float(score)


def calculate_portfolio_return_series(
    weights: Dict[str, float],
    returns: pd.DataFrame,
) -> pd.Series:
    weights = normalize_weights(weights)
    assets = [asset for asset in weights.keys() if asset in returns.columns]
    w = np.array([weights[asset] for asset in assets], dtype=float)
    w = w / w.sum()
    return returns[assets].dot(w)


def calculate_portfolio_return_correlation(
    weights_a: Dict[str, float],
    weights_b: Dict[str, float],
    returns: pd.DataFrame,
) -> float:
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
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    np.random.seed(42)

    candidates = []
    generated_count = request.num_simulations
    guideline_pass_count = 0
    suitable_count = 0

    for _ in range(request.num_simulations):
        base_weights = generate_random_weights()

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
        )

        if metrics["risk_level"] is not None:
            guideline_pass_count += 1

        if not is_suitable_for_client(metrics, request.risk_profile):
            continue

        suitable_count += 1

        score = score_portfolio(
            metrics=metrics,
            client_risk_profile=request.risk_profile,
            stress_affects_scoring=request.stress_affects_scoring,
        )

        candidates.append(
            {
                "weights": final_weights,
                "metrics": metrics,
                "score": score,
            }
        )

    if len(candidates) == 0:
        raise RuntimeError(
            "기준표와 고객 위험성향 기준을 통과한 포트폴리오가 없습니다. "
            "num_simulations를 늘리거나 기준표를 재검토해야 합니다."
        )

    candidates = sorted(candidates, key=lambda x: x["score"], reverse=True)

    recommendation_1 = candidates[0]
    recommendation_2 = None

    for candidate in candidates[1:]:
        corr = calculate_portfolio_return_correlation(
            recommendation_1["weights"],
            candidate["weights"],
            returns,
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
        )

    search_summary = {
        "generated_portfolios": generated_count,
        "guideline_pass_portfolios": guideline_pass_count,
        "suitable_portfolios": suitable_count,
        "filtered_out_portfolios": generated_count - suitable_count,
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
    correlation_with_recommended_1: Optional[float] = None,
) -> Dict[str, Any]:
    metrics = calculate_metrics(
        weights=weights,
        returns=returns,
        expected_returns=expected_returns,
        request=request,
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
            "financial_income_comprehensive_tax_status": metrics["tax_breakdown"]["financial_income_comprehensive_tax"],
            "risk_level": metrics["risk_level"],
            "risk_level_label": metrics["risk_level_label"],
            "stock_weight": metrics["stock_weight"],
            "bond_cash_weight": metrics["bond_cash_weight"],
            "alternative_weight": metrics["alternative_weight"],

            # 듀레이션은 표시용 6종 지표가 아니라 점수화/내부 설명용
            "portfolio_duration": metrics["portfolio_duration"],
            "target_duration": metrics["target_duration"],
            "duration_fit_score": metrics["duration_fit_score"],

            "stress_test": metrics["stress_test"],
        },
        "tax_breakdown": metrics["tax_breakdown"],
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
            "scoring_weights": SCORING_WEIGHTS,
            "second_portfolio_max_correlation": SECOND_PORTFOLIO_MAX_CORRELATION,
            "duration_targets": {
                "short_horizon_1_to_3_years": 1.5,
                "middle_horizon_4_to_7_years": 4.0,
                "long_horizon_8_plus_years": 7.0,
            },
            "low_coupon_bond_proxy": "484790.KS를 저쿠폰채 price proxy로 사용",
            "separate_tax_bond_proxy": "273130.KS를 분리과세 채권 price proxy로 사용",
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
        "common_tax_rules": {
            "financial_income_comprehensive_tax_threshold": FINANCIAL_INCOME_COMPREHENSIVE_TAX_THRESHOLD,
            "overseas_stock_gain_deduction": OVERSEAS_STOCK_GAIN_DEDUCTION,
            "overseas_stock_capital_gains_tax_rate": OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE,
            "isa_general_tax_free_limit": ISA_GENERAL_TAX_FREE_LIMIT,
            "isa_seogmin_tax_free_limit": ISA_SEOGMIN_TAX_FREE_LIMIT,
            "isa_low_tax_rate": ISA_LOW_TAX_RATE,
            "isa_mandatory_holding_years": ISA_MANDATORY_HOLDING_YEARS,
            "irp_tax_credit_limit": IRP_PENSION_COMBINED_TAX_CREDIT_LIMIT,
        },
        "note": "절세제안 문구는 제외. 종합과세 임계점, 해외주식 양도세 추정, ISA/IRP/일반계좌 배치 정보만 전달.",
    }


# ============================================================
# 12. 전체 분석 실행
# ============================================================

def run_analysis_core(request: PortfolioRequest) -> Dict[str, Any]:
    if request.unique_need_amount > request.total_asset:
        raise ValueError("Unique 필요금액은 총자산보다 클 수 없습니다.")

    prices = download_price_data(
        period=request.period,
        cash_return=request.cash_return,
    )

    returns = calculate_daily_returns(prices)

    expected_returns = calculate_expected_returns(
        returns=returns,
        expected_return_haircut=request.expected_return_haircut,
        enable_black_litterman=request.enable_black_litterman,
        view_expected_returns=request.view_expected_returns,
        view_weight=request.view_weight,
    )

    if request.current_weights is None:
        current_weights = get_default_current_weights()
    else:
        validate_weights(request.current_weights)
        current_weights = normalize_weights(request.current_weights)

    recommendations, search_summary = find_recommended_portfolios(
        returns=returns,
        expected_returns=expected_returns,
        request=request,
    )

    current_response = build_portfolio_response(
        name="현재 포트폴리오",
        api_key="current",
        weights=current_weights,
        returns=returns,
        expected_returns=expected_returns,
        request=request,
    )

    rec_1_response = build_portfolio_response(
        name="포트폴리오 A",
        api_key="portfolio_a",
        weights=recommendations[0]["weights"],
        returns=returns,
        expected_returns=expected_returns,
        request=request,
        score=recommendations[0]["score"],
    )

    rec_2_response = build_portfolio_response(
        name="포트폴리오 B",
        api_key="portfolio_b",
        weights=recommendations[1]["weights"],
        returns=returns,
        expected_returns=expected_returns,
        request=request,
        score=recommendations[1]["score"],
        correlation_with_recommended_1=recommendations[1].get("correlation_with_recommended_1"),
    )

    correlation_matrix = returns.corr().round(4).to_dict()
    asset_summary = build_asset_summary(returns, expected_returns)

    unique_ratio = request.unique_need_amount / request.total_asset

    return {
        "input_summary": {
            "total_asset": request.total_asset,
            "unique_need_amount": request.unique_need_amount,
            "unique_ratio": round(float(unique_ratio), 6),
            "unique_asset": request.unique_asset,
            "unique_asset_label": ASSET_NAMES_KR[request.unique_asset],
            "risk_profile": request.risk_profile,
            "client_risk_level": CLIENT_RISK_LEVEL[request.risk_profile],
            "investment_horizon_years": request.investment_horizon_years,
            "tax_sensitivity": request.tax_sensitivity,
            "liquidity_need": request.liquidity_need,
            "risk_free_rate": request.risk_free_rate,
            "cash_return": request.cash_return,
            "period": request.period,
            "num_simulations": request.num_simulations,
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
            "isa_remaining_capacity": request.isa_remaining_capacity,
            "isa_years_until_liquid": request.isa_years_until_liquid,
            "irp_enabled": request.irp_enabled,
            "irp_remaining_tax_credit_capacity": request.irp_remaining_tax_credit_capacity,
            "irp_tax_credit_rate": request.irp_tax_credit_rate,
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
            "portfolio_generation": "Monte Carlo 방식으로 후보 포트폴리오 생성. 6th 기본값은 5,000개.",
            "optimization_basis": "Mean-Variance 기반: 기대수익률, 공분산 기반 변동성, Sharpe Ratio 계산.",
            "risk_classification": "변동성, MDD, 유동성 커버리지, 자산구성비중을 hard filter로 사용.",
            "soft_scoring": "기대수익률, 세후수익률, Sharpe, Sortino, 금융소득 통제, 듀레이션 적합도 반영.",
            "duration_logic": "투자 가능 기간에 따라 목표 듀레이션을 단기 1.5년, 중기 4년, 장기 7년으로 두고 차이를 점수화.",
            "suitability_filter": "포트폴리오 위험등급이 고객 위험성향 이하인 경우만 추천.",
            "liquidity_metric": "현금+국채/저쿠폰채/분리과세채권 금액에서 ISA 의무기간 잠김 금액을 제외한 값 / 단기 필요금액.",
            "tax_logic": "금융소득종합과세 검토액, 해외주식 양도세 추정액, ISA/IRP 효과를 각 포트폴리오별로 계산.",
            "second_portfolio_logic": f"포트폴리오 B는 포트폴리오 A와 수익률 상관계수 {SECOND_PORTFOLIO_MAX_CORRELATION} 이하인 후보 중 점수가 높은 후보.",
            "stress_test_logic": "금리 충격은 -듀레이션×금리변화, 환율 충격은 외화노출자산×환율변화로 단순 추정.",
        },
        "notes": [
            "본 결과는 정보제공 목적이며 투자 판단과 책임은 투자자 본인에게 있습니다.",
            "기대수익률은 과거 일별 수익률을 연율화한 뒤 보수 조정한 추정값입니다.",
            "세금 계산은 간이 추정이며 실제 세액은 고객의 전체 소득, 실현손익, 보유계좌, 상품별 세법 요건에 따라 달라집니다.",
            "점수화 가중치와 포트폴리오 B 상관계수 기준은 공식 규정값이 아니라 프로젝트용 모델링 가정입니다.",
        ],
    }


def run_full_analysis(request: AnalysisRequest) -> Dict[str, Any]:
    session_id = str(uuid.uuid4())

    SESSION_REQUEST_STORE[session_id] = {
        "ips": model_to_dict(request.ips),
        "scenario": model_to_dict(request.scenario),
    }

    portfolio_request = convert_analysis_to_portfolio_request(request)
    core = run_analysis_core(portfolio_request)

    core["session_id"] = session_id
    core["scenario_summary"] = {
        "base_interest_rate": request.scenario.base_interest_rate,
        "base_fx_rate_krw_per_usd": request.scenario.base_fx_rate_krw_per_usd,
        "stressed_interest_rate": request.scenario.base_interest_rate + request.scenario.stress_interest_rate_shock,
        "stressed_fx_rate_krw_per_usd": request.scenario.base_fx_rate_krw_per_usd * (1 + request.scenario.stress_fx_shock),
        "stress_interest_rate_shock": request.scenario.stress_interest_rate_shock,
        "stress_fx_shock": request.scenario.stress_fx_shock,
        "stress_affects_scoring": request.scenario.stress_affects_scoring,
        "rrttllu": request.scenario.rrttllu,
    }

    core["backtest"] = extract_backtest_payload(core)
    core["tax_inputs"] = extract_tax_inputs_payload(core)

    return core


# ============================================================
# 13. API Endpoints
# ============================================================

@app.get("/")
def root():
    return {
        "message": "AI IPS Portfolio Analysis API - 6.0.0 separated endpoints",
        "swagger": "/docs",
    }


@app.get("/assets")
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
        }
        for asset in ASSET_TICKERS
    }


@app.get("/guidelines")
def get_guidelines():
    return get_guideline_definition()


@app.post("/api/portfolio/all")
def api_portfolio_all(request: AnalysisRequest):
    """
    최초 대시보드용 전체 API.
    현재 포트폴리오 / 포트폴리오 A / 포트폴리오 B / 백테스트 / 절세 입력값을 한 번에 반환.
    """
    try:
        return run_full_analysis(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/portfolio/current")
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/portfolio/a")
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/portfolio/b")
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/portfolio/bundle")
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/backtest")
def api_backtest(request: AnalysisRequest):
    """
    현재 / 포트폴리오 A / 포트폴리오 B 백테스트 데이터만 반환.
    """
    try:
        full = run_full_analysis(request)
        return extract_backtest_payload(full)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tax-inputs")
def api_tax_inputs(request: AnalysisRequest):
    """
    절세 최적화 파트에 넘길 값만 반환.
    절세제안 문구는 제외하고, 종합과세 임계점/해외주식 양도세/ISA·IRP·일반계좌 정보만 반환.
    """
    try:
        full = run_full_analysis(request)
        return extract_tax_inputs_payload(full)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}/request")
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

@app.post("/analyze")
def analyze_portfolio(request: PortfolioRequest):
    try:
        return run_analysis_core(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))