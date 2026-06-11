"""시장 데이터·포트폴리오 지표 API — frontend의 app/api/* 라우트 + lib 계산 로직 이식."""
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.market import yfinance_client
from app.market.financial_calc import apply_stress_scenario, calc_portfolio_metrics
from app.market.portfolios import (
    ALL_TICKERS,
    DEFAULT_PORTFOLIOS,
    HISTORICAL_CRISES,
    STRESS_SCENARIOS,
    calc_crisis_pnl,
    combine_tuner_shocks,
)
from app.market.schemas import (
    HistoricalCrisis,
    IndicatorData,
    MacroIndicators,
    MarketDataPoint,
    PortfolioProposal,
    StressedPortfolio,
    StressScenario,
)

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


async def _fetch_all_market_data() -> dict[str, MarketDataPoint]:
    market_data: dict[str, MarketDataPoint] = {}
    # 순차 처리로 rate limit 회피 (캐시 레이어 포함)
    for ticker in ALL_TICKERS:
        market_data[ticker] = await yfinance_client.fetch_historical(ticker)
    return market_data


@router.get("/portfolios", response_model=list[PortfolioProposal])
async def get_portfolios() -> list[PortfolioProposal]:
    market_data = await _fetch_all_market_data()

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


@router.get("/historical-crises", response_model=list[HistoricalCrisis])
async def get_historical_crises() -> list[HistoricalCrisis]:
    """과거 주요 경제 위기(2008·2020·2022) 재현 시 포트폴리오별 예상 손실률(P&L).

    위기 기간의 자산군별 실제 실현 수익률(사전 정의 상수, 원화 환산 기준)을
    현재 비중에 적용한다. 시장 데이터 조회가 필요 없어 항상 즉시 응답한다.
    """
    crises: list[HistoricalCrisis] = []
    for crisis in HISTORICAL_CRISES:
        results = {
            portfolio.id: calc_crisis_pnl(crisis, portfolio.allocations)
            for portfolio in DEFAULT_PORTFOLIOS
        }
        crises.append(crisis.model_copy(update={"results": results}))

    return crises


@router.get("/stressed-portfolios", response_model=list[StressedPortfolio])
async def get_stressed_portfolios(
    base_rate_delta_bp: float = Query(
        0.0, ge=-600, le=600, description="기준금리 변화량 (bp, 슬라이더 - 현재값)"
    ),
    krw_usd_delta: float = Query(
        0.0, ge=-1000, le=1000, description="원/달러 변화량 (원, 슬라이더 - 현재값)"
    ),
) -> list[StressedPortfolio]:
    """스트레스 조율기(슬라이더) 입력을 받아 포트폴리오 3종의 전체 지표를
    충격 주입 후 재계산한다 — 기대수익률·변동성·샤프·소르티노·MDD 모두 변한다.

    충격은 기준 시나리오(+100bp, +200원) 계수의 선형 스케일링이며, 시계열에
    드리프트+변동성 확대로 주입된다 (financial_calc.calc_portfolio_metrics 참고).
    """
    market_data = await _fetch_all_market_data()
    shocks = combine_tuner_shocks(base_rate_delta_bp, krw_usd_delta)

    results: list[StressedPortfolio] = []
    for portfolio in DEFAULT_PORTFOLIOS:
        base = calc_portfolio_metrics(portfolio.allocations, market_data)
        stressed = calc_portfolio_metrics(portfolio.allocations, market_data, shocks=shocks)
        results.append(
            StressedPortfolio(
                id=portfolio.id, nameKr=portfolio.nameKr, base=base, stressed=stressed
            )
        )

    return results
