"""기본 포트폴리오·스트레스 시나리오 정의 — frontend/lib/portfolios.ts 이식."""
from app.market.schemas import AssetAllocation, PortfolioProposal, StressScenario

DEFAULT_PORTFOLIOS: list[PortfolioProposal] = [
    PortfolioProposal(
        id="current",
        name="Current Portfolio",
        nameKr="현재 포트폴리오",
        description="기존 보수적 자산 배분",
        theme="안정형",
        allocations=[
            AssetAllocation(ticker="TLT", name="US Long-Term Bond", nameKr="미국 장기채", weight=0.40, assetClass="bond", color="#3B82F6"),
            AssetAllocation(ticker="069500.KS", name="KODEX 200", nameKr="국내 주식(KOSPI200)", weight=0.30, assetClass="domestic_equity", color="#10B981"),
            AssetAllocation(ticker="VYM", name="Vanguard High Dividend", nameKr="미국 고배당주", weight=0.20, assetClass="dividend", color="#F59E0B"),
            AssetAllocation(ticker="GLD", name="SPDR Gold", nameKr="금", weight=0.10, assetClass="gold", color="#EF4444"),
        ],
    ),
    PortfolioProposal(
        id="proposalA",
        name="Proposal A: Income",
        nameKr="제안 A: 인컴/배당 중심",
        description="안정적 현금흐름 극대화",
        theme="고배당 인컴형",
        allocations=[
            AssetAllocation(ticker="TLT", name="US Long-Term Bond", nameKr="미국 장기채", weight=0.30, assetClass="bond", color="#3B82F6"),
            AssetAllocation(ticker="069500.KS", name="KODEX 200", nameKr="국내 주식(KOSPI200)", weight=0.25, assetClass="domestic_equity", color="#10B981"),
            AssetAllocation(ticker="VYM", name="Vanguard High Dividend", nameKr="미국 고배당주", weight=0.30, assetClass="dividend", color="#F59E0B"),
            AssetAllocation(ticker="GLD", name="SPDR Gold", nameKr="금", weight=0.15, assetClass="gold", color="#EF4444"),
        ],
    ),
    PortfolioProposal(
        id="proposalB",
        name="Proposal B: Growth",
        nameKr="제안 B: 글로벌 성장형",
        description="장기 자산 증식 극대화",
        theme="글로벌 성장/대체자산",
        allocations=[
            AssetAllocation(ticker="TLT", name="US Long-Term Bond", nameKr="미국 장기채", weight=0.10, assetClass="bond", color="#3B82F6"),
            AssetAllocation(ticker="069500.KS", name="KODEX 200", nameKr="국내 주식(KOSPI200)", weight=0.10, assetClass="domestic_equity", color="#10B981"),
            AssetAllocation(ticker="QQQ", name="Nasdaq 100 ETF", nameKr="미국 성장주(나스닥100)", weight=0.30, assetClass="us_equity", color="#8B5CF6"),
            AssetAllocation(ticker="VNQ", name="Vanguard REIT", nameKr="글로벌 리츠", weight=0.20, assetClass="reit", color="#06B6D4"),
            AssetAllocation(ticker="GLD", name="SPDR Gold", nameKr="금", weight=0.15, assetClass="gold", color="#EF4444"),
            AssetAllocation(ticker="GSG", name="iShares Commodity", nameKr="원자재", weight=0.15, assetClass="commodity", color="#F97316"),
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
STRESS_SCENARIOS: list[StressScenario] = [
    StressScenario(
        id="rate_hike",
        name="Fed Rate Hike +100bps",
        nameKr="미국 기준금리 100bp 급등",
        description="채권 가격 급락, 성장주 하락",
        icon="📈",
        shocks={
            # 듀레이션 근사식 ΔP/P ≈ -duration × Δy 적용. TLT(20년+ 미국채) 평균
            # duration ≈ 17년 기준 -17%이나, 수익률곡선 평행이동이 아닌 점·일부
            # 헤지 효과를 감안해 보수적으로 -12% 사용.
            # 출처: Fabozzi, "Bond Markets, Analysis, and Strategies" 듀레이션 근사식.
            "bond": -0.12,
            # 할인율(무위험금리) 1%p 상승에 따른 성장주 밸류에이션(DCF/PER) 축소 효과.
            # 2022년 Fed 긴축 사이클 중 나스닥100 하락폭 대비 금리 상승폭 비율을
            # 참고한 비례 추정.
            "us_equity": -0.08,
            # 코스피는 미국 금리에 동조하되 환헤지·내수 비중으로 민감도가 절반 수준이라는 가정.
            "domestic_equity": -0.05,
            # 고배당주는 채권 대체재 성격으로 금리에 민감하나, 실적 기반 밸류에이션 비중이
            # 높아 성장주보다 충격이 작다는 가정.
            "dividend": -0.04,
            # 명목금리 상승은 통상 금에 약세 요인이나, 긴축이 인플레 기대 재상승을
            # 동반하면 실질금리 변화가 제한적이라는 가정 하에 소폭 양(+)으로 설정.
            "gold": 0.02,
            # 리츠는 차입비용 증가 + 할인율 상승으로 채권과 유사하게 민감.
            # 출처: NAREIT 자료상 보고되는 금리 1%p 상승 시 평균 영향 범위(-8~-12%) 참고.
            "reit": -0.10,
            # 원자재는 금리보다 인플레이션 기대에 더 연동되며, 긴축 초기 인플레 압력
            # 지속을 가정해 소폭 양(+)으로 설정.
            "commodity": 0.03,
        },
        results={},
    ),
    StressScenario(
        id="krw_depreciation",
        name="KRW/USD +200won",
        nameKr="원/달러 환율 급등 (+200원)",
        description="환노출 해외주식 평가익↑, 국내주식 하락",
        icon="💱",
        shocks={
            # 원/달러 1,500원 기준 +200원 ≈ 13.3% 절하. 환노출 자산은 환산이익이
            # 발생하나 일부 환헤지 비중을 가정해 절하율의 약 60%만 반영.
            "bond": 0.08,
            "us_equity": 0.10,
            "dividend": 0.09,
            "reit": 0.07,
            # 원화 약세는 외국인 자금 유출 압력 + 수입물가 상승에 따른 내수 부담으로
            # 코스피에 평균적으로 음(-)의 영향을 준다는 가정.
            "domestic_equity": -0.07,
            # 금은 달러 표시 자산이므로 원화 환산 시 환차익이 그대로 반영된다는 가정
            # (절하율의 약 60% 반영, 환노출 자산과 동일 가정).
            "gold": 0.08,
            "commodity": 0.06,
        },
        results={},
    ),
]

ALL_TICKERS = ["TLT", "069500.KS", "VYM", "GLD", "QQQ", "VNQ", "GSG"]
