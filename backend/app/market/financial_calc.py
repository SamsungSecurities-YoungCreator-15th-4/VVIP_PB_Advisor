"""포트폴리오 정량 지표 계산 — frontend/lib/financial-calc.ts 이식.

세금 계산 근거: 소득세법 제14조(금융소득종합과세), 소득세법 제55조(종합소득세 누진세율,
2026년 기준 지방소득세 10% 포함), 소득세법 제129조(이자·배당소득 원천징수세율 15.4%).

# TODO(채권 3분할): 회의에서 "일반채/저쿠폰채/분리과세채" 3분류 및 종합과세 산입 여부가
# 논의 중이나 아직 확정되지 않음 (PR #19 review, kookguk/Choi-Jung-Hyeon 코멘트 참고).
# 기준이 확정되면 AssetClass에 하위 타입을 추가하고 calc_after_tax_return의
# `assetClass in ("dividend", "bond")` 분기를 분류별로 세분화해야 한다.
"""
from app.market.schemas import (
    AssetAllocation,
    BacktestPoint,
    MarketDataPoint,
    PortfolioMetrics,
)

RISK_FREE_RATE = 0.035  # 3.5% 국고채

MIN_COMMON_DATES = 10  # 공통 거래일이 이보다 적으면 실데이터 기반 계산을 포기하고 fallback 사용

# 자산군 간 대표 상관계수 — 실시간 시세에서 공통 거래일이 부족해 실제 공분산을
# 계산할 수 없을 때만 사용하는 fallback 값이다.
# 출처: BlackRock Capital Market Assumptions, J.P. Morgan Long-Term Capital Market
# Assumptions, Ibbotson SBBI 등에서 통상 보고되는 자산군별 장기 상관관계 범위를
# 참고한 대표값(point estimate)이며, 실측 상관행렬이 아니다.
# 한계: (1) 비선형성·꼬리 위험(tail dependence) 미반영, (2) 국면(레짐)에 따라
# 실제 상관관계는 위 범위를 크게 벗어날 수 있음(예: 위기 시 상관관계 수렴),
# (3) 한국 시장 고유 특성(환헤지 여부, 거래시간 차이) 미반영.
_FALLBACK_CORRELATIONS: dict[str, float] = {
    "bond-domestic_equity": 0.1,
    "bond-us_equity": -0.05,
    "bond-gold": 0.1,
    "bond-reit": 0.2,
    "bond-commodity": 0.0,
    "bond-dividend": 0.15,
    "domestic_equity-us_equity": 0.65,
    "domestic_equity-gold": -0.05,
    "domestic_equity-reit": 0.5,
    "domestic_equity-commodity": 0.3,
    "domestic_equity-dividend": 0.6,
    "us_equity-gold": -0.1,
    "us_equity-reit": 0.55,
    "us_equity-commodity": 0.25,
    "us_equity-dividend": 0.75,
    "gold-reit": 0.1,
    "gold-commodity": 0.5,
    "gold-dividend": -0.05,
    "reit-commodity": 0.3,
    "reit-dividend": 0.5,
    "commodity-dividend": 0.2,
}


def _get_fallback_correlation(a: str, b: str) -> float:
    if a == b:
        return 1.0
    key = "-".join(sorted((a, b)))
    return _FALLBACK_CORRELATIONS.get(key, 0.3)


def _aligned_weekly_returns(
    allocations: list[AssetAllocation],
    market_data: dict[str, MarketDataPoint],
) -> tuple[list[str], dict[str, list[float]]] | None:
    """공통 거래일(교집합) 기준으로 정렬한 자산별 주간 수익률을 반환한다.

    한·미 등 시장별 휴장일이 달라 인덱스로 단순 매칭하면 서로 다른 날짜의
    수익률이 결합될 수 있어, 모든 자산에 데이터가 있는 날짜만 사용한다.
    데이터가 부족하면 None을 반환한다.
    """
    price_maps: dict[str, dict[str, float]] = {}
    for alloc in allocations:
        data = market_data.get(alloc.ticker)
        if not data or len(data.dates) < 2:
            return None
        price_maps[alloc.ticker] = dict(zip(data.dates, data.prices))

    date_sets = [set(m.keys()) for m in price_maps.values()]
    common_dates = sorted(set.intersection(*date_sets))
    if len(common_dates) < MIN_COMMON_DATES:
        return None

    returns: dict[str, list[float]] = {}
    for ticker, price_map in price_maps.items():
        series = [price_map[d] for d in common_dates]
        returns[ticker] = [
            (series[i] - series[i - 1]) / series[i - 1] for i in range(1, len(series))
        ]

    return common_dates, returns


def _covariance(a: list[float], b: list[float]) -> float:
    n = len(a)
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    return sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b)) / n


def calc_portfolio_metrics(
    allocations: list[AssetAllocation],
    market_data: dict[str, MarketDataPoint],
) -> PortfolioMetrics:
    weights = [a.weight for a in allocations]
    tickers = [a.ticker for a in allocations]

    annual_returns = [market_data[t].annualReturn if t in market_data else 0.06 for t in tickers]
    expected_return = sum(w * r for w, r in zip(weights, annual_returns))

    aligned = _aligned_weekly_returns(allocations, market_data)

    if aligned is not None:
        common_dates, weekly_returns = aligned

        # 실측 주간수익률 공분산(연율화) 기반 포트폴리오 분산
        portfolio_variance = 0.0
        for i, ti in enumerate(tickers):
            for j, tj in enumerate(tickers):
                cov_annual = _covariance(weekly_returns[ti], weekly_returns[tj]) * 52
                portfolio_variance += weights[i] * weights[j] * cov_annual

        backtest_data = _backtest_from_returns(common_dates, weights, tickers, weekly_returns)
        max_drawdown = calc_mdd([d.value for d in backtest_data])
    else:
        # 실데이터 부족 시에만 대표 상관계수 fallback 사용. 백테스트/MDD는
        # 가짜 시계열을 생성하지 않고 "데이터 없음(N/A)"으로 둔다.
        vols = [market_data[t].annualVolatility if t in market_data else 0.15 for t in tickers]
        portfolio_variance = 0.0
        for i in range(len(weights)):
            for j in range(len(weights)):
                corr = _get_fallback_correlation(allocations[i].assetClass, allocations[j].assetClass)
                portfolio_variance += weights[i] * weights[j] * vols[i] * vols[j] * corr

        backtest_data = []
        max_drawdown = None

    volatility = (max(0.0, portfolio_variance)) ** 0.5
    sharpe_ratio = (expected_return - RISK_FREE_RATE) / volatility if volatility > 0 else 0.0

    return PortfolioMetrics(
        expectedReturn=expected_return,
        volatility=volatility,
        sharpeRatio=sharpe_ratio,
        maxDrawdown=max_drawdown,
        backtestData=backtest_data,
    )


def _backtest_from_returns(
    common_dates: list[str],
    weights: list[float],
    tickers: list[str],
    weekly_returns: dict[str, list[float]],
) -> list[BacktestPoint]:
    result: list[BacktestPoint] = []
    portfolio_value = 1.0
    n_periods = len(weekly_returns[tickers[0]])

    for t in range(n_periods):
        period_return = sum(weights[i] * weekly_returns[tickers[i]][t] for i in range(len(tickers)))
        portfolio_value *= 1 + period_return
        result.append(BacktestPoint(date=common_dates[t + 1], value=portfolio_value))

    return result


def calc_mdd(values: list[float]) -> float:
    if not values:
        return 0.0

    max_drawdown = 0.0
    peak = values[0]

    for v in values:
        if v > peak:
            peak = v
        drawdown = (peak - v) / peak
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    return max_drawdown


def calc_after_tax_return(
    gross_return: float,
    portfolio: list[AssetAllocation],
    total_assets: float,  # 억 원
    other_financial_income: float,  # 억 원
) -> tuple[float, float, bool]:
    """반환값: (afterTaxReturn, taxAmount, isComprehensive)"""
    annual_gross_income = gross_return * total_assets  # 억 원

    # 이자·배당소득만 금융소득종합과세 대상 (자본이득 제외)
    dividend_income = sum(
        a.weight * gross_return * total_assets * 0.5
        for a in portfolio
        if a.assetClass in ("dividend", "bond")
    )

    total_financial_income = dividend_income + other_financial_income  # 억 원
    COMPREHENSIVE_TAX_THRESHOLD = 0.2  # 2천만원 = 0.2억

    is_comprehensive = total_financial_income > COMPREHENSIVE_TAX_THRESHOLD

    tax_amount = 0.0  # 억 원

    if is_comprehensive:
        # 억 원 → 만원 변환 후 누진세율 + 누진공제 적용 (지방소득세 10% 포함)
        income_manwon = total_financial_income * 10000
        if income_manwon <= 1400:
            total_tax_manwon = income_manwon * 0.066
        elif income_manwon <= 5000:
            total_tax_manwon = income_manwon * 0.165 - 138.6
        elif income_manwon <= 8800:
            total_tax_manwon = income_manwon * 0.264 - 633.6
        elif income_manwon <= 15000:
            total_tax_manwon = income_manwon * 0.385 - 1698.4
        else:
            total_tax_manwon = income_manwon * 0.495 - 3348.4

        # 이 포트폴리오의 배당소득 비율만큼 세금 안분
        portfolio_share = (dividend_income / total_financial_income) if total_financial_income > 0 else 0.0
        tax_amount = (total_tax_manwon / 10000) * portfolio_share
    else:
        # 2천만원 이하: 원천징수세율 15.4%를 배당소득에만 부과
        tax_amount = dividend_income * 0.154

    after_tax_return = (
        (annual_gross_income - tax_amount) / total_assets if annual_gross_income > 0 else 0.0
    )

    return after_tax_return, tax_amount, is_comprehensive


def apply_stress_scenario(
    portfolio_return: float,
    allocations: list[AssetAllocation],
    shocks: dict[str, float],
) -> float:
    stressed_return = 0.0
    for alloc in allocations:
        shock = shocks.get(alloc.assetClass, 0.0)
        base_return = portfolio_return * alloc.weight
        stressed_return += base_return + alloc.weight * shock
    return stressed_return
