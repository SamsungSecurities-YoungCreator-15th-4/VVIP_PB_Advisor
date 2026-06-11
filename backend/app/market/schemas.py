"""market 모듈 응답 스키마 — frontend/lib/types.ts 와 1:1 대응."""
from typing import Literal

from pydantic import BaseModel

# 채권은 과세 구조에 따라 3분류한다 (2026-06 회의 확정):
#   bond_regular      일반채 — 표면이자 전액 이자소득 과세(종합과세 합산)
#   bond_low_coupon   저쿠폰채 — 표면금리만 과세, 매매차익 비과세(개인) → 절세형
#   bond_separate_tax 분리과세채 — 만기 10년 이상 장기채, 분리과세(33%) 신청 가능
# "bond"는 레거시 호환용으로만 유지한다.
AssetClass = Literal[
    "domestic_equity", "us_equity", "bond",
    "bond_regular", "bond_low_coupon", "bond_separate_tax",
    "gold", "reit", "commodity", "dividend",
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


class StressedPortfolio(BaseModel):
    """스트레스 조율기(슬라이더) 적용 결과 — 기준/충격 적용 후 전체 지표 쌍."""

    id: Literal["current", "proposalA", "proposalB"]
    nameKr: str
    base: PortfolioMetrics
    stressed: PortfolioMetrics


class AfterTaxReturnResult(BaseModel):
    afterTaxReturn: float
    taxAmount: float
    isComprehensive: bool
