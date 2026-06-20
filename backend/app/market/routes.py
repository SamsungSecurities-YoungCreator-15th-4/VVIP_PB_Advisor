"""시장 데이터·포트폴리오 지표 API — frontend의 app/api/* 라우트 + lib 계산 로직 이식."""
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.market import yfinance_client
from app.market.financial_calc import (
    DEFAULT_MARGINAL_INCOME_TAX_RATE,
    apply_stress_scenario,
    calc_after_tax_return,
    calc_financial_income,
    calc_portfolio_metrics,
)
from app.market.portfolios import (
    ALL_TICKERS,
    DEFAULT_PORTFOLIOS,
    HISTORICAL_CRISES,
    STRESS_SCENARIOS,
    calc_crisis_pnl,
    combine_tuner_shocks,
)
from app.market.schemas import (
    AccountSlot,
    HistoricalCrisis,
    IndicatorData,
    MacroIndicators,
    MarketDataPoint,
    PortfolioProposal,
    StressedPortfolio,
    StressScenario,
    TaxAdviceCard,
)
from app.market.tax_optimizer import calc_account_allocation, calc_tax_advice

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
    total_assets: float = Query(
        50.0, gt=0, le=100000, description="고객 운용자산 (억 원) — 세후수익률 계산용"
    ),
    other_financial_income: float = Query(
        0.0, ge=0, le=100000, description="고객의 다른 금융소득 (억 원) — 종합과세 합산용"
    ),
    isa_used_manwon: float = Query(
        0.0, ge=0, le=10000, description="고객 ISA 당해 기납입액 (만원) — 잔여 한도 계산용"
    ),
    pension_used_manwon: float = Query(
        0.0, ge=0, le=10000, description="고객 연금저축+IRP 당해 납입액 (만원) — 세액공제 활용도"
    ),
    realized_loss_manwon: float = Query(
        0.0, ge=0, le=1000000, description="확정 가능 평가손실 (만원) — Tax-loss harvesting용"
    ),
    marginal_tax_rate: float = Query(
        DEFAULT_MARGINAL_INCOME_TAX_RATE,
        ge=0,
        le=0.495,
        description="고객 한계세율(지방세 포함, 0~0.495) — 종합과세 추가과세·분리과세 비교용",
    ),
    age: int | None = Query(
        None, ge=0, le=120, description="고객 나이 — 연금 55세 수령요건 게이팅용"
    ),
    horizon_years: float | None = Query(
        None, ge=0, le=100, description="투자기간(년) — ISA 3년·연금 lock-up 게이팅용"
    ),
    near_term_need_manwon: float = Query(
        0.0, ge=0, le=100000000, description="단기 필요자금(만원) — 묶이는 금액에서 제외"
    ),
    near_term_need_years: float | None = Query(
        None, ge=0, le=100, description="단기 필요자금 필요 시점(년)"
    ),
    isa_opened: bool = Query(
        True, description="ISA 기존 개설 여부 — False면 신규 개설 가능 판정 적용"
    ),
) -> list[StressedPortfolio]:
    """스트레스 조율기(슬라이더) 입력을 받아 포트폴리오 3종의 전체 지표를
    충격 주입 후 재계산한다 — 기대수익률·변동성·샤프·소르티노·MDD·세후수익률 모두 변한다.

    충격은 기준 시나리오(+100bp, +200원) 계수의 선형 스케일링이며, 시계열에
    드리프트+변동성 확대로 주입된다 (financial_calc.calc_portfolio_metrics 참고).
    세후수익률은 총자산 규모에 따라 종합과세 구간이 달라져 total_assets가 필요하다.
    """
    market_data = await _fetch_all_market_data()
    shocks = combine_tuner_shocks(base_rate_delta_bp, krw_usd_delta)

    def with_after_tax(metrics, allocations):
        after_tax, _, _ = calc_after_tax_return(
            metrics.expectedReturn, allocations, total_assets, other_financial_income
        )
        return metrics.model_copy(update={"afterTaxReturn": after_tax})

    # 계좌 배치 활용도는 고객 입력(기납입액)에만 의존 — 포트폴리오와 무관하게 동일.
    account_allocation = [
        AccountSlot(**slot)
        for slot in calc_account_allocation(isa_used_manwon, pension_used_manwon)
    ]

    results: list[StressedPortfolio] = []
    for portfolio in DEFAULT_PORTFOLIOS:
        base = calc_portfolio_metrics(portfolio.allocations, market_data)
        stressed = calc_portfolio_metrics(portfolio.allocations, market_data, shocks=shocks)
        # 절세 제안은 해당 포트폴리오의 보유 구성에 따라 절감액이 달라진다.
        tax_advice = [
            TaxAdviceCard(**card)
            for card in calc_tax_advice(
                portfolio.allocations,
                base.expectedReturn,
                total_assets,
                isa_used_manwon,
                realized_loss_manwon,
                other_financial_income=other_financial_income,
                marginal_income_tax_rate=marginal_tax_rate,
                pension_used_manwon=pension_used_manwon,
                age=age,
                horizon_years=horizon_years,
                near_term_need_manwon=near_term_need_manwon,
                near_term_need_years=near_term_need_years,
                isa_opened=isa_opened,
            )
        ]
        results.append(
            StressedPortfolio(
                id=portfolio.id,
                nameKr=portfolio.nameKr,
                base=with_after_tax(base, portfolio.allocations),
                stressed=with_after_tax(stressed, portfolio.allocations),
                dividendIncome=calc_financial_income(
                    base.expectedReturn, portfolio.allocations, total_assets
                ),
                accountAllocation=account_allocation,
                taxAdvice=tax_advice,
            )
        )

    return results
