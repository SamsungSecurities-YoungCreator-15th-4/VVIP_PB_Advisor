"""market 모듈 응답 스키마 — frontend/lib/types.ts 와 1:1 대응."""
from typing import Literal

from pydantic import BaseModel

# 자산 분류 11종 (2026-06-10 회의 확정). 절세 seed.sql(PR #27) 키와 명칭 일치.
#
# 주식 4:
#   domestic_equity    국내 주식 (KOSPI200)
#   overseas_dividend  해외 고배당주 (← dividend 개명)
#   overseas_blue_chip 해외 우량주 — S&P500 (신규)
#   overseas_growth    해외 성장주 — 나스닥100 (← us_equity 개명)
# 채권 3 — 과세 구조 기준 분류:
#   general_bond       일반채 — 표면이자 전액 이자소득 과세(종합과세 합산) (← bond 분화)
#   low_coupon_bond    저쿠폰채 — 표면금리만 과세, 매매차익 비과세(개인) → 절세형
#   separate_tax_bond  분리과세채 — 만기 10년 이상 장기채, 분리과세(33%) 신청 가능
# 대체자산 4:
#   reit / dollar(신규) / gold / commodity
AssetClass = Literal[
    "domestic_equity", "overseas_dividend", "overseas_blue_chip", "overseas_growth",
    "general_bond", "separate_tax_bond", "low_coupon_bond",
    "reit", "dollar", "gold", "commodity",
]


class IndicatorData(BaseModel):
    price: float
    change: float
    changePct: float
    # 정적 지표 (기준금리·CPI 등 발표 시에만 수동 갱신 — 의도된 하드코딩)
    isStatic: bool | None = None
    # 실시간 조회 실패로 마지막 확인값(종가/캐시)을 반환한 경우 True.
    # 프론트는 이 플래그로 "지연 시세"임을 표시해 라이브로 오인하지 않게 한다.
    isFallback: bool | None = None


# 시세/환율 단건 조회 결과 (IndicatorData와 동일한 형태)
QuoteResult = IndicatorData
ForexResult = IndicatorData


class MacroIndicators(BaseModel):
    baseRate: IndicatorData
    treasuryYield: IndicatorData
    krwUsd: IndicatorData
    cpi: IndicatorData
    kospi: IndicatorData
    sp500: IndicatorData
    fetchedAt: str


class MarketDataPoint(BaseModel):
    ticker: str
    prices: list[float]
    dates: list[str]
    annualReturn: float
    annualVolatility: float


class AssetAllocation(BaseModel):
    ticker: str
    name: str
    nameKr: str
    weight: float
    assetClass: AssetClass
    color: str


class BacktestPoint(BaseModel):
    date: str
    value: float


class PortfolioMetrics(BaseModel):
    expectedReturn: float
    volatility: float
    sharpeRatio: float
    # 소르티노는 실측 주간수익률의 하방편차가 필요하므로, 공통 거래일이
    # 부족하거나 하방편차가 0이면 None(N/A) — 가짜 값으로 채우지 않는다.
    sortinoRatio: float | None
    # 공통 거래일이 부족해 실측 백테스트를 만들 수 없는 경우 None(N/A)
    # — 가짜 시계열로 대체하지 않는다.
    maxDrawdown: float | None
    # 세후 기대수익률(소수, 예: 0.05 = 5%). 총자산(total_assets)에 따라 달라지므로
    # 라우트에서 calc_after_tax_return으로 채워 넣는다. 미계산 시 None.
    afterTaxReturn: float | None = None
    backtestData: list[BacktestPoint]


class PortfolioProposal(BaseModel):
    id: Literal["current", "proposalA", "proposalB"]
    name: str
    nameKr: str
    description: str
    theme: str
    allocations: list[AssetAllocation]
    metrics: PortfolioMetrics | None = None


class StressScenario(BaseModel):
    id: str
    name: str
    nameKr: str
    description: str
    icon: str
    shocks: dict[str, float]
    results: dict[str, float]


class HistoricalCrisis(BaseModel):
    """과거 주요 경제 위기 재현 시나리오 — 위기 기간 실제 수익률 기반 예상 P&L."""

    id: str
    name: str
    nameKr: str
    period: str  # 예: "2008-09 ~ 2009-03"
    description: str
    icon: str
    # 자산군 → 위기 기간 실현 수익률 (원화 환산 기준 점추정치)
    assetReturns: dict[str, float]
    # 포트폴리오 id → 예상 P&L (기간 수익률, 음수 = 손실)
    results: dict[str, float]


class AccountSlot(BaseModel):
    """절세 계좌 배치 활용도 한 칸 — 법정 한도 대비 고객 기납입액(만원).
    used/limit가 None이면 한도 개념이 없는 계좌(예: 일반계좌)."""

    key: Literal["isa", "pension", "general"]
    usedManwon: int | None = None
    limitManwon: int | None = None


class TaxAdviceCard(BaseModel):
    """절세 제안 한 건 — 실제 세법 수식 + 적합성(lock-up) 게이팅 결과.
    applicable=False면 합산 제외. ineligibleReason이 있으면 제도상 부적합(사유 표시),
    없으면 절감 효과 없음/한도 소진(비노출 권장)."""

    key: Literal[
        "isa",
        "pension_credit",
        "separate_bond",
        "low_tax_dividend",
        "overseas_exemption",
        "tax_loss",
    ]
    savingManwon: int
    applicable: bool
    transferableManwon: int = 0  # ISA·연금 등 이전/납입 가능 금액(만원)
    ineligibleReason: str | None = None  # 제도상 부적합 사유(있으면 사유와 함께 표시)


class StressedPortfolio(BaseModel):
    """스트레스 조율기(슬라이더) 적용 결과 — 기준/충격 적용 후 전체 지표 쌍."""

    id: Literal["current", "proposalA", "proposalB"]
    nameKr: str
    base: PortfolioMetrics
    stressed: PortfolioMetrics
    # 포트폴리오의 연간 이자·배당성 금융소득(억 원) — 종합과세 기준선(2천만) 점검용.
    # 기준(base) 기대수익률 기반. 고객의 다른 금융소득과 합산해 초과 여부를 판정한다.
    dividendIncome: float = 0.0
    # 절세 계좌 배치 활용도(법정 한도 대비 기납입액) — tax_optimizer로 채운다.
    accountAllocation: list[AccountSlot] = []
    # 절세 제안 4종의 실제 절감액 — tax_optimizer로 채운다.
    taxAdvice: list[TaxAdviceCard] = []


class AfterTaxReturnResult(BaseModel):
    afterTaxReturn: float
    taxAmount: float
    isComprehensive: bool
