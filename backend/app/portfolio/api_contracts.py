# ruff: noqa: E501
"""Swagger/OpenAPI용 포트폴리오 calculate 요청·응답 계약.

계산 엔진의 내부 AnalysisRequest는 그대로 유지하고,
프론트/STT 연동에서 사용하는 ips_json 계약을 명시적으로 문서화한다.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .constants import DEFAULT_BENCHMARK_KEY, BenchmarkKey


class ExtensibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class STTIPSJson(BaseModel):
    Goal: Optional[Any] = Field(None, description="고객 목표 원문")
    Asset: Any = Field(
        ...,
        description="STT 계약 기준 운용자산. 숫자/단위 없는 숫자 문자열은 억원, '18억' 등 단위 문자열도 허용",
        examples=[18],
    )
    Return: Any = Field(..., description="목표 세후수익률(%). 예: 8은 8%", examples=[8])
    Risk: Any = Field(..., description="위험성향. 예: 안정형/균형형/공격형", examples=["균형형"])
    Time: Any = Field(..., description="투자기간(년)", examples=[10])
    Tax: Any = Field(
        ...,
        description=(
            "세금 관련 발화 원문. 결정론적 registry 파서가 우선이며, 누락 가능성이 있을 때만 "
            "Tax 전용 LLM이 원문 검증을 거쳐 허용 fact를 보완"
        ),
        examples=["금융소득종합과세가 걱정되고 ISA는 2022년 가입, 올해 1,500만원 납입"],
    )
    Liquidity: Any = Field(..., description="유동성 필요 수준. 예: 낮음/중간/높음", examples=["중간"])
    Legal: Optional[Any] = Field(
        None,
        description=(
            "법률·규제·계약 관련 자유문장. 결정론적 안전망을 우선하고 Legal 전용 LLM은 "
            "미분류 검토 주제만 보완하며 포트폴리오 비중·점수에는 반영하지 않음"
        ),
    )
    Unique: Optional[Any] = Field(None, description="필요자금·ISA·IRP·승계 등 고객 고유 상황 원문")

    model_config = ConfigDict(extra="ignore")


class CurrentPortfolioItem(BaseModel):
    asset_class: str = Field(..., description="백엔드 자산 키")
    weight: float = Field(..., ge=0, le=100, description="비중(%). 전체 합계 100")


class ScenarioInput(BaseModel):
    base_interest_rate: Optional[float] = None
    base_fx_rate_krw_per_usd: Optional[float] = Field(None, gt=0)
    stress_interest_rate_shock: float = 0.0
    stress_fx_shock: float = 0.0
    stress_affects_scoring: bool = False

    model_config = ConfigDict(extra="ignore")


class PortfolioCalculateRequest(BaseModel):
    client_id: Optional[str] = Field(None, description="고객 ID")
    customer_id: Optional[str] = Field(None, description="consultations 응답 customer_id 호환 필드")
    consultation_id: Optional[str] = Field(None, description="상담 ID")
    ips_json: STTIPSJson
    current_portfolio: Optional[List[CurrentPortfolioItem]] = None
    benchmark_key: BenchmarkKey = DEFAULT_BENCHMARK_KEY
    period: str = "5y"
    num_simulations: int = Field(5000, ge=500, le=100000)
    expected_return_haircut: float = Field(0.75, ge=0.0, le=1.0)
    random_seed: int = Field(42, ge=0)
    scenario: Optional[ScenarioInput] = None

    # 구조화 값이 이미 있는 연동 경로는 텍스트 파서보다 우선한다.
    marginal_income_tax_rate: Optional[float] = Field(None, ge=0, le=0.495)
    external_financial_income_krw: Optional[float] = Field(None, ge=0)
    external_financial_income_manwon: Optional[float] = Field(None, ge=0)
    overseas_realized_loss: Optional[float] = Field(None, ge=0)
    overseas_realized_gain_krw: Optional[float] = Field(None, ge=0)
    isa_current_year_contribution: Optional[float] = Field(None, ge=0)

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "client_id": "00000000-0000-0000-0000-000000000000",
                "consultation_id": "11111111-1111-1111-1111-111111111111",
                "ips_json": {
                    "Goal": "장기 자산 성장과 절세",
                    "Asset": 18,
                    "Return": 8,
                    "Risk": "균형형",
                    "Time": 10,
                    "Tax": "금융소득종합과세가 걱정되고 ISA는 2022년 가입, 올해 1,500만원 납입",
                    "Liquidity": "중간",
                    "Legal": None,
                    "Unique": "3년 뒤 자녀 전세자금 3억원 필요, IRP는 2016년 가입",
                },
                "current_portfolio": [
                    {"asset_class": "domestic_equity", "weight": 25},
                    {"asset_class": "overseas_blue_chip", "weight": 25},
                    {"asset_class": "general_bond", "weight": 30},
                    {"asset_class": "cash", "weight": 20},
                ],
                "benchmark_key": "msci_acwi",
                "period": "5y",
                "num_simulations": 5000,
            }
        },
    )


class AllocationItemResponse(BaseModel):
    asset_class: str
    name: str
    weight: float = Field(description="표시 비중(%), 소수점 둘째 자리, allocation 합계 100.00")


class BacktestPointResponse(BaseModel):
    date: str
    value: float
    base_index: float


class BenchmarkMetadataResponse(ExtensibleModel):
    benchmark_key: Optional[str] = None
    ticker: Optional[str] = None
    label: Optional[str] = None
    currency: Optional[str] = None
    applicable: Optional[bool] = None
    reason: Optional[str] = None
    affects_portfolio_recommendation: Optional[bool] = None


class BenchmarkSeriesResponse(BaseModel):
    metadata: BenchmarkMetadataResponse = Field(default_factory=BenchmarkMetadataResponse)
    backtest: List[BacktestPointResponse] = Field(default_factory=list)


class BenchmarkCollectionResponse(ExtensibleModel):
    kospi: Optional[BenchmarkSeriesResponse] = None
    sp500: Optional[BenchmarkSeriesResponse] = None
    msci_acwi: Optional[BenchmarkSeriesResponse] = None


class BenchmarkComparisonResponse(ExtensibleModel):
    beta: Optional[float] = None
    metadata: BenchmarkMetadataResponse = Field(default_factory=BenchmarkMetadataResponse)


class BenchmarkComparisonsResponse(ExtensibleModel):
    kospi: Optional[BenchmarkComparisonResponse] = None
    sp500: Optional[BenchmarkComparisonResponse] = None
    msci_acwi: Optional[BenchmarkComparisonResponse] = None


class PortfolioMetricsResponse(ExtensibleModel):
    expected_return: float = Field(description="%")
    volatility: float = Field(description="%")
    sharpe: float
    sortino: float
    mdd: float = Field(description="%")
    beta: Optional[float] = None
    beta_benchmark: Optional[BenchmarkMetadataResponse] = None
    selected_benchmark_key: Optional[str] = None
    benchmark_comparisons: BenchmarkComparisonsResponse = Field(default_factory=BenchmarkComparisonsResponse)
    after_tax_return: float = Field(description="%")


class PortfolioMetricsKRWResponse(ExtensibleModel):
    basis: str
    total_asset: float
    expected_return: float
    after_tax_return: float
    mdd: float
    volatility_band: float
    note: str


class VsCurrentKRWResponse(ExtensibleModel):
    after_tax_return_delta: float
    mdd_loss_improvement: float
    basis: str


class TaxWaterfallResponse(ExtensibleModel):
    gross_return: float
    dividend_interest_tax: float
    capital_gains_tax: float
    transaction_cost: float
    fx_cost: float
    after_tax: float


class PortfolioTaxResponse(ExtensibleModel):
    waterfall: TaxWaterfallResponse
    saved_vs_current: float
    summary: str
    calculation_notes: List[str] = Field(default_factory=list)


class PortfolioItemResponse(ExtensibleModel):
    kind: Literal["current", "A", "B"]
    rank: Optional[int] = None
    label: str
    badge: Optional[str] = None
    allocation: List[AllocationItemResponse]
    allocation_total: float = Field(100.0, description="표시 비중 합계")
    metrics: PortfolioMetricsResponse
    metrics_krw: PortfolioMetricsKRWResponse
    vs_current_krw: VsCurrentKRWResponse
    backtest: List[BacktestPointResponse]
    benchmark: BenchmarkSeriesResponse
    benchmarks: BenchmarkCollectionResponse
    tax: PortfolioTaxResponse


class CorrelationAssetResponse(BaseModel):
    asset_class: str
    name: str


class CorrelationHeatmapResponse(BaseModel):
    assets: List[CorrelationAssetResponse]
    matrix: List[List[float]]
    value_type: Literal["correlation"] = "correlation"


class RejectionCountsResponse(ExtensibleModel):
    suitability: int = 0
    liquidity: int = 0
    historical_var_95: int = 0
    risk_contribution: int = 0


class SearchSummaryResponse(ExtensibleModel):
    generated_portfolios: int
    guideline_pass_portfolios: int
    suitable_portfolios: int
    liquidity_pass_portfolios: int
    risk_control_pass_portfolios: int
    common_filter_pass_portfolios: int
    filtered_out_portfolios: int
    rejection_counts: RejectionCountsResponse
    selection_method: str
    portfolio_a_selection_mode: str
    portfolio_b_selection_mode: str
    portfolio_b_available: bool
    target_after_tax_return: float
    eligible_assets: List[str] = Field(default_factory=list)
    excluded_by_horizon: List[str] = Field(default_factory=list)
    constraint_warnings: List[str] = Field(default_factory=list)


class ScenarioSummaryResponse(ExtensibleModel):
    base_interest_rate: float
    base_fx_rate_krw_per_usd: float
    stressed_interest_rate: float
    stressed_fx_rate_krw_per_usd: float
    stress_interest_rate_shock: float
    stress_fx_shock: float
    stress_affects_scoring: bool
    rrttllu: Dict[str, Any] = Field(default_factory=dict)
    unique_profile: Dict[str, Any] = Field(default_factory=dict)


class DataSnapshotResponse(ExtensibleModel):
    data_source: Optional[str] = None
    period: Optional[str] = None
    data_start: Optional[str] = None
    data_end: Optional[str] = None
    fallback_used: Optional[bool] = None
    fallback_reason: Optional[str] = None
    backtest_data_snapshot: Dict[str, Any] = Field(default_factory=dict)


class InputAdapterResponse(ExtensibleModel):
    source: str
    client_id: Optional[str] = None
    consultation_id: Optional[str] = None
    flat_ips_keys_used: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class MethodologyResponse(ExtensibleModel):
    portfolio_generation: str
    optimization_basis: str
    risk_classification: str
    selection_logic: str
    duration_logic: str
    suitability_filter: str
    liquidity_metric: str
    tax_logic: str
    second_portfolio_logic: str
    stress_test_logic: str
    var_erc_logic: str
    benchmark_beta_logic: str
    corporate_context_logic: str
    backtest_caution: str


class PortfolioCalculateResponseContract(BaseModel):
    client_id: Optional[str] = None
    consultation_id: str
    calculation_session_id: str
    as_of: str
    risk_profile: str
    risk_profile_label: str
    portfolios: List[PortfolioItemResponse]
    correlation_heatmap: CorrelationHeatmapResponse
    search_summary: SearchSummaryResponse
    scenario_summary: ScenarioSummaryResponse
    data_snapshot: DataSnapshotResponse
    input_adapter: InputAdapterResponse
    methodology: MethodologyResponse
    notes: List[str]


class PortfolioStressTestResponseContract(BaseModel):
    consultation_id: str
    calculation_session_id: str
    as_of: str
    risk_profile: str
    risk_profile_label: str
    portfolios: List[PortfolioItemResponse]
    scenario_summary: ScenarioSummaryResponse
    data_snapshot: DataSnapshotResponse
    input_adapter: InputAdapterResponse
