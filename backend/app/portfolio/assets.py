# ruff: noqa: E501
"""확정 자산군 정의·분류(§1). portfolio_logic.py 모듈 분할 1단계로 분리.

순수 데이터만 담는다. 이자·배당 수익률 가정은 constants.DEFAULT_CASH_RETURN 에 의존.
"""

from .constants import DEFAULT_CASH_RETURN


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

# ============================================================
# 대시보드 표시용 8개 자산군
# ============================================================
# 내부 추천·세금·위험 계산은 위 12개 자산을 그대로 사용한다.
# 아래 그룹은 최종 API 응답의 도넛 차트와 상관관계 히트맵에만 사용한다.
#
# 그룹 키는 프론트와 합의할 안정적인 API 키다.
# dict 삽입 순서가 곧 차트/히트맵 표시 순서다.
DASHBOARD_ASSET_GROUPS = {
    "domestic_equity": {
        "label": "국내주식",
        "assets": ("domestic_equity",),
    },
    "overseas_equity": {
        "label": "해외주식",
        "assets": (
            "overseas_blue_chip",
            "overseas_growth",
            "overseas_dividend",
        ),
    },
    "bond": {
        "label": "채권",
        "assets": (
            "general_bond",
            "low_coupon_bond",
            "separate_tax_bond",
        ),
    },
    "gold": {
        "label": "금",
        "assets": ("gold",),
    },
    "reit": {
        "label": "리츠",
        "assets": ("reit",),
    },
    "commodity": {
        "label": "원자재",
        "assets": ("commodity",),
    },
    "dollar": {
        "label": "달러",
        "assets": ("dollar",),
    },
    "cash": {
        "label": "현금",
        "assets": ("cash",),
    },
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
