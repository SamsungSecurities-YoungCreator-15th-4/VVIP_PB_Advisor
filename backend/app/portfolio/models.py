# ruff: noqa: E501
"""포트폴리오 계산 엔진 요청/응답 Pydantic 모델(§3). 모듈 분할 2단계로 분리."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .constants import (
    DEFAULT_BENCHMARK_KEY,
    DEFAULT_CASH_RETURN,
    DEFAULT_RANDOM_SEED,
    DEFAULT_RISK_FREE_RATE,
    IRP_PENSION_COMBINED_TAX_CREDIT_LIMIT,
    IRP_TAX_CREDIT_RATE_HIGH_INCOME,
    IRP_TAX_CREDIT_RATE_LOW_INCOME,
    ISA_MANDATORY_HOLDING_YEARS,
    ISA_TOTAL_CONTRIBUTION_LIMIT,
    BenchmarkKey,
)


# ============================================================
# 3. Request Models
# ============================================================


class IPSRequest(BaseModel):
    total_asset: float = Field(..., gt=0)
    unique_need_amount: float = Field(..., ge=0)
    unique_asset: str = Field(...)
    # Unique는 더 이상 특정 자산 하나만 의미하지 않는다.
    # 자연어/dict/list 원문은 unique_profile에 보존하고,
    # 현재 엔진이 해석 가능한 필요자금·ISA·IRP 정보만 결정론적으로 반영한다.
    unique_items: List[Dict[str, Any]] = Field(default_factory=list)
    unique_profile: Dict[str, Any] = Field(default_factory=dict)
    age: Optional[int] = Field(None, ge=0, le=120)
    client_context: Dict[str, Any] = Field(default_factory=dict)
    # RRTTLLU.Return은 퍼센트 단위다. 예: 8.0 -> 내부 비교값 0.08
    target_after_tax_return: Optional[float] = Field(None, gt=0.0, le=1.0)

    risk_profile: Literal["conservative", "balanced", "aggressive"] = Field(...)
    investment_horizon_years: int = Field(..., ge=1, le=50)
    # Tax는 STT 자유 텍스트를 원문+결정론적 tax_profile로 보존한다.
    # tax_sensitivity는 기존 AnalysisRequest 하위 호환용이며 STT 경로에서는 사용하지 않는다.
    tax_text: str = Field("")
    tax_profile: Dict[str, Any] = Field(default_factory=dict)
    tax_sensitivity: Optional[Literal["low", "medium", "high"]] = Field(None)
    liquidity_need: Literal["low", "mid", "high"] = Field(...)

    current_weights: Optional[Dict[str, float]] = Field(None)

    risk_free_rate: float = Field(DEFAULT_RISK_FREE_RATE)
    cash_return: float = Field(DEFAULT_CASH_RETURN)
    period: str = Field("5y")
    benchmark_key: BenchmarkKey = Field(DEFAULT_BENCHMARK_KEY)

    num_simulations: int = Field(5000, ge=500, le=100000)
    expected_return_haircut: float = Field(0.75, ge=0.0, le=1.0)
    random_seed: int = Field(DEFAULT_RANDOM_SEED, ge=0)

    enable_black_litterman: bool = Field(False)
    view_expected_returns: Optional[Dict[str, float]] = Field(None)
    view_weight: float = Field(0.35, ge=0.0, le=1.0)

    marginal_income_tax_rate: float = Field(0.24, ge=0.06, le=0.495)
    overseas_stock_realized_gain_rate: float = Field(0.0, ge=0.0, le=1.0)
    overseas_realized_loss: float = Field(0.0, ge=0)
    overseas_realized_gain_krw: Optional[float] = Field(
        None,
        ge=0,
        description="발화/구조화 입력에서 명시된 해외주식 실현이익(원). 없으면 기존 realized_gain_rate 추정을 사용",
    )
    # 외부 금융소득 입력은 단위 혼동을 막기 위해 명시형 필드를 우선 사용한다.
    # 우선순위: external_financial_income_krw > external_financial_income_manwon
    #          > other_financial_income(기존 호환, 원 단위).
    other_financial_income: float = Field(
        0.0, ge=0, description="기존 호환 필드: 현재 포트폴리오 외 연 이자·배당 금융소득(원)"
    )
    external_financial_income_krw: Optional[float] = Field(
        None, ge=0, description="현재 포트폴리오 외 연 이자·배당 금융소득(원)"
    )
    external_financial_income_manwon: Optional[float] = Field(
        None, ge=0, description="현재 포트폴리오 외 연 이자·배당 금융소득(만원)"
    )
    pension_tax_liability_sufficient: bool = Field(True)

    isa_enabled: bool = Field(True)
    isa_type: Literal["general", "seogmin"] = Field("general")
    isa_account_exists: bool = Field(False)
    isa_account_age_years: float = Field(0.0, ge=0, le=50)
    isa_cumulative_contribution: float = Field(0.0, ge=0)
    isa_current_year_contribution: float = Field(0.0, ge=0)
    isa_recent_3yr_comprehensive_taxed: bool = Field(False)
    isa_existing_account_usable: bool = Field(True)
    isa_remaining_capacity: float = Field(ISA_TOTAL_CONTRIBUTION_LIMIT, ge=0)
    isa_remaining_capacity_override: Optional[float] = Field(None, ge=0)
    isa_years_until_liquid: float = Field(ISA_MANDATORY_HOLDING_YEARS, ge=0, le=50)

    irp_enabled: bool = Field(True)
    irp_eligible: bool = Field(True)
    irp_account_exists: bool = Field(False)
    irp_account_age_years: float = Field(0.0, ge=0, le=80)
    irp_cumulative_contribution: float = Field(0.0, ge=0)
    irp_current_year_contribution: float = Field(0.0, ge=0)
    irp_remaining_tax_credit_capacity: float = Field(
        IRP_PENSION_COMBINED_TAX_CREDIT_LIMIT, ge=0
    )
    irp_remaining_tax_credit_capacity_override: Optional[float] = Field(None, ge=0)
    irp_tax_credit_rate: float = Field(
        IRP_TAX_CREDIT_RATE_HIGH_INCOME, ge=0.0, le=IRP_TAX_CREDIT_RATE_LOW_INCOME
    )
    irp_years_until_access: float = Field(0.0, ge=0, le=80)


class ScenarioRequest(BaseModel):
    base_interest_rate: float = Field(...)
    base_fx_rate_krw_per_usd: float = Field(..., gt=0)

    stress_interest_rate_shock: float = Field(...)
    stress_fx_shock: float = Field(...)

    # 다경님 쪽 시나리오 테스트에서 넘어오는 값.
    # 구조가 아직 확정되지 않았으므로 dict로 받아 프론트/타 팀과 유연하게 연결.
    rrttllu: Dict[str, Any] = Field(...)

    # false: 스트레스 결과는 표시만 하고 추천 점수에는 미반영
    # true: 스트레스 손실이 큰 포트폴리오를 점수에서 감점
    stress_affects_scoring: bool = Field(False)


class PortfolioCalculateResponse(BaseModel):
    client_id: Optional[str] = None
    consultation_id: str
    calculation_session_id: str
    as_of: str
    risk_profile: str
    risk_profile_label: str
    portfolios: List[Dict[str, Any]]
    search_summary: Dict[str, Any]
    scenario_summary: Dict[str, Any]
    data_snapshot: Dict[str, Any]
    input_adapter: Dict[str, Any]
    methodology: Dict[str, Any]
    notes: List[str]


class PortfolioStressTestResponse(BaseModel):
    consultation_id: str
    calculation_session_id: str
    as_of: str
    risk_profile: str
    risk_profile_label: str
    portfolios: List[Dict[str, Any]]
    scenario_summary: Dict[str, Any]
    data_snapshot: Dict[str, Any]
    input_adapter: Dict[str, Any]


class AnalysisRequest(BaseModel):
    ips: IPSRequest = Field(...)
    scenario: ScenarioRequest = Field(...)


# 기존 /analyze 호환용
class PortfolioRequest(BaseModel):
    total_asset: float = Field(..., gt=0)
    unique_need_amount: float = Field(0, ge=0)
    unique_asset: str = Field("general_bond")
    unique_items: List[Dict[str, Any]] = Field(default_factory=list)
    unique_profile: Dict[str, Any] = Field(default_factory=dict)
    age: Optional[int] = Field(None, ge=0, le=120)
    client_context: Dict[str, Any] = Field(default_factory=dict)
    # RRTTLLU.Return은 퍼센트 단위다. 예: 8.0 -> 내부 비교값 0.08
    target_after_tax_return: Optional[float] = Field(None, gt=0.0, le=1.0)
    risk_profile: Literal["conservative", "balanced", "aggressive"] = Field(...)
    investment_horizon_years: int = Field(10, ge=1, le=50)
    tax_text: str = Field("")
    tax_profile: Dict[str, Any] = Field(default_factory=dict)
    tax_sensitivity: Optional[Literal["low", "medium", "high"]] = Field(None)
    liquidity_need: Literal["low", "mid", "high"] = Field("mid")
    current_weights: Optional[Dict[str, float]] = Field(None)

    risk_free_rate: float = Field(DEFAULT_RISK_FREE_RATE)
    cash_return: float = Field(DEFAULT_CASH_RETURN)
    period: str = Field("5y")
    benchmark_key: BenchmarkKey = Field(DEFAULT_BENCHMARK_KEY)
    num_simulations: int = Field(5000, ge=500, le=100000)
    expected_return_haircut: float = Field(0.75, ge=0.0, le=1.0)
    random_seed: int = Field(DEFAULT_RANDOM_SEED, ge=0)

    enable_black_litterman: bool = Field(False)
    view_expected_returns: Optional[Dict[str, float]] = Field(None)
    view_weight: float = Field(0.35, ge=0.0, le=1.0)

    stress_interest_rate_shock: float = Field(0.01)
    stress_fx_shock: float = Field(0.10)
    stress_affects_scoring: bool = Field(False)

    marginal_income_tax_rate: float = Field(0.24, ge=0.06, le=0.495)
    overseas_stock_realized_gain_rate: float = Field(0.0, ge=0.0, le=1.0)
    overseas_realized_loss: float = Field(0.0, ge=0)
    overseas_realized_gain_krw: Optional[float] = Field(
        None,
        ge=0,
        description="발화/구조화 입력에서 명시된 해외주식 실현이익(원). 없으면 기존 realized_gain_rate 추정을 사용",
    )
    # 외부 금융소득 입력은 단위 혼동을 막기 위해 명시형 필드를 우선 사용한다.
    # 우선순위: external_financial_income_krw > external_financial_income_manwon
    #          > other_financial_income(기존 호환, 원 단위).
    other_financial_income: float = Field(
        0.0, ge=0, description="기존 호환 필드: 현재 포트폴리오 외 연 이자·배당 금융소득(원)"
    )
    external_financial_income_krw: Optional[float] = Field(
        None, ge=0, description="현재 포트폴리오 외 연 이자·배당 금융소득(원)"
    )
    external_financial_income_manwon: Optional[float] = Field(
        None, ge=0, description="현재 포트폴리오 외 연 이자·배당 금융소득(만원)"
    )
    pension_tax_liability_sufficient: bool = Field(True)

    isa_enabled: bool = Field(True)
    isa_type: Literal["general", "seogmin"] = Field("general")
    isa_account_exists: bool = Field(False)
    isa_account_age_years: float = Field(0.0, ge=0, le=50)
    isa_cumulative_contribution: float = Field(0.0, ge=0)
    isa_current_year_contribution: float = Field(0.0, ge=0)
    isa_recent_3yr_comprehensive_taxed: bool = Field(False)
    isa_existing_account_usable: bool = Field(True)
    isa_remaining_capacity: float = Field(ISA_TOTAL_CONTRIBUTION_LIMIT, ge=0)
    isa_remaining_capacity_override: Optional[float] = Field(None, ge=0)
    isa_years_until_liquid: float = Field(ISA_MANDATORY_HOLDING_YEARS, ge=0, le=50)

    irp_enabled: bool = Field(True)
    irp_eligible: bool = Field(True)
    irp_account_exists: bool = Field(False)
    irp_account_age_years: float = Field(0.0, ge=0, le=80)
    irp_cumulative_contribution: float = Field(0.0, ge=0)
    irp_current_year_contribution: float = Field(0.0, ge=0)
    irp_remaining_tax_credit_capacity: float = Field(
        IRP_PENSION_COMBINED_TAX_CREDIT_LIMIT, ge=0
    )
    irp_remaining_tax_credit_capacity_override: Optional[float] = Field(None, ge=0)
    irp_tax_credit_rate: float = Field(
        IRP_TAX_CREDIT_RATE_HIGH_INCOME, ge=0.0, le=IRP_TAX_CREDIT_RATE_LOW_INCOME
    )
    irp_years_until_access: float = Field(0.0, ge=0, le=80)
