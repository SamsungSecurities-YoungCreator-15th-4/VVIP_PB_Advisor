"""백엔드 기준 포트폴리오 API 계약.

프론트엔드는 이 파일의 Request/Response 모델을 그대로 따라야 한다.
모든 금액은 KRW, 모든 비율은 소수(rate) 단위다.
예: 6% -> 0.06, 100bp -> 0.01.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


AssetKey = Literal[
    "domestic_equity",
    "overseas_blue_chip",
    "overseas_growth",
    "overseas_dividend",
    "general_bond",
    "separate_tax_bond",
    "low_coupon_bond",
    "reit",
    "gold",
    "commodity",
    "dollar",
    "cash",
]
BenchmarkKey = Literal["kospi", "sp500", "msci_acwi"]
RiskProfile = Literal["conservative", "balanced", "aggressive"]
TaxSensitivity = Literal["low", "medium", "high"]
LiquidityNeed = Literal["low", "mid", "high"]
IsaType = Literal["general", "seogmin"]
PortfolioKind = Literal["current", "A", "B"]
ReserveAssetKey = Literal["cash", "general_bond", "low_coupon_bond", "separate_tax_bond"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CurrentAllocationItem(StrictModel):
    asset_class: AssetKey
    weight_rate: float = Field(..., ge=0.0, le=1.0)


class UniqueInput(StrictModel):
    """고객 고유 상황.

    raw_text가 있으면 Azure Structured Output으로 의미 매핑한다.
    structured_mapping이 이미 있으면 재호출하지 않고 그대로 검증/반영한다.
    명시형 필드는 LLM 장애 시에도 계산 가능한 안전한 기본 입력이다.
    """

    raw_text: str | None = None
    structured_mapping: dict[str, Any] | None = None
    need_amount_krw: float = Field(0.0, ge=0.0)
    reserve_asset: ReserveAssetKey = "cash"


class IsaInput(StrictModel):
    enabled: bool = True
    isa_type: IsaType = "general"
    account_exists: bool = False
    account_age_years: float = Field(0.0, ge=0.0, le=50.0)
    cumulative_contribution_krw: float = Field(0.0, ge=0.0)
    current_year_contribution_krw: float = Field(0.0, ge=0.0)
    recent_3yr_comprehensive_taxed: bool = False
    existing_account_usable: bool = True
    remaining_capacity_krw: float = Field(100_000_000.0, ge=0.0)
    remaining_capacity_override_krw: float | None = Field(None, ge=0.0)
    years_until_liquid: float = Field(3.0, ge=0.0, le=50.0)


class IrpInput(StrictModel):
    enabled: bool = True
    eligible: bool = True
    account_exists: bool = False
    account_age_years: float = Field(0.0, ge=0.0, le=80.0)
    cumulative_contribution_krw: float = Field(0.0, ge=0.0)
    current_year_contribution_krw: float = Field(0.0, ge=0.0)
    remaining_tax_credit_capacity_krw: float = Field(9_000_000.0, ge=0.0)
    remaining_tax_credit_capacity_override_krw: float | None = Field(None, ge=0.0)
    tax_credit_rate: float = Field(0.132, ge=0.0, le=0.165)
    years_until_access: float = Field(0.0, ge=0.0, le=80.0)


class TaxInput(StrictModel):
    marginal_income_tax_rate: float = Field(0.24, ge=0.06, le=0.495)
    overseas_stock_realized_gain_rate: float = Field(0.0, ge=0.0, le=1.0)
    overseas_realized_loss_krw: float = Field(0.0, ge=0.0)
    external_financial_income_krw: float = Field(0.0, ge=0.0)
    pension_tax_liability_sufficient: bool = True


class OptimizationInput(StrictModel):
    period: str = Field("5y", min_length=2, max_length=8)
    num_simulations: int = Field(5000, ge=500, le=100_000)
    expected_return_haircut: float = Field(0.75, ge=0.0, le=1.0)
    random_seed: int = Field(42, ge=0)
    risk_free_rate: float = Field(0.035, ge=-1.0, le=1.0)
    cash_return: float = Field(0.025, ge=-1.0, le=1.0)
    enable_black_litterman: bool = False
    view_expected_returns: dict[AssetKey, float] | None = None
    view_weight: float = Field(0.35, ge=0.0, le=1.0)


class PortfolioIpsInput(StrictModel):
    total_asset_krw: float = Field(..., gt=0.0)
    target_after_tax_return_rate: float | None = Field(None, ge=0.0, le=1.0)
    age: int | None = Field(None, ge=0, le=120)
    risk_profile: RiskProfile
    investment_horizon_years: int = Field(..., ge=1, le=50)
    tax_sensitivity: TaxSensitivity
    liquidity_need: LiquidityNeed
    unique: UniqueInput = Field(default_factory=UniqueInput)
    tax: TaxInput = Field(default_factory=TaxInput)
    isa: IsaInput = Field(default_factory=IsaInput)
    irp: IrpInput = Field(default_factory=IrpInput)
    optimization: OptimizationInput = Field(default_factory=OptimizationInput)
    client_context: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_unique_amount(self) -> "PortfolioIpsInput":
        if self.unique.need_amount_krw > self.total_asset_krw:
            raise ValueError("unique.need_amount_krw는 total_asset_krw보다 클 수 없습니다.")
        return self


class ScenarioInput(StrictModel):
    base_interest_rate: float = Field(..., ge=-1.0, le=1.0)
    base_fx_rate_krw_per_usd: float = Field(..., gt=0.0)
    stress_interest_rate_shock_rate: float = Field(0.0, ge=-1.0, le=1.0)
    stress_fx_shock_rate: float = Field(0.0, ge=-1.0, le=10.0)
    stress_affects_scoring: bool = False
    rrttllu: dict[str, Any] = Field(default_factory=dict)


class AiInsightCitationInput(StrictModel):
    doc_id: str | None = None
    source_type: str | None = None
    title: str
    published_date: str | None = None
    chunk: str | None = None
    similarity: float | None = None


class ExternalAiInsightInput(StrictModel):
    """다른 팀의 RAG/LLM 출력.

    포트폴리오 API는 이 내용을 새로 생성하지 않는다.
    의미 매핑만 수행하고 추천 비중에는 자동 반영하지 않는다.
    """

    answer: str = Field(..., min_length=1)
    citations: list[AiInsightCitationInput] = Field(default_factory=list)
    as_of: datetime | None = None
    structured_mapping: dict[str, Any] | None = None


class PortfolioCalculationRequest(StrictModel):
    api_version: Literal["portfolio-api-v1"] = "portfolio-api-v1"
    client_id: str | None = None
    consultation_id: str | None = None
    ips: PortfolioIpsInput
    current_portfolio: list[CurrentAllocationItem] = Field(default_factory=list)
    scenario: ScenarioInput
    ai_insight: ExternalAiInsightInput | None = None
    semantic_mapping_enabled: bool = True

    @model_validator(mode="after")
    def validate_current_weights(self) -> "PortfolioCalculationRequest":
        if not self.current_portfolio:
            return self
        total = sum(item.weight_rate for item in self.current_portfolio)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                "current_portfolio.weight_rate 합계는 1.0이어야 합니다. "
                f"현재 합계: {total}"
            )
        assets = [item.asset_class for item in self.current_portfolio]
        if len(assets) != len(set(assets)):
            raise ValueError("current_portfolio에는 같은 asset_class를 중복할 수 없습니다.")
        return self


class BacktestPoint(StrictModel):
    date: str
    value: float
    base_index: float


class AllocationItem(StrictModel):
    asset_class: AssetKey
    name: str
    weight_rate: float = Field(..., ge=0.0, le=1.0)


class BenchmarkCatalogItem(StrictModel):
    key: BenchmarkKey
    ticker: str
    label: str
    official_index_series: bool
    proxy_note: str | None = None


class BenchmarkCatalog(StrictModel):
    policy: str
    default_key: BenchmarkKey
    selection_scope: list[Literal["backtest_chart", "beta"]]
    affects_portfolio_recommendation: Literal[False]
    items: list[BenchmarkCatalogItem]


class BenchmarkMetadata(StrictModel):
    key: BenchmarkKey
    ticker: str
    label: str
    official_index_series: bool
    proxy_note: str | None = None
    policy: str | None = None
    available: bool
    reason: str | None = None
    data_start: str | None = None
    data_end: str | None = None
    observations: int | None = None
    common_data_start: str | None = None
    common_data_end: str | None = None
    common_observations: int | None = None


class BenchmarkResult(StrictModel):
    metadata: BenchmarkMetadata
    series: list[BacktestPoint]
    beta: float | None = None


class PortfolioMetrics(StrictModel):
    expected_return_rate: float
    volatility_rate: float
    sharpe_ratio: float
    sortino_ratio: float
    mdd_rate: float
    after_tax_return_rate: float
    beta_by_benchmark: dict[BenchmarkKey, float | None]


class PortfolioMoneyMetrics(StrictModel):
    total_asset_krw: float
    expected_return_amount_krw: float
    after_tax_return_amount_krw: float
    mdd_amount_krw: float
    volatility_band_amount_krw: float


class TaxWaterfall(StrictModel):
    gross_return_krw: float
    dividend_interest_tax_krw: float
    capital_gains_tax_krw: float
    after_tax_profit_krw: float


class PortfolioTaxResult(StrictModel):
    waterfall: TaxWaterfall
    saved_vs_current_krw: float
    summary: str


class PortfolioResult(StrictModel):
    kind: PortfolioKind
    rank: int | None
    label: str
    badge: str | None
    allocation: list[AllocationItem]
    metrics: PortfolioMetrics
    metrics_krw: PortfolioMoneyMetrics
    backtest: list[BacktestPoint]
    benchmarks: dict[BenchmarkKey, BenchmarkResult]
    tax: PortfolioTaxResult
    selection_summary: dict[str, Any]


class TargetReturnResult(StrictModel):
    annual_after_tax_rate: float | None
    source: Literal["ips.target_after_tax_return_rate", "not_provided"]


class SemanticMappingResult(StrictModel):
    unique: dict[str, Any]
    ai_insight: dict[str, Any]


class PortfolioCalculationResponse(StrictModel):
    api_version: Literal["portfolio-api-v1"]
    client_id: str | None
    consultation_id: str
    calculation_session_id: str
    as_of: datetime
    risk_profile: RiskProfile
    risk_profile_label: str
    target_after_tax_return: TargetReturnResult
    benchmark_catalog: BenchmarkCatalog
    portfolios: list[PortfolioResult]
    search_summary: dict[str, Any]
    scenario_summary: dict[str, Any]
    semantic_mapping: SemanticMappingResult
    data_snapshot: dict[str, Any]
    methodology: dict[str, Any]
    notes: list[str]


class AssetConfig(StrictModel):
    label: str
    ticker: str
    duration_years: float
    income_taxable_asset: bool
    cash_like_asset: bool
    stock_asset: bool
    bond_cash_asset: bool
    alternative_asset: bool
    fx_sensitive_asset: bool
    overseas_capital_gain_asset: bool
    income_yield_assumption: float | None = None


class ApiMethodCatalog(StrictModel):
    get: list[str]
    post: list[str]


class UnitContract(StrictModel):
    money: Literal["KRW"]
    rates: Literal["decimal"]
    weights: Literal["decimal"]
    examples: dict[str, str]


class PortfolioConfigResponse(StrictModel):
    api_version: Literal["portfolio-api-v1"]
    assets: dict[AssetKey, AssetConfig]
    guidelines: dict[str, Any]
    benchmarks: BenchmarkCatalog
    methods: ApiMethodCatalog
    units: UnitContract
