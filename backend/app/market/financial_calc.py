"""포트폴리오 정량 지표 계산 — frontend/lib/financial-calc.ts 이식.

세금 계산 근거: 소득세법 제14조(금융소득종합과세), 소득세법 제55조(종합소득세 누진세율,
2026년 기준 지방소득세 10% 포함), 소득세법 제129조(이자·배당소득 원천징수세율 15.4%,
만기 10년 이상 장기채권 분리과세 신청 시 30% + 지방소득세 = 33%).

채권 3분류(2026-06 회의 확정):
  - general_bond(일반채): 표면이자 전액 이자소득 → 종합과세 합산
  - low_coupon_bond(저쿠폰채): 표면금리만 이자과세, 매매차익은 개인 비과세
    → 과세 대상 경상소득 비중이 낮음
  - separate_tax_bond(분리과세채): 분리과세 신청 시 33% 원천징수로 납세 종결,
    종합과세 합산 제외

스트레스 테스트(시계열 충격 주입):
  자산군별 연간 충격 s를 실측 주간수익률 시계열에 주입해
  기대수익률·변동성·샤프·소르티노·MDD를 "전부" 일관되게 재계산한다.
    r'_t = mean + (r_t - mean) × vol_mult(s) + s/52
  - 드리프트: s/52 균등 분배 (연간 충격의 주간 환산)
  - 변동성 확대: vol_mult(s) = min(1 + VOL_STRESS_BETA·|s|, VOL_STRESS_CAP)
    위기 국면에서 변동성이 동반 상승하는 레짐 효과의 선형 근사 (점추정 가정,
    실측 회귀계수 아님 — 2008/2020/2022 위기 시 실현변동성 1.3~2배 확대 사례 참고).
"""
from app.market.schemas import (
    AssetAllocation,
    BacktestPoint,
    MarketDataPoint,
    PortfolioMetrics,
)

RISK_FREE_RATE = 0.035  # 3.5% 국고채

MIN_COMMON_DATES = 10  # 공통 거래일이 이보다 적으면 실데이터 기반 계산을 포기하고 fallback 사용

# 충격 1단위(|s|=100%)당 변동성 확대 계수와 상한. |s|=15% 충격이면 변동성 1.3배.
VOL_STRESS_BETA = 2.0
VOL_STRESS_CAP = 1.6

# 자산군 간 대표 상관계수 — 실시간 시세에서 공통 거래일이 부족해 실제 공분산을
# 계산할 수 없을 때만 사용하는 fallback 값이다.
# 출처: BlackRock Capital Market Assumptions, J.P. Morgan Long-Term Capital Market
# Assumptions, Ibbotson SBBI 등에서 통상 보고되는 자산군별 장기 상관관계 범위를
# 참고한 대표값(point estimate)이며, 실측 상관행렬이 아니다.
# 한계: (1) 비선형성·꼬리 위험(tail dependence) 미반영, (2) 국면(레짐)에 따라
# 실제 상관관계는 위 범위를 크게 벗어날 수 있음(예: 위기 시 상관관계 수렴),
# (3) 한국 시장 고유 특성(환헤지 여부, 거래시간 차이) 미반영.
_FALLBACK_CORRELATIONS: dict[str, float] = {
    # 채권(general_bond로 정규화) × 나머지
    "domestic_equity-general_bond": 0.1,
    "general_bond-overseas_growth": -0.05,
    "general_bond-overseas_blue_chip": -0.05,
    "general_bond-overseas_dividend": 0.15,
    "general_bond-gold": 0.1,
    "general_bond-reit": 0.2,
    "commodity-general_bond": 0.0,
    "dollar-general_bond": -0.05,
    # 국내 주식 × 나머지
    "domestic_equity-overseas_growth": 0.65,
    "domestic_equity-overseas_blue_chip": 0.65,
    "domestic_equity-overseas_dividend": 0.6,
    "domestic_equity-gold": -0.05,
    "domestic_equity-reit": 0.5,
    "commodity-domestic_equity": 0.3,
    # 원/달러 급등 국면에서 코스피 약세가 반복되는 강한 역상관.
    "dollar-domestic_equity": -0.4,
    # 해외 성장주(나스닥100) × 나머지
    "overseas_blue_chip-overseas_growth": 0.9,
    "overseas_dividend-overseas_growth": 0.75,
    "gold-overseas_growth": -0.1,
    "overseas_growth-reit": 0.55,
    "commodity-overseas_growth": 0.25,
    "dollar-overseas_growth": -0.2,
    # 해외 우량주(S&P500) × 나머지 — 성장주와 유사하되 배당주와 더 가깝다는 가정.
    "overseas_blue_chip-overseas_dividend": 0.85,
    "gold-overseas_blue_chip": -0.1,
    "overseas_blue_chip-reit": 0.6,
    "commodity-overseas_blue_chip": 0.25,
    "dollar-overseas_blue_chip": -0.2,
    # 해외 고배당주 × 나머지
    "gold-overseas_dividend": -0.05,
    "overseas_dividend-reit": 0.5,
    "commodity-overseas_dividend": 0.2,
    "dollar-overseas_dividend": -0.15,
    # 금·리츠·원자재·달러 상호 간
    "gold-reit": 0.1,
    "commodity-gold": 0.5,
    # 원화 환산 기준 금·달러 모두 환차익을 공유 → 양(+)의 상관 가정.
    "dollar-gold": 0.25,
    "commodity-reit": 0.3,
    "dollar-reit": -0.15,
    # 원자재는 달러 표시 가격이라 달러 강세 시 약세(역상관) 경향.
    "commodity-dollar": -0.1,
}

# 채권 3분류는 fallback 상관계수 조회 시 "general_bond"로 정규화한다 (시장 위험 동질 가정).
_BOND_SUBTYPES = ("general_bond", "low_coupon_bond", "separate_tax_bond")


def _normalize_class(asset_class: str) -> str:
    return "general_bond" if asset_class in _BOND_SUBTYPES else asset_class


def _get_fallback_correlation(a: str, b: str) -> float:
    a, b = _normalize_class(a), _normalize_class(b)
    if a == b:
        return 1.0
    key = "-".join(sorted((a, b)))
    return _FALLBACK_CORRELATIONS.get(key, 0.3)


def _vol_multiplier(shock: float) -> float:
    return min(1.0 + VOL_STRESS_BETA * abs(shock), VOL_STRESS_CAP)


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


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


def calc_portfolio_metrics(
    allocations: list[AssetAllocation],
    market_data: dict[str, MarketDataPoint],
    shocks: dict[str, float] | None = None,
) -> PortfolioMetrics:
    """포트폴리오 지표 계산. shocks를 주면 시계열 충격 주입 후 전 지표를 재계산한다.

    shocks: 자산군(assetClass) → 연간 기대수익률 충격(예: -0.12 = -12%p).
    shocks가 None이거나 전부 0이면 기준(base) 지표와 동일하다.
    """
    shocks = shocks or {}
    weights = [a.weight for a in allocations]
    tickers = [a.ticker for a in allocations]
    alloc_shocks = [shocks.get(a.assetClass, 0.0) for a in allocations]

    annual_returns = [market_data[t].annualReturn if t in market_data else 0.06 for t in tickers]
    expected_return = sum(
        w * (r + s) for w, r, s in zip(weights, annual_returns, alloc_shocks)
    )

    aligned = _aligned_weekly_returns(allocations, market_data)

    if aligned is not None:
        common_dates, weekly_returns = aligned

        # 배분(allocation)별 충격 주입 시계열. 같은 티커라도 자산군이 다르면
        # (예: 저쿠폰채/분리과세채 동일 프록시) 충격이 다를 수 있어 배분 단위로 만든다.
        stressed_series: list[list[float]] = []
        for alloc, s in zip(allocations, alloc_shocks):
            base_series = weekly_returns[alloc.ticker]
            m = _mean(base_series)
            vm = _vol_multiplier(s)
            stressed_series.append([m + (r - m) * vm + s / 52 for r in base_series])

        # 포트폴리오 주간수익률 → 분산·백테스트·MDD·소르티노를 한 시계열에서 일관 계산
        n_periods = len(stressed_series[0])
        portfolio_weekly = [
            sum(weights[i] * stressed_series[i][t] for i in range(len(weights)))
            for t in range(n_periods)
        ]

        mean_weekly = _mean(portfolio_weekly)
        portfolio_variance = (
            sum((r - mean_weekly) ** 2 for r in portfolio_weekly) / n_periods * 52
        )

        backtest_data = _backtest_from_portfolio_returns(common_dates, portfolio_weekly)
        max_drawdown = calc_mdd([d.value for d in backtest_data])
        sortino_ratio = _sortino(portfolio_weekly, expected_return)
    else:
        # 실데이터 부족 시에만 대표 상관계수 fallback 사용. 충격의 변동성 확대는
        # 자산별 연변동성에 vol_mult를 곱해 반영한다. 백테스트/MDD/소르티노는
        # 가짜 시계열을 생성하지 않고 "데이터 없음(N/A)"으로 둔다.
        vols = [
            (market_data[t].annualVolatility if t in market_data else 0.15)
            * _vol_multiplier(s)
            for t, s in zip(tickers, alloc_shocks)
        ]
        portfolio_variance = 0.0
        for i in range(len(weights)):
            for j in range(len(weights)):
                corr = _get_fallback_correlation(
                    allocations[i].assetClass, allocations[j].assetClass
                )
                portfolio_variance += weights[i] * weights[j] * vols[i] * vols[j] * corr

        backtest_data = []
        max_drawdown = None
        sortino_ratio = None

    volatility = (max(0.0, portfolio_variance)) ** 0.5
    sharpe_ratio = (expected_return - RISK_FREE_RATE) / volatility if volatility > 0 else 0.0

    return PortfolioMetrics(
        expectedReturn=expected_return,
        volatility=volatility,
        sharpeRatio=sharpe_ratio,
        sortinoRatio=sortino_ratio,
        maxDrawdown=max_drawdown,
        backtestData=backtest_data,
    )


def _sortino(portfolio_weekly: list[float], expected_return: float) -> float | None:
    """소르티노 지수 = (기대수익률 - 무위험수익률) / 연율화 하방편차.

    하방편차는 주간 MAR(무위험수익률/52) 미달분의 RMS를 √52로 연율화.
    하방 이탈이 전혀 없으면(division by zero) None을 반환한다.
    """
    mar_weekly = RISK_FREE_RATE / 52
    downside_sq = [min(0.0, r - mar_weekly) ** 2 for r in portfolio_weekly]
    downside_dev = (_mean(downside_sq) ** 0.5) * (52 ** 0.5)
    if downside_dev <= 0:
        return None
    return (expected_return - RISK_FREE_RATE) / downside_dev


def _backtest_from_portfolio_returns(
    common_dates: list[str],
    portfolio_weekly: list[float],
) -> list[BacktestPoint]:
    result: list[BacktestPoint] = []
    portfolio_value = 1.0

    for t, period_return in enumerate(portfolio_weekly):
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


# ── 세금 계산 ────────────────────────────────────────────────────────────────

# 자산군별 "총수익 중 과세 대상 경상소득(이자·배당)" 비중 가정 (자본이득 제외).
#   - overseas_dividend: 총수익의 절반이 배당이라는 기존 가정 유지
#   - overseas_blue_chip: S&P500 배당수익률(≈1.5%) / 장기 총수익(≈7%) → 20% 가정
#   - general_bond: 국고채 수익 대부분이 표면이자라는 가정 (85%)
#   - low_coupon_bond: 표면금리(≈1%대)만 이자과세, 매매차익은 개인 비과세 → 15%
#   - separate_tax_bond: 이자 비중은 일반채와 동일하나 과세 방식이 분리과세
#   - dollar: 달러 예금/RP 이자만 과세, 환차익은 개인 비과세 → 30% 가정
_TAXABLE_INCOME_PORTION: dict[str, float] = {
    "overseas_dividend": 0.5,
    "overseas_blue_chip": 0.2,
    "general_bond": 0.85,
    "low_coupon_bond": 0.15,
    "separate_tax_bond": 0.85,
    "dollar": 0.3,
}

# 만기 10년 이상 장기채권 분리과세 신청 시 원천징수세율 (소득세법 §129①1,
# 30% + 지방소득세 10% = 33%). 신청 시 종합과세 합산에서 제외되어 납세 종결.
SEPARATE_TAX_RATE = 0.33

# 이자·배당소득 원천징수세율 15.4% (소득세법 §129, 지방소득세 포함)
WITHHOLDING_TAX_RATE = 0.154


def calc_after_tax_return(
    gross_return: float,
    portfolio: list[AssetAllocation],
    total_assets: float,  # 억 원
    other_financial_income: float,  # 억 원
) -> tuple[float, float, bool]:
    """반환값: (afterTaxReturn, taxAmount, isComprehensive)"""
    annual_gross_income = gross_return * total_assets  # 억 원

    # 종합과세 합산 대상 경상소득 (분리과세채 제외)
    comprehensive_income = sum(
        a.weight * gross_return * total_assets * _TAXABLE_INCOME_PORTION[a.assetClass]
        for a in portfolio
        if a.assetClass in _TAXABLE_INCOME_PORTION and a.assetClass != "separate_tax_bond"
    )
    # 분리과세채 경상소득 (분리과세 신청 시 종합과세 합산 제외)
    separate_income = sum(
        a.weight * gross_return * total_assets * _TAXABLE_INCOME_PORTION[a.assetClass]
        for a in portfolio
        if a.assetClass == "separate_tax_bond"
    )

    total_financial_income = comprehensive_income + other_financial_income  # 억 원
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

        # 이 포트폴리오의 종합과세 대상 소득 비율만큼 세금 안분
        portfolio_share = (
            (comprehensive_income / total_financial_income) if total_financial_income > 0 else 0.0
        )
        tax_amount = (total_tax_manwon / 10000) * portfolio_share

        # 종합과세 대상자는 분리과세 신청이 유리하다고 가정 → 33% 원천징수로 종결
        tax_amount += separate_income * SEPARATE_TAX_RATE
    else:
        # 2천만원 이하: 분리과세 신청 실익 없음(33% > 15.4%) → 전부 원천징수 15.4%
        tax_amount = (comprehensive_income + separate_income) * WITHHOLDING_TAX_RATE

    after_tax_return = (
        (annual_gross_income - tax_amount) / total_assets if annual_gross_income > 0 else 0.0
    )

    return after_tax_return, tax_amount, is_comprehensive


def apply_stress_scenario(
    portfolio_return: float,
    allocations: list[AssetAllocation],
    shocks: dict[str, float],
) -> float:
    """(레거시) 기대수익률에만 충격을 가산하는 단순 시나리오 적용.

    /api/stress-scenarios의 고정 시나리오 막대그래프용으로만 유지한다.
    전 지표(변동성·MDD·소르티노 포함) 재계산은 calc_portfolio_metrics(shocks=...)를 사용할 것.
    """
    stressed_return = 0.0
    for alloc in allocations:
        shock = shocks.get(alloc.assetClass, 0.0)
        base_return = portfolio_return * alloc.weight
        stressed_return += base_return + alloc.weight * shock
    return stressed_return
