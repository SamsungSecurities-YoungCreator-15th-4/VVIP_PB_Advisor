# ruff: noqa: E501
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal, Tuple, Any
import uuid
import json
import threading
import logging
import re
import numpy as np
import pandas as pd
import yfinance as yf

router = APIRouter(tags=["portfolio"])
logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")


# ============================================================
# 0. 기본 설정
# ============================================================

TRADING_DAYS = 252
SORTINO_NO_DOWNSIDE_CAP = 3.0
MIN_COMMON_PRICE_OBSERVATIONS = 126
MAX_SESSION_REQUEST_STORE_SIZE = 100
BACKTEST_BASE_INDEX = 100.0
SEPARATE_TAX_BOND_MIN_HOLDING_YEARS = 3

# 시계열 충격 주입(calculate_metrics(shocks=...))에서 쓰는 변동성 확대 계수와 상한.
# 충격 |s| 1단위(=100%p)당 변동성 확대량 BETA, 상한 CAP. |s|=15%면 변동성 약 1.3배.
# 위기 국면에서 실현변동성이 함께 확대되는 현상을 반영한 프로젝트용 선형 근사다.
VOL_STRESS_BETA = 2.0
VOL_STRESS_CAP = 1.6

# PR #65 재현성 원칙: 모든 RNG 경로는 동일한 기본 시드를 사용한다.
DEFAULT_RANDOM_SEED = 42

# 최종 포트폴리오 지표 Range용 Monte Carlo.
# 후보 포트폴리오 생성용 Monte Carlo와 분리된 별도 계산이다.
MONTE_CARLO_METRIC_RANGE_VERSION = (
    "correlated-buy-and-hold-after-tax-mdd-p20-p80-v1"
)
MONTE_CARLO_METRIC_RANGE_SIMULATIONS = 10_000
MONTE_CARLO_METRIC_RANGE_MAX_HORIZON_YEARS = 5
MONTE_CARLO_METRIC_RANGE_STEPS_PER_YEAR = 12
MONTE_CARLO_METRIC_RANGE_SEED_OFFSET = 100_003
MONTE_CARLO_METRIC_RANGE_PERCENTILES = (10, 20, 50, 80, 90)
MONTE_CARLO_METRIC_RANGE_DISPLAY_LOWER = 20
MONTE_CARLO_METRIC_RANGE_DISPLAY_CENTER = 50
MONTE_CARLO_METRIC_RANGE_DISPLAY_UPPER = 80


# 프로젝트 가정: 약 3개월 미만의 공통 관측치로는 베타를 표시하지 않는다.
MIN_BETA_OBSERVATIONS = 60

# 0.5 * Σ|wA-wB|. 0.10은 전체 자산의 최소 10% 재배치를 뜻한다.
PORTFOLIO_B_MIN_WEIGHT_DISTANCE = 0.10

# 포트폴리오 가격 데이터 마지막 성공 스냅샷.
PRICE_SNAPSHOT_VERSION = 1
PRICE_SNAPSHOT_DIR = (
    Path(__file__).resolve().parents[2] / ".cache" / "portfolio"
)
PRICE_SNAPSHOT_PATH = PRICE_SNAPSHOT_DIR / "price_frames.json"
_PRICE_SNAPSHOT_LOCK = threading.RLock()

# 벤치마크는 추천 자산군이 아니라 최종 결과 비교용 데이터다.
# PB는 KOSPI, S&P 500, MSCI ACWI 중 하나를 표시 기준으로 선택할 수 있다.
BenchmarkKey = Literal["kospi", "sp500", "msci_acwi"]

DEFAULT_BENCHMARK_KEY: BenchmarkKey = "msci_acwi"
BENCHMARK_POLICY_VERSION = "pb-selectable-display-only-v1"

BENCHMARK_CONFIGS: Dict[str, Dict[str, Any]] = {
    "kospi": {
        "series_key": "_benchmark_kospi",
        "ticker": "^KS11",
        "label": "KOSPI",
        "currency": "KRW",
        "official_index_series": True,
        "proxy_note": None,
    },
    "sp500": {
        "series_key": "_benchmark_sp500",
        "ticker": "^GSPC",
        "label": "S&P 500",
        "currency": "USD",
        "official_index_series": True,
        "proxy_note": None,
    },
    "msci_acwi": {
        "series_key": "_benchmark_msci_acwi",
        "ticker": "ACWI",
        "label": "MSCI ACWI (ACWI ETF proxy)",
        "currency": "USD",
        "official_index_series": False,
        "proxy_note": (
            "공식 MSCI 지수 원시계열이 아니라 iShares MSCI ACWI ETF(ACWI)의 "
            "가격수익률을 글로벌 시장 대용치로 사용합니다."
        ),
    },
}

BENCHMARK_SERIES_KEYS = {
    config["series_key"] for config in BENCHMARK_CONFIGS.values()
}
PENSION_RECEIVE_AGE = 55

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

# seed.sql tax_rule.rule_key와 맞추기 위한 alias rule.
# 기존 세부 key는 추적용으로 유지하고, 화면/DB 연동 시에는 seed_rule_key를 우선 사용한다.
TAX_RULE_TABLE.update(
    {
        "financial_income_tax_threshold": {
            "value": FINANCIAL_INCOME_COMPREHENSIVE_TAX_THRESHOLD,
            "unit": "KRW",
            "source": "seed.sql tax_rule alias: financial_income_tax_threshold",
            "legacy_key": "financial_income_comprehensive_tax_threshold",
        },
        "overseas_stock_transfer_tax": {
            "value": OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE,
            "unit": "rate",
            "source": "seed.sql tax_rule alias: overseas_stock_transfer_tax",
            "params": {
                "basic_deduction": OVERSEAS_STOCK_GAIN_DEDUCTION,
                "loss_offset_scope": "overseas_equity_same_year",
            },
            "legacy_keys": [
                "overseas_stock_gain_deduction",
                "overseas_stock_capital_gains_tax_rate",
            ],
        },
        "isa_tax_exemption": {
            "value": ISA_LOW_TAX_RATE,
            "unit": "rate",
            "source": "seed.sql tax_rule alias: isa_tax_exemption",
            "params": {
                "general_tax_free_limit": ISA_GENERAL_TAX_FREE_LIMIT,
                "seogmin_tax_free_limit": ISA_SEOGMIN_TAX_FREE_LIMIT,
                "mandatory_holding_years": ISA_MANDATORY_HOLDING_YEARS,
                "annual_contribution_limit": ISA_ANNUAL_CONTRIBUTION_LIMIT,
                "total_contribution_limit": ISA_TOTAL_CONTRIBUTION_LIMIT,
            },
            "legacy_keys": [
                "isa_general_tax_free_limit",
                "isa_seogmin_tax_free_limit",
                "isa_low_tax_rate",
                "isa_mandatory_holding_years",
            ],
        },
        "pension_account_tax_credit": {
            "value": IRP_TAX_CREDIT_RATE_HIGH_INCOME,
            "unit": "rate",
            "source": "seed.sql tax_rule: pension_account_tax_credit",
            "params": {
                "tax_credit_limit": IRP_PENSION_COMBINED_TAX_CREDIT_LIMIT,
                "high_income_rate": IRP_TAX_CREDIT_RATE_HIGH_INCOME,
                "low_income_rate": IRP_TAX_CREDIT_RATE_LOW_INCOME,
            },
            "legacy_keys": [
                "irp_tax_credit",
                "irp_tax_credit_limit",
                "irp_tax_credit_rate_high_income",
                "irp_tax_credit_rate_low_income",
            ],
        },
        # 하위호환용 코드 alias. DB 조회 시에는 위 seed key를 사용한다.
        "irp_tax_credit": {
            "value": IRP_TAX_CREDIT_RATE_HIGH_INCOME,
            "unit": "rate",
            "source": "legacy alias of pension_account_tax_credit",
            "seed_rule_key": "pension_account_tax_credit",
        },
    }
)

# 하위호환용 상관계수 기준값.
# 포트폴리오 A/B 선정에는 사용하지 않고 화면 참고값 계산만 유지한다.
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
    "common_suitability_filter",
    "common_liquidity_filter",
    "common_historical_var_95_filter",
    "common_risk_contribution_filter",
    "portfolio_a_after_tax_return_desc",
    "portfolio_b_target_return_then_risk_contribution_asc",
]



# ============================================================
# 3. Request Models
# ============================================================


class IPSRequest(BaseModel):
    total_asset: float = Field(..., gt=0)
    unique_need_amount: float = Field(..., ge=0)
    unique_asset: str = Field(...)
    # Unique는 더 이상 특정 자산 하나만 의미하지 않는다.
    # 자연어/dict/list 원문은 unique_profile에 보존하고,
    # 현재 엔진이 해석 가능한 필요자금·ISA·IRP 정보만 결정론적으로 반영한다.
    unique_items: List[Dict[str, Any]] = Field(default_factory=list)
    unique_profile: Dict[str, Any] = Field(default_factory=dict)
    age: Optional[int] = Field(None, ge=0, le=120)
    client_context: Dict[str, Any] = Field(default_factory=dict)
    # RRTTLLU.Return은 퍼센트 단위다. 예: 8.0 -> 내부 비교값 0.08
    target_after_tax_return: Optional[float] = Field(None, gt=0.0, le=1.0)

    risk_profile: Literal["conservative", "balanced", "aggressive"] = Field(...)
    investment_horizon_years: int = Field(..., ge=1, le=50)
    tax_sensitivity: Literal["low", "medium", "high"] = Field(...)
    liquidity_need: Literal["low", "mid", "high"] = Field(...)

    current_weights: Optional[Dict[str, float]] = Field(None)

    risk_free_rate: float = Field(DEFAULT_RISK_FREE_RATE)
    cash_return: float = Field(DEFAULT_CASH_RETURN)
    period: str = Field("5y")
    benchmark_key: BenchmarkKey = Field(DEFAULT_BENCHMARK_KEY)

    num_simulations: int = Field(5000, ge=500, le=100000)
    expected_return_haircut: float = Field(0.75, ge=0.0, le=1.0)
    random_seed: int = Field(DEFAULT_RANDOM_SEED, ge=0)

    enable_black_litterman: bool = Field(False)
    view_expected_returns: Optional[Dict[str, float]] = Field(None)
    view_weight: float = Field(0.35, ge=0.0, le=1.0)

    marginal_income_tax_rate: float = Field(0.24, ge=0.06, le=0.495)
    overseas_stock_realized_gain_rate: float = Field(0.0, ge=0.0, le=1.0)
    overseas_realized_loss: float = Field(0.0, ge=0)
    # 외부 금융소득 입력은 단위 혼동을 막기 위해 명시형 필드를 우선 사용한다.
    # 우선순위: external_financial_income_krw > external_financial_income_manwon
    #          > other_financial_income(기존 호환, 원 단위).
    other_financial_income: float = Field(
        0.0, ge=0, description="기존 호환 필드: 현재 포트폴리오 외 연 이자·배당 금융소득(원)"
    )
    external_financial_income_krw: Optional[float] = Field(
        None, ge=0, description="현재 포트폴리오 외 연 이자·배당 금융소득(원)"
    )
    external_financial_income_manwon: Optional[float] = Field(
        None, ge=0, description="현재 포트폴리오 외 연 이자·배당 금융소득(만원)"
    )
    pension_tax_liability_sufficient: bool = Field(True)

    isa_enabled: bool = Field(True)
    isa_type: Literal["general", "seogmin"] = Field("general")
    isa_account_exists: bool = Field(False)
    isa_account_age_years: float = Field(0.0, ge=0, le=50)
    isa_cumulative_contribution: float = Field(0.0, ge=0)
    isa_current_year_contribution: float = Field(0.0, ge=0)
    isa_recent_3yr_comprehensive_taxed: bool = Field(False)
    isa_existing_account_usable: bool = Field(True)
    isa_remaining_capacity: float = Field(ISA_TOTAL_CONTRIBUTION_LIMIT, ge=0)
    isa_remaining_capacity_override: Optional[float] = Field(None, ge=0)
    isa_years_until_liquid: float = Field(ISA_MANDATORY_HOLDING_YEARS, ge=0, le=50)

    irp_enabled: bool = Field(True)
    irp_eligible: bool = Field(True)
    irp_account_exists: bool = Field(False)
    irp_account_age_years: float = Field(0.0, ge=0, le=80)
    irp_cumulative_contribution: float = Field(0.0, ge=0)
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


class PortfolioCalculateResponse(BaseModel):
    client_id: Optional[str] = None
    consultation_id: str
    calculation_session_id: str
    as_of: str
    risk_profile: str
    risk_profile_label: str
    portfolios: List[Dict[str, Any]]
    search_summary: Dict[str, Any]
    scenario_summary: Dict[str, Any]
    data_snapshot: Dict[str, Any]
    input_adapter: Dict[str, Any]
    methodology: Dict[str, Any]
    notes: List[str]


class PortfolioStressTestResponse(BaseModel):
    consultation_id: str
    calculation_session_id: str
    as_of: str
    risk_profile: str
    risk_profile_label: str
    portfolios: List[Dict[str, Any]]
    scenario_summary: Dict[str, Any]
    data_snapshot: Dict[str, Any]
    input_adapter: Dict[str, Any]


class AnalysisRequest(BaseModel):
    ips: IPSRequest = Field(...)
    scenario: ScenarioRequest = Field(...)


# 기존 /analyze 호환용
class PortfolioRequest(BaseModel):
    total_asset: float = Field(..., gt=0)
    unique_need_amount: float = Field(0, ge=0)
    unique_asset: str = Field("general_bond")
    unique_items: List[Dict[str, Any]] = Field(default_factory=list)
    unique_profile: Dict[str, Any] = Field(default_factory=dict)
    age: Optional[int] = Field(None, ge=0, le=120)
    client_context: Dict[str, Any] = Field(default_factory=dict)
    # RRTTLLU.Return은 퍼센트 단위다. 예: 8.0 -> 내부 비교값 0.08
    target_after_tax_return: Optional[float] = Field(None, gt=0.0, le=1.0)
    risk_profile: Literal["conservative", "balanced", "aggressive"] = Field(...)
    investment_horizon_years: int = Field(10, ge=1, le=50)
    tax_sensitivity: Literal["low", "medium", "high"] = Field("medium")
    liquidity_need: Literal["low", "mid", "high"] = Field("mid")
    current_weights: Optional[Dict[str, float]] = Field(None)

    risk_free_rate: float = Field(DEFAULT_RISK_FREE_RATE)
    cash_return: float = Field(DEFAULT_CASH_RETURN)
    period: str = Field("5y")
    benchmark_key: BenchmarkKey = Field(DEFAULT_BENCHMARK_KEY)
    num_simulations: int = Field(5000, ge=500, le=100000)
    expected_return_haircut: float = Field(0.75, ge=0.0, le=1.0)
    random_seed: int = Field(DEFAULT_RANDOM_SEED, ge=0)

    enable_black_litterman: bool = Field(False)
    view_expected_returns: Optional[Dict[str, float]] = Field(None)
    view_weight: float = Field(0.35, ge=0.0, le=1.0)

    stress_interest_rate_shock: float = Field(0.01)
    stress_fx_shock: float = Field(0.10)
    stress_affects_scoring: bool = Field(False)

    marginal_income_tax_rate: float = Field(0.24, ge=0.06, le=0.495)
    overseas_stock_realized_gain_rate: float = Field(0.0, ge=0.0, le=1.0)
    overseas_realized_loss: float = Field(0.0, ge=0)
    # 외부 금융소득 입력은 단위 혼동을 막기 위해 명시형 필드를 우선 사용한다.
    # 우선순위: external_financial_income_krw > external_financial_income_manwon
    #          > other_financial_income(기존 호환, 원 단위).
    other_financial_income: float = Field(
        0.0, ge=0, description="기존 호환 필드: 현재 포트폴리오 외 연 이자·배당 금융소득(원)"
    )
    external_financial_income_krw: Optional[float] = Field(
        None, ge=0, description="현재 포트폴리오 외 연 이자·배당 금융소득(원)"
    )
    external_financial_income_manwon: Optional[float] = Field(
        None, ge=0, description="현재 포트폴리오 외 연 이자·배당 금융소득(만원)"
    )
    pension_tax_liability_sufficient: bool = Field(True)

    isa_enabled: bool = Field(True)
    isa_type: Literal["general", "seogmin"] = Field("general")
    isa_account_exists: bool = Field(False)
    isa_account_age_years: float = Field(0.0, ge=0, le=50)
    isa_cumulative_contribution: float = Field(0.0, ge=0)
    isa_current_year_contribution: float = Field(0.0, ge=0)
    isa_recent_3yr_comprehensive_taxed: bool = Field(False)
    isa_existing_account_usable: bool = Field(True)
    isa_remaining_capacity: float = Field(ISA_TOTAL_CONTRIBUTION_LIMIT, ge=0)
    isa_remaining_capacity_override: Optional[float] = Field(None, ge=0)
    isa_years_until_liquid: float = Field(ISA_MANDATORY_HOLDING_YEARS, ge=0, le=50)

    irp_enabled: bool = Field(True)
    irp_eligible: bool = Field(True)
    irp_account_exists: bool = Field(False)
    irp_account_age_years: float = Field(0.0, ge=0, le=80)
    irp_cumulative_contribution: float = Field(0.0, ge=0)
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


# ============================================================
# 5. 가격 데이터
# ============================================================


def _empty_benchmark_snapshot(reason: str) -> Dict[str, Any]:
    return {
        "policy": BENCHMARK_POLICY_VERSION,
        "default_key": DEFAULT_BENCHMARK_KEY,
        "affects_portfolio_recommendation": False,
        "options": {
            key: {
                "key": key,
                "ticker": config["ticker"],
                "label": config["label"],
                "official_index_series": config["official_index_series"],
                "proxy_note": config["proxy_note"],
                "available": False,
                "reason": reason,
                "data_start": None,
                "data_end": None,
                "observations": 0,
            }
            for key, config in BENCHMARK_CONFIGS.items()
        },
    }


def download_benchmark_returns(
    period: str,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """비교용 벤치마크 수익률을 투자자산 데이터와 별도로 조회한다.

    이 함수의 결과는 베타와 비교 차트에만 사용한다.
    추천 후보 생성, 기대수익률, 공분산, VaR, ERC, 순위에는 전달하지 않는다.
    """
    tickers = [config["ticker"] for config in BENCHMARK_CONFIGS.values()]

    try:
        raw = yf.download(
            tickers,
            period=period,
            auto_adjust=True,
            progress=False,
            group_by="column",
            threads=True,
        )
    except Exception:
        logger.warning("벤치마크 시세 조회 실패", exc_info=True)
        return pd.DataFrame(), _empty_benchmark_snapshot("download_failed")

    if raw.empty:
        return pd.DataFrame(), _empty_benchmark_snapshot("download_empty")

    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" not in raw.columns.get_level_values(0):
            return pd.DataFrame(), _empty_benchmark_snapshot("close_price_missing")
        close = raw["Close"].copy()
    else:
        if "Close" not in raw.columns:
            return pd.DataFrame(), _empty_benchmark_snapshot("close_price_missing")
        close = raw[["Close"]].copy()
        if len(tickers) == 1:
            close.columns = tickers

    if isinstance(close, pd.Series):
        close = close.to_frame(name=tickers[0])

    close = close.dropna(how="all").sort_index()

    series_map: Dict[str, pd.Series] = {}
    option_meta: Dict[str, Any] = {}

    for key, config in BENCHMARK_CONFIGS.items():
        ticker = config["ticker"]
        base_meta = {
            "key": key,
            "ticker": ticker,
            "label": config["label"],
            "official_index_series": config["official_index_series"],
            "proxy_note": config["proxy_note"],
        }

        if ticker not in close.columns:
            option_meta[key] = {
                **base_meta,
                "available": False,
                "reason": "benchmark_data_missing",
                "data_start": None,
                "data_end": None,
                "observations": 0,
            }
            continue

        price_series = (
            close[ticker]
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )
        benchmark_return = (
            price_series
            .pct_change(fill_method=None)
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )

        if benchmark_return.empty:
            option_meta[key] = {
                **base_meta,
                "available": False,
                "reason": "benchmark_data_empty",
                "data_start": None,
                "data_end": None,
                "observations": 0,
            }
            continue

        series_key = config["series_key"]
        benchmark_return.name = series_key
        series_map[series_key] = benchmark_return

        option_meta[key] = {
            **base_meta,
            "series_key": series_key,
            "available": True,
            "reason": None,
            "data_start": benchmark_return.index[0].strftime("%Y-%m-%d"),
            "data_end": benchmark_return.index[-1].strftime("%Y-%m-%d"),
            "observations": int(len(benchmark_return)),
        }

    benchmark_frame = (
        pd.concat(series_map.values(), axis=1)
        if series_map
        else pd.DataFrame()
    )

    snapshot = {
        "policy": BENCHMARK_POLICY_VERSION,
        "default_key": DEFAULT_BENCHMARK_KEY,
        "affects_portfolio_recommendation": False,
        "options": option_meta,
    }
    return benchmark_frame, snapshot


def _price_snapshot_key(
    kind: str,
    period: str,
    cash_return: float,
) -> str:
    return f"{kind}|{period}|cash={float(cash_return):.8f}"


def _read_price_snapshot_store() -> Dict[str, Any]:
    with _PRICE_SNAPSHOT_LOCK:
        try:
            with open(
                PRICE_SNAPSHOT_PATH,
                encoding="utf-8",
            ) as file:
                payload = json.load(file)
        except (
            OSError,
            json.JSONDecodeError,
            TypeError,
        ):
            return {
                "version": PRICE_SNAPSHOT_VERSION,
                "snapshots": {},
            }

    if not isinstance(payload, dict):
        return {
            "version": PRICE_SNAPSHOT_VERSION,
            "snapshots": {},
        }

    payload.setdefault(
        "version",
        PRICE_SNAPSHOT_VERSION,
    )
    payload.setdefault("snapshots", {})
    return payload


def _frame_to_snapshot_payload(
    frame: pd.DataFrame,
) -> Dict[str, Any]:
    return {
        "saved_at": datetime.now(KST).isoformat(),
        "index": [
            pd.Timestamp(value).isoformat()
            for value in frame.index
        ],
        "columns": [
            str(column)
            for column in frame.columns
        ],
        "data": [
            [
                None
                if pd.isna(value)
                else float(value)
                for value in row
            ]
            for row in frame.to_numpy()
        ],
        "attrs": dict(frame.attrs),
    }


def _snapshot_payload_to_frame(
    payload: Dict[str, Any],
) -> pd.DataFrame:
    frame = pd.DataFrame(
        data=payload.get("data", []),
        index=pd.to_datetime(
            payload.get("index", [])
        ),
        columns=payload.get("columns", []),
        dtype=float,
    ).sort_index()
    frame.attrs.update(payload.get("attrs", {}))
    return frame


def _save_price_frame_snapshot(
    key: str,
    frame: pd.DataFrame,
) -> None:
    payload = _frame_to_snapshot_payload(frame)

    with _PRICE_SNAPSHOT_LOCK:
        store = _read_price_snapshot_store()
        store["version"] = PRICE_SNAPSHOT_VERSION
        store.setdefault("snapshots", {})[
            key
        ] = payload

        PRICE_SNAPSHOT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )
        temporary_path = (
            PRICE_SNAPSHOT_PATH.with_suffix(".tmp")
        )
        try:
            with open(
                temporary_path,
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    store,
                    file,
                    ensure_ascii=False,
                    default=str,
                )
            temporary_path.replace(
                PRICE_SNAPSHOT_PATH
            )
        except OSError:
            logger.warning(
                "가격 스냅샷 저장 실패: %s",
                PRICE_SNAPSHOT_PATH,
                exc_info=True,
            )


def _load_price_frame_snapshot(
    key: str,
) -> Optional[
    Tuple[pd.DataFrame, Dict[str, Any]]
]:
    payload = (
        _read_price_snapshot_store()
        .get("snapshots", {})
        .get(key)
    )
    if not isinstance(payload, dict):
        return None

    try:
        frame = _snapshot_payload_to_frame(
            payload
        )
    except (
        TypeError,
        ValueError,
        KeyError,
    ):
        logger.warning(
            "가격 스냅샷 복원 실패: %s",
            key,
            exc_info=True,
        )
        return None

    if frame.empty:
        return None

    return frame, {
        "saved_at": payload.get("saved_at"),
        "cache_key": key,
    }


def _apply_live_data_metadata(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    snapshot = dict(
        frame.attrs.get("data_snapshot", {})
    )
    snapshot.update(
        {
            "data_source": "yfinance_live",
            "fallback_used": False,
            "fallback_reason": None,
        }
    )
    frame.attrs["data_snapshot"] = snapshot
    return frame


def _apply_cached_data_metadata(
    frame: pd.DataFrame,
    *,
    cache_metadata: Dict[str, Any],
    error: Exception,
) -> pd.DataFrame:
    snapshot = dict(
        frame.attrs.get("data_snapshot", {})
    )
    snapshot.update(
        {
            "data_source": (
                "disk_last_success_snapshot"
            ),
            "fallback_used": True,
            "fallback_saved_at": (
                cache_metadata.get("saved_at")
            ),
            "fallback_reason": (
                f"{type(error).__name__}: "
                f"{str(error)}"
            )[:300],
            "note": (
                "실시간 조회 실패로 마지막 성공 "
                "스냅샷을 사용했습니다. 현재안과 "
                "추천안 A/B는 동일한 시계열로 "
                "계산됩니다."
            ),
        }
    )
    frame.attrs["data_snapshot"] = snapshot
    return frame

def _download_price_data_live(period: str, cash_return: float) -> pd.DataFrame:
    """추천·지표 계산용 투자자산 가격 데이터.

    벤치마크는 이 함수에서 조회하지 않는다. 따라서 벤치마크의 결측치,
    상장 이력, 데이터 시작일은 추천 포트폴리오에 영향을 주지 않는다.
    """
    tickers = {
        asset: ticker
        for asset, ticker in ASSET_TICKERS.items()
        if ticker != "CASH"
    }

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
        if asset != "cash"
        and asset in prices.columns
        and prices[asset].notna().any()
    ]
    excluded_assets = [
        asset
        for asset in ASSET_TICKERS.keys()
        if asset != "cash" and asset not in available_assets
    ]

    if excluded_assets:
        raise RuntimeError(
            "확정 자산군 중 가격 데이터를 가져오지 못한 자산이 있습니다. "
            f"excluded_assets={excluded_assets}. "
            "티커, 상장일, yfinance 다운로드 상태를 확인해 주세요."
        )

    first_valid_dates = {
        asset: prices[asset].first_valid_index()
        for asset in available_assets
    }
    common_start = max(first_valid_dates.values())
    limiting_assets = [
        asset
        for asset, start_date in first_valid_dates.items()
        if start_date == common_start
    ]

    common_prices = (
        prices.loc[common_start:, available_assets]
        .ffill()
        .dropna(how="any")
    )

    if len(common_prices) < MIN_COMMON_PRICE_OBSERVATIONS:
        raise RuntimeError(
            "공통 실제 가격 데이터 구간이 너무 짧습니다. "
            f"observations={len(common_prices)}, "
            f"min_required={MIN_COMMON_PRICE_OBSERVATIONS}, "
            f"common_start={common_start.date() if common_start is not None else None}, "
            f"limiting_assets={limiting_assets}. "
            "최근 상장 ETF proxy를 더 긴 이력 proxy로 바꾸는지 검토해 주세요."
        )

    daily_cash_return = (1 + cash_return) ** (1 / TRADING_DAYS) - 1
    common_prices["cash"] = (
        (1 + daily_cash_return) ** np.arange(len(common_prices))
    )

    ordered_assets = [
        asset
        for asset in ASSET_TICKERS.keys()
        if asset in common_prices.columns
    ]
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
            asset: date.strftime("%Y-%m-%d")
            for asset, date in first_valid_dates.items()
        },
        "limiting_assets": limiting_assets,
        "usage": "metrics_and_recommendation_investable_assets_only",
        "benchmark_included": False,
        "note": (
            "추천·기대수익률·공분산·위험지표 계산용 데이터. "
            "벤치마크는 포함하지 않으며, 전체 투자자산의 공통 실제 가격 구간만 사용."
        ),
    }

    return common_prices


def download_price_data(
    period: str,
    cash_return: float,
) -> pd.DataFrame:
    cache_key = _price_snapshot_key(
        "analysis_prices",
        period,
        cash_return,
    )
    try:
        prices = _download_price_data_live(
            period=period,
            cash_return=cash_return,
        )
        prices = _apply_live_data_metadata(
            prices
        )
        _save_price_frame_snapshot(
            cache_key,
            prices,
        )
        return prices
    except Exception as error:
        cached = _load_price_frame_snapshot(
            cache_key
        )
        if cached is None:
            raise

        cached_prices, metadata = cached
        logger.warning(
            "가격 조회 실패. 마지막 성공 "
            "스냅샷 사용: %s",
            cache_key,
            exc_info=True,
        )
        return _apply_cached_data_metadata(
            cached_prices,
            cache_metadata=metadata,
            error=error,
        )


def _download_backtest_price_data_live(
    period: str,
    cash_return: float,
) -> pd.DataFrame:
    """백테스트 차트 전용 투자자산 5년 가격 데이터.

    벤치마크는 별도 함수에서 조회하고 이 결과에는 포함하지 않는다.
    """
    period = "5y"

    tickers = {
        asset: ticker
        for asset, ticker in ASSET_TICKERS.items()
        if ticker != "CASH"
    }

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

    if prices.empty:
        raise RuntimeError("가격 데이터가 비어 있습니다.")

    base_index = prices.index
    daily_cash_return = (1 + cash_return) ** (1 / TRADING_DAYS) - 1

    backtest_prices = pd.DataFrame(index=base_index)
    first_valid_dates: Dict[str, Any] = {}
    cash_substituted_assets: Dict[str, Any] = {}
    excluded_assets: List[str] = []

    for asset in ASSET_TICKERS.keys():
        if asset == "cash":
            continue

        if asset not in prices.columns or prices[asset].notna().sum() == 0:
            excluded_assets.append(asset)
            continue

        series = prices[asset].reindex(base_index).ffill()
        first_valid_date = series.first_valid_index()

        if first_valid_date is None:
            excluded_assets.append(asset)
            continue

        first_valid_dates[asset] = first_valid_date
        first_pos = base_index.get_loc(first_valid_date)

        if first_pos > 0:
            first_real_price = float(series.loc[first_valid_date])
            reverse_steps = np.arange(first_pos, 0, -1)
            pre_listing_values = first_real_price / (
                (1 + daily_cash_return) ** reverse_steps
            )
            series.iloc[:first_pos] = pre_listing_values

            cash_substituted_assets[asset] = {
                "substituted_from": base_index[0].strftime("%Y-%m-%d"),
                "substituted_until": base_index[first_pos - 1].strftime(
                    "%Y-%m-%d"
                ),
                "first_real_price_date": first_valid_date.strftime("%Y-%m-%d"),
                "method": (
                    "backtest_only_pre_listing_period_replaced_with_cash_return"
                ),
            }

        backtest_prices[asset] = series.ffill()

    if excluded_assets:
        raise RuntimeError(
            "확정 자산군 중 가격 데이터를 전혀 가져오지 못한 자산이 있습니다. "
            f"excluded_assets={excluded_assets}. "
            "티커 또는 yfinance 다운로드 상태를 확인해 주세요."
        )

    backtest_prices["cash"] = (
        (1 + daily_cash_return) ** np.arange(len(base_index))
    )

    ordered_assets = [
        asset
        for asset in ASSET_TICKERS.keys()
        if asset in backtest_prices.columns
    ]
    backtest_prices = backtest_prices[ordered_assets]

    if backtest_prices.isna().any().any():
        missing_assets = backtest_prices.columns[
            backtest_prices.isna().any()
        ].tolist()
        raise RuntimeError(
            "백테스트용 현금 대체 이후에도 결측치가 남아 있습니다. "
            f"missing_assets={missing_assets}"
        )

    if len(backtest_prices) < MIN_COMMON_PRICE_OBSERVATIONS:
        raise RuntimeError(
            "5년 백테스트 가격 데이터 구간이 너무 짧습니다. "
            f"observations={len(backtest_prices)}, "
            f"min_required={MIN_COMMON_PRICE_OBSERVATIONS}"
        )

    backtest_prices.attrs["data_snapshot"] = {
        "period_requested": period,
        "as_of": backtest_prices.index[-1].strftime("%Y-%m-%d"),
        "data_start": backtest_prices.index[0].strftime("%Y-%m-%d"),
        "data_end": backtest_prices.index[-1].strftime("%Y-%m-%d"),
        "observations": int(len(backtest_prices)),
        "available_assets": ordered_assets,
        "excluded_assets": excluded_assets,
        "first_valid_dates": {
            asset: date.strftime("%Y-%m-%d")
            for asset, date in first_valid_dates.items()
        },
        "cash_substituted_assets": cash_substituted_assets,
        "limiting_assets": [],
        "usage": "backtest_chart_investable_assets_only",
        "benchmark_included": False,
        "note": (
            "백테스트 차트 전용 투자자산 데이터. "
            "신규 상장 또는 데이터 시작 전 구간만 현금 수익률로 대체하며, "
            "벤치마크는 별도 조회."
        ),
    }

    return backtest_prices


def download_backtest_price_data(
    period: str,
    cash_return: float,
) -> pd.DataFrame:
    fixed_period = "5y"
    cache_key = _price_snapshot_key(
        "backtest_prices",
        fixed_period,
        cash_return,
    )
    try:
        prices = (
            _download_backtest_price_data_live(
                period=fixed_period,
                cash_return=cash_return,
            )
        )
        prices = _apply_live_data_metadata(
            prices
        )
        _save_price_frame_snapshot(
            cache_key,
            prices,
        )
        return prices
    except Exception as error:
        cached = _load_price_frame_snapshot(
            cache_key
        )
        if cached is None:
            raise

        cached_prices, metadata = cached
        logger.warning(
            "백테스트 조회 실패. 마지막 성공 "
            "스냅샷 사용: %s",
            cache_key,
            exc_info=True,
        )
        return _apply_cached_data_metadata(
            cached_prices,
            cache_metadata=metadata,
            error=error,
        )


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


def resolve_external_financial_income_krw(request: PortfolioRequest) -> float:
    """현재 포트폴리오 외 연 이자·배당 금융소득을 원 단위로 정규화한다.

    프론트 화면은 만원 입력을 사용하므로 명시형 필드를 함께 지원한다.
    여러 필드가 동시에 오면 단위가 명확한 krw → manwon → 기존 필드 순으로 사용한다.
    """
    explicit_krw = getattr(request, "external_financial_income_krw", None)
    if explicit_krw is not None:
        return max(safe_float(explicit_krw), 0.0)

    explicit_manwon = getattr(request, "external_financial_income_manwon", None)
    if explicit_manwon is not None:
        return max(safe_float(explicit_manwon), 0.0) * 10_000

    return max(safe_float(getattr(request, "other_financial_income", 0.0)), 0.0)


def calculate_financial_income_comprehensive_tax_status(
    portfolio_financial_income: float,
    external_financial_income: float = 0.0,
    marginal_income_tax_rate: float = 0.24,
) -> Dict[str, Any]:
    """금융소득종합과세 임계선 화면과 세후 계산에 쓰는 단일 상태값.

    - portfolio_financial_income: 추천 포트폴리오에서 예상되는 연 이자·배당(원)
    - external_financial_income: 예금·기존 계좌 등 현재 포트폴리오 외 금융소득(원)
    - 총 금융소득이 2,000만원을 초과하는지 판단한다.
    - 포트폴리오 세후수익률에는 외부소득 자체의 세금을 떠넘기지 않도록
      '외부소득만 있을 때 대비 포트폴리오로 증가한 추가세액'을 별도 산출한다.
    """
    portfolio_income = max(safe_float(portfolio_financial_income), 0.0)
    external_income = max(safe_float(external_financial_income), 0.0)
    total_income = portfolio_income + external_income
    threshold = FINANCIAL_INCOME_COMPREHENSIVE_TAX_THRESHOLD
    excess = max(total_income - threshold, 0.0)
    external_only_excess = max(external_income - threshold, 0.0)

    marginal_rate = min(max(safe_float(marginal_income_tax_rate), 0.0), 0.495)
    additional_rate = max(marginal_rate - DEFAULT_WITHHOLDING_TAX_RATE, 0.0)
    total_additional_tax = excess * additional_rate
    external_baseline_tax = external_only_excess * additional_rate
    portfolio_incremental_tax = max(total_additional_tax - external_baseline_tax, 0.0)

    def to_manwon(value: float) -> int:
        return int(round(value / 10_000))

    return {
        # 기존 키는 총 금융소득 의미로 유지해 기존 프론트와 하위호환한다.
        "taxable_financial_income": safe_round(total_income, 0),
        "portfolio_financial_income": safe_round(portfolio_income, 0),
        "external_financial_income": safe_round(external_income, 0),
        "total_financial_income": safe_round(total_income, 0),
        "threshold": threshold,
        "excess_over_threshold": safe_round(excess, 0),
        "is_over_threshold": total_income > threshold,
        "withholding_tax_rate": DEFAULT_WITHHOLDING_TAX_RATE,
        "marginal_income_tax_rate": safe_round(marginal_rate, 6),
        "additional_tax_rate": safe_round(additional_rate, 6),
        "estimated_additional_tax_total": safe_round(total_additional_tax, 0),
        "estimated_additional_tax_external_baseline": safe_round(
            external_baseline_tax, 0
        ),
        "estimated_additional_tax_attributable_to_portfolio": safe_round(
            portfolio_incremental_tax, 0
        ),
        "rule_key": "financial_income_tax_threshold",
        "basis": (
            "현재 포트폴리오 외 금융소득과 포트폴리오 예상 이자·배당을 합산해 "
            "금융소득종합과세 2,000만원 기준을 점검합니다. 실제 세액은 다른 종합소득과 "
            "공제사항을 포함해 확인해야 합니다."
        ),
        # TaxGauge가 별도 환산 로직 없이 바로 사용할 수 있는 표시 계약.
        "gauge": {
            "external_financial_income_manwon": to_manwon(external_income),
            "portfolio_financial_income_manwon": to_manwon(portfolio_income),
            "total_financial_income_manwon": to_manwon(total_income),
            "threshold_manwon": to_manwon(threshold),
            "excess_over_threshold_manwon": to_manwon(excess),
            "estimated_additional_tax_manwon": to_manwon(total_additional_tax),
            "is_over_threshold": total_income > threshold,
            "withholding_rate_pct": safe_round(
                DEFAULT_WITHHOLDING_TAX_RATE * 100, 1
            ),
            "marginal_rate_pct": safe_round(marginal_rate * 100, 1),
            "additional_rate_pct": safe_round(additional_rate * 100, 1),
            "separate_rate_label": f"{DEFAULT_WITHHOLDING_TAX_RATE * 100:.1f}%",
            "comprehensive_rate_label": f"예상 {marginal_rate * 100:.1f}%",
            "rate_note": (
                "49.5%는 최고세율이며, 화면에는 고객 입력 한계세율을 표시합니다."
            ),
        },
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
        "rule_keys": ["overseas_stock_transfer_tax"],
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


def calculate_irp_status(
    request: PortfolioRequest,
) -> Dict[str, Any]:
    calculated_capacity = max(
        IRP_PENSION_COMBINED_TAX_CREDIT_LIMIT
        - request.irp_current_year_contribution,
        0.0,
    )
    manual_capacity = (
        request.irp_remaining_tax_credit_capacity
    )
    if (
        request
        .irp_remaining_tax_credit_capacity_override
        is not None
    ):
        manual_capacity = (
            request
            .irp_remaining_tax_credit_capacity_override
        )

    remaining_capacity = min(
        calculated_capacity,
        manual_capacity,
    )
    age_input_available = (
        request.age is not None
    )

    derived_years_until_access: (
        Optional[float]
    ) = None
    if age_input_available:
        derived_years_until_access = float(
            max(
                PENSION_RECEIVE_AGE
                - request.age,
                0,
            )
        )

    effective_years_until_access = max(
        safe_float(
            request.irp_years_until_access
        ),
        safe_float(
            derived_years_until_access
        ),
    )
    horizon_suitable = bool(
        age_input_available
        and (
            request.age
            >= PENSION_RECEIVE_AGE
            or (
                request
                .investment_horizon_years
                >= effective_years_until_access
            )
        )
    )
    manual_review_required = bool(
        request.irp_enabled
        and request.irp_eligible
        and not age_input_available
    )
    irp_usable = bool(
        request.irp_enabled
        and request.irp_eligible
        and age_input_available
        and horizon_suitable
        and remaining_capacity > 0
    )

    if not irp_usable:
        remaining_capacity = 0.0

    if irp_usable:
        reason = (
            "irp_tax_credit_capacity_available"
        )
    elif not request.irp_enabled:
        reason = "irp_disabled_by_input"
    elif not request.irp_eligible:
        reason = "irp_not_eligible"
    elif not age_input_available:
        reason = (
            "age_missing_manual_review_required"
        )
    elif not horizon_suitable:
        reason = (
            "investment_horizon_shorter_"
            "than_pension_access"
        )
    else:
        reason = (
            "irp_remaining_capacity_zero"
        )

    return {
        "enabled": request.irp_enabled,
        "eligible": request.irp_eligible,
        "usable": irp_usable,
        "age": request.age,
        "age_input_available": (
            age_input_available
        ),
        "manual_review_required": (
            manual_review_required
        ),
        "pension_receive_age": (
            PENSION_RECEIVE_AGE
        ),
        "horizon_suitable": (
            horizon_suitable
        ),
        "investment_horizon_years": (
            request.investment_horizon_years
        ),
        "account_exists": (
            request.irp_account_exists
        ),
        "account_age_years": safe_round(
            request.irp_account_age_years,
            2,
        ),
        "cumulative_contribution": safe_round(
            request.irp_cumulative_contribution,
            0,
        ),
        "annual_tax_credit_limit": (
            IRP_PENSION_COMBINED_TAX_CREDIT_LIMIT
        ),
        "current_year_contribution": (
            safe_round(
                request
                .irp_current_year_contribution,
                0,
            )
        ),
        "calculated_remaining_capacity": (
            safe_round(
                calculated_capacity,
                0,
            )
        ),
        "remaining_tax_credit_capacity_input": (
            safe_round(
                request
                .irp_remaining_tax_credit_capacity,
                0,
            )
        ),
        "remaining_capacity_override": (
            safe_round(
                request
                .irp_remaining_tax_credit_capacity_override,
                0,
            )
            if (
                request
                .irp_remaining_tax_credit_capacity_override
                is not None
            )
            else None
        ),
        "remaining_tax_credit_capacity": (
            safe_round(
                remaining_capacity,
                0,
            )
        ),
        "tax_credit_rate": (
            request.irp_tax_credit_rate
        ),
        "years_until_access_input": (
            safe_round(
                request.irp_years_until_access,
                2,
            )
        ),
        "years_until_access_derived_from_age": (
            safe_round(
                derived_years_until_access,
                2,
            )
            if (
                derived_years_until_access
                is not None
            )
            else None
        ),
        "years_until_access": safe_round(
            effective_years_until_access,
            2,
        ),
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

    # 일반과세계좌의 명확한 역할 1: 단기 필요자금은 lock-up 계좌보다 먼저 확보한다.
    liquidity_reserve_target = min(max(request.unique_need_amount, 0.0), total_asset)
    liquidity_reserve_remaining = liquidity_reserve_target
    reserve_priority = ["cash", "general_bond", "low_coupon_bond", "separate_tax_bond"]
    for asset in reserve_priority:
        amount = min(remaining_amounts.get(asset, 0.0), liquidity_reserve_remaining)
        if amount > 0:
            taxable_alloc[asset] += amount
            remaining_amounts[asset] -= amount
            liquidity_reserve_remaining -= amount
        if liquidity_reserve_remaining <= 0:
            break

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

    # 일반과세계좌의 역할 2: 세제계좌 한도·적격성 적용 후 나머지 투자자산을 계속 운용한다.
    for asset, amount in remaining_amounts.items():
        taxable_alloc[asset] += max(amount, 0.0)

    isa_total = sum(isa_alloc.values())
    irp_total = sum(irp_alloc.values())
    taxable_total = sum(taxable_alloc.values())
    liquidity_reserve_allocated = max(
        liquidity_reserve_target - liquidity_reserve_remaining, 0.0
    )

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
            "rule_keys": ["isa_tax_exemption"],
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
            "rule_keys": ["pension_account_tax_credit"],
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
            "account_role": "taxable_investment_and_liquidity",
            "display_name": "일반과세 자산 운용",
            "allocated_amount": safe_round(taxable_total, 0),
            "liquidity_reserve_target": safe_round(liquidity_reserve_target, 0),
            "liquidity_reserve_allocated": safe_round(liquidity_reserve_allocated, 0),
            "liquidity_reserve_shortfall": safe_round(liquidity_reserve_remaining, 0),
            "liquidity_reserve_basis": "cash_like_assets_only",
            "liquidity_reserve_assets": reserve_priority,
            "liquidity_reserve_fully_funded": (
                liquidity_reserve_remaining <= 1e-6
            ),
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



def calculate_six_strategy_tax_model(
    weights: Dict[str, float],
    expected_returns: pd.Series,
    total_asset: float,
    request: PortfolioRequest,
    account_buckets: Optional[
        Dict[str, Any]
    ] = None,
) -> Dict[str, Any]:
    try:
        from .tax_advice import (
            calc_combined_tax_saving,
            calc_tax_advice,
        )
    except ImportError:
        from tax_advice import (
            calc_combined_tax_saving,
            calc_tax_advice,
        )

    normalized = normalize_weights(
        weights
    )
    portfolio = [
        {
            "asset_class": asset,
            "weight": safe_float(weight),
        }
        for asset, weight
        in normalized.items()
        if safe_float(weight) > 1e-12
    ]
    expected_return = sum(
        normalized.get(asset, 0.0)
        * safe_float(
            expected_returns.get(asset)
        )
        for asset in normalized
        if asset in expected_returns.index
    )
    expected_by_asset = {
        asset: safe_float(
            expected_returns.get(asset)
        )
        for asset in normalized
        if asset in expected_returns.index
    }

    if account_buckets is None:
        account_buckets = (
            allocate_account_buckets(
                normalized,
                total_asset,
                request,
            )
        )
    isa_status = account_buckets["isa"]
    irp_status = account_buckets["irp"]

    kwargs = {
        "isa_used_manwon": (
            request
            .isa_current_year_contribution
            / 10_000
        ),
        "pension_used_manwon": (
            request
            .irp_current_year_contribution
            / 10_000
        ),
        "realized_loss_manwon": (
            request.overseas_realized_loss
            / 10_000
        ),
        "other_financial_income": (
            resolve_external_financial_income_krw(
                request
            )
            / 1e8
        ),
        "marginal_income_tax_rate": (
            request
            .marginal_income_tax_rate
        ),
        "age": request.age,
        "horizon_years": (
            request
            .investment_horizon_years
        ),
        "near_term_need_manwon": (
            request.unique_need_amount
            / 10_000
        ),
        "near_term_need_years": (
            request.unique_profile.get(
                "liquidity_need_years"
            )
        ),
        "isa_opened": (
            request.isa_account_exists
        ),
        "isa_can_open_new": (
            isa_status.get(
                "can_open_new",
                True,
            )
        ),
        "isa_usable": (
            isa_status.get("usable")
        ),
        "isa_years_until_liquid": (
            isa_status.get(
                "years_until_liquid"
            )
        ),
        "pension_usable": (
            irp_status.get("usable")
        ),
        "pension_tax_liability_sufficient": (
            request
            .pension_tax_liability_sufficient
        ),
        "pension_tax_credit_rate": (
            request.irp_tax_credit_rate
        ),
        "expected_returns_by_asset": (
            expected_by_asset or None
        ),
    }

    standalone = calc_tax_advice(
        portfolio,
        expected_return,
        total_asset / 1e8,
        **kwargs,
    )
    combined = (
        calc_combined_tax_saving(
            portfolio,
            expected_return,
            total_asset / 1e8,
            **kwargs,
        )
    )
    return {
        "model_version": (
            "six_strategy_combined_v1"
        ),
        "standalone": standalone,
        "combined": combined,
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

        asset_expected_return = safe_float(
            expected_returns[asset]
        )
        asset_profit = (
            weight
            * total_asset
            * asset_expected_return
        )
        gross_profit += asset_profit

        income_profit = (
            estimate_income_profit_for_asset(
                asset=asset,
                weight=weight,
                expected_return=asset_expected_return,
                total_asset=total_asset,
            )
        )
        if income_profit > 0:
            withholding_tax += (
                income_profit
                * DEFAULT_WITHHOLDING_TAX_RATE
            )

    portfolio_financial_income = (
        estimate_taxable_financial_income(
            weights,
            expected_returns,
            total_asset,
        )
    )
    external_financial_income = (
        resolve_external_financial_income_krw(
            request
        )
    )
    comprehensive_tax_status = (
        calculate_financial_income_comprehensive_tax_status(
            portfolio_financial_income=(
                portfolio_financial_income
            ),
            external_financial_income=(
                external_financial_income
            ),
            marginal_income_tax_rate=(
                request.marginal_income_tax_rate
            ),
        )
    )

    overseas_tax = (
        estimate_overseas_stock_capital_gains_tax(
            weights=weights,
            expected_returns=expected_returns,
            total_asset=total_asset,
            realized_gain_rate=(
                request
                .overseas_stock_realized_gain_rate
            ),
        )
    )

    account_buckets = allocate_account_buckets(
        weights,
        total_asset,
        request,
    )

    legacy_tax_saving_effect = (
        estimate_tax_saving_effect(
            weights=weights,
            expected_returns=expected_returns,
            total_asset=total_asset,
            request=request,
            account_buckets=account_buckets,
        )
    )
    legacy_account_only_tax_saving = (
        safe_float(
            legacy_tax_saving_effect.get(
                "estimated_total_tax_saving"
            )
        )
    )

    six_strategy_tax_model = (
        calculate_six_strategy_tax_model(
            weights=weights,
            expected_returns=expected_returns,
            total_asset=total_asset,
            request=request,
            account_buckets=account_buckets,
        )
    )
    calculated_six_strategy_saving = (
        safe_float(
            six_strategy_tax_model
            .get("combined", {})
            .get("totalWon")
        )
    )

    additional_comprehensive_tax = safe_float(
        comprehensive_tax_status[
            "estimated_additional_tax_"
            "attributable_to_portfolio"
        ]
    )

    total_tax_before_saving = (
        withholding_tax
        + overseas_tax["estimated_tax"]
        + additional_comprehensive_tax
    )

    modeled_tax_reduction = min(
        calculated_six_strategy_saving,
        max(total_tax_before_saving, 0.0),
    )
    total_tax_after_saving = max(
        total_tax_before_saving
        - modeled_tax_reduction,
        0.0,
    )

    after_tax_profit = (
        gross_profit
        - total_tax_after_saving
    )
    after_tax_return = (
        after_tax_profit / total_asset
        if total_asset > 0
        else 0.0
    )

    tax_saving_effect = {
        **legacy_tax_saving_effect,
        "selection_model": (
            "six_strategy_combined_v1"
        ),
        "legacy_account_only_tax_saving": (
            safe_round(
                legacy_account_only_tax_saving,
                0,
            )
        ),
        "estimated_total_tax_saving": (
            safe_round(
                modeled_tax_reduction,
                0,
            )
        ),
        "calculated_six_strategy_saving": (
            safe_round(
                calculated_six_strategy_saving,
                0,
            )
        ),
        "modeled_tax_reduction": safe_round(
            modeled_tax_reduction,
            0,
        ),
        "unapplied_credit_or_saving": (
            safe_round(
                max(
                    calculated_six_strategy_saving
                    - modeled_tax_reduction,
                    0.0,
                ),
                0,
            )
        ),
    }

    tax_breakdown = {
        "gross_profit": safe_round(
            gross_profit,
            0,
        ),
        "withholding_tax_estimate": (
            safe_round(
                withholding_tax,
                0,
            )
        ),
        "financial_income_comprehensive_tax": (
            comprehensive_tax_status
        ),
        "additional_comprehensive_tax_estimate": (
            safe_round(
                additional_comprehensive_tax,
                0,
            )
        ),
        "additional_comprehensive_tax_total_estimate": (
            comprehensive_tax_status[
                "estimated_additional_tax_total"
            ]
        ),
        "additional_comprehensive_tax_external_baseline": (
            comprehensive_tax_status[
                "estimated_additional_tax_"
                "external_baseline"
            ]
        ),
        "overseas_stock_capital_gains_tax": (
            overseas_tax
        ),
        "account_buckets": account_buckets,
        "tax_saving_effect": tax_saving_effect,
        "six_strategy_tax_model": (
            six_strategy_tax_model
        ),
        "total_tax_before_saving": safe_round(
            total_tax_before_saving,
            0,
        ),
        "total_tax_after_saving": safe_round(
            total_tax_after_saving,
            0,
        ),
        "after_tax_profit": safe_round(
            after_tax_profit,
            0,
        ),
        "after_tax_return": safe_round(
            after_tax_return,
            6,
        ),
        "tax_disclaimer": (
            "세금 계산은 프로젝트용 간이 "
            "추정입니다. 실제 세액은 전체 소득, "
            "실현손익, 공제 및 상품별 요건에 따라 "
            "달라집니다."
        ),
    }

    return (
        float(after_tax_return),
        tax_breakdown,
    )


# ============================================================
# 8. 지표 계산
# ============================================================


def calculate_mdd(portfolio_daily_returns: pd.Series) -> float:
    cumulative = (1 + portfolio_daily_returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    return float(drawdown.min())


def build_portfolio_benchmark(
    weights: Dict[str, float],
    returns: pd.DataFrame,
    benchmark_key: str,
) -> Tuple[
    Optional[pd.Series],
    Dict[str, Any],
]:
    config = get_benchmark_config(
        benchmark_key
    )
    series_key = config["series_key"]
    normalized = normalize_weights(weights)
    equity_exposure = sum(
        normalized.get(asset, 0.0)
        for asset in [*STOCK_ASSETS, "reit"]
    )

    base_meta = {
        "policy": BENCHMARK_POLICY_VERSION,
        "benchmark_key": benchmark_key,
        "series_key": series_key,
        "ticker": config["ticker"],
        "label": config["label"],
        "currency": config.get("currency"),
        "return_basis": (
            "native_currency_adjusted_close_"
            "price_return"
        ),
        "comparison_role": (
            "display_and_beta_only"
        ),
        "minimum_beta_observations": (
            MIN_BETA_OBSERVATIONS
        ),
        "official_index_series": config[
            "official_index_series"
        ],
        "proxy_note": config["proxy_note"],
        "equity_portfolio_weight": safe_round(
            equity_exposure,
            6,
        ),
        "affects_portfolio_recommendation": (
            False
        ),
    }

    if series_key not in returns.columns:
        return None, {
            **base_meta,
            "applicable": False,
            "reason": "benchmark_data_missing",
        }

    benchmark = (
        returns[series_key]
        .replace(
            [np.inf, -np.inf],
            np.nan,
        )
        .dropna()
    )
    if benchmark.empty:
        return None, {
            **base_meta,
            "applicable": False,
            "reason": "benchmark_data_empty",
        }

    return benchmark, {
        **base_meta,
        "applicable": True,
        "reason": None,
    }


def align_portfolio_and_benchmark_returns(
    portfolio_daily_returns: pd.Series,
    benchmark_daily_returns: Optional[
        pd.Series
    ],
) -> pd.DataFrame:
    if benchmark_daily_returns is None:
        return pd.DataFrame(
            columns=[
                "portfolio",
                "benchmark",
            ]
        )

    return (
        pd.concat(
            [
                portfolio_daily_returns.rename(
                    "portfolio"
                ),
                benchmark_daily_returns.rename(
                    "benchmark"
                ),
            ],
            axis=1,
        )
        .replace(
            [np.inf, -np.inf],
            np.nan,
        )
        .dropna(how="any")
        .sort_index()
    )


def calculate_benchmark_comparisons(
    portfolio_daily_returns: pd.Series,
    weights: Dict[str, float],
    returns: pd.DataFrame,
) -> Dict[str, Any]:
    comparisons: Dict[str, Any] = {}

    for benchmark_key in (
        BENCHMARK_CONFIGS.keys()
    ):
        benchmark_returns, metadata = (
            build_portfolio_benchmark(
                weights=weights,
                returns=returns,
                benchmark_key=benchmark_key,
            )
        )
        metadata = dict(metadata)

        if benchmark_returns is None:
            beta = None
            common_observations = 0
        else:
            aligned = (
                align_portfolio_and_benchmark_returns(
                    portfolio_daily_returns,
                    benchmark_returns,
                )
            )
            common_observations = len(
                aligned
            )
            metadata.update(
                {
                    "common_observations": (
                        common_observations
                    ),
                    "common_data_start": (
                        aligned.index[0].strftime(
                            "%Y-%m-%d"
                        )
                        if common_observations > 0
                        else None
                    ),
                    "common_data_end": (
                        aligned.index[-1].strftime(
                            "%Y-%m-%d"
                        )
                        if common_observations > 0
                        else None
                    ),
                }
            )

            if (
                common_observations
                < MIN_BETA_OBSERVATIONS
            ):
                beta = None
                metadata.update(
                    {
                        "applicable": False,
                        "reason": (
                            "insufficient_common_"
                            "observations"
                        ),
                    }
                )
            else:
                beta = calculate_beta(
                    portfolio_daily_returns,
                    benchmark_returns,
                )
                if beta is None:
                    metadata.update(
                        {
                            "applicable": False,
                            "reason": (
                                "benchmark_variance_"
                                "or_covariance_invalid"
                            ),
                        }
                    )

        comparisons[benchmark_key] = {
            "beta": (
                safe_round(beta, 6)
                if beta is not None
                else None
            ),
            "metadata": metadata,
        }

    return comparisons


def calculate_beta(
    portfolio_daily_returns: pd.Series,
    benchmark_daily_returns: Optional[
        pd.Series
    ],
) -> Optional[float]:
    aligned = (
        align_portfolio_and_benchmark_returns(
            portfolio_daily_returns,
            benchmark_daily_returns,
        )
    )
    if len(aligned) < MIN_BETA_OBSERVATIONS:
        return None

    benchmark_variance = float(
        aligned["benchmark"].var()
    )
    if (
        benchmark_variance < 1e-12
        or not np.isfinite(
            benchmark_variance
        )
    ):
        return None

    covariance = float(
        aligned["portfolio"].cov(
            aligned["benchmark"]
        )
    )
    if not np.isfinite(covariance):
        return None

    beta = (
        covariance / benchmark_variance
    )
    return (
        float(beta)
        if np.isfinite(beta)
        else None
    )


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


# ── 시계열 충격 주입 ──────────────────────────────────────────────────────────
# 기존 calculate_stress_test가 스트레스 수익률 한 값을 내는 것과 달리, 아래 헬퍼는
# 자산별 충격을 일별수익률에 주입해 기대수익률·변동성·샤프·소르티노·MDD·세후수익률을
# 동일한 계산 경로에서 재계산한다. PR #69의 하위호환 규약을 그대로 유지한다.


def _vol_multiplier(shock: float) -> float:
    """충격 절댓값에 따른 변동성 확대 계수."""
    return min(1.0 + VOL_STRESS_BETA * abs(float(shock)), VOL_STRESS_CAP)


def derive_asset_shocks_from_macro(
    assets: List[str],
    request: PortfolioRequest,
) -> Dict[str, float]:
    """금리·환율 입력을 자산별 연간 기대수익률 충격으로 환산한다."""
    shocks: Dict[str, float] = {}
    for asset in assets:
        shock = 0.0
        if asset in INTEREST_RATE_SENSITIVE_ASSETS:
            shock += -ASSET_DURATION_YEARS.get(asset, 0.0) * request.stress_interest_rate_shock
        if asset in FX_SENSITIVE_ASSETS:
            shock += request.stress_fx_shock
        if shock != 0.0:
            shocks[asset] = float(shock)
    return shocks


def apply_return_shocks(
    selected_returns: pd.DataFrame,
    selected_expected_returns: pd.Series,
    shocks: Dict[str, float],
) -> Tuple[pd.DataFrame, pd.Series]:
    """자산별 연간 충격을 일별수익률과 기대수익률에 주입한다(원본 비변형)."""
    stressed_returns = selected_returns.copy()
    stressed_expected = selected_expected_returns.copy()
    for asset in stressed_returns.columns:
        shock = float(shocks.get(asset, 0.0))
        if shock == 0.0:
            continue
        column = stressed_returns[asset]
        mean = float(column.mean())
        multiplier = _vol_multiplier(shock)
        stressed_returns[asset] = (
            mean + (column - mean) * multiplier + shock / TRADING_DAYS
        )
        if asset in stressed_expected.index:
            stressed_expected[asset] = float(stressed_expected[asset]) + shock
    return stressed_returns, stressed_expected


def shift_expected_returns(
    expected_returns: pd.Series,
    shocks: Dict[str, float],
) -> pd.Series:
    """세금 계산용 전체 기대수익률 시리즈에도 같은 충격을 반영한다."""
    shifted = expected_returns.copy()
    for asset, shock in shocks.items():
        if asset in shifted.index:
            shifted[asset] = float(shifted[asset]) + float(shock)
    return shifted




def _nearest_positive_semidefinite(
    matrix: np.ndarray,
) -> np.ndarray:
    clean = np.nan_to_num(
        np.asarray(matrix, dtype=float),
        nan=0.0,
        posinf=0.0,
        neginf=0.0,
    )
    symmetric = (clean + clean.T) / 2.0

    try:
        eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
        eigenvalues = np.clip(eigenvalues, 0.0, None)
        corrected = (
            eigenvectors
            @ np.diag(eigenvalues)
            @ eigenvectors.T
        )
        return (corrected + corrected.T) / 2.0
    except np.linalg.LinAlgError:
        return np.diag(
            np.clip(np.diag(symmetric), 0.0, None)
        )


def _metric_percentile_payload(
    values: np.ndarray,
    *,
    digits: int,
    unit: str,
) -> Dict[str, Any]:
    levels = list(MONTE_CARLO_METRIC_RANGE_PERCENTILES)
    percentile_values = np.percentile(values, levels)
    mapped = {
        f"p{level}": safe_round(value, digits)
        for level, value in zip(levels, percentile_values)
    }

    return {
        **mapped,
        "lower": mapped[
            f"p{MONTE_CARLO_METRIC_RANGE_DISPLAY_LOWER}"
        ],
        "center": mapped[
            f"p{MONTE_CARLO_METRIC_RANGE_DISPLAY_CENTER}"
        ],
        "upper": mapped[
            f"p{MONTE_CARLO_METRIC_RANGE_DISPLAY_UPPER}"
        ],
        "lower_percentile": (
            MONTE_CARLO_METRIC_RANGE_DISPLAY_LOWER
        ),
        "center_percentile": (
            MONTE_CARLO_METRIC_RANGE_DISPLAY_CENTER
        ),
        "upper_percentile": (
            MONTE_CARLO_METRIC_RANGE_DISPLAY_UPPER
        ),
        "unit": unit,
        "direction": "higher_is_better",
    }


def _effective_tax_rate_from_breakdown(
    tax_breakdown: Dict[str, Any],
) -> float:
    gross_profit = safe_float(
        tax_breakdown.get("gross_profit")
    )
    total_tax_after_saving = safe_float(
        tax_breakdown.get("total_tax_after_saving")
    )
    if gross_profit <= 1e-12:
        return 0.0

    return float(
        np.clip(
            total_tax_after_saving / gross_profit,
            0.0,
            1.0,
        )
    )


def calculate_monte_carlo_metric_ranges(
    weights: Dict[str, float],
    returns: pd.DataFrame,
    expected_returns: pd.Series,
    total_asset: float,
    investment_horizon_years: float,
    tax_breakdown: Dict[str, Any],
    random_seed: int = DEFAULT_RANDOM_SEED,
    num_simulations: Optional[int] = None,
) -> Dict[str, Any]:
    # 세후수익률과 MDD를 동일한 미래 시장 경로에서 계산한다.
    normalized_weights = normalize_weights(weights)
    total_asset = safe_float(total_asset)

    if total_asset <= 0:
        return {
            "available": False,
            "reason": "total_asset_must_be_positive",
        }

    try:
        requested_years = float(investment_horizon_years)
    except (TypeError, ValueError):
        requested_years = 1.0

    horizon_years = max(
        1,
        min(
            int(round(requested_years)),
            MONTE_CARLO_METRIC_RANGE_MAX_HORIZON_YEARS,
        ),
    )
    months = (
        horizon_years
        * MONTE_CARLO_METRIC_RANGE_STEPS_PER_YEAR
    )
    simulations = max(
        int(
            num_simulations
            if num_simulations is not None
            else MONTE_CARLO_METRIC_RANGE_SIMULATIONS
        ),
        100,
    )

    # 비중과 무관한 공통 자산 순서와 시드를 사용하므로
    # 현재안/A/B에 같은 시장 시나리오가 적용된다.
    assets = [
        asset
        for asset in ASSET_TICKERS.keys()
        if (
            asset in returns.columns
            and asset in expected_returns.index
        )
    ]

    missing_weighted_assets = [
        asset
        for asset, weight in normalized_weights.items()
        if (
            safe_float(weight) > 1e-12
            and asset not in assets
        )
    ]
    if missing_weighted_assets:
        return {
            "available": False,
            "reason": "weighted_asset_data_missing",
            "missing_assets": missing_weighted_assets,
        }

    if not assets:
        return {
            "available": False,
            "reason": "no_common_assets",
        }

    clean_returns = (
        returns[assets]
        .replace([np.inf, -np.inf], np.nan)
        .dropna(how="any")
    )
    if len(clean_returns) < MIN_BETA_OBSERVATIONS:
        return {
            "available": False,
            "reason": "insufficient_return_observations",
            "observations": len(clean_returns),
            "minimum_observations": MIN_BETA_OBSERVATIONS,
        }

    daily_log_returns = np.log1p(
        clean_returns.clip(lower=-0.999999)
    )
    monthly_covariance = (
        daily_log_returns.cov().to_numpy(dtype=float)
        * TRADING_DAYS
        / MONTE_CARLO_METRIC_RANGE_STEPS_PER_YEAR
    )
    monthly_covariance = _nearest_positive_semidefinite(
        monthly_covariance
    )

    annual_expected = (
        expected_returns
        .reindex(assets)
        .fillna(0.0)
        .to_numpy(dtype=float)
    )
    annual_expected = np.clip(
        annual_expected,
        -0.95,
        None,
    )

    # 로그정규 모형에서 단순수익률 기대값이 기존 기대수익률과
    # 최대한 맞도록 분산 보정항을 차감한다.
    monthly_log_mean = (
        np.log1p(annual_expected)
        / MONTE_CARLO_METRIC_RANGE_STEPS_PER_YEAR
        - 0.5 * np.diag(monthly_covariance)
    )

    weight_vector = np.array(
        [
            safe_float(normalized_weights.get(asset))
            for asset in assets
        ],
        dtype=float,
    )
    weight_total = float(weight_vector.sum())
    if weight_total <= 0:
        return {
            "available": False,
            "reason": "portfolio_weight_sum_zero",
        }
    weight_vector = weight_vector / weight_total

    asset_values = np.broadcast_to(
        weight_vector * total_asset,
        (simulations, len(assets)),
    ).copy()

    gross_portfolio_value = np.full(
        simulations,
        total_asset,
        dtype=float,
    )
    running_peak = gross_portfolio_value.copy()
    path_mdd = np.zeros(simulations, dtype=float)

    scenario_seed = (
        int(random_seed)
        + MONTE_CARLO_METRIC_RANGE_SEED_OFFSET
    )
    rng = np.random.default_rng(scenario_seed)

    for _ in range(months):
        monthly_log_draws = rng.multivariate_normal(
            mean=monthly_log_mean,
            cov=monthly_covariance,
            size=simulations,
            check_valid="ignore",
        )
        asset_values *= np.exp(monthly_log_draws)
        gross_portfolio_value = asset_values.sum(axis=1)

        running_peak = np.maximum(
            running_peak,
            gross_portfolio_value,
        )
        drawdown = (
            gross_portfolio_value / running_peak - 1.0
        )
        path_mdd = np.minimum(path_mdd, drawdown)

    effective_tax_rate = _effective_tax_rate_from_breakdown(
        tax_breakdown
    )
    gross_gain = gross_portfolio_value - total_asset
    after_tax_terminal_asset = (
        total_asset
        + np.where(
            gross_gain > 0,
            gross_gain * (1.0 - effective_tax_rate),
            gross_gain,
        )
    )
    after_tax_terminal_asset = np.maximum(
        after_tax_terminal_asset,
        0.0,
    )
    after_tax_annualized_return = (
        np.power(
            np.maximum(
                after_tax_terminal_asset / total_asset,
                1e-12,
            ),
            1.0 / horizon_years,
        )
        - 1.0
    )

    scenario_basis_id = (
        f"{MONTE_CARLO_METRIC_RANGE_VERSION}:"
        f"{scenario_seed}:{simulations}:{horizon_years}:"
        f"{clean_returns.index[0].strftime('%Y-%m-%d')}:"
        f"{clean_returns.index[-1].strftime('%Y-%m-%d')}"
    )

    return {
        "available": True,
        "version": MONTE_CARLO_METRIC_RANGE_VERSION,
        "scenario_basis_id": scenario_basis_id,
        "simulation_count": simulations,
        "horizon_years": horizon_years,
        "time_step": "monthly",
        "rebalancing": "none_buy_and_hold",
        "common_market_scenarios": True,
        "random_seed": scenario_seed,
        "display_range": {
            "lower_percentile": (
                MONTE_CARLO_METRIC_RANGE_DISPLAY_LOWER
            ),
            "center_percentile": (
                MONTE_CARLO_METRIC_RANGE_DISPLAY_CENTER
            ),
            "upper_percentile": (
                MONTE_CARLO_METRIC_RANGE_DISPLAY_UPPER
            ),
            "central_coverage": 0.60,
            "label": "P20-P80",
        },
        "after_tax_return": _metric_percentile_payload(
            after_tax_annualized_return,
            digits=6,
            unit="rate",
        ),
        "mdd": _metric_percentile_payload(
            path_mdd,
            digits=6,
            unit="rate",
        ),
        "effective_tax_rate_proxy": safe_round(
            effective_tax_rate,
            6,
        ),
        "assumptions": {
            "path_model": (
                "correlated_multivariate_log_returns"
            ),
            "drift_source": "asset_expected_returns",
            "covariance_source": (
                "historical_daily_log_return_covariance"
            ),
            "after_tax_method": (
                "positive_terminal_gain_adjusted_by_"
                "current_effective_tax_rate_proxy"
            ),
            "mdd_method": (
                "minimum_drawdown_of_same_simulated_"
                "gross_portfolio_path"
            ),
            "tax_on_loss": False,
            "fees_in_simulated_paths": False,
            "range_note": (
                "세후수익률과 MDD는 동일한 10,000개 "
                "Buy & Hold 시장 경로에서 계산하며, "
                "P20~P80은 경로의 중앙 60% 범위입니다."
            ),
            "disclaimer": (
                "시뮬레이션 결과는 실제 수익을 보장하지 않습니다."
            ),
        },
    }


def calculate_metric_amounts(
    metrics: Dict[str, Any],
    total_asset: float,
    tax_breakdown: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """비율 지표를 프론트 표기용 원화 금액으로 환산한다.

    - after_tax_return_amount: 세후 기대수익률 × 현재 총자산. 연간 세후 기대 이익이다.
    - mdd_amount: 백테스트 일별 수익률 기준 최대낙폭 × 현재 총자산. 세금 반영값이 아니다.
    - volatility_band_amount: 연율화 변동성 × 현재 총자산. 손익 확정값이 아니라 변동 폭 근사다.
    """
    total_asset = safe_float(total_asset)
    after_tax_profit = None
    if tax_breakdown is not None:
        after_tax_profit = tax_breakdown.get("after_tax_profit")

    return {
        "basis": "portfolio_total_asset",
        "total_asset": safe_round(total_asset, 0),
        "expected_return_amount": safe_round(
            safe_float(metrics.get("expected_return")) * total_asset,
            0,
        ),
        "after_tax_return_amount": safe_round(
            safe_float(after_tax_profit)
            if after_tax_profit is not None
            else safe_float(metrics.get("after_tax_return")) * total_asset,
            0,
        ),
        "mdd_amount": safe_round(safe_float(metrics.get("mdd")) * total_asset, 0),
        "volatility_band_amount": safe_round(
            safe_float(metrics.get("volatility")) * total_asset,
            0,
        ),
        "historical_var_95_daily_loss_amount": safe_round(
            -safe_float(metrics.get("historical_var_95_daily_loss")) * total_asset,
            0,
        ),
        "note": (
            "원화 지표는 현재 총자산에 각 포트폴리오의 비율 지표를 곱한 값. "
            "after_tax_return_amount만 세후 기대 이익이며, MDD/VaR는 과거 수익률 기반 손실률의 원화 환산이다."
        ),
    }


def calculate_metrics(
    weights: Dict[str, float],
    returns: pd.DataFrame,
    expected_returns: pd.Series,
    request: PortfolioRequest,
    cov_matrix: Optional[pd.DataFrame] = None,
    include_benchmark_metrics: bool = False,
    shocks: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """포트폴리오 지표의 단일 계산 진입점.

    벤치마크 지표는 최종 결과 표시 단계에서만 계산한다.
    추천 후보 계산에서는 include_benchmark_metrics=False를 유지한다.
    """
    weights = normalize_weights(weights)
    validate_required_assets_available(
        weights,
        list(returns.columns),
        "portfolio_weights",
    )

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

    expected_returns_for_tax = expected_returns
    if shocks:
        selected_returns, selected_expected_returns = apply_return_shocks(
            selected_returns,
            selected_expected_returns,
            shocks,
        )
        expected_returns_for_tax = shift_expected_returns(
            expected_returns,
            shocks,
        )
        cov_matrix = None

    if cov_matrix is None:
        selected_cov_matrix = selected_returns.cov() * TRADING_DAYS
    else:
        selected_cov_matrix = cov_matrix.reindex(
            index=assets,
            columns=assets,
        ).fillna(0.0)

    portfolio_return = float(np.dot(w, selected_expected_returns))
    variance = float(
        np.dot(w.T, np.dot(selected_cov_matrix.values, w))
    )
    portfolio_volatility = float(np.sqrt(max(variance, 0.0)))
    portfolio_daily_returns = selected_returns.dot(w)

    if portfolio_volatility < 1e-8 or np.isnan(portfolio_volatility):
        sharpe = 0.0
    else:
        sharpe = float(
            (portfolio_return - request.risk_free_rate)
            / portfolio_volatility
        )

    sortino = calculate_sortino(
        portfolio_daily_returns=portfolio_daily_returns,
        annual_return=portfolio_return,
        risk_free_rate=request.risk_free_rate,
    )
    mdd = calculate_mdd(portfolio_daily_returns)

    if include_benchmark_metrics:
        benchmark_comparisons = calculate_benchmark_comparisons(
            portfolio_daily_returns=portfolio_daily_returns,
            weights=weights,
            returns=returns,
        )
        selected_comparison = benchmark_comparisons[request.benchmark_key]
        beta = selected_comparison["beta"]
        benchmark_meta = selected_comparison["metadata"]
    else:
        benchmark_comparisons = {}
        beta = None
        benchmark_meta = {
            "policy": BENCHMARK_POLICY_VERSION,
            "benchmark_key": request.benchmark_key,
            "applicable": None,
            "reason": "deferred_until_final_portfolio",
            "affects_portfolio_recommendation": False,
        }

    after_tax_return, tax_breakdown = calculate_after_tax_return(
        weights=weights,
        expected_returns=expected_returns_for_tax,
        total_asset=request.total_asset,
        request=request,
    )

    taxable_financial_income = estimate_taxable_financial_income(
        weights=weights,
        expected_returns=expected_returns_for_tax,
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
    target_duration = target_duration_by_horizon(
        request.investment_horizon_years
    )
    duration_fit_score = calculate_duration_fit_score(
        portfolio_duration,
        target_duration,
    )

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

    metric_amounts = calculate_metric_amounts(
        temp_metrics,
        request.total_asset,
        tax_breakdown,
    )

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
        "beta": beta,
        "beta_benchmark": benchmark_meta,
        "selected_benchmark_key": request.benchmark_key,
        "benchmark_comparisons": benchmark_comparisons,
        "taxable_financial_income": safe_round(
            taxable_financial_income,
            0,
        ),
        "liquidity_coverage": safe_round(liquidity_coverage, 6),
        "stock_weight": safe_round(group_weights["stock_weight"], 6),
        "bond_cash_weight": safe_round(
            group_weights["bond_cash_weight"],
            6,
        ),
        "alternative_weight": safe_round(
            group_weights["alternative_weight"],
            6,
        ),
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
        "risk_level_label": RISK_LEVEL_NAME.get(
            risk_level,
            "기준 미충족",
        ),
        "metric_amounts": metric_amounts,
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
            "index_value": safe_round((1.0 + value) * BACKTEST_BASE_INDEX, 4),
            "base_index": BACKTEST_BASE_INDEX,
        }
        for date, value in cumulative.items()
    ]


def calculate_benchmark_cumulative_returns(
    weights: Dict[str, float],
    returns: pd.DataFrame,
    benchmark_key: str,
) -> Dict[str, Any]:
    benchmark_daily_returns, metadata = build_portfolio_benchmark(
        weights=weights,
        returns=returns,
        benchmark_key=benchmark_key,
    )
    if benchmark_daily_returns is None:
        return {
            "metadata": metadata,
            "series": [],
        }

    cumulative = (1 + benchmark_daily_returns).cumprod() - 1
    return {
        "metadata": metadata,
        "series": [
            {
                "date": date.strftime("%Y-%m-%d"),
                "value": safe_round(value, 6),
                "index_value": safe_round(
                    (1.0 + value) * BACKTEST_BASE_INDEX,
                    4,
                ),
                "base_index": BACKTEST_BASE_INDEX,
            }
            for date, value in cumulative.items()
        ],
    }


def calculate_all_benchmark_cumulative_returns(
    weights: Dict[str, float],
    returns: pd.DataFrame,
) -> Dict[str, Any]:
    return {
        benchmark_key: calculate_benchmark_cumulative_returns(
            weights=weights,
            returns=returns,
            benchmark_key=benchmark_key,
        )
        for benchmark_key in BENCHMARK_CONFIGS.keys()
    }


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



def is_separate_tax_bond_allowed(request: PortfolioRequest) -> bool:
    return request.investment_horizon_years >= SEPARATE_TAX_BOND_MIN_HOLDING_YEARS


def get_effective_unique_asset(request: PortfolioRequest) -> str:
    unique_asset = validate_unique_asset(request.unique_asset)
    if unique_asset == "separate_tax_bond" and not is_separate_tax_bond_allowed(request):
        return "cash"
    return unique_asset


def get_recommendation_eligible_assets(
    available_assets: List[str],
    request: PortfolioRequest,
) -> List[str]:
    eligible_assets = list(available_assets)
    if not is_separate_tax_bond_allowed(request):
        eligible_assets = [
            asset for asset in eligible_assets if asset != "separate_tax_bond"
        ]
    return eligible_assets


def build_constraint_warnings(request: PortfolioRequest) -> List[str]:
    warnings = []
    if not is_separate_tax_bond_allowed(request):
        warnings.append(
            "investment_horizon_years가 3년 미만이므로 추천 포트폴리오에서는 "
            "분리과세채(separate_tax_bond)를 제외했습니다. 현재 포트폴리오에 이미 "
            "들어온 비중은 평가만 수행합니다."
        )
        if request.unique_asset == "separate_tax_bond":
            warnings.append(
                "unique_asset=separate_tax_bond 입력은 3년 미만 기간 조건과 맞지 않아 "
                "unique 필요자금 배치 자산을 cash로 대체했습니다."
            )
    return warnings


def generate_random_weights(
    assets: Optional[List[str]] = None,
    rng: Optional[np.random.Generator] = None,
) -> Dict[str, float]:
    assets = assets or list(ASSET_TICKERS.keys())
    if not assets:
        raise ValueError("랜덤 포트폴리오를 생성할 자산 목록이 비어 있습니다.")

    rng = rng or np.random.default_rng(DEFAULT_RANDOM_SEED)
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
    """포트폴리오 A 순위: 공통 필터 통과 후보 중 세후수익률 최대."""
    return (
        safe_float(metrics.get("after_tax_return")),
        safe_float(metrics.get("expected_return")),
        safe_float(metrics.get("sharpe_ratio")),
        -safe_float(metrics.get("historical_var_95_daily_loss")),
        -safe_float(metrics.get("risk_contribution_max_share")),
        safe_float(metrics.get("mdd")),
    )


def build_portfolio_b_rank_tuple(metrics: Dict[str, Any]) -> Tuple[Any, ...]:
    """목표 달성 후보 중 위험기여도 집중도를 가장 먼저 최소화한다."""
    return (
        safe_float(metrics.get("risk_contribution_max_share")),
        safe_float(metrics.get("historical_var_95_daily_loss")),
        safe_float(metrics.get("volatility")),
        -safe_float(metrics.get("after_tax_return")),
        -safe_float(metrics.get("sharpe_ratio")),
    )


def build_portfolio_b_fallback_rank_tuple(
    metrics: Dict[str, Any],
    target_after_tax_return: float,
) -> Tuple[Any, ...]:
    """목표 달성 후보가 없으면 목표 부족 폭을 먼저 최소화한다."""
    after_tax_return = safe_float(metrics.get("after_tax_return"))
    target_shortfall = max(target_after_tax_return - after_tax_return, 0.0)
    return (
        target_shortfall,
        safe_float(metrics.get("risk_contribution_max_share")),
        safe_float(metrics.get("historical_var_95_daily_loss")),
        safe_float(metrics.get("volatility")),
        -after_tax_return,
    )


def build_selection_summary(
    metrics: Dict[str, Any],
    portfolio_type: str = "current",
    target_after_tax_return: Optional[float] = None,
) -> Dict[str, Any]:
    after_tax_return = safe_float(metrics.get("after_tax_return"))
    risk_control = metrics.get("selection_risk_control", {})
    checks = risk_control.get("checks", {})

    common_filters = {
        "suitability": True,
        "liquidity": True,
        "historical_var_95": bool(checks.get("historical_var_95", False)),
        "risk_contribution": bool(checks.get("risk_contribution", False)),
    }

    if portfolio_type == "A":
        return {
            "portfolio_type": "A",
            "strategy_type": "return_seeking",
            "ranking_basis": [
                "after_tax_return_desc",
                "expected_return_desc",
                "sharpe_ratio_desc",
                "historical_var_95_asc",
                "risk_contribution_max_share_asc",
            ],
            "common_filters": common_filters,
            "risk_control": risk_control,
            "primary_objective": "after_tax_return_desc",
            "achieved_after_tax_return": safe_round(after_tax_return, 6),
            "note": (
                "고객 적합성·유동성·VaR·위험기여도 제한을 모두 통과한 후보 중 "
                "예상 세후수익률이 가장 높은 포트폴리오입니다."
            ),
        }

    if portfolio_type == "B":
        target = safe_float(target_after_tax_return)
        target_shortfall = max(target - after_tax_return, 0.0)
        target_met = after_tax_return >= target
        return {
            "portfolio_type": "B",
            "strategy_type": "target_return_risk_minimizing",
            "ranking_basis": (
                [
                    "target_after_tax_return_filter",
                    "risk_contribution_max_share_asc",
                    "historical_var_95_asc",
                    "volatility_asc",
                    "after_tax_return_desc",
                ]
                if target_met
                else [
                    "target_shortfall_asc",
                    "risk_contribution_max_share_asc",
                    "historical_var_95_asc",
                    "volatility_asc",
                    "after_tax_return_desc",
                ]
            ),
            "common_filters": common_filters,
            "risk_control": risk_control,
            "primary_objective": (
                "risk_contribution_max_share_asc"
                if target_met
                else "target_shortfall_asc"
            ),
            "target_after_tax_return": safe_round(target, 6),
            "achieved_after_tax_return": safe_round(after_tax_return, 6),
            "target_met": target_met,
            "target_shortfall": safe_round(target_shortfall, 6),
            "note": (
                "IPS 목표 세후수익률을 충족한 후보 중 위험기여도 집중도가 "
                "가장 낮은 포트폴리오입니다."
                if target_met
                else "IPS 목표 세후수익률 달성 후보가 없어 목표 부족 폭이 가장 작고 "
                "위험기여도 집중도가 낮은 대체 포트폴리오를 선택했습니다."
            ),
        }

    return {
        "portfolio_type": portfolio_type,
        "ranking_basis": [],
        "risk_control": risk_control,
        "note": "현재 포트폴리오는 추천 후보 선정 대상이 아닙니다.",
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



def calculate_weight_distance(
    weights_a: Dict[str, float],
    weights_b: Dict[str, float],
) -> float:
    normalized_a = normalize_weights(
        weights_a
    )
    normalized_b = normalize_weights(
        weights_b
    )
    assets = (
        set(normalized_a)
        | set(normalized_b)
    )
    return float(
        0.5
        * sum(
            abs(
                normalized_a.get(
                    asset,
                    0.0,
                )
                - normalized_b.get(
                    asset,
                    0.0,
                )
            )
            for asset in assets
        )
    )

def find_recommended_portfolios(
    returns: pd.DataFrame,
    expected_returns: pd.Series,
    request: PortfolioRequest,
    cov_matrix: Optional[pd.DataFrame] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """공통 하드필터 후 A는 세후수익률 최대, B는 목표수익률 달성 후 위험 최소."""
    target_after_tax_return = safe_float(
        request.target_after_tax_return,
        default=np.nan,
    )
    if not np.isfinite(target_after_tax_return) or target_after_tax_return <= 0:
        raise ValueError(
            "포트폴리오 B 선정에 필요한 RRTTLLU.Return 목표 세후수익률이 없습니다."
        )

    rng = np.random.default_rng(request.random_seed)
    candidates: List[Dict[str, Any]] = []
    generated_count = request.num_simulations
    guideline_pass_count = 0
    suitable_count = 0
    liquidity_pass_count = 0
    risk_control_pass_count = 0
    common_filter_pass_count = 0
    rejection_counts = {
        "suitability": 0,
        "liquidity": 0,
        "historical_var_95": 0,
        "risk_contribution": 0,
    }

    raw_available_assets = [
        asset for asset in ASSET_TICKERS.keys() if asset in returns.columns
    ]
    available_assets = get_recommendation_eligible_assets(
        raw_available_assets,
        request,
    )
    effective_unique_asset = get_effective_unique_asset(request)
    validate_required_assets_available(
        {effective_unique_asset: 1.0},
        raw_available_assets,
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

        suitability_passed = is_suitable_for_client(metrics, request.risk_profile)
        guideline_detail = evaluate_guideline_detail(metrics, request.risk_profile)
        liquidity_passed = bool(
            guideline_detail.get("hard_checks", {}).get("liquidity_coverage", False)
        )
        risk_control = metrics.get("selection_risk_control", {})
        risk_checks = risk_control.get("checks", {})
        var_passed = bool(risk_checks.get("historical_var_95", False))
        risk_contribution_passed = bool(
            risk_checks.get("risk_contribution", False)
        )

        if suitability_passed:
            suitable_count += 1
        else:
            rejection_counts["suitability"] += 1

        if liquidity_passed:
            liquidity_pass_count += 1
        else:
            rejection_counts["liquidity"] += 1

        if var_passed:
            pass
        else:
            rejection_counts["historical_var_95"] += 1

        if risk_contribution_passed:
            pass
        else:
            rejection_counts["risk_contribution"] += 1

        if risk_control.get("passed", False):
            risk_control_pass_count += 1

        common_filter_passed = all(
            (
                suitability_passed,
                liquidity_passed,
                var_passed,
                risk_contribution_passed,
            )
        )
        if not common_filter_passed:
            continue

        common_filter_pass_count += 1
        candidates.append(
            {
                "weights": final_weights,
                "metrics": metrics,
                "selection_rank": build_selection_rank_tuple(metrics),
            }
        )

    if not candidates:
        raise RuntimeError(
            "고객 적합성·유동성·VaR·위험기여도 제한을 모두 통과한 "
            "포트폴리오가 없습니다. num_simulations 또는 위험 기준을 검토해야 합니다."
        )

    candidates = sorted(
        candidates,
        key=lambda candidate: candidate["selection_rank"],
        reverse=True,
    )

    # 포트폴리오 A: 공통 필터 통과 후보 중 세후수익률 최대.
    recommendation_1 = candidates[0]
    recommendation_1["selection_summary"] = build_selection_summary(
        recommendation_1["metrics"],
        portfolio_type="A",
        target_after_tax_return=target_after_tax_return,
    )

    # B는 A와 최소 비중 차이가 있는
    # 별도 대안을 우선한다.
    raw_portfolio_b_pool = candidates[1:]
    portfolio_b_available = bool(
        raw_portfolio_b_pool
    )
    distance_pairs = [
        (
            candidate,
            calculate_weight_distance(
                recommendation_1["weights"],
                candidate["weights"],
            ),
        )
        for candidate in raw_portfolio_b_pool
    ]
    distinct_pairs = [
        (candidate, distance)
        for candidate, distance in distance_pairs
        if (
            distance
            >= PORTFOLIO_B_MIN_WEIGHT_DISTANCE
        )
    ]

    if distinct_pairs:
        portfolio_b_pool = []
        for candidate, distance in distinct_pairs:
            candidate[
                "_weight_distance_from_a"
            ] = distance
            portfolio_b_pool.append(candidate)
        portfolio_b_distinctness_mode = (
            "minimum_weight_distance_met"
        )
    elif distance_pairs:
        maximum_distance = max(
            distance
            for _, distance in distance_pairs
        )
        portfolio_b_pool = []
        for candidate, distance in distance_pairs:
            if abs(
                distance - maximum_distance
            ) <= 1e-12:
                candidate[
                    "_weight_distance_from_a"
                ] = distance
                portfolio_b_pool.append(candidate)
        portfolio_b_distinctness_mode = (
            "most_distinct_candidate_fallback"
        )
    else:
        copied = dict(recommendation_1)
        copied[
            "_weight_distance_from_a"
        ] = 0.0
        portfolio_b_pool = [copied]
        portfolio_b_distinctness_mode = (
            "no_alternative_candidate"
        )

    target_met_candidates = [
        candidate
        for candidate in portfolio_b_pool
        if safe_float(candidate["metrics"].get("after_tax_return"))
        >= target_after_tax_return
    ]

    if target_met_candidates:
        recommendation_2 = min(
            target_met_candidates,
            key=lambda candidate: build_portfolio_b_rank_tuple(candidate["metrics"]),
        )
        portfolio_b_selection_mode = "target_met_risk_minimization"
    else:
        recommendation_2 = min(
            portfolio_b_pool,
            key=lambda candidate: build_portfolio_b_fallback_rank_tuple(
                candidate["metrics"],
                target_after_tax_return,
            ),
        )
        portfolio_b_selection_mode = "target_shortfall_fallback"

    recommendation_2["selection_summary"] = build_selection_summary(
        recommendation_2["metrics"],
        portfolio_type="B",
        target_after_tax_return=target_after_tax_return,
    )

    portfolio_b_weight_distance = safe_float(
        recommendation_2.get(
            "_weight_distance_from_a",
            calculate_weight_distance(
                recommendation_1["weights"],
                recommendation_2["weights"],
            ),
        )
    )
    recommendation_2[
        "selection_summary"
    ].update(
        {
            "portfolio_b_available": (
                portfolio_b_available
            ),
            "weight_distance_from_portfolio_a": (
                safe_round(
                    portfolio_b_weight_distance,
                    6,
                )
            ),
            "minimum_weight_distance_required": (
                PORTFOLIO_B_MIN_WEIGHT_DISTANCE
            ),
            "distinctness_threshold_met": (
                portfolio_b_weight_distance
                >= PORTFOLIO_B_MIN_WEIGHT_DISTANCE
            ),
            "distinctness_mode": (
                portfolio_b_distinctness_mode
            ),
        }
    )

    # A/B 상관계수는 선정 조건이 아니라 화면 참고값으로만 제공한다.
    recommendation_1_series = calculate_portfolio_return_series(
        recommendation_1["weights"],
        returns,
    )
    recommendation_2["correlation_with_recommended_1"] = (
        calculate_portfolio_return_correlation(
            recommendation_1["weights"],
            recommendation_2["weights"],
            returns,
            series_a=recommendation_1_series,
        )
    )

    search_summary = {
        "generated_portfolios": generated_count,
        "guideline_pass_portfolios": guideline_pass_count,
        "suitable_portfolios": suitable_count,
        "liquidity_pass_portfolios": liquidity_pass_count,
        "risk_control_pass_portfolios": risk_control_pass_count,
        "common_filter_pass_portfolios": common_filter_pass_count,
        "filtered_out_portfolios": generated_count - common_filter_pass_count,
        "rejection_counts": rejection_counts,
        "selection_method": 'portfolio_a_max_after_tax_return_portfolio_b_target_risk_minimization',
        "portfolio_a_selection_mode": "max_after_tax_return",
        "portfolio_b_selection_mode": portfolio_b_selection_mode,
        "portfolio_b_available": portfolio_b_available,
        "portfolio_b_distinctness_mode": portfolio_b_distinctness_mode,
        "portfolio_b_weight_distance": safe_round(
            portfolio_b_weight_distance, 6
        ),
        "portfolio_b_min_weight_distance": (
            PORTFOLIO_B_MIN_WEIGHT_DISTANCE
        ),
        "target_after_tax_return": safe_round(target_after_tax_return, 6),
        "random_seed": request.random_seed,
        "eligible_assets": available_assets,
        "excluded_by_horizon": (
            ["separate_tax_bond"]
            if "separate_tax_bond" in raw_available_assets
            and "separate_tax_bond" not in available_assets
            else []
        ),
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
    backtest_returns: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    metrics = calculate_metrics(
        weights=weights,
        returns=returns,
        expected_returns=expected_returns,
        request=request,
        cov_matrix=cov_matrix,
        include_benchmark_metrics=True,
    )

    monte_carlo_metric_ranges = (
        calculate_monte_carlo_metric_ranges(
            weights=weights,
            returns=returns,
            expected_returns=expected_returns,
            total_asset=request.total_asset,
            investment_horizon_years=(
                request.investment_horizon_years
            ),
            tax_breakdown=metrics["tax_breakdown"],
            random_seed=request.random_seed,
        )
    )

    cumulative_source_returns = (
        backtest_returns
        if backtest_returns is not None
        else returns
    )
    cumulative_returns = calculate_cumulative_returns(
        weights,
        cumulative_source_returns,
    )
    benchmark_backtests = calculate_all_benchmark_cumulative_returns(
        weights=weights,
        returns=cumulative_source_returns,
    )
    benchmark_backtest = benchmark_backtests[request.benchmark_key]

    response = {
        "api_key": api_key,
        "name": name,
        "weights": {
            asset: {
                "label": ASSET_NAMES_KR.get(asset, asset),
                "ticker": ASSET_TICKERS.get(asset, asset),
                "weight": round(float(weight), 6),
                "amount": round(
                    float(weight) * request.total_asset,
                    0,
                ),
            }
            for asset, weight in weights.items()
        },
        "asset_expected_returns": {
            asset: safe_round(expected_returns.get(asset), 6)
            for asset in weights
            if asset in expected_returns.index
        },
        "metrics": {
            "expected_return": metrics["expected_return"],
            "volatility": metrics["volatility"],
            "sharpe_ratio": metrics["sharpe_ratio"],
            "sortino_ratio": metrics["sortino_ratio"],
            "mdd": metrics["mdd"],
            "beta": metrics["beta"],
            "beta_benchmark": metrics["beta_benchmark"],
            "selected_benchmark_key": metrics[
                "selected_benchmark_key"
            ],
            "benchmark_comparisons": metrics[
                "benchmark_comparisons"
            ],
            "liquidity_coverage": metrics["liquidity_coverage"],
            "after_tax_return": metrics["after_tax_return"],
            "after_tax_return_range": (
                monte_carlo_metric_ranges.get(
                    "after_tax_return"
                )
                if monte_carlo_metric_ranges.get(
                    "available"
                )
                else None
            ),
            "mdd_range": (
                monte_carlo_metric_ranges.get("mdd")
                if monte_carlo_metric_ranges.get(
                    "available"
                )
                else None
            ),
            "monte_carlo_range_basis": (
                monte_carlo_metric_ranges
            ),
            "krw": metrics["metric_amounts"],
            "metric_amounts": metrics["metric_amounts"],
            "taxable_financial_income": metrics[
                "taxable_financial_income"
            ],
            "portfolio_financial_income": metrics["tax_breakdown"][
                "financial_income_comprehensive_tax"
            ]["portfolio_financial_income"],
            "total_financial_income": metrics["tax_breakdown"][
                "financial_income_comprehensive_tax"
            ]["total_financial_income"],
            "financial_income_comprehensive_tax_status": (
                metrics["tax_breakdown"][
                    "financial_income_comprehensive_tax"
                ]
            ),
            "financial_income_tax_gauge": metrics["tax_breakdown"][
                "financial_income_comprehensive_tax"
            ]["gauge"],
            "risk_level": metrics["risk_level"],
            "risk_level_label": metrics["risk_level_label"],
            "stock_weight": metrics["stock_weight"],
            "bond_cash_weight": metrics["bond_cash_weight"],
            "alternative_weight": metrics["alternative_weight"],
            "portfolio_duration": metrics["portfolio_duration"],
            "target_duration": metrics["target_duration"],
            "duration_fit_score": metrics["duration_fit_score"],
            "historical_var_95": metrics["historical_var_95"],
            "historical_var_95_daily_loss": metrics[
                "historical_var_95_daily_loss"
            ],
            "risk_contribution": metrics["risk_contribution"],
            "risk_contribution_max_share": metrics[
                "risk_contribution_max_share"
            ],
            "selection_risk_control": metrics[
                "selection_risk_control"
            ],
            "stress_test": metrics["stress_test"],
        },
        "metric_amounts": metrics["metric_amounts"],
        "tax_breakdown": metrics["tax_breakdown"],
        "financial_income_tax_gauge": metrics["tax_breakdown"][
            "financial_income_comprehensive_tax"
        ]["gauge"],
        "selection_summary": (
            selection_summary
            if selection_summary is not None
            else build_selection_summary(metrics)
        ),
        "guideline_report": build_guideline_report(metrics),
        "cumulative_returns": cumulative_returns,
        # 기존 프론트 호환: PB가 선택한 한 개
        "benchmark_backtest": benchmark_backtest,
        # 신규 계약: PB가 선택할 수 있는 전체 3종
        "benchmark_backtests": benchmark_backtests,
    }

    if score is not None:
        response["score"] = round(float(score), 6)

    if correlation_with_recommended_1 is not None:
        response["correlation_with_recommended_1"] = round(
            float(correlation_with_recommended_1),
            6,
        )

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
            "portfolio_b_target_source": "RRTTLLU.Return",
            "portfolio_b_objective": "target_return_then_risk_contribution_minimization",
            "portfolio_a_b_correlation_usage": "display_only",
            "benchmark_policy": BENCHMARK_POLICY_VERSION,
            "benchmark_policy_note": (
                "KOSPI, S&P 500, MSCI ACWI 3종을 비교용으로 제공. "
                "벤치마크는 베타·비교 차트에만 사용하며 추천 로직에는 미반영."
            ),
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


def extract_backtest_payload(
    full_response: Dict[str, Any],
) -> Dict[str, Any]:
    data_snapshot = full_response["input_summary"].get(
        "backtest_data_snapshot",
        full_response["input_summary"].get("data_snapshot", {}),
    )
    portfolios = full_response["portfolios"]

    return {
        "session_id": full_response["session_id"],
        "selected_benchmark_key": full_response["input_summary"][
            "benchmark_key"
        ],
        "benchmark_catalog": get_benchmark_catalog(),
        "basis": {
            "base_index": BACKTEST_BASE_INDEX,
            "base_date": data_snapshot.get("data_start"),
            "as_of": (
                data_snapshot.get("as_of")
                or data_snapshot.get("data_end")
            ),
            "note": (
                "백테스트 차트는 5년 구간을 100으로 둔 누적수익률 지수. "
                "벤치마크 3종은 추천 계산과 분리된 비교선."
            ),
        },
        "data_snapshot": data_snapshot,
        "backtest": {
            "current": portfolios["current"]["cumulative_returns"],
            "portfolio_a": portfolios["recommended_1"][
                "cumulative_returns"
            ],
            "portfolio_b": portfolios["recommended_2"][
                "cumulative_returns"
            ],
        },
        # 기존 호환: 선택된 벤치마크
        "benchmarks": {
            "current": portfolios["current"]["benchmark_backtest"],
            "portfolio_a": portfolios["recommended_1"][
                "benchmark_backtest"
            ],
            "portfolio_b": portfolios["recommended_2"][
                "benchmark_backtest"
            ],
        },
        # 신규: 전체 3종
        "benchmark_options": {
            "current": portfolios["current"]["benchmark_backtests"],
            "portfolio_a": portfolios["recommended_1"][
                "benchmark_backtests"
            ],
            "portfolio_b": portfolios["recommended_2"][
                "benchmark_backtests"
            ],
        },
        "summary_metrics": {
            "current": portfolios["current"]["metrics"],
            "portfolio_a": portfolios["recommended_1"]["metrics"],
            "portfolio_b": portfolios["recommended_2"]["metrics"],
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
        "horizon_suitable": irp.get("horizon_suitable"),
        "reason": irp.get("reason"),
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
        "account_key": "taxable_account",
        "display_name": taxable.get("display_name", "일반과세 자산 운용"),
        "account_role": taxable.get("account_role", "residual_and_liquidity"),
        "allocated_amount": taxable["allocated_amount"],
        "liquidity_reserve_target": taxable.get("liquidity_reserve_target", 0.0),
        "liquidity_reserve_allocated": taxable.get("liquidity_reserve_allocated", 0.0),
        "liquidity_reserve_shortfall": taxable.get("liquidity_reserve_shortfall", 0.0),
        "estimated_tax_after_strategy": tax_breakdown["total_tax_after_saving"],
        "status_label": "세제계좌 외 자산 운용",
        "description": (
            "세제계좌 한도 초과 자산과 단기 유동성 자산을 일반과세계좌에서 운용합니다. "
            "손익통산·저회전·과세효율화 전략의 적용 대상이며, 미투자 현금 잔액을 뜻하지 않습니다."
        ),
        "allocations": taxable["allocations"],
    }


TAX_STRATEGY_META = {
    "isa": {
        "title": "ISA 계좌 활용",
        "calculation_order": 1,
        "rule_keys": ["isa_tax_exemption"],
    },
    "pension_credit": {
        "title": "연금계좌 세액공제",
        "calculation_order": 6,
        "rule_keys": ["pension_account_tax_credit"],
    },
    "separate_bond": {
        "title": "분리과세 채권",
        "calculation_order": 3,
        "rule_keys": [],
    },
    "low_tax_dividend": {
        "title": "저율과세 배당주",
        "calculation_order": 2,
        "rule_keys": [],
    },
    "overseas_exemption": {
        "title": "해외주식 양도 250만 공제",
        "calculation_order": 5,
        "rule_keys": ["overseas_stock_transfer_tax"],
    },
    "tax_loss": {
        "title": "Tax-loss Harvesting",
        "calculation_order": 4,
        "rule_keys": ["capital_loss_offset"],
    },
}


def build_tax_strategy_reason(
    strategy_key: str,
    raw_reason: Any,
    card: Dict[str, Any],
    contribution: float,
) -> Dict[str, Any]:
    """내부 부적합 사유를 화면에서 바로 이해할 수 있는 문구로 바꾼다."""
    raw_text = (
        str(raw_reason).strip()
        if raw_reason is not None and str(raw_reason).strip()
        else None
    )

    if contribution > 0:
        return {"reason": None, "reason_code": None, "raw_reason": raw_text}

    if raw_text and "상위 효율 전략 적용 후" in raw_text:
        return {
            "reason": (
                "중복 적용 가능한 과세소득이 앞선 절세 전략에서 모두 사용되어 "
                "이 전략의 추가 절감액은 0원입니다."
            ),
            "reason_code": "shared_tax_base_exhausted",
            "raw_reason": raw_text,
        }

    if strategy_key == "isa":
        if raw_text and "신규 개설 불가" in raw_text:
            reason = "ISA 신규 개설 적격성 조건을 충족하지 못해 이번 절세안에서 제외했습니다."
            code = "isa_new_account_ineligible"
        elif raw_text and "투자기간" in raw_text:
            reason = (
                f"{raw_text}. 고객의 투자기간보다 ISA 잔여 의무보유기간이 길어 "
                "단기 유동성 제약이 발생할 수 있습니다."
            )
            code = "isa_lockup_exceeds_horizon"
        elif raw_text and "적격성·잔여한도" in raw_text:
            reason = (
                "ISA 계좌 사용 요건을 충족하지 못했거나 사용 가능한 "
                "잔여 납입한도가 없어 적용하지 않았습니다."
            )
            code = "isa_ineligible_or_no_capacity"
        else:
            reason = (
                "ISA로 이전할 적격 자산 또는 사용 가능한 납입한도가 없어 "
                "예상 절감액이 없습니다."
            )
            code = "isa_no_transferable_amount"
        return {"reason": reason, "reason_code": code, "raw_reason": raw_text}

    if strategy_key == "pension_credit":
        if raw_text and "투자기간" in raw_text:
            reason = (
                f"{raw_text}. 연금 수령 가능 시점 전에 자금이 필요할 수 있어 "
                "IRP 배치 대상에서 제외했습니다."
            )
            code = "pension_lockup_exceeds_horizon"
        elif raw_text and "산출세액" in raw_text:
            reason = (
                "예상 산출세액이 세액공제액보다 작아 IRP 납입액 전부에 대한 "
                "공제 효과를 적용할 수 없습니다."
            )
            code = "insufficient_tax_liability"
        else:
            reason = (
                "IRP 사용 요건을 충족하지 못했거나 당해 연도 세액공제 한도를 "
                "이미 모두 사용했습니다."
            )
            code = "pension_ineligible_or_no_capacity"
        return {"reason": reason, "reason_code": code, "raw_reason": raw_text}

    if strategy_key == "separate_bond":
        if raw_text and "한계세율" in raw_text:
            reason = (
                "고객 한계세율이 분리과세 가정세율보다 높지 않아 "
                "분리과세 채권의 추가 절세 효과가 없습니다."
            )
            code = "marginal_rate_not_high_enough"
        elif raw_text and "초과분 없음" in raw_text:
            reason = (
                "예상 금융소득이 종합과세 기준을 초과하지 않아 "
                "분리과세 전환으로 줄일 추가 세금이 없습니다."
            )
            code = "no_comprehensive_tax_excess"
        else:
            reason = (
                "현재 포트폴리오에서 분리과세 전환 대상이 되는 "
                "채권 이자소득이 계산되지 않았습니다."
            )
            code = "no_eligible_bond_income"
        return {"reason": reason, "reason_code": code, "raw_reason": raw_text}

    if strategy_key == "low_tax_dividend":
        if raw_text and "초과분 없음" in raw_text:
            reason = (
                "예상 금융소득이 종합과세 기준을 초과하지 않아 "
                "배당소득 조정에 따른 추가 절세 효과가 없습니다."
            )
            code = "no_comprehensive_tax_excess"
        else:
            reason = (
                "현재 포트폴리오에 절세 대상으로 계산할 "
                "배당주·리츠의 예상 배당소득이 없습니다."
            )
            code = "no_eligible_dividend_income"
        return {"reason": reason, "reason_code": code, "raw_reason": raw_text}

    if strategy_key == "overseas_exemption":
        return {
            "reason": (
                "해외주식의 예상 가격차익이 없거나 기본공제를 적용할 "
                "양도차익이 없어 절세액이 계산되지 않았습니다."
            ),
            "reason_code": "no_overseas_capital_gain",
            "raw_reason": raw_text,
        }

    if strategy_key == "tax_loss":
        return {
            "reason": (
                "상계할 해외주식 양도차익 또는 확정 가능한 해외주식 손실이 없어 "
                "Tax-loss Harvesting 효과가 없습니다."
            ),
            "reason_code": "no_offsettable_gain_or_loss",
            "raw_reason": raw_text,
        }

    return {
        "reason": raw_text or "현재 입력 조건에서는 예상 절세 효과가 없습니다.",
        "reason_code": "not_applicable",
        "raw_reason": raw_text,
    }


def build_six_tax_strategy_cards(
    portfolio_response: Dict[str, Any],
    request: PortfolioRequest,
) -> Dict[str, Any]:
    stored_model = (
        portfolio_response
        .get("tax_breakdown", {})
        .get("six_strategy_tax_model")
    )
    if stored_model:
        standalone = stored_model.get(
            "standalone",
            [],
        )
        combined = stored_model.get(
            "combined",
            {},
        )
    else:
        weights = {
            asset: safe_float(
                info.get("weight")
            )
            for asset, info
            in portfolio_response[
                "weights"
            ].items()
        }
        expected_returns = pd.Series(
            {
                asset: safe_float(value)
                for asset, value
                in portfolio_response.get(
                    "asset_expected_returns",
                    {},
                ).items()
            },
            dtype=float,
        )
        fallback_model = (
            calculate_six_strategy_tax_model(
                weights=weights,
                expected_returns=(
                    expected_returns
                ),
                total_asset=(
                    request.total_asset
                ),
                request=request,
                account_buckets=(
                    portfolio_response[
                        "tax_breakdown"
                    ]["account_buckets"]
                ),
            )
        )
        standalone = (
            fallback_model.get(
                "standalone",
                [],
            )
        )
        combined = fallback_model.get(
            "combined",
            {},
        )
    standalone_map = {card["key"]: card for card in standalone}
    contribution_won = combined.get("contributionsWon", {})

    cards = []
    for key, meta in TAX_STRATEGY_META.items():
        card = standalone_map.get(key, {})
        contribution = safe_float(contribution_won.get(key))
        raw_reason = (
            combined.get("ineligible", {}).get(key)
            or combined.get("exhausted", {}).get(key)
            or card.get("ineligibleReason")
        )
        reason_payload = build_tax_strategy_reason(
            strategy_key=key,
            raw_reason=raw_reason,
            card=card,
            contribution=contribution,
        )
        cards.append(
            {
                "key": key,
                "title": meta["title"],
                "calculation_order": meta["calculation_order"],
                "rule_keys": meta.get("rule_keys", []),
                "standalone_saving": safe_round(
                    safe_float(card.get("savingWon")), 0
                ),
                "combined_contribution": safe_round(contribution, 0),
                "combined_contribution_manwon": int(round(contribution / 10_000)),
                "applicable": bool(card.get("applicable")) and contribution > 0,
                "transferable_amount": safe_round(
                    safe_float(card.get("transferableManwon")) * 10_000, 0
                ),
                "reason": reason_payload["reason"],
                "reason_code": reason_payload["reason_code"],
                "raw_reason": reason_payload["raw_reason"],
            }
        )

    # 계산 순서와 화면 표시 순서는 분리한다.
    # 계산 엔진은 중복 과세소득을 제거하기 위한 calculation_order를 유지하고,
    # 화면 카드는 고객마다 위치가 바뀌지 않도록 TAX_STRATEGY_META의 고정 순서를 쓴다.
    for rank, card in enumerate(cards, start=1):
        card["priority_rank"] = rank

    return {
        "cards": cards,
        "combined_total": safe_round(combined.get("totalWon"), 0),
        "combined_total_manwon": combined.get("totalManwon", 0),
        "calculation_order": combined.get("calculationOrder", []),
        "display_order_basis": "fixed_strategy_order",
        "overlap_policy": (
            "종합과세 초과분은 ISA→저율배당→분리과세채 순으로 한 번만 사용하고, "
            "해외주식 손실과 250만원 기본공제는 같은 양도차익에 순차 적용합니다."
        ),
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
    six_strategy = build_six_tax_strategy_cards(portfolio_response, request)
    combined_tax_saving = safe_float(six_strategy["combined_total"])
    modeled_tax_reduction = min(combined_tax_saving, max(tax_before, 0.0))
    combined_tax_after = max(tax_before - modeled_tax_reduction, 0.0)
    combined_after_tax_profit = gross_profit - combined_tax_after
    combined_after_tax_return = (
        combined_after_tax_profit / request.total_asset
        if request.total_asset > 0
        else 0.0
    )

    return {
        "portfolio_key": portfolio_key,
        "portfolio_name": portfolio_response["name"],
        "total_asset": safe_round(request.total_asset, 0),
        "headline": {
            "annual_tax_saving": safe_round(combined_tax_saving, 0),
            "tax_amount_before": safe_round(tax_before, 0),
            "tax_amount_after": safe_round(combined_tax_after, 0),
            "after_tax_return_before": safe_round(before_after_tax_return, 6),
            "after_tax_return_after": safe_round(combined_after_tax_return, 6),
            "after_tax_return_improvement_p": safe_round(
                combined_after_tax_return - before_after_tax_return, 6
            ),
            "modeled_tax_reduction": safe_round(modeled_tax_reduction, 0),
            "unapplied_credit_or_saving": safe_round(
                max(combined_tax_saving - modeled_tax_reduction, 0.0), 0
            ),
            "legacy_account_only_tax_saving": safe_round(tax_saving, 0),
        },
        "strategy_cards": six_strategy,
        "financial_income_tax_gauge": tax_breakdown[
            "financial_income_comprehensive_tax"
        ]["gauge"],
        "financial_income_comprehensive_tax_status": tax_breakdown[
            "financial_income_comprehensive_tax"
        ],
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
    constraint_warnings = build_constraint_warnings(request)
    request.unique_asset = get_effective_unique_asset(request)
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

    backtest_prices = download_backtest_price_data(
        period="5y",
        cash_return=request.cash_return,
    )
    backtest_data_snapshot = backtest_prices.attrs.get("data_snapshot", {})
    backtest_returns = calculate_daily_returns(backtest_prices)

    benchmark_returns, benchmark_snapshot = download_benchmark_returns(
        period=request.period,
    )
    if request.period == "5y":
        backtest_benchmark_returns = benchmark_returns
        backtest_benchmark_snapshot = benchmark_snapshot
    else:
        (
            backtest_benchmark_returns,
            backtest_benchmark_snapshot,
        ) = download_benchmark_returns(period="5y")

    analysis_returns = attach_benchmark_returns(
        returns,
        benchmark_returns,
    )
    analysis_backtest_returns = attach_benchmark_returns(
        backtest_returns,
        backtest_benchmark_returns,
    )

    data_snapshot = {
        **data_snapshot,
        "benchmarks": benchmark_snapshot,
    }
    backtest_data_snapshot = {
        **backtest_data_snapshot,
        "benchmarks": backtest_benchmark_snapshot,
    }

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
        returns=analysis_returns,
        expected_returns=expected_returns,
        request=request,
        cov_matrix=cov_matrix,
        backtest_returns=analysis_backtest_returns,
    )

    rec_1_response = build_portfolio_response(
        name="포트폴리오 A",
        api_key="portfolio_a",
        weights=recommendations[0]["weights"],
        returns=analysis_returns,
        expected_returns=expected_returns,
        request=request,
        selection_summary=recommendations[0]["selection_summary"],
        cov_matrix=cov_matrix,
        backtest_returns=analysis_backtest_returns,
    )

    rec_2_response = build_portfolio_response(
        name="포트폴리오 B",
        api_key="portfolio_b",
        weights=recommendations[1]["weights"],
        returns=analysis_returns,
        expected_returns=expected_returns,
        request=request,
        selection_summary=recommendations[1]["selection_summary"],
        correlation_with_recommended_1=recommendations[1].get("correlation_with_recommended_1"),
        cov_matrix=cov_matrix,
        backtest_returns=analysis_backtest_returns,
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

"comparison_basis": {
    "same_analysis_return_matrix": True,
    "same_expected_return_assumptions": True,
    "same_covariance_matrix": True,
    "same_tax_assumptions": True,
    "same_risk_free_rate": True,
    "same_cash_return": True,
    "analysis_period_requested": (
        request.period
    ),
    "analysis_data_start": (
        data_snapshot.get(
            "data_start"
        )
    ),
    "analysis_data_end": (
        data_snapshot.get(
            "data_end"
        )
    ),
    "backtest_period": "5y",
    "same_backtest_return_matrix": True,
    "backtest_data_start": (
        backtest_data_snapshot.get(
            "data_start"
        )
    ),
    "backtest_data_end": (
        backtest_data_snapshot.get(
            "data_end"
        )
    ),
    "compared_portfolios": [
        "current",
        "portfolio_a",
        "portfolio_b",
    ],
},
            "unique_asset_label": ASSET_NAMES_KR[request.unique_asset],
            "unique_items": request.unique_items,
            "unique_profile": request.unique_profile,
            "age": request.age,
            "client_context": request.client_context,
            "target_after_tax_return": request.target_after_tax_return,
            "analysis_scope": request.client_context.get(
                "calculation_scope",
                "개인 투자포트폴리오 계산",
            ),
            "unique_engine_note": (
                "Unique 원문은 보존하되 LLM 없이 결정론적 규칙으로 "
                "금액·시점·ISA·IRP 및 범용 법인/승계 플래그만 반영합니다."
            ),
            "risk_profile": request.risk_profile,
            "client_risk_level": CLIENT_RISK_LEVEL[request.risk_profile],
            "investment_horizon_years": request.investment_horizon_years,
            "tax_sensitivity": request.tax_sensitivity,
            "liquidity_need": request.liquidity_need,
            "risk_free_rate": request.risk_free_rate,
            "risk_free_rate_basis": "미국 기준 무위험이자율. 시나리오 테스트 금리와 분리.",
            "cash_return": request.cash_return,
            "period": request.period,
            "benchmark_key": request.benchmark_key,
            "benchmark_catalog": get_benchmark_catalog(),
            "backtest_period": "5y",
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
            "overseas_realized_loss": request.overseas_realized_loss,
            "other_financial_income": request.other_financial_income,
            "external_financial_income_krw": resolve_external_financial_income_krw(
                request
            ),
            "external_financial_income_manwon": safe_round(
                resolve_external_financial_income_krw(request) / 10_000, 0
            ),
            "pension_tax_liability_sufficient": request.pension_tax_liability_sufficient,
            "isa_enabled": request.isa_enabled,
            "isa_type": request.isa_type,
            "isa_account_exists": request.isa_account_exists,
            "isa_account_age_years": request.isa_account_age_years,
            "isa_cumulative_contribution": request.isa_cumulative_contribution,
            "isa_current_year_contribution": request.isa_current_year_contribution,
            "isa_recent_3yr_comprehensive_taxed": (
                request.isa_recent_3yr_comprehensive_taxed
            ),
            "isa_remaining_capacity": request.isa_remaining_capacity,
            "isa_remaining_capacity_override": request.isa_remaining_capacity_override,
            "isa_years_until_liquid": request.isa_years_until_liquid,
            "irp_enabled": request.irp_enabled,
            "irp_eligible": request.irp_eligible,
            "irp_account_exists": request.irp_account_exists,
            "irp_account_age_years": request.irp_account_age_years,
            "irp_cumulative_contribution": request.irp_cumulative_contribution,
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
            "backtest_data_snapshot": backtest_data_snapshot,
        },
        "search_summary": {
            **search_summary,
            "constraint_warnings": constraint_warnings,
        },
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
            "optimization_basis": "Mean-Variance 기반: 실제 가격 데이터의 기대수익률, 공분산 기반 변동성, Sharpe Ratio 계산.",
            "risk_classification": "변동성, MDD, 유동성 커버리지, 자산구성비중을 hard filter로 사용.",
            "selection_logic": (
                "고객 적합성·유동성·95% Historical VaR·위험기여도 집중도 제한을 "
                "모두 통과한 후보만 추천 대상으로 사용합니다. 포트폴리오 A는 세후수익률 "
                "최대, 포트폴리오 B는 IPS 목표 세후수익률 달성 후 위험집중도 최소를 "
                "목적으로 선정합니다."
            ),
            "duration_logic": "듀레이션은 채권형 자산에만 적용하고 ETF proxy 기준 수치를 사용.",
            "suitability_filter": "포트폴리오 위험등급이 고객 위험성향 이하인 경우만 추천.",
            "liquidity_metric": "현금+일반채/저쿠폰채/분리과세채 금액에서 ISA 의무기간 잠김 금액을 제외한 값 / 단기 필요금액.",
            "tax_logic": (
                "금융소득종합과세 검토액, 해외주식 양도세 추정액, "
                "ISA/IRP 효과를 포트폴리오별로 계산. 배당·이자성 수익과 "
                "가격차익은 간이 분리하여 중복 과세를 피함."
            ),
            "second_portfolio_logic": (
                "포트폴리오 B는 RRTTLLU.Return을 목표 세후수익률로 사용합니다. "
                "목표를 충족한 후보 중 위험기여도 최대 집중도가 가장 낮은 후보를 선택하고, "
                "목표 달성 후보가 없으면 목표 부족 폭이 가장 작은 후보를 선택합니다. "
                "포트폴리오 A와의 상관계수는 선정 조건이 아니라 화면 참고값으로만 제공합니다."
            ),
            "stress_test_logic": "금리 충격은 채권형 자산에만 -듀레이션×금리변화를 적용.",
            "var_erc_logic": "95% historical VaR와 공분산 기반 위험기여도 집중도를 리스크 관리에 반영.",
            "benchmark_beta_logic": (
                "KOSPI, S&P 500, MSCI ACWI 중 PB가 선택한 벤치마크를 표시 기준으로 사용. "
                "세 벤치마크의 베타와 백테스트 비교값은 최종 포트폴리오 확정 후 계산하며, "
                "후보 생성·필터·순위에는 반영하지 않음."
            ),
            "corporate_context_logic": (
                "법인·가업승계 키워드는 범용 advisory flag와 단기 유동성 제약으로만 "
                "반영하며 법인세·기업가치 세액은 개인 포트폴리오 엔진에서 계산하지 않음."
            ),
            "backtest_caution": (
                "추천·기대수익률·위험지표는 실제 가격 데이터만 사용하고, "
                "백테스트 차트만 과제 조건에 따라 5년 구간으로 고정함. "
                "신규 상장 또는 데이터 시작 전 구간은 백테스트 차트에서만 현금 수익률로 대체함."
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
        "unique_profile": core["input_summary"].get("unique_profile", {}),
    }

    core["backtest"] = extract_backtest_payload(core)
    core["tax_optimizer"] = build_tax_optimizer_map(core, portfolio_request)
    core["tax_inputs"] = extract_tax_inputs_payload(core)

    return core



# ============================================================
# 12-1. API 입력 어댑터
# ============================================================
# 프론트 연동용 보조 로직.
# 검증된 사실: consultations API의 ips_json은 Goal/Asset/Return/Risk/Time/Tax/Liquidity/Legal/Unique
# 형태이고, 포트폴리오 계산 로직은 AnalysisRequest 형태를 사용한다.
# 프로젝트용 처리: /portfolio/calculate는 AnalysisRequest와 consultations 응답/ips_json을 모두 받을 수 있게 정규화한다.

KOREAN_MONEY_UNITS = {
    "억": 100_000_000,
    "만": 10_000,
    "천": 1_000,
}

# 금액·연도 파싱 정규식의 ReDoS 방어 상한. 정상 IPS·상담 텍스트는 이보다 훨씬 짧다.
# 비정상적으로 긴 입력은 잘라 정규식의 위치 재스캔(O(N^2))을 상수 시간으로 묶는다.
_MAX_TEXT_PARSE_LEN = 2000


def parse_amount_krw(value: Any, default: float = 0.0) -> float:
    """숫자, dict, '3억', '2,000만 원' 같은 문자열에서 원화 금액/숫자를 추출한다.

    단위가 없는 숫자 문자열은 그대로 숫자로 본다. 해석할 수 없으면 default를 반환한다.
    """
    if value is None:
        return default

    if isinstance(value, bool):
        return default

    if isinstance(value, (int, float)):
        return safe_float(value, default)

    if isinstance(value, dict):
        for key in (
            "amount",
            "need_amount",
            "unique_need_amount",
            "total_asset",
            "Asset",
            "asset",
            "value",
        ):
            if key in value:
                parsed = parse_amount_krw(value.get(key), default=None)
                if parsed is not None:
                    return parsed
        return default

    text_value = str(value).strip()
    if not text_value:
        return default

    normalized = text_value.replace(",", "")[:_MAX_TEXT_PARSE_LEN]
    total = 0.0
    matched_unit = False
    for number_text, unit in re.findall(r"([0-9]++(?:\.[0-9]++)?)\s*+([억만천])", normalized):
        matched_unit = True
        total += float(number_text) * KOREAN_MONEY_UNITS[unit]

    if matched_unit:
        return float(total)

    number_match = re.search(r"-?[0-9]+(?:\.[0-9]+)?", normalized)
    if number_match:
        return safe_float(number_match.group(0), default)

    return default



def stringify_unique_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            parts.append(f"{key}: {stringify_unique_value(item)}")
        return " | ".join(parts)
    if isinstance(value, list):
        return " | ".join(stringify_unique_value(item) for item in value)
    return str(value)


def find_keyword_window(text: str, keywords: List[str], radius: int = 90) -> str:
    lower_text = text.lower()
    for keyword in keywords:
        index = lower_text.find(keyword.lower())
        if index >= 0:
            start = max(index - radius, 0)
            end = min(index + len(keyword) + radius, len(text))
            return text[start:end]
    return ""



def truncate_at_stop_keywords(text: str, stop_keywords: List[str]) -> str:
    lower_text = text.lower()
    cut_points = [
        lower_text.find(keyword.lower())
        for keyword in stop_keywords
        if lower_text.find(keyword.lower()) > 0
    ]
    if not cut_points:
        return text
    return text[: min(cut_points)]


def find_account_segment(
    text: str,
    keywords: List[str],
    stop_keywords: List[str],
    radius_before: int = 0,
    radius_after: int = 140,
) -> str:
    lower_text = text.lower()
    indexes = [
        lower_text.find(keyword.lower())
        for keyword in keywords
        if lower_text.find(keyword.lower()) >= 0
    ]
    if not indexes:
        return ""

    index = min(indexes)
    start = max(index - radius_before, 0)
    end = min(index + radius_after, len(text))

    stop_indexes = [
        lower_text.find(stop.lower(), index + 1)
        for stop in stop_keywords
        if lower_text.find(stop.lower(), index + 1) > index
    ]
    if stop_indexes:
        end = min(end, min(stop_indexes))

    return text[start:end]


def parse_start_year_from_text(text: str) -> Optional[int]:
    for pattern in (
        r"(19[0-9]{2}|20[0-9]{2})\s*년\s*(?:에\s*)?(?:가입|개설|시작)",
        r"(?:가입|개설|시작)\s*(?:연도|년도)?\s*[:=]?\s*(19[0-9]{2}|20[0-9]{2})",
    ):
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None


def calculate_account_age_years_from_start_year(start_year: Optional[int]) -> float:
    if start_year is None:
        return 0.0
    current_year = datetime.now(KST).year
    return float(max(current_year - int(start_year), 0))


def parse_relative_years_from_text(text: str) -> Optional[float]:
    match = re.search(
        r"([0-9]++(?:\.[0-9]++)?)\s*+년\s*+(?:후|뒤|내|안|이내)",
        text[:_MAX_TEXT_PARSE_LEN],
    )
    if match:
        return safe_float(match.group(1), 0.0)
    return None


def parse_amount_near_keywords(text: str, keywords: List[str]) -> float:
    window = find_keyword_window(text, keywords)
    if not window:
        return 0.0
    return parse_amount_krw(window)



def parse_explicit_money_amount_krw(value: Any) -> float:
    text_value = stringify_unique_value(value).replace(",", "").strip()[:_MAX_TEXT_PARSE_LEN]
    if not text_value:
        return 0.0

    total = 0.0
    matched_unit = False
    for number_text, unit in re.findall(r"([0-9]++(?:\.[0-9]++)?)\s*+([억만천])", text_value):
        matched_unit = True
        total += float(number_text) * KOREAN_MONEY_UNITS[unit]
    if matched_unit:
        return float(total)

    won_match = re.search(r"([0-9]++(?:\.[0-9]++)?)\s*+원", text_value)
    if won_match:
        return safe_float(won_match.group(1), 0.0)

    return 0.0


def parse_current_year_contribution(text: str, keywords: List[str]) -> Optional[float]:
    window = find_keyword_window(text, keywords, radius=120)
    if not window:
        return None

    if re.search(r"(?:올해|금년|당해).{0,30}(?:납입|입금).{0,30}(?:없|무|0원|0\s*원)", window):
        return 0.0
    if re.search(r"(?:납입|입금).{0,30}(?:없|무|0원|0\s*원)", window):
        return 0.0

    current_year_match = re.search(
        r"(?:올해|금년|당해).{0,40}([0-9]++(?:\.[0-9]++)?\s*+[억만천]?)\s*+(?:원)?\s*+(?:납입|입금)",
        window,
    )
    if current_year_match:
        return parse_amount_krw(current_year_match.group(1))

    return None


def contains_negative_account_signal(text: str, keywords: List[str]) -> bool:
    window = find_keyword_window(text, keywords, radius=80)
    if not window:
        return False
    return bool(re.search(r"(?:미가입|없음|없다|안\s*만듦|안\s*만들)", window))



def parse_liquidity_need_amount(unique_value: Any, text: str) -> float:
    """Unique에서 별도 확보해야 하는 유동성 금액만 추출한다.

    ISA/IRP 납입액을 unique_need_amount로 오인하지 않도록,
    주거·전세·생활비·필요자금 등 개인 유동성 신호가 있거나
    명시 key가 있을 때만 우선 추출한다.
    """
    if isinstance(unique_value, dict):
        for key in (
            "unique_need_amount",
            "need_amount",
            "liquidity_need_amount",
            "required_amount",
            "personal_need_amount",
        ):
            if key in unique_value:
                return parse_amount_krw(unique_value.get(key))

    personal_liquidity_keywords = [
        "전세",
        "주거",
        "목돈",
        "필요자금",
        "필요 자금",
        "필요",
        "유동성",
        "생활비",
        "학자금",
        "결혼",
        "병원",
        "긴급",
    ]
    for keyword in personal_liquidity_keywords:
        window = find_keyword_window(text, [keyword], radius=120)
        window = truncate_at_stop_keywords(
            window,
            ["ISA", "isa", "IRP", "irp", "개인종합자산관리", "개인형퇴직연금", "퇴직연금"],
        )
        amount = parse_amount_krw(window)
        if amount > 0:
            return amount

    has_account_info = bool(
        find_keyword_window(text, ["isa", "개인종합자산관리"], radius=30)
        or find_keyword_window(text, ["irp", "개인형퇴직연금", "퇴직연금"], radius=30)
    )
    if has_account_info:
        return 0.0

    return parse_amount_krw(unique_value)


def extract_generic_client_context(unique_value: Any, text: str) -> Dict[str, Any]:
    """Extract only generic, auditable context flags; never persona-name rules."""
    lower = text.lower()
    has_corporation = bool(
        re.search(r"법인|회사\s*대표|기업\s*대표|사업체|오너|경영권", lower)
    )
    estate_succession_goal = bool(
        re.search(r"가업\s*승계|기업\s*승계|상속|증여|후계", lower)
    )
    corporate_liquidity_window = find_keyword_window(
        text, ["법인", "운전자금", "사업자금", "회사 자금"], radius=140
    )
    corporate_liquidity_window = truncate_at_stop_keywords(
        corporate_liquidity_window,
        ["ISA", "isa", "IRP", "irp", "개인종합자산관리", "개인형퇴직연금"],
    )
    corporate_liquidity_need = 0.0
    if corporate_liquidity_window and re.search(
        r"운전자금|사업자금|법인.{0,20}유동성|회사.{0,20}유동성",
        corporate_liquidity_window,
    ):
        corporate_liquidity_need = parse_amount_krw(corporate_liquidity_window)

    flags: List[str] = []
    if has_corporation:
        flags.append("corporate_finance_review_required")
    if estate_succession_goal:
        flags.append("estate_succession_review_required")

    return {
        "has_corporation": has_corporation,
        "estate_succession_goal": estate_succession_goal,
        "corporate_liquidity_need_amount": safe_round(
            corporate_liquidity_need, 0
        ),
        "advisory_flags": flags,
        "calculation_scope": (
            "개인 투자포트폴리오와 명시된 단기 필요자금만 계산. "
            "법인세·기업가치·지분이전 세액은 별도 법인/세무 모듈 검토 대상."
        ),
    }


def extract_unique_profile(unique_value: Any) -> Dict[str, Any]:
    """Unique 원문에서 현재 엔진이 안전하게 해석 가능한 정보만 추출한다.

    LLM을 붙이지 않는 이상 '무엇이든 의미까지 이해'할 수는 없으므로,
    원문은 raw/text로 보존하고 금액·상대시점·ISA·IRP 같은 명시 패턴만 반영한다.
    """
    text = stringify_unique_value(unique_value).strip()
    client_context = extract_generic_client_context(unique_value, text)
    liquidity_amount = parse_liquidity_need_amount(unique_value, text)
    corporate_need = safe_float(
        client_context.get("corporate_liquidity_need_amount")
    )
    # 동일 문구가 일반 유동성 파서와 법인 파서에 동시에 잡힐 수 있어 합산하지 않고
    # 더 큰 명시 금액을 사용한다. 구조화 입력이 있으면 unique_need_amount로 직접 전달한다.
    liquidity_amount = max(liquidity_amount, corporate_need)
    liquidity_years = parse_relative_years_from_text(text)

    isa_window = find_account_segment(
        text,
        ["isa", "개인종합자산관리"],
        ["irp", "개인형퇴직연금", "퇴직연금"],
    )
    irp_window = find_account_segment(
        text,
        ["irp", "개인형퇴직연금", "퇴직연금"],
        ["isa", "개인종합자산관리"],
    )

    isa_start_year = parse_start_year_from_text(isa_window)
    isa_contribution = parse_explicit_money_amount_krw(isa_window) if isa_window else 0.0
    isa_account_exists = bool(isa_window) and not bool(
        re.search(r"(?:(?:ISA|isa|IRP|irp|개인종합자산관리|개인형퇴직연금|퇴직연금)\s*(?:계좌\s*)?(?:없음|없다)|미가입|계좌\s*없|가입.{0,5}안|개설.{0,5}안|안\s*만듦|안\s*만들)", isa_window)
    )

    irp_start_year = parse_start_year_from_text(irp_window)
    irp_current_year_contribution = parse_current_year_contribution(
        irp_window,
        ["irp", "개인형퇴직연금", "퇴직연금"],
    )
    irp_cumulative_contribution = parse_explicit_money_amount_krw(irp_window) if irp_window else 0.0
    irp_account_exists = bool(irp_window) and not bool(
        re.search(r"(?:(?:ISA|isa|IRP|irp|개인종합자산관리|개인형퇴직연금|퇴직연금)\s*(?:계좌\s*)?(?:없음|없다)|미가입|계좌\s*없|가입.{0,5}안|개설.{0,5}안|안\s*만듦|안\s*만들)", irp_window)
    )

    items: List[Dict[str, Any]] = []
    if liquidity_amount > 0:
        items.append(
            {
                "type": "liquidity_need",
                "amount": safe_round(liquidity_amount, 0),
                "years_until_need": safe_round(liquidity_years, 2)
                if liquidity_years is not None
                else None,
                "source": "unique",
            }
        )
    if isa_window:
        items.append(
            {
                "type": "isa_account",
                "account_exists": isa_account_exists,
                "start_year": isa_start_year,
                "account_age_years": safe_round(
                    calculate_account_age_years_from_start_year(isa_start_year),
                    2,
                ),
                "cumulative_contribution": safe_round(isa_contribution, 0),
                "source": "unique",
            }
        )
    if irp_window:
        items.append(
            {
                "type": "irp_account",
                "account_exists": irp_account_exists,
                "start_year": irp_start_year,
                "account_age_years": safe_round(
                    calculate_account_age_years_from_start_year(irp_start_year),
                    2,
                ),
                "cumulative_contribution": safe_round(irp_cumulative_contribution, 0),
                "current_year_contribution": safe_round(
                    irp_current_year_contribution,
                    0,
                )
                if irp_current_year_contribution is not None
                else None,
                "source": "unique",
            }
        )

    if client_context["advisory_flags"]:
        items.append(
            {
                "type": "advisory_context",
                "flags": client_context["advisory_flags"],
                "source": "unique",
            }
        )

    return {
        "raw": unique_value,
        "text": text,
        "items": items,
        "client_context": client_context,
        "liquidity_need_amount": safe_round(liquidity_amount, 0),
        "liquidity_need_years": safe_round(liquidity_years, 2)
        if liquidity_years is not None
        else None,
        "isa": {
            "detected": bool(isa_window),
            "account_exists": isa_account_exists,
            "start_year": isa_start_year,
            "account_age_years": safe_round(
                calculate_account_age_years_from_start_year(isa_start_year),
                2,
            ),
            "cumulative_contribution": safe_round(isa_contribution, 0),
        },
        "irp": {
            "detected": bool(irp_window),
            "account_exists": irp_account_exists,
            "start_year": irp_start_year,
            "account_age_years": safe_round(
                calculate_account_age_years_from_start_year(irp_start_year),
                2,
            ),
            "cumulative_contribution": safe_round(irp_cumulative_contribution, 0),
            "current_year_contribution": safe_round(
                irp_current_year_contribution,
                0,
            )
            if irp_current_year_contribution is not None
            else None,
        },
        "parser_note": (
            "LLM 미사용 규칙 기반 파서. 금액·n년 후·ISA/IRP 가입연도/납입액처럼 "
            "명시된 패턴만 계산 입력에 반영하고, 그 외 자연어는 raw/text로 보존한다."
        ),
    }


def apply_unique_profile_to_ips_payload(
    ips_payload: Dict[str, Any],
    unique_value: Any,
    adapter_warnings: List[str],
) -> Dict[str, Any]:
    profile = extract_unique_profile(unique_value)
    result = dict(ips_payload)

    result["unique_profile"] = {
        **profile,
        **result.get("unique_profile", {}),
    }
    result["unique_items"] = result.get("unique_items") or profile["items"]
    result["client_context"] = {
        **profile.get("client_context", {}),
        **result.get("client_context", {}),
    }

    if safe_float(result.get("unique_need_amount")) <= 0:
        result["unique_need_amount"] = profile["liquidity_need_amount"]

    if not result.get("unique_asset"):
        result["unique_asset"] = normalize_unique_asset_value(unique_value)

    isa_info = profile["isa"]
    if isa_info["detected"]:
        if "isa_account_exists" not in result:
            result["isa_account_exists"] = isa_info["account_exists"]
        if safe_float(result.get("isa_account_age_years")) <= 0:
            result["isa_account_age_years"] = isa_info["account_age_years"]
        if safe_float(result.get("isa_cumulative_contribution")) <= 0:
            result["isa_cumulative_contribution"] = isa_info["cumulative_contribution"]

    irp_info = profile["irp"]
    if irp_info["detected"]:
        if "irp_account_exists" not in result:
            result["irp_account_exists"] = irp_info["account_exists"]
        if safe_float(result.get("irp_account_age_years")) <= 0:
            result["irp_account_age_years"] = irp_info["account_age_years"]
        if safe_float(result.get("irp_cumulative_contribution")) <= 0:
            result["irp_cumulative_contribution"] = irp_info["cumulative_contribution"]
        if irp_info["current_year_contribution"] is not None and safe_float(
            result.get("irp_current_year_contribution")
        ) <= 0:
            result["irp_current_year_contribution"] = irp_info[
                "current_year_contribution"
            ]

    if profile["text"] and not profile["items"]:
        adapter_warnings.append(
            "Unique 원문은 보존했지만 규칙 기반 파서가 계산에 반영할 수 있는 "
            "금액·시점·ISA·IRP 패턴을 찾지 못했습니다."
        )

    return result


def normalize_risk_profile_value(value: Any) -> str:
    text_value = str(value or "").strip().lower()
    mapping = {
        "안정형": "conservative",
        "보수형": "conservative",
        "conservative": "conservative",
        "균형형": "balanced",
        "중립형": "balanced",
        "balanced": "balanced",
        "공격형": "aggressive",
        "적극형": "aggressive",
        "aggressive": "aggressive",
    }
    if text_value in mapping:
        return mapping[text_value]
    raise ValueError(f"투자성향 값을 해석할 수 없습니다: {value}")


def normalize_liquidity_value(value: Any) -> str:
    text_value = str(value or "").strip().lower()
    mapping = {
        "낮음": "low",
        "낮은": "low",
        "low": "low",
        "중간": "mid",
        "보통": "mid",
        "중": "mid",
        "medium": "mid",
        "mid": "mid",
        "높음": "high",
        "높은": "high",
        "high": "high",
    }
    if text_value in mapping:
        return mapping[text_value]
    raise ValueError(f"유동성 값을 해석할 수 없습니다: {value}")


def normalize_tax_sensitivity_value(value: Any) -> str:
    text_value = str(value or "").strip().lower()
    mapping = {
        "낮음": "low",
        "낮은": "low",
        "low": "low",
        "중간": "medium",
        "보통": "medium",
        "중": "medium",
        "mid": "medium",
        "medium": "medium",
        "높음": "high",
        "높은": "high",
        "high": "high",
    }
    if text_value in mapping:
        return mapping[text_value]
    raise ValueError(f"세금 민감도 값을 해석할 수 없습니다: {value}")


def normalize_unique_asset_value(value: Any) -> str:
    if value is None:
        return "cash"

    if isinstance(value, dict):
        for key in ("unique_asset", "asset_class", "asset", "type"):
            if key in value:
                return normalize_unique_asset_value(value.get(key))
        return "cash"

    text_value = str(value).strip()
    canonical = canonicalize_asset_key(text_value)
    if canonical in UNIQUE_ASSETS:
        return canonical

    personal_liquidity_keywords = (
        "전세",
        "주거",
        "목돈",
        "필요",
        "유동성",
        "생활비",
        "학자금",
        "결혼",
        "병원",
        "긴급",
    )
    if any(keyword in text_value for keyword in personal_liquidity_keywords):
        return "cash"
    if "분리" in text_value:
        return "separate_tax_bond"
    if "저쿠폰" in text_value:
        return "low_coupon_bond"
    if "채" in text_value or "국채" in text_value:
        return "general_bond"
    return "cash"


def extract_flat_ips_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """상담 API 응답 또는 ips_json 자체에서 flat IPS dict를 꺼낸다."""
    candidate = payload

    if "ips_json" in candidate and isinstance(candidate["ips_json"], dict):
        candidate = candidate["ips_json"]
    elif "ips" in candidate and isinstance(candidate["ips"], dict):
        candidate = candidate["ips"]

    rrttllu = candidate.get("RRTTLLU")
    if isinstance(rrttllu, dict):
        flattened = {
            "Goal": candidate.get("Goal"),
            "Asset": candidate.get("Asset"),
        }
        flattened.update(rrttllu)
        candidate = flattened

    required_keys = {"Asset", "Risk", "Time", "Tax", "Liquidity"}
    if not required_keys.issubset(candidate.keys()):
        missing = sorted(required_keys - set(candidate.keys()))
        raise ValueError(
            "AnalysisRequest 또는 상담 IPS 형식으로 해석할 수 없습니다. "
            f"필수 IPS 키 누락: {missing}"
        )

    return candidate



def extract_request_metadata(payload: Dict[str, Any]) -> Dict[str, Any]:
    """명세서 ⑤ 요청에서 고객·상담 식별자를 추출한다."""
    client_id = payload.get("client_id") or payload.get("customer_id")
    consultation_id = payload.get("consultation_id")

    nested_consultation = payload.get("consultation")
    if not consultation_id and isinstance(nested_consultation, dict):
        consultation_id = nested_consultation.get("consultation_id")

    return {
        "client_id": str(client_id) if client_id else None,
        "consultation_id": str(consultation_id) if consultation_id else None,
    }


def extract_current_weights_from_portfolio(
    payload: Dict[str, Any],
    adapter_warnings: List[str],
) -> Optional[Dict[str, float]]:
    """명세서 current_portfolio 배열을 내부 current_weights dict로 변환한다."""
    current_portfolio = payload.get("current_portfolio")

    if current_portfolio is None:
        ips_payload = payload.get("ips")
        if isinstance(ips_payload, dict):
            current_portfolio = ips_payload.get("current_portfolio")

    if current_portfolio is None:
        explicit_weights = payload.get("current_weights")
        if explicit_weights is not None:
            return normalize_weights(explicit_weights)

        ips_payload = payload.get("ips")
        if isinstance(ips_payload, dict) and ips_payload.get("current_weights") is not None:
            return normalize_weights(ips_payload["current_weights"])

        adapter_warnings.append(
            "current_portfolio/current_weights 입력이 없어 현재 포트폴리오는 "
            "현금 100%로 계산했습니다."
        )
        return None

    if not isinstance(current_portfolio, list) or len(current_portfolio) == 0:
        raise ValueError("current_portfolio는 비어 있지 않은 배열이어야 합니다.")

    weights: Dict[str, float] = {}
    total_weight_percent = 0.0

    for item in current_portfolio:
        if not isinstance(item, dict):
            raise ValueError("current_portfolio의 각 항목은 객체여야 합니다.")

        asset_class = item.get("asset_class")
        if asset_class is None:
            raise ValueError("current_portfolio 항목에 asset_class가 필요합니다.")

        asset = canonicalize_asset_key(str(asset_class))
        if asset not in ASSET_TICKERS:
            raise ValueError(f"지원하지 않는 current_portfolio 자산군입니다: {asset_class}")

        weight_percent = safe_float(item.get("weight"), default=np.nan)
        if not np.isfinite(weight_percent) or weight_percent < 0:
            raise ValueError("current_portfolio.weight는 0 이상의 숫자여야 합니다.")

        total_weight_percent += weight_percent
        weights[asset] = weights.get(asset, 0.0) + weight_percent / 100.0

    if abs(total_weight_percent - 100.0) > 1e-6:
        raise ValueError(
            "current_portfolio weight 합계는 100이어야 합니다. "
            f"현재 합계: {total_weight_percent}"
        )

    return normalize_weights(weights)

def extract_optional_age(payload: Dict[str, Any]) -> Optional[int]:
    candidates: List[Any] = [
        payload.get("age"),
        payload.get("customer_age"),
        payload.get("client_age"),
    ]
    for nested_key in ("customer", "client", "persona", "profile", "ips"):
        nested = payload.get(nested_key)
        if isinstance(nested, dict):
            candidates.extend(
                [nested.get("age"), nested.get("customer_age"), nested.get("client_age")]
            )
    for value in candidates:
        if value is None or isinstance(value, bool):
            continue
        match = re.search(r"[0-9]{1,3}", str(value))
        if match:
            age = int(match.group(0))
            if 0 <= age <= 120:
                return age
    return None


def normalize_analysis_request_payload(
    payload: Dict[str, Any],
) -> Tuple[AnalysisRequest, Dict[str, Any]]:
    """명세서 ⑤용 payload를 내부 AnalysisRequest로 정규화한다.

    허용 입력:
    1. 기존 AnalysisRequest: {"ips": {...}, "scenario": {...}}
    2. 상담 API 응답: {"ips_json": {Goal, Asset, ...}, ...}
    3. flat IPS dict: {Goal, Asset, Return, Risk, Time, Tax, Liquidity, Legal, Unique}
    """
    adapter_warnings: List[str] = []
    request_metadata = extract_request_metadata(payload)
    current_weights_from_portfolio = extract_current_weights_from_portfolio(
        payload,
        adapter_warnings,
    )

    has_analysis_ips = (
        "ips" in payload
        and isinstance(payload.get("ips"), dict)
        and "total_asset" in payload["ips"]
    )
    if has_analysis_ips:
        normalized_payload = dict(payload)
        normalized_ips = dict(normalized_payload["ips"])
        normalized_ips["liquidity_need"] = normalize_liquidity_value(
            normalized_ips.get("liquidity_need")
        )
        if current_weights_from_portfolio is not None:
            normalized_ips["current_weights"] = current_weights_from_portfolio
        scenario_payload = normalized_payload.get("scenario")
        rrttllu_payload = (
            scenario_payload.get("rrttllu")
            if isinstance(scenario_payload, dict)
            else {}
        )
        unique_value = (
            normalized_ips.get("Unique")
            or normalized_ips.get("unique")
            or normalized_ips.get("unique_raw")
        )
        if unique_value is None and isinstance(rrttllu_payload, dict):
            unique_value = rrttllu_payload.get("Unique")
        if unique_value is not None:
            normalized_ips = apply_unique_profile_to_ips_payload(
                normalized_ips,
                unique_value,
                adapter_warnings,
            )
        normalized_payload["ips"] = normalized_ips
        return AnalysisRequest(**normalized_payload), {
            "source": "analysis_request",
            "client_id": request_metadata["client_id"],
            "consultation_id": request_metadata["consultation_id"],
            "warnings": adapter_warnings,
        }

    flat_ips = extract_flat_ips_payload(payload)

    total_asset = parse_amount_krw(flat_ips.get("Asset"))
    if total_asset <= 0:
        raise ValueError("IPS의 Asset 값을 총자산으로 해석할 수 없습니다.")

    investment_horizon = int(max(parse_amount_krw(flat_ips.get("Time")), 1))
    unique_value = flat_ips.get("Unique")
    unique_profile = extract_unique_profile(unique_value)
    unique_need_amount = safe_float(unique_profile.get("liquidity_need_amount"))
    if unique_need_amount <= 0:
        adapter_warnings.append(
            "IPS의 Unique 값에서 별도 필요자금을 숫자로 추출하지 못해 unique_need_amount=0으로 계산했습니다."
        )

    scenario_input = payload.get("scenario") if isinstance(payload.get("scenario"), dict) else {}
    if not scenario_input:
        adapter_warnings.append(
            "scenario 입력이 없어 stress shock은 0으로 두고, 기준 금리는 기본 risk_free_rate를 사용했습니다."
        )

    base_fx_rate = safe_float(
        scenario_input.get("base_fx_rate_krw_per_usd", payload.get("base_fx_rate_krw_per_usd")),
        1.0,
    )
    if base_fx_rate == 1.0 and "base_fx_rate_krw_per_usd" not in scenario_input:
        adapter_warnings.append(
            "base_fx_rate_krw_per_usd가 없어 1.0을 표시용 기본값으로 사용했습니다. 스트레스 테스트 화면에서는 실제 환율 입력을 넘겨야 합니다."
        )

    analysis_payload = {
        "ips": {
            "total_asset": total_asset,
            "unique_need_amount": unique_need_amount,
            "unique_asset": normalize_unique_asset_value(unique_value),
            "unique_items": unique_profile["items"],
            "unique_profile": unique_profile,
            "age": extract_optional_age(payload),
            "client_context": unique_profile.get("client_context", {}),
            "target_after_tax_return": normalize_target_after_tax_return(
                flat_ips.get("Return"),
                percent_input=True,
            ),
            "risk_profile": normalize_risk_profile_value(flat_ips.get("Risk")),
            "investment_horizon_years": investment_horizon,
            "tax_sensitivity": normalize_tax_sensitivity_value(flat_ips.get("Tax")),
            "liquidity_need": normalize_liquidity_value(flat_ips.get("Liquidity")),
            "current_weights": current_weights_from_portfolio,
            "risk_free_rate": safe_float(
                scenario_input.get("risk_free_rate", payload.get("risk_free_rate")),
                DEFAULT_RISK_FREE_RATE,
            ),
            "cash_return": safe_float(
                payload.get("cash_return"),
                DEFAULT_CASH_RETURN,
            ),
            "period": str(payload.get("period", "5y")),
            "benchmark_key": payload.get(
                "benchmark_key",
                payload.get("benchmark", DEFAULT_BENCHMARK_KEY),
            ),
            "num_simulations": int(safe_float(payload.get("num_simulations"), 5000)),
            "expected_return_haircut": safe_float(
                payload.get("expected_return_haircut"),
                0.75,
            ),
            "random_seed": int(
                safe_float(payload.get("random_seed"), DEFAULT_RANDOM_SEED)
            ),
            "overseas_realized_loss": safe_float(
                payload.get("overseas_realized_loss"), 0.0
            ),
            "other_financial_income": safe_float(
                payload.get("other_financial_income"), 0.0
            ),
            "external_financial_income_krw": (
                safe_float(payload.get("external_financial_income_krw"), 0.0)
                if payload.get("external_financial_income_krw") is not None
                else None
            ),
            "external_financial_income_manwon": (
                safe_float(payload.get("external_financial_income_manwon"), 0.0)
                if payload.get("external_financial_income_manwon") is not None
                else None
            ),
            "pension_tax_liability_sufficient": bool(
                payload.get("pension_tax_liability_sufficient", True)
            ),
            "isa_account_exists": unique_profile["isa"]["account_exists"],
            "isa_account_age_years": unique_profile["isa"]["account_age_years"],
            "isa_cumulative_contribution": unique_profile["isa"]["cumulative_contribution"],
            "isa_current_year_contribution": safe_float(
                payload.get("isa_current_year_contribution"), 0.0
            ),
            "irp_account_exists": unique_profile["irp"]["account_exists"],
            "irp_account_age_years": unique_profile["irp"]["account_age_years"],
            "irp_cumulative_contribution": unique_profile["irp"]["cumulative_contribution"],
            "irp_current_year_contribution": (
                unique_profile["irp"]["current_year_contribution"]
                if unique_profile["irp"]["current_year_contribution"] is not None
                else 0.0
            ),
        },
        "scenario": {
            "base_interest_rate": safe_float(
                scenario_input.get(
                    "base_interest_rate",
                    payload.get("base_interest_rate"),
                ),
                DEFAULT_RISK_FREE_RATE,
            ),
            "base_fx_rate_krw_per_usd": base_fx_rate,
            "stress_interest_rate_shock": safe_float(
                scenario_input.get(
                    "stress_interest_rate_shock",
                    payload.get("stress_interest_rate_shock"),
                ),
                0.0,
            ),
            "stress_fx_shock": safe_float(
                scenario_input.get("stress_fx_shock", payload.get("stress_fx_shock")),
                0.0,
            ),
            "rrttllu": payload.get("rrttllu") or payload.get("RRTTLLU") or {},
            "stress_affects_scoring": bool(
                scenario_input.get(
                    "stress_affects_scoring",
                    payload.get("stress_affects_scoring", False),
                )
            ),
        },
    }

    return AnalysisRequest(**analysis_payload), {
        "source": "consultation_ips_adapter",
        "client_id": request_metadata["client_id"],
        "consultation_id": request_metadata["consultation_id"],
        "flat_ips_keys_used": sorted(flat_ips.keys()),
        "warnings": adapter_warnings,
    }


# ============================================================
# 12-2. API 명세서 ⑤ 응답 포맷터
# ============================================================


def rate_to_percent(value: Any, digits: int = 2) -> float:
    return safe_round(safe_float(value) * 100.0, digits)


def build_allocation_payload(portfolio: Dict[str, Any]) -> List[Dict[str, Any]]:
    allocation = []
    for asset, info in portfolio["weights"].items():
        weight = safe_float(info.get("weight"))
        if weight <= 1e-12:
            continue
        allocation.append(
            {
                "asset_class": asset,
                "name": info.get("label", ASSET_NAMES_KR.get(asset, asset)),
                "weight": safe_round(weight * 100.0, 2),
            }
        )
    return allocation


def build_backtest_payload(
    cumulative_returns: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    monthly_points: Dict[str, Dict[str, Any]] = {}
    for point in cumulative_returns:
        date_text = str(point.get("date", ""))
        if not date_text:
            continue
        month_key = date_text[:7]
        value = safe_float(
            point.get("index_value"),
            (1.0 + safe_float(point.get("value"))) * BACKTEST_BASE_INDEX,
        )
        monthly_points[month_key] = {
            "date": month_key,
            "value": safe_round(value, 2),
            "base_index": BACKTEST_BASE_INDEX,
        }

    return list(monthly_points.values())


def build_metrics_payload(
    portfolio: Dict[str, Any],
) -> Dict[str, Any]:
    metrics = portfolio["metrics"]
    return {
        "expected_return": rate_to_percent(metrics["expected_return"]),
        "volatility": rate_to_percent(metrics["volatility"]),
        "sharpe": safe_round(metrics["sharpe_ratio"], 4),
        "sortino": safe_round(metrics["sortino_ratio"], 4),
        "mdd": rate_to_percent(metrics["mdd"]),
        "beta": safe_round(metrics.get("beta"), 4)
        if metrics.get("beta") is not None
        else None,
        "beta_benchmark": metrics.get("beta_benchmark"),
        "selected_benchmark_key": metrics.get(
            "selected_benchmark_key"
        ),
        "benchmark_comparisons": metrics.get(
            "benchmark_comparisons",
            {},
        ),
        "after_tax_return": rate_to_percent(metrics["after_tax_return"]),
    }


def build_metrics_krw_payload(
    portfolio: Dict[str, Any],
    total_asset: float,
) -> Dict[str, Any]:
    metrics = portfolio["metrics"]
    amount_metrics = metrics.get("krw") or portfolio.get("metric_amounts") or {}
    return {
        "basis": amount_metrics.get("basis", "portfolio_total_asset"),
        "total_asset": safe_round(total_asset, 0),
        "expected_return": safe_round(
            amount_metrics.get(
                "expected_return_amount",
                safe_float(metrics["expected_return"]) * total_asset,
            ),
            0,
        ),
        "after_tax_return": safe_round(
            amount_metrics.get(
                "after_tax_return_amount",
                safe_float(metrics["after_tax_return"]) * total_asset,
            ),
            0,
        ),
        "mdd": safe_round(
            amount_metrics.get(
                "mdd_amount",
                safe_float(metrics["mdd"]) * total_asset,
            ),
            0,
        ),
        "volatility_band": safe_round(
            amount_metrics.get(
                "volatility_band_amount",
                safe_float(metrics["volatility"]) * total_asset,
            ),
            0,
        ),
        "note": amount_metrics.get(
            "note",
            "원화 지표는 현재 총자산에 비율 지표를 곱한 값입니다.",
        ),
    }


def build_tax_summary(
    portfolio: Dict[str, Any],
    tax_saving: float,
) -> str:
    tax_breakdown = portfolio["tax_breakdown"]
    comprehensive_status = tax_breakdown["financial_income_comprehensive_tax"]

    if comprehensive_status["is_over_threshold"]:
        return "금융소득 2,000만원 초과 가능성이 있어 종합과세 검토가 필요합니다."

    if tax_saving > 0:
        return "ISA·IRP 배치 효과를 반영해 현재 대비 세후 결과가 개선됩니다."

    return "이자·배당 금융소득은 2,000만원 기준 이하로 간이 추정됩니다."


def build_tax_payload(
    portfolio: Dict[str, Any],
    current_portfolio: Dict[str, Any],
) -> Dict[str, Any]:
    tax_breakdown = portfolio["tax_breakdown"]
    current_tax = current_portfolio["tax_breakdown"]
    overseas_tax = tax_breakdown["overseas_stock_capital_gains_tax"]

    gross_profit = safe_float(tax_breakdown["gross_profit"])
    dividend_interest_tax = -safe_float(tax_breakdown["withholding_tax_estimate"])
    capital_gains_tax = -safe_float(overseas_tax["estimated_tax"])
    total_tax_after_saving = safe_float(tax_breakdown["total_tax_after_saving"])
    after_tax_profit = safe_float(tax_breakdown["after_tax_profit"])

    current_total_tax = safe_float(current_tax["total_tax_after_saving"])
    saved_vs_current = max(current_total_tax - total_tax_after_saving, 0.0)

    return {
        "waterfall": {
            "gross_return": safe_round(gross_profit, 0),
            "dividend_interest_tax": safe_round(dividend_interest_tax, 0),
            "capital_gains_tax": safe_round(capital_gains_tax, 0),
            "transaction_cost": 0.0,
            "fx_cost": 0.0,
            "after_tax": safe_round(after_tax_profit, 0),
        },
        "saved_vs_current": safe_round(saved_vs_current, 0),
        "summary": build_tax_summary(portfolio, saved_vs_current),
        "calculation_notes": [
            "transaction_cost와 fx_cost는 현재 계산 로직에 별도 모델이 없어 0으로 표시합니다.",
            "세금 계산은 하드코딩 규칙표 기반 간이 추정입니다.",
        ],
    }


def build_spec_portfolio_item(
    kind: str,
    rank: Optional[int],
    label: str,
    badge: Optional[str],
    portfolio: Dict[str, Any],
    current_portfolio: Dict[str, Any],
    total_asset: float,
) -> Dict[str, Any]:
    metrics_krw = build_metrics_krw_payload(portfolio, total_asset)
    current_metrics_krw = build_metrics_krw_payload(current_portfolio, total_asset)
    vs_current_krw = {
        "after_tax_return_delta": safe_round(
            safe_float(metrics_krw.get("after_tax_return"))
            - safe_float(current_metrics_krw.get("after_tax_return")),
            0,
        ),
        "mdd_loss_improvement": safe_round(
            safe_float(metrics_krw.get("mdd"))
            - safe_float(current_metrics_krw.get("mdd")),
            0,
        ),
        "basis": "portfolio_amount_minus_current_amount",
    }
    item = {
        "kind": kind,
        "rank": rank,
        "label": label,
        "badge": badge,
        "allocation": build_allocation_payload(portfolio),
        "metrics": build_metrics_payload(portfolio),
        "metrics_krw": metrics_krw,
        "vs_current_krw": vs_current_krw,
        "backtest": build_backtest_payload(portfolio["cumulative_returns"]),
        "benchmark": {
            "metadata": portfolio.get(
                "benchmark_backtest",
                {},
            ).get("metadata", {}),
            "backtest": build_backtest_payload(
                portfolio.get(
                    "benchmark_backtest",
                    {},
                ).get("series", [])
            ),
        },
        "benchmarks": {
            key: {
                "metadata": benchmark.get("metadata", {}),
                "backtest": build_backtest_payload(
                    benchmark.get("series", [])
                ),
            }
            for key, benchmark in portfolio.get(
                "benchmark_backtests",
                {},
            ).items()
        },
        "tax": build_tax_payload(portfolio, current_portfolio),
    }
    return item


def build_portfolio_calculate_response(
    full_response: Dict[str, Any],
    adapter_info: Dict[str, Any],
) -> Dict[str, Any]:
    portfolios = full_response["portfolios"]
    current = portfolios["current"]
    total_asset = safe_float(full_response["input_summary"]["total_asset"])
    calculation_session_id = full_response["session_id"]
    consultation_id = adapter_info.get("consultation_id") or calculation_session_id

    warnings = list(adapter_info.get("warnings", []))
    if not adapter_info.get("consultation_id"):
        warnings.append(
            "consultation_id가 없어 계산 session_id를 consultation_id 필드에 넣었습니다. "
            "실제 상담 ID가 필요하면 ④ 응답의 consultation_id를 함께 전달해야 합니다."
        )

    return {
        "client_id": adapter_info.get("client_id"),
        "consultation_id": consultation_id,
        "calculation_session_id": calculation_session_id,
        "as_of": datetime.now(KST).isoformat(timespec="seconds"),
        "risk_profile": full_response["input_summary"]["risk_profile"],
        "risk_profile_label": RISK_LEVEL_NAME[
            full_response["input_summary"]["client_risk_level"]
        ],
        "portfolios": [
            build_spec_portfolio_item(
                kind="current",
                rank=None,
                label="현재 포트폴리오",
                badge=None,
                portfolio=current,
                current_portfolio=current,
                total_asset=total_asset,
            ),
            build_spec_portfolio_item(
                kind="A",
                rank=1,
                label="포트폴리오 A",
                badge="베스트",
                portfolio=portfolios["recommended_1"],
                current_portfolio=current,
                total_asset=total_asset,
            ),
            build_spec_portfolio_item(
                kind="B",
                rank=2,
                label="포트폴리오 B",
                badge="추천",
                portfolio=portfolios["recommended_2"],
                current_portfolio=current,
                total_asset=total_asset,
            ),
        ],
        "search_summary": full_response["search_summary"],
        "scenario_summary": full_response["scenario_summary"],
        "data_snapshot": {
            **full_response["input_summary"].get("data_snapshot", {}),
            "backtest_data_snapshot": full_response["input_summary"].get(
                "backtest_data_snapshot", {}
            ),
        },
        "input_adapter": {
            **adapter_info,
            "warnings": warnings,
        },
        "methodology": full_response["methodology"],
        "notes": full_response["notes"],
    }



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


@router.post("/portfolio/calculate", response_model=PortfolioCalculateResponse)
def portfolio_calculate(request: Dict[str, Any]):
    """API 명세서 ⑤ 포트폴리오 계산."""
    try:
        normalized_request, adapter_info = normalize_analysis_request_payload(request)
        full = run_full_analysis(normalized_request)
        return build_portfolio_calculate_response(full, adapter_info)
    except Exception as e:
        raise public_http_exception(e)


@router.post("/portfolio/stress-test", response_model=PortfolioStressTestResponse)
def portfolio_stress_test(request: Dict[str, Any]):
    """API 명세서 ⑥ 스트레스 테스트."""
    try:
        normalized_request, adapter_info = normalize_analysis_request_payload(request)
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
        asset_shocks = derive_asset_shocks_from_macro(assets, req)
        stressed = calculate_metrics(
            weights,
            analysis_returns,
            expected_returns,
            req,
            include_benchmark_metrics=True,
            shocks=asset_shocks,
        )

        return {
            "as_of": datetime.now(KST).isoformat(timespec="seconds"),
            "stress_interest_rate_shock": req.stress_interest_rate_shock,
            "stress_fx_shock": req.stress_fx_shock,
            "asset_shocks": {k: safe_round(v, 6) for k, v in asset_shocks.items()},
            "base": base,
            "stressed": stressed,
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

