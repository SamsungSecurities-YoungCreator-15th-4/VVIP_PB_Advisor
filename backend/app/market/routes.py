"""시장 데이터·포트폴리오 지표 API — frontend의 app/api/* 라우트 + lib 계산 로직 이식."""
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.market import yfinance_client
from app.market.financial_calc import apply_stress_scenario, calc_portfolio_metrics
from app.market.portfolios import ALL_TICKERS, DEFAULT_PORTFOLIOS, STRESS_SCENARIOS
from app.market.schemas import (
    IndicatorData,
    MacroIndicators,
    MarketDataPoint,
    PortfolioProposal,
    StressScenario,
)

router = APIRouter(prefix="/api", tags=["market"])

# 최근 확인된 실제값 (2026-06-06 금요일 종가 기준) — API 실패 시 빈 화면 방지용
MACRO_FALLBACKS: dict[str, IndicatorData] = {
    "baseRate": IndicatorData(price=2.75, change=0, changePct=0, isStatic=True),
    "treasuryYield": IndicatorData(price=4.536, change=0.061, changePct=1.36),
    "krwUsd": IndicatorData(price=1545.29, change=-9.70, changePct=-0.62),
    "cpi": IndicatorData(price=2.6, change=0, changePct=0, isStatic=True),
    "kospi": IndicatorData(price=8160.59, change=-24.70, changePct=-0.30),
    "sp500": IndicatorData(price=7383.74, change=-196.32, changePct=-2.59),
}


@router.get("/macro-indicators", response_model=MacroIndicators)
async def get_macro_indicators() -> MacroIndicators:
    quotes, forex_result = await asyncio.gather(
        yfinance_client.fetch_quotes(["^KS11", "^GSPC", "^TNX"]),
        yfinance_client.fetch_usd_krw(),
    )

    def pick(symbol: str, key: str) -> IndicatorData:
        live = quotes.get(symbol)
        if live and live.price > 0:
            return live
        return MACRO_FALLBACKS[key]

    krw_usd = forex_result if forex_result.price > 0 else MACRO_FALLBACKS["krwUsd"]

    return MacroIndicators(
        baseRate=MACRO_FALLBACKS["baseRate"],
        treasuryYield=pick("^TNX", "treasuryYield"),
        krwUsd=krw_usd,
        cpi=MACRO_FALLBACKS["cpi"],
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


@router.get("/portfolios", response_model=list[PortfolioProposal])
async def get_portfolios() -> list[PortfolioProposal]:
    market_data: dict[str, MarketDataPoint] = {}
    for ticker in ALL_TICKERS:
        market_data[ticker] = await yfinance_client.fetch_historical(ticker)

    portfolios: list[PortfolioProposal] = []
    for portfolio in DEFAULT_PORTFOLIOS:
        metrics = calc_portfolio_metrics(portfolio.allocations, market_data)
        portfolios.append(portfolio.model_copy(update={"metrics": metrics}))

    return portfolios


@router.get("/stress-scenarios", response_model=list[StressScenario])
async def get_stress_scenarios() -> list[StressScenario]:
    portfolios = await get_portfolios()

    scenarios: list[StressScenario] = []
    for scenario in STRESS_SCENARIOS:
        results: dict[str, float] = {}
        for portfolio in portfolios:
            if portfolio.metrics is None:
                continue
            stressed_return = apply_stress_scenario(
                portfolio.metrics.expectedReturn, portfolio.allocations, scenario.shocks
            )
            # 시나리오 발생 시 기대수익률의 변화량(p.p.)
            results[portfolio.id] = stressed_return - portfolio.metrics.expectedReturn

        scenarios.append(scenario.model_copy(update={"results": results}))

    return scenarios
