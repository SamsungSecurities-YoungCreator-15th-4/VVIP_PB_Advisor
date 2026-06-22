"""시장 데이터 API — yfinance 실시간 시세/환율 조회.

상단 매크로 지표 티커와 차트용 원시 시세만 제공한다. 포트폴리오 지표·스트레스·세금
계산은 계산 엔진(portfolio_logic, PR #30)이 담당하므로 이 모듈은 데이터 공급만 한다.
"""
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.market import yfinance_client
from app.market.schemas import IndicatorData, MacroIndicators, MarketDataPoint

router = APIRouter(prefix="/api", tags=["market"])

# ── 정적 지표 (의도된 하드코딩, 미국 기준) ──────────────────────────────────
# 기준금리·CPI는 발표(FOMC·BLS) 시에만 바뀌므로 실시간 조회 없이 수동 갱신한다.
#   - baseRate: 미국 연준 기준금리(Fed Funds Rate). FOMC 결정 시 아래 값 갱신.
#   - cpi: 미국 소비자물가지수 전년동월비(%). BLS 발표 시 갱신.
# 갱신 시 기준일 주석도 함께 수정할 것.
STATIC_INDICATORS: dict[str, IndicatorData] = {
    "baseRate": IndicatorData(price=3.75, change=0, changePct=0, isStatic=True),  # 2026-06 기준
    "cpi": IndicatorData(price=4.2, change=0, changePct=0, isStatic=True),  # 2026-06 기준
}

# 최근 확인된 실제값 (2026-06-06 금요일 종가 기준) — 실시간 조회 실패 시 빈 화면
# 방지용. isFallback=True로 내려보내 프론트가 "지연 시세"로 표시하게 한다.
MACRO_FALLBACKS: dict[str, IndicatorData] = {
    "treasuryYield": IndicatorData(price=4.536, change=0.061, changePct=1.36, isFallback=True),
    "krwUsd": IndicatorData(price=1545.29, change=-9.70, changePct=-0.62, isFallback=True),
    "kospi": IndicatorData(price=8160.59, change=-24.70, changePct=-0.30, isFallback=True),
    "sp500": IndicatorData(price=7383.74, change=-196.32, changePct=-2.59, isFallback=True),
}


@router.get("/macro-indicators", response_model=MacroIndicators)
async def get_macro_indicators(
    force: bool = Query(
        False, description="true면 5분 캐시를 무시하고 강제 재조회 (새로고침 버튼용)"
    ),
) -> MacroIndicators:
    quotes, forex_result = await asyncio.gather(
        yfinance_client.fetch_quotes(["^KS11", "^GSPC", "^TNX"], force=force),
        yfinance_client.fetch_usd_krw(force=force),
    )

    def pick(symbol: str, key: str) -> IndicatorData:
        live = quotes.get(symbol)
        if live and live.price > 0:
            return live
        return MACRO_FALLBACKS[key]

    krw_usd = forex_result if forex_result.price > 0 else MACRO_FALLBACKS["krwUsd"]

    return MacroIndicators(
        baseRate=STATIC_INDICATORS["baseRate"],
        treasuryYield=pick("^TNX", "treasuryYield"),
        krwUsd=krw_usd,
        cpi=STATIC_INDICATORS["cpi"],
        kospi=pick("^KS11", "kospi"),
        sp500=pick("^GSPC", "sp500"),
        fetchedAt=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/market-data")
async def get_market_data(
    tickers: str = Query(..., description="콤마로 구분된 티커 목록"),
) -> dict[str, MarketDataPoint]:
    ticker_list = [t for t in tickers.split(",") if t]

    result: dict[str, MarketDataPoint] = {}
    # 순차 처리로 rate limit 회피 (캐시 레이어 포함)
    for ticker in ticker_list:
        result[ticker] = await yfinance_client.fetch_historical(ticker)

    return result
