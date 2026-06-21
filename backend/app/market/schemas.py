"""market 모듈 응답 스키마 — yfinance 실시간 시세/시장 데이터.

포트폴리오 지표·스트레스·세금 계산은 계산 엔진(portfolio_logic, PR #30)이 담당하며,
이 모듈은 yfinance 데이터 공급만 한다.
"""
from pydantic import BaseModel


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
