"""기본 포트폴리오·스트레스 시나리오·과거 위기 시나리오 정의 — frontend/lib/portfolios.ts 이식.

채권 슬리브는 과세 구조 기준 3분류(일반채/저쿠폰채/분리과세채)로 구성한다
(2026-06 회의 확정). 시장 프록시:
  - 일반채: KOSEF 국고채10년 (148070.KS), 듀레이션 ≈ 8년
  - 저쿠폰채/분리과세채: KBSTAR KIS국고채30년Enhanced (385560.KS) — 저쿠폰
    장기 국고채(듀레이션 ≈ 20년)의 가격 민감도 프록시. 두 분류는 시장 위험은
    같고 과세 처리(financial_calc.calc_after_tax_return)만 다르다.
"""
from app.market.schemas import (
    AssetAllocation,
    HistoricalCrisis,
    PortfolioProposal,
    StressScenario,
)

DEFAULT_PORTFOLIOS: list[PortfolioProposal] = [
    PortfolioProposal(
        id="current",
        name="Current Portfolio",
        nameKr="현재 포트폴리오",
        description="기존 보수적 자산 배분",
        theme="안정형",
        allocations=[
            AssetAllocation(
                ticker="148070.KS", name="KTB 10Y (Regular)", nameKr="일반채 (국고채 10년)",
                weight=0.20, assetClass="general_bond", color="#3B82F6",
            ),
            AssetAllocation(
                ticker="385560.KS", name="KTB 30Y Low-Coupon", nameKr="저쿠폰채 (장기 국고채)",
                weight=0.10, assetClass="low_coupon_bond", color="#60A5FA",
            ),
            AssetAllocation(
                ticker="385560.KS", name="KTB Separate-Tax", nameKr="분리과세채 (장기 국고채)",
                weight=0.10, assetClass="separate_tax_bond", color="#1D4ED8",
            ),
            AssetAllocation(
                ticker="069500.KS", name="KODEX 200", nameKr="국내 주식(KOSPI200)",
                weight=0.30, assetClass="domestic_equity", color="#10B981",
            ),
            AssetAllocation(
                ticker="VYM", name="Vanguard High Dividend", nameKr="미국 고배당주",
                weight=0.20, assetClass="overseas_dividend", color="#F59E0B",
            ),
            AssetAllocation(
                ticker="GLD", name="SPDR Gold", nameKr="금",
                weight=0.10, assetClass="gold", color="#EF4444",
            ),
        ],
    ),
    PortfolioProposal(
        id="proposalA",
        name="Proposal A: Income",
        nameKr="제안 A: 인컴/배당 중심",
        description="안정적 현금흐름 극대화",
        theme="고배당 인컴형",
        allocations=[
            AssetAllocation(
                ticker="148070.KS", name="KTB 10Y (Regular)", nameKr="일반채 (국고채 10년)",
                weight=0.14, assetClass="general_bond", color="#3B82F6",
            ),
            AssetAllocation(
                ticker="385560.KS", name="KTB 30Y Low-Coupon", nameKr="저쿠폰채 (장기 국고채)",
                weight=0.08, assetClass="low_coupon_bond", color="#60A5FA",
            ),
            AssetAllocation(
                ticker="385560.KS", name="KTB Separate-Tax", nameKr="분리과세채 (장기 국고채)",
                weight=0.08, assetClass="separate_tax_bond", color="#1D4ED8",
            ),
            AssetAllocation(
                ticker="069500.KS", name="KODEX 200", nameKr="국내 주식(KOSPI200)",
                weight=0.25, assetClass="domestic_equity", color="#10B981",
            ),
            AssetAllocation(
                ticker="VYM", name="Vanguard High Dividend", nameKr="미국 고배당주",
                weight=0.30, assetClass="overseas_dividend", color="#F59E0B",
            ),
            AssetAllocation(
                ticker="GLD", name="SPDR Gold", nameKr="금",
                weight=0.15, assetClass="gold", color="#EF4444",
            ),
        ],
    ),
    PortfolioProposal(
        id="proposalB",
        name="Proposal B: Growth",
        nameKr="제안 B: 글로벌 성장형",
        description="장기 자산 증식 극대화",
        theme="글로벌 성장/대체자산",
        allocations=[
            AssetAllocation(
                ticker="148070.KS", name="KTB 10Y (Regular)", nameKr="일반채 (국고채 10년)",
                weight=0.04, assetClass="general_bond", color="#3B82F6",
            ),
            AssetAllocation(
                ticker="385560.KS", name="KTB 30Y Low-Coupon", nameKr="저쿠폰채 (장기 국고채)",
                weight=0.03, assetClass="low_coupon_bond", color="#60A5FA",
            ),
            AssetAllocation(
                ticker="385560.KS", name="KTB Separate-Tax", nameKr="분리과세채 (장기 국고채)",
                weight=0.03, assetClass="separate_tax_bond", color="#1D4ED8",
            ),
            AssetAllocation(
                ticker="069500.KS", name="KODEX 200", nameKr="국내 주식(KOSPI200)",
                weight=0.10, assetClass="domestic_equity", color="#10B981",
            ),
            AssetAllocation(
                ticker="QQQ", name="Nasdaq 100 ETF", nameKr="미국 성장주(나스닥100)",
                weight=0.30, assetClass="overseas_growth", color="#8B5CF6",
            ),
            AssetAllocation(
                ticker="VNQ", name="Vanguard REIT", nameKr="글로벌 리츠",
                weight=0.20, assetClass="reit", color="#06B6D4",
            ),
            AssetAllocation(
                ticker="GLD", name="SPDR Gold", nameKr="금",
                weight=0.15, assetClass="gold", color="#EF4444",
            ),
            AssetAllocation(
                ticker="GSG", name="iShares Commodity", nameKr="원자재",
                weight=0.15, assetClass="commodity", color="#F97316",
            ),
        ],
    ),
]

# ── 스트레스 시나리오 충격계수 ──────────────────────────────────────────────
#
# 아래 shocks 값은 "자산군 자기자본 1단위당 시나리오 발생 시 연간 기대수익률
# 변화량"을 듀레이션·베타 등 표준 근사식으로 추정한 점추정치(point estimate)이며,
# 실측 회귀계수가 아니다. 다음 4가지 한계를 항상 함께 고지한다.
#
#   1) 비선형성 미반영: 실제 가격-요인 관계는 비선형(예: 채권 컨벡시티,
#      옵션성 상품)이나 선형 충격으로 단순화함.
#   2) 자산 간 상관관계 무시: 각 자산군에 독립적으로 충격을 적용하므로,
#      복합 충격 시 실제 분산효과·전이효과(contagion)는 반영되지 않음.
#   3) 시기의존성(regime dependence): 위기 국면에서는 상관관계·변동성이
#      평시와 크게 달라질 수 있어 점추정치의 적용 범위를 벗어날 수 있음.
#   4) 한국 시장 특수성: 환헤지 비율, 거래시간 차이, 외국인 수급 등
#      한국 고유 요인은 별도 보정 없이 단순 부호/크기로만 반영함.

# 기준금리 +100bp 당 자산군별 연간 기대수익률 충격.
# 채권은 듀레이션 근사식 ΔP/P ≈ -duration × Δy 적용
# (출처: Fabozzi, "Bond Markets, Analysis, and Strategies").
RATE_SHOCKS_PER_100BP: dict[str, float] = {
    # 일반채(국고채 10년): duration ≈ 8년 → -8%이나 한·미 금리 비동조
    # 가능성을 감안해 보수적으로 -7% 사용.
    "general_bond": -0.07,
    # 저쿠폰채: 표면금리가 낮을수록 듀레이션이 만기에 근접 (장기 저쿠폰
    # 국고채 duration ≈ 20년+) → 이론상 -20%이나 보수적으로 -15%.
    "low_coupon_bond": -0.15,
    # 분리과세채(만기 10년 이상 장기채): duration ≈ 12~15년 → -11%.
    "separate_tax_bond": -0.11,
    # 할인율(무위험금리) 1%p 상승에 따른 성장주 밸류에이션(DCF/PER) 축소 효과.
    # 2022년 Fed 긴축 사이클 중 나스닥100 하락폭 대비 금리 상승폭 비율 참고.
    "overseas_growth": -0.08,
    # 해외 우량주(S&P500): 성장주 대비 밸류에이션 듀레이션이 짧아 충격을
    # 나스닥100의 약 3/4 수준으로 가정 (2022년 S&P500/나스닥100 하락폭 비율 참고).
    "overseas_blue_chip": -0.06,
    # 코스피는 미국 금리에 동조하되 환헤지·내수 비중으로 민감도가 절반 수준이라는 가정.
    "domestic_equity": -0.05,
    # 고배당주는 채권 대체재 성격으로 금리에 민감하나, 실적 기반 밸류에이션 비중이
    # 높아 성장주보다 충격이 작다는 가정.
    "overseas_dividend": -0.04,
    # 명목금리 상승은 통상 금에 약세 요인이나, 긴축이 인플레 기대 재상승을
    # 동반하면 실질금리 변화가 제한적이라는 가정 하에 소폭 양(+)으로 설정.
    "gold": 0.02,
    # 리츠는 차입비용 증가 + 할인율 상승으로 채권과 유사하게 민감.
    # 출처: NAREIT 자료상 금리 1%p 상승 시 평균 영향 범위(-8~-12%) 참고.
    "reit": -0.10,
    # 원자재는 금리보다 인플레이션 기대에 더 연동되며, 긴축 초기 인플레 압력
    # 지속을 가정해 소폭 양(+)으로 설정.
    "commodity": 0.03,
    # 미국 기준금리 인상 → 한미 금리차 확대 → 달러 강세(원화 환산 가치 상승).
    # 2022년 긴축기 금리 +4%p 대비 원/달러 상승 비율을 1%p당 근사 → +4%.
    "dollar": 0.04,
}

# 원/달러 +200원 당 자산군별 연간 기대수익률 충격.
# 원/달러 1,500원 기준 +200원 ≈ 13.3% 절하. 환노출 해외자산은 환산이익이
# 발생하나 일부 환헤지 비중을 가정해 절하율의 약 60%만 반영.
FX_SHOCKS_PER_200WON: dict[str, float] = {
    # 원화표시 국고채: 환차익 없음. 원화 약세 → 외국인 채권자금 유출 +
    # 한은 인상 압력으로 소폭 음(-), 듀레이션이 길수록 민감하다는 가정.
    "general_bond": -0.01,
    "low_coupon_bond": -0.03,
    "separate_tax_bond": -0.02,
    "overseas_growth": 0.10,
    "overseas_blue_chip": 0.10,
    "overseas_dividend": 0.09,
    "reit": 0.07,
    # 달러 자산은 환헤지 없이 보유한다고 가정 → +200원 절하율(≈13.3%) 전액 반영.
    "dollar": 0.13,
    # 원화 약세는 외국인 자금 유출 압력 + 수입물가 상승에 따른 내수 부담으로
    # 코스피에 평균적으로 음(-)의 영향을 준다는 가정.
    "domestic_equity": -0.07,
    # 금은 달러 표시 자산이므로 원화 환산 시 환차익이 그대로 반영된다는 가정
    # (절하율의 약 60% 반영, 환노출 자산과 동일 가정).
    "gold": 0.08,
    "commodity": 0.06,
}


def combine_tuner_shocks(base_rate_delta_bp: float, krw_usd_delta: float) -> dict[str, float]:
    """슬라이더(조율기) 입력을 자산군별 연간 수익률 충격으로 변환한다.

    기준 시나리오(+100bp, +200원) 충격계수를 선형 비례로 스케일링한다.
    한계: 선형 외삽이므로 기준점에서 멀어질수록(예: ±300bp) 비선형 효과
    (컨벡시티, 패닉 국면)가 과소/과대 평가될 수 있다.
    """
    rate_scale = base_rate_delta_bp / 100.0
    fx_scale = krw_usd_delta / 200.0

    classes = set(RATE_SHOCKS_PER_100BP) | set(FX_SHOCKS_PER_200WON)
    return {
        cls: RATE_SHOCKS_PER_100BP.get(cls, 0.0) * rate_scale
        + FX_SHOCKS_PER_200WON.get(cls, 0.0) * fx_scale
        for cls in classes
    }


STRESS_SCENARIOS: list[StressScenario] = [
    StressScenario(
        id="rate_hike",
        name="Fed Rate Hike +100bps",
        nameKr="미국 기준금리 100bp 급등",
        description="채권 가격 급락, 성장주 하락",
        icon="📈",
        shocks=RATE_SHOCKS_PER_100BP,
        results={},
    ),
    StressScenario(
        id="krw_depreciation",
        name="KRW/USD +200won",
        nameKr="원/달러 환율 급등 (+200원)",
        description="환노출 해외주식 평가익↑, 국내 자산 하락",
        icon="💱",
        shocks=FX_SHOCKS_PER_200WON,
        results={},
    ),
]

ALL_TICKERS = ["148070.KS", "385560.KS", "069500.KS", "VYM", "GLD", "QQQ", "VNQ", "GSG"]

# ── 과거 주요 경제 위기 재현 시나리오 ───────────────────────────────────────
#
# 각 위기 기간의 자산군별 "실제 실현 수익률"을 사전 정의 상수로 적용해
# 예상 손실률(P&L) = Σ(비중 × 위기 기간 수익률)을 구한다.
#
# 라이브 조회가 아닌 상수로 정의한 이유: 채권 ETF 프록시(148070.KS는 2011년,
# 385560.KS는 2021년 상장)가 2008·2020년에 존재하지 않아 실시간 조회가 불가능.
# 대신 당시 실제 지수·금리 데이터에서 산출한 값을 상수로 박고 출처를 주석으로 남긴다.
#
# 산출 기준:
#   - 모든 수치는 "원화 환산" 기간 수익률 점추정치 (연율화 아님).
#     해외자산 = 현지통화 수익률 × 당시 원/달러 변동을 곱해 환산.
#   - 채권 분류별 수치는 당시 국고채 금리 변동 × 분류별 듀레이션(일반 8년/
#     저쿠폰 20년/분리과세 13년) 근사로 산출.
#   - 한계: 사후 확정치 기반이므로 동일 위기 재발 시 수익률을 보장하지 않으며,
#     기간 구간(저점) 선택에 따라 수치가 달라질 수 있다.
HISTORICAL_CRISES: list[HistoricalCrisis] = [
    HistoricalCrisis(
        id="gfc_2008",
        name="2008 Global Financial Crisis",
        nameKr="2008 글로벌 금융위기",
        period="2008-09 ~ 2009-03",
        description="리먼 파산 → 글로벌 신용경색. 주식·리츠·원자재 폭락, 안전자산(국채·금) 급등",
        icon="🏦",
        assetReturns={
            # 국고채 10년 금리 5.8% → 3.9% 급락(한은 기준금리 5.25→2.0%) → 듀레이션별 가격 상승
            "general_bond": 0.10,
            "low_coupon_bond": 0.18,
            "separate_tax_bond": 0.13,
            # KOSPI 1,414 → 저점 989 (2008-10)
            "domestic_equity": -0.30,
            # 나스닥100 -43% × 원/달러 +41% (1,116→1,571원) ≈ -19%
            "overseas_growth": -0.19,
            # S&P500 -46% (1,282→676) × 원/달러 +41% ≈ -24%
            "overseas_blue_chip": -0.24,
            "overseas_dividend": -0.18,
            # 원/달러 1,116 → 1,571원 (환차익 그대로 반영)
            "dollar": 0.41,
            # 금 현지 +12% × 환율 효과 → 원화 환산 대폭 상승
            "gold": 0.45,
            # 미국 리츠(FTSE NAREIT) -55% × 환율
            "reit": -0.37,
            # 원자재(GSCI) 유가 147→40달러 폭락 -55% × 환율
            "commodity": -0.37,
        },
        results={},
    ),
    HistoricalCrisis(
        id="covid_2020",
        name="2020 COVID-19 Shock",
        nameKr="2020 코로나 쇼크",
        period="2020-02 ~ 2020-03",
        description="팬데믹 봉쇄 충격. 5주간 全자산 동반 급락(상관관계 수렴), 금도 마진콜 매도",
        icon="🦠",
        assetReturns={
            # 국고채 10년 금리 1.6% → 1.1% 하락 (한은 빅컷 1.25→0.75%)
            "general_bond": 0.02,
            "low_coupon_bond": 0.05,
            "separate_tax_bond": 0.03,
            # KOSPI 2,210 → 1,457 (2020-03-19 저점)
            "domestic_equity": -0.34,
            # 나스닥100 -28% × 환율 +6% (1,190→1,266원)
            "overseas_growth": -0.24,
            # S&P500 -34% (3,386→2,237) × 환율 +6% ≈ -30%
            "overseas_blue_chip": -0.30,
            # 원/달러 1,190 → 1,266원
            "dollar": 0.06,
            # 고배당주(VYM) -35% — 금융·에너지 비중이 높아 더 크게 하락
            "overseas_dividend": -0.31,
            # 금: 유동성 확보 매도(마진콜)로 현지 -3% × 환율 ≈ 보합
            "gold": 0.00,
            # 미국 리츠 -42% (상업용 부동산 봉쇄 직격)
            "reit": -0.38,
            # 원자재: WTI 사상 첫 마이너스 유가, GSCI -50%
            "commodity": -0.47,
        },
        results={},
    ),
    HistoricalCrisis(
        id="rate_hike_2022",
        name="2022 Fed Tightening Cycle",
        nameKr="2022 금리 인상기",
        period="2022-01 ~ 2022-10",
        description="Fed 0→4% 급속 긴축. 주식·채권 동반 하락(60/40 최악의 해), 원자재만 상승",
        icon="📈",
        assetReturns={
            # 국고채 10년 금리 2.3% → 4.6% 급등 → 듀레이션별 가격 급락
            "general_bond": -0.16,
            "low_coupon_bond": -0.35,
            "separate_tax_bond": -0.22,
            # KOSPI 2,978 → 2,294
            "domestic_equity": -0.23,
            # 나스닥100 -33% × 환율 +20% (1,190→1,424원)
            "overseas_growth": -0.20,
            # S&P500 -25% (4,797→3,577) × 환율 +20% ≈ -10%
            "overseas_blue_chip": -0.10,
            # 원/달러 1,190 → 1,424원
            "dollar": 0.20,
            # 고배당주(VYM) 현지 보합(-1%) × 환율 +20% → 원화 기준 플러스
            "overseas_dividend": 0.10,
            # 금 현지 -10% × 환율 +20%
            "gold": 0.08,
            # 미국 리츠 -28% × 환율
            "reit": -0.14,
            # 원자재: 에너지 급등(GSCI +30%대) × 환율
            "commodity": 0.35,
        },
        results={},
    ),
]


def calc_crisis_pnl(crisis: HistoricalCrisis, allocations: list[AssetAllocation]) -> float:
    """위기 기간 예상 P&L = Σ(자산 비중 × 해당 자산군의 위기 기간 실현 수익률)."""
    return sum(
        alloc.weight * crisis.assetReturns.get(alloc.assetClass, 0.0)
        for alloc in allocations
    )
