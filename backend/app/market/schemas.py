"""market 모듈 응답 스키마 — frontend/lib/types.ts 와 1:1 대응."""
from typing import Literal

from pydantic import BaseModel

AssetClass = Literal[
    "domestic_equity", "us_equity", "bond", "gold", "reit", "commodity", "dividend"
]


class IndicatorData(BaseModel):
    price: float
    change: float
    changePct: float
    isStatic: bool | None = None


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


class AfterTaxReturnResult(BaseModel):
    afterTaxReturn: float
    taxAmount: float
    isComprehensive: bool
