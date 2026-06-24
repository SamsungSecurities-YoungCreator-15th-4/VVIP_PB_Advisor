# ruff: noqa: E501
"""포트폴리오 계산 엔진 상수·기준표(§0 기본설정 + §2 기준표/리스크 기준).

portfolio_logic.py 모듈 분할 1단계로 분리. 순수 데이터/설정만 담는다(behavior 없음).
"""

import threading
from pathlib import Path
from typing import Any, Dict, Literal


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
