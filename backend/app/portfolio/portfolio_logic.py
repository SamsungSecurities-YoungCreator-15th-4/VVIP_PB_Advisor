# ruff: noqa: E501
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal, Tuple, Any
import uuid
import logging
import re
import numpy as np

# ── 분할: 상수·기준표 → constants.py, 자산군 정의 → assets.py 로 이동.
#    외부 importer(테스트·tax_advice 등) 호환을 위해 여기서 re-export 한다.
from .constants import (  # noqa: F401
    TRADING_DAYS,
    SORTINO_NO_DOWNSIDE_CAP,
    MIN_COMMON_PRICE_OBSERVATIONS,
    MAX_SESSION_REQUEST_STORE_SIZE,
    BACKTEST_BASE_INDEX,
    SEPARATE_TAX_BOND_MIN_HOLDING_YEARS,
    VOL_STRESS_BETA,
    VOL_STRESS_CAP,
    DEFAULT_RANDOM_SEED,
    MONTE_CARLO_METRIC_RANGE_VERSION,
    MONTE_CARLO_METRIC_RANGE_SIMULATIONS,
    MONTE_CARLO_METRIC_RANGE_MAX_HORIZON_YEARS,
    MONTE_CARLO_METRIC_RANGE_STEPS_PER_YEAR,
    MONTE_CARLO_METRIC_RANGE_SEED_OFFSET,
    MONTE_CARLO_METRIC_RANGE_PERCENTILES,
    MONTE_CARLO_METRIC_RANGE_DISPLAY_LOWER,
    MONTE_CARLO_METRIC_RANGE_DISPLAY_CENTER,
    MONTE_CARLO_METRIC_RANGE_DISPLAY_UPPER,
    MIN_BETA_OBSERVATIONS,
    PORTFOLIO_B_MIN_WEIGHT_DISTANCE,
    PRICE_SNAPSHOT_VERSION,
    PRICE_SNAPSHOT_DIR,
    PRICE_SNAPSHOT_PATH,
    _PRICE_SNAPSHOT_LOCK,
    BenchmarkKey,
    DEFAULT_BENCHMARK_KEY,
    BENCHMARK_POLICY_VERSION,
    BENCHMARK_CONFIGS,
    BENCHMARK_SERIES_KEYS,
    PENSION_RECEIVE_AGE,
    DEFAULT_RISK_FREE_RATE,
    DEFAULT_CASH_RETURN,
    FINANCIAL_INCOME_COMPREHENSIVE_TAX_THRESHOLD,
    OVERSEAS_STOCK_GAIN_DEDUCTION,
    OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE,
    DEFAULT_WITHHOLDING_TAX_RATE,
    ISA_GENERAL_TAX_FREE_LIMIT,
    ISA_SEOGMIN_TAX_FREE_LIMIT,
    ISA_LOW_TAX_RATE,
    ISA_MANDATORY_HOLDING_YEARS,
    ISA_ANNUAL_CONTRIBUTION_LIMIT,
    ISA_TOTAL_CONTRIBUTION_LIMIT,
    IRP_PENSION_COMBINED_TAX_CREDIT_LIMIT,
    IRP_TAX_CREDIT_RATE_HIGH_INCOME,
    IRP_TAX_CREDIT_RATE_LOW_INCOME,
    TAX_RULE_TABLE_VERSION,
    TAX_RULE_EFFECTIVE_DATE,
    TAX_RULE_TABLE,
    SECOND_PORTFOLIO_MAX_CORRELATION,
    GUIDELINE_RULES,
    SELECTION_RISK_CONTROLS,
    SELECTION_RANKING_BASIS,
)
from .assets import (  # noqa: F401
    ASSET_TICKERS,
    ASSET_NAMES_KR,
    LEGACY_ASSET_ALIASES,
    UNIQUE_ASSETS,
    STOCK_ASSETS,
    OVERSEAS_STOCK_CAPITAL_GAIN_ASSETS,
    OVERSEAS_STOCK_ASSETS,
    BOND_ASSETS,
    BOND_CASH_ASSETS,
    ALTERNATIVE_ASSETS,
    CASH_LIKE_ASSETS,
    INCOME_TAXABLE_ASSETS,
    ASSET_INCOME_YIELD_ASSUMPTIONS,
    ISA_PRIORITY_ASSETS,
    IRP_PRIORITY_ASSETS,
    ASSET_DURATION_YEARS,
    INTEREST_RATE_SENSITIVE_ASSETS,
    FX_SENSITIVE_ASSETS,
    CLIENT_RISK_LEVEL,
    RISK_LEVEL_NAME,
)
# ── 분할 2단계: 요청/응답 모델 → models.py, 기본 유틸 → utils.py 로 이동.
from .models import (  # noqa: F401
    IPSRequest,
    ScenarioRequest,
    PortfolioCalculateResponse,
    PortfolioStressTestResponse,
    AnalysisRequest,
    PortfolioRequest,
)
from .utils import (  # noqa: F401
    SESSION_REQUEST_STORE,
    model_to_dict,
    canonicalize_asset_key,
    canonicalize_weights,
    canonicalize_asset_return_map,
    validate_unique_asset,
    validate_weights,
    validate_required_assets_available,
    normalize_weights,
    get_default_current_weights,
    cap01,
    safe_float,
    safe_round,
    normalize_target_after_tax_return,
    get_benchmark_config,
    get_benchmark_catalog,
    attach_benchmark_returns,
    save_session_request,
    public_http_exception,
    convert_analysis_to_portfolio_request,
)
# ── 분할 re-export (호환 유지)
from .prices import (  # noqa: F401
    _empty_benchmark_snapshot,
    download_benchmark_returns,
    _price_snapshot_key,
    _read_price_snapshot_store,
    _frame_to_snapshot_payload,
    _snapshot_payload_to_frame,
    _save_price_frame_snapshot,
    _load_price_frame_snapshot,
    _apply_live_data_metadata,
    _apply_cached_data_metadata,
    _download_price_data_live,
    download_price_data,
    _download_backtest_price_data_live,
    download_backtest_price_data,
    calculate_daily_returns,
)
from .expected_returns import (  # noqa: F401
    calculate_expected_returns,
)
# ── 분할 re-export (호환 유지)
from .tax_accounts import (  # noqa: F401
    get_common_tax_rules,
    estimate_income_profit_for_asset,
    estimate_overseas_capital_gain_profit_for_asset,
    estimate_taxable_financial_income,
    resolve_external_financial_income_krw,
    calculate_financial_income_comprehensive_tax_status,
    estimate_overseas_stock_capital_gains_tax,
    calculate_isa_status,
    calculate_irp_status,
    allocate_account_buckets,
    estimate_tax_saving_effect,
    calculate_six_strategy_tax_model,
    calculate_after_tax_return,
)
# ── 분할 re-export (호환 유지)
from .metrics import (  # noqa: F401
    calculate_mdd,
    build_portfolio_benchmark,
    align_portfolio_and_benchmark_returns,
    calculate_benchmark_comparisons,
    calculate_beta,
    calculate_sortino,
    calculate_historical_var,
    calculate_risk_contribution,
    evaluate_selection_risk_controls,
    calculate_asset_group_weights,
    calculate_portfolio_duration,
    target_duration_by_horizon,
    calculate_duration_fit_score,
    calculate_isa_locked_amount,
    calculate_liquidity_coverage,
    calculate_stress_test,
    _vol_multiplier,
    derive_asset_shocks_from_macro,
    CRISIS_SCENARIO_SHOCKS,
    resolve_scenario_shocks,
    apply_return_shocks,
    shift_expected_returns,
    _nearest_positive_semidefinite,
    _metric_percentile_payload,
    _effective_tax_rate_from_breakdown,
    calculate_monte_carlo_metric_ranges,
    calculate_metric_amounts,
    calculate_metrics,
    calculate_cumulative_returns,
    calculate_benchmark_cumulative_returns,
    calculate_all_benchmark_cumulative_returns,
    evaluate_guideline_detail,
    check_guideline,
    classify_portfolio_by_guidelines,
    is_suitable_for_client,
)
# ── 분할 re-export (호환 유지)
from .generation import (  # noqa: F401
    is_separate_tax_bond_allowed,
    get_effective_unique_asset,
    get_recommendation_eligible_assets,
    build_constraint_warnings,
    generate_random_weights,
    apply_unique_constraint,
    build_selection_rank_tuple,
    build_portfolio_b_rank_tuple,
    build_portfolio_b_fallback_rank_tuple,
    build_selection_summary,
    calculate_portfolio_return_series,
    calculate_portfolio_return_correlation,
    calculate_weight_distance,
    find_recommended_portfolios,
)
from .responses import (  # noqa: F401
    build_guideline_report,
    build_portfolio_response,
    build_asset_summary,
    get_guideline_definition,
    extract_backtest_payload,
    build_isa_tax_card,
    build_irp_tax_card,
    build_taxable_account_card,
    TAX_STRATEGY_META,
    build_tax_strategy_reason,
    build_six_tax_strategy_cards,
    build_tax_optimizer_payload,
    build_tax_optimizer_map,
    extract_tax_inputs_payload,
)


router = APIRouter(tags=["portfolio"])
logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")


# ============================================================
# 12. 전체 분석 실행
# ============================================================


def run_analysis_core(request: PortfolioRequest) -> Dict[str, Any]:
    if request.unique_need_amount > request.total_asset:
        raise ValueError("Unique 필요금액은 총자산보다 클 수 없습니다.")

    request.unique_asset = validate_unique_asset(request.unique_asset)
    constraint_warnings = build_constraint_warnings(request)
    request.unique_asset = get_effective_unique_asset(request)
    request.current_weights = canonicalize_weights(request.current_weights)
    request.view_expected_returns = canonicalize_asset_return_map(request.view_expected_returns)

    prices = download_price_data(
        period=request.period,
        cash_return=request.cash_return,
    )
    data_snapshot = prices.attrs.get("data_snapshot", {})

    returns = calculate_daily_returns(prices)
    cov_matrix = returns.cov() * TRADING_DAYS

    expected_returns = calculate_expected_returns(
        returns=returns,
        expected_return_haircut=request.expected_return_haircut,
        enable_black_litterman=request.enable_black_litterman,
        view_expected_returns=request.view_expected_returns,
        view_weight=request.view_weight,
    )

    backtest_prices = download_backtest_price_data(
        period="5y",
        cash_return=request.cash_return,
    )
    backtest_data_snapshot = backtest_prices.attrs.get("data_snapshot", {})
    backtest_returns = calculate_daily_returns(backtest_prices)

    benchmark_returns, benchmark_snapshot = download_benchmark_returns(
        period=request.period,
    )
    if request.period == "5y":
        backtest_benchmark_returns = benchmark_returns
        backtest_benchmark_snapshot = benchmark_snapshot
    else:
        (
            backtest_benchmark_returns,
            backtest_benchmark_snapshot,
        ) = download_benchmark_returns(period="5y")

    analysis_returns = attach_benchmark_returns(
        returns,
        benchmark_returns,
    )
    analysis_backtest_returns = attach_benchmark_returns(
        backtest_returns,
        backtest_benchmark_returns,
    )

    data_snapshot = {
        **data_snapshot,
        "benchmarks": benchmark_snapshot,
    }
    backtest_data_snapshot = {
        **backtest_data_snapshot,
        "benchmarks": backtest_benchmark_snapshot,
    }

    validate_required_assets_available(
        {request.unique_asset: 1.0},
        list(returns.columns),
        "unique_asset",
    )

    if request.current_weights is None:
        current_weights = get_default_current_weights()
    else:
        validate_weights(request.current_weights)
        validate_required_assets_available(
            request.current_weights,
            list(returns.columns),
            "current_weights",
        )
        current_weights = normalize_weights(request.current_weights)

    recommendations, search_summary = find_recommended_portfolios(
        returns=returns,
        expected_returns=expected_returns,
        request=request,
        cov_matrix=cov_matrix,
    )

    current_response = build_portfolio_response(
        name="현재 포트폴리오",
        api_key="current",
        weights=current_weights,
        returns=analysis_returns,
        expected_returns=expected_returns,
        request=request,
        cov_matrix=cov_matrix,
        backtest_returns=analysis_backtest_returns,
    )

    rec_1_response = build_portfolio_response(
        name="포트폴리오 A",
        api_key="portfolio_a",
        weights=recommendations[0]["weights"],
        returns=analysis_returns,
        expected_returns=expected_returns,
        request=request,
        selection_summary=recommendations[0]["selection_summary"],
        cov_matrix=cov_matrix,
        backtest_returns=analysis_backtest_returns,
    )

    rec_2_response = build_portfolio_response(
        name="포트폴리오 B",
        api_key="portfolio_b",
        weights=recommendations[1]["weights"],
        returns=analysis_returns,
        expected_returns=expected_returns,
        request=request,
        selection_summary=recommendations[1]["selection_summary"],
        correlation_with_recommended_1=recommendations[1].get("correlation_with_recommended_1"),
        cov_matrix=cov_matrix,
        backtest_returns=analysis_backtest_returns,
    )

    correlation_matrix = returns.corr().round(4).to_dict()
    asset_summary = build_asset_summary(returns, expected_returns)

    unique_ratio = request.unique_need_amount / request.total_asset

    return {
        "input_summary": {
            "total_asset": request.total_asset,
            "unique_need_amount": request.unique_need_amount,
            "unique_ratio": safe_round(unique_ratio, 6),
            "unique_asset": request.unique_asset,

"comparison_basis": {
    "same_analysis_return_matrix": True,
    "same_expected_return_assumptions": True,
    "same_covariance_matrix": True,
    "same_tax_assumptions": True,
    "same_risk_free_rate": True,
    "same_cash_return": True,
    "analysis_period_requested": (
        request.period
    ),
    "analysis_data_start": (
        data_snapshot.get(
            "data_start"
        )
    ),
    "analysis_data_end": (
        data_snapshot.get(
            "data_end"
        )
    ),
    "backtest_period": "5y",
    "same_backtest_return_matrix": True,
    "backtest_data_start": (
        backtest_data_snapshot.get(
            "data_start"
        )
    ),
    "backtest_data_end": (
        backtest_data_snapshot.get(
            "data_end"
        )
    ),
    "compared_portfolios": [
        "current",
        "portfolio_a",
        "portfolio_b",
    ],
},
            "unique_asset_label": ASSET_NAMES_KR[request.unique_asset],
            "unique_items": request.unique_items,
            "unique_profile": request.unique_profile,
            "age": request.age,
            "client_context": request.client_context,
            "target_after_tax_return": request.target_after_tax_return,
            "analysis_scope": request.client_context.get(
                "calculation_scope",
                "개인 투자포트폴리오 계산",
            ),
            "unique_engine_note": (
                "Unique 원문은 보존하되 LLM 없이 결정론적 규칙으로 "
                "금액·시점·ISA·IRP 및 범용 법인/승계 플래그만 반영합니다."
            ),
            "risk_profile": request.risk_profile,
            "client_risk_level": CLIENT_RISK_LEVEL[request.risk_profile],
            "investment_horizon_years": request.investment_horizon_years,
            "tax_sensitivity": request.tax_sensitivity,
            "liquidity_need": request.liquidity_need,
            "risk_free_rate": request.risk_free_rate,
            "risk_free_rate_basis": "미국 기준 무위험이자율. 시나리오 테스트 금리와 분리.",
            "cash_return": request.cash_return,
            "period": request.period,
            "benchmark_key": request.benchmark_key,
            "benchmark_catalog": get_benchmark_catalog(),
            "backtest_period": "5y",
            "num_simulations": request.num_simulations,
            "random_seed": request.random_seed,
            "expected_return_haircut": request.expected_return_haircut,
            "enable_black_litterman": request.enable_black_litterman,
            "view_expected_returns": request.view_expected_returns,
            "view_weight": request.view_weight,
            "stress_interest_rate_shock": request.stress_interest_rate_shock,
            "stress_fx_shock": request.stress_fx_shock,
            "stress_affects_scoring": request.stress_affects_scoring,
            "marginal_income_tax_rate": request.marginal_income_tax_rate,
            "overseas_stock_realized_gain_rate": request.overseas_stock_realized_gain_rate,
            "overseas_realized_loss": request.overseas_realized_loss,
            "other_financial_income": request.other_financial_income,
            "external_financial_income_krw": resolve_external_financial_income_krw(
                request
            ),
            "external_financial_income_manwon": safe_round(
                resolve_external_financial_income_krw(request) / 10_000, 0
            ),
            "pension_tax_liability_sufficient": request.pension_tax_liability_sufficient,
            "isa_enabled": request.isa_enabled,
            "isa_type": request.isa_type,
            "isa_account_exists": request.isa_account_exists,
            "isa_account_age_years": request.isa_account_age_years,
            "isa_cumulative_contribution": request.isa_cumulative_contribution,
            "isa_current_year_contribution": request.isa_current_year_contribution,
            "isa_recent_3yr_comprehensive_taxed": (
                request.isa_recent_3yr_comprehensive_taxed
            ),
            "isa_remaining_capacity": request.isa_remaining_capacity,
            "isa_remaining_capacity_override": request.isa_remaining_capacity_override,
            "isa_years_until_liquid": request.isa_years_until_liquid,
            "irp_enabled": request.irp_enabled,
            "irp_eligible": request.irp_eligible,
            "irp_account_exists": request.irp_account_exists,
            "irp_account_age_years": request.irp_account_age_years,
            "irp_cumulative_contribution": request.irp_cumulative_contribution,
            "irp_current_year_contribution": request.irp_current_year_contribution,
            "irp_remaining_tax_credit_capacity": (
                request.irp_remaining_tax_credit_capacity
            ),
            "irp_remaining_tax_credit_capacity_override": (
                request.irp_remaining_tax_credit_capacity_override
            ),
            "irp_tax_credit_rate": request.irp_tax_credit_rate,
            "irp_years_until_access": request.irp_years_until_access,
            "data_snapshot": data_snapshot,
            "backtest_data_snapshot": backtest_data_snapshot,
        },
        "search_summary": {
            **search_summary,
            "constraint_warnings": constraint_warnings,
        },
        "portfolios": {
            "current": current_response,
            "recommended_1": rec_1_response,
            "recommended_2": rec_2_response,
        },
        "correlation_matrix": correlation_matrix,
        "asset_summary": asset_summary,
        "guideline_definition": get_guideline_definition(),
        "methodology": {
            "portfolio_generation": (
                "Monte Carlo 방식으로 후보 포트폴리오 생성. "
                "8th 기본값은 5,000개이며 request.random_seed로 재현 가능."
            ),
            "optimization_basis": "Mean-Variance 기반: 실제 가격 데이터의 기대수익률, 공분산 기반 변동성, Sharpe Ratio 계산.",
            "risk_classification": "변동성, MDD, 유동성 커버리지, 자산구성비중을 hard filter로 사용.",
            "selection_logic": (
                "고객 적합성·유동성·95% Historical VaR·위험기여도 집중도 제한을 "
                "모두 통과한 후보만 추천 대상으로 사용합니다. 포트폴리오 A는 세후수익률 "
                "최대, 포트폴리오 B는 IPS 목표 세후수익률 달성 후 위험집중도 최소를 "
                "목적으로 선정합니다."
            ),
            "duration_logic": "듀레이션은 채권형 자산에만 적용하고 ETF proxy 기준 수치를 사용.",
            "suitability_filter": "포트폴리오 위험등급이 고객 위험성향 이하인 경우만 추천.",
            "liquidity_metric": "현금+일반채/저쿠폰채/분리과세채 금액에서 ISA 의무기간 잠김 금액을 제외한 값 / 단기 필요금액.",
            "tax_logic": (
                "금융소득종합과세 검토액, 해외주식 양도세 추정액, "
                "ISA/IRP 효과를 포트폴리오별로 계산. 배당·이자성 수익과 "
                "가격차익은 간이 분리하여 중복 과세를 피함."
            ),
            "second_portfolio_logic": (
                "포트폴리오 B는 RRTTLLU.Return을 목표 세후수익률로 사용합니다. "
                "목표를 충족한 후보 중 위험기여도 최대 집중도가 가장 낮은 후보를 선택하고, "
                "목표 달성 후보가 없으면 목표 부족 폭이 가장 작은 후보를 선택합니다. "
                "포트폴리오 A와의 상관계수는 선정 조건이 아니라 화면 참고값으로만 제공합니다."
            ),
            "stress_test_logic": "금리 충격은 채권형 자산에만 -듀레이션×금리변화를 적용.",
            "var_erc_logic": "95% historical VaR와 공분산 기반 위험기여도 집중도를 리스크 관리에 반영.",
            "benchmark_beta_logic": (
                "KOSPI, S&P 500, MSCI ACWI 중 PB가 선택한 벤치마크를 표시 기준으로 사용. "
                "세 벤치마크의 베타와 백테스트 비교값은 최종 포트폴리오 확정 후 계산하며, "
                "후보 생성·필터·순위에는 반영하지 않음."
            ),
            "corporate_context_logic": (
                "법인·가업승계 키워드는 범용 advisory flag와 단기 유동성 제약으로만 "
                "반영하며 법인세·기업가치 세액은 개인 포트폴리오 엔진에서 계산하지 않음."
            ),
            "backtest_caution": (
                "추천·기대수익률·위험지표는 실제 가격 데이터만 사용하고, "
                "백테스트 차트만 과제 조건에 따라 5년 구간으로 고정함. "
                "신규 상장 또는 데이터 시작 전 구간은 백테스트 차트에서만 현금 수익률로 대체함."
            ),
        },
        "notes": [
            "본 결과는 정보제공 목적이며 투자 판단과 책임은 투자자 본인에게 있습니다.",
            "기대수익률은 과거 일별 수익률을 연율화한 뒤 보수 조정한 추정값입니다.",
            (
                "세금 계산은 간이 추정입니다. 실제 세액은 전체 소득, "
                "실현손익, 보유계좌, 상품별 요건에 따라 달라집니다."
            ),
            "8th는 임의 scoring weight 합산식을 제거하고 VaR·ERC 기반 리스크 통제를 사용합니다.",
        ],
    }


def run_full_analysis(request: AnalysisRequest) -> Dict[str, Any]:
    session_id = str(uuid.uuid4())

    save_session_request(
        session_id,
        {
            "ips": model_to_dict(request.ips),
            "scenario": model_to_dict(request.scenario),
        },
    )

    portfolio_request = convert_analysis_to_portfolio_request(request)
    core = run_analysis_core(portfolio_request)

    core["session_id"] = session_id
    core["scenario_summary"] = {
        "base_interest_rate": request.scenario.base_interest_rate,
        "base_fx_rate_krw_per_usd": request.scenario.base_fx_rate_krw_per_usd,
        "stressed_interest_rate": request.scenario.base_interest_rate
        + request.scenario.stress_interest_rate_shock,
        "stressed_fx_rate_krw_per_usd": request.scenario.base_fx_rate_krw_per_usd
        * (1 + request.scenario.stress_fx_shock),
        "stress_interest_rate_shock": request.scenario.stress_interest_rate_shock,
        "stress_fx_shock": request.scenario.stress_fx_shock,
        "stress_affects_scoring": request.scenario.stress_affects_scoring,
        "risk_free_rate_used_for_sharpe_sortino": core["input_summary"]["risk_free_rate"],
        "risk_free_rate_note": "Sharpe/Sortino 기준 금리는 scenario.base_interest_rate와 분리됨.",
        "rrttllu": request.scenario.rrttllu,
        "unique_profile": core["input_summary"].get("unique_profile", {}),
    }

    core["backtest"] = extract_backtest_payload(core)
    core["tax_optimizer"] = build_tax_optimizer_map(core, portfolio_request)
    core["tax_inputs"] = extract_tax_inputs_payload(core)

    return core



# ============================================================
# 12-1. API 입력 어댑터
# ============================================================
# 프론트 연동용 보조 로직.
# 검증된 사실: consultations API의 ips_json은 Goal/Asset/Return/Risk/Time/Tax/Liquidity/Legal/Unique
# 형태이고, 포트폴리오 계산 로직은 AnalysisRequest 형태를 사용한다.
# 프로젝트용 처리: /portfolio/calculate는 AnalysisRequest와 consultations 응답/ips_json을 모두 받을 수 있게 정규화한다.

KOREAN_MONEY_UNITS = {
    "억": 100_000_000,
    "만": 10_000,
    "천": 1_000,
}

# 금액·연도 파싱 정규식의 ReDoS 방어 상한. 정상 IPS·상담 텍스트는 이보다 훨씬 짧다.
# 비정상적으로 긴 입력은 잘라 정규식의 위치 재스캔(O(N^2))을 상수 시간으로 묶는다.
_MAX_TEXT_PARSE_LEN = 2000


def parse_amount_krw(value: Any, default: float = 0.0) -> float:
    """숫자, dict, '3억', '2,000만 원' 같은 문자열에서 원화 금액/숫자를 추출한다.

    단위가 없는 숫자 문자열은 그대로 숫자로 본다. 해석할 수 없으면 default를 반환한다.
    """
    if value is None:
        return default

    if isinstance(value, bool):
        return default

    if isinstance(value, (int, float)):
        return safe_float(value, default)

    if isinstance(value, dict):
        for key in (
            "amount",
            "need_amount",
            "unique_need_amount",
            "total_asset",
            "Asset",
            "asset",
            "value",
        ):
            if key in value:
                parsed = parse_amount_krw(value.get(key), default=None)
                if parsed is not None:
                    return parsed
        return default

    text_value = str(value).strip()
    if not text_value:
        return default

    normalized = text_value.replace(",", "")[:_MAX_TEXT_PARSE_LEN]
    total = 0.0
    matched_unit = False
    for number_text, unit in re.findall(r"([0-9]++(?:\.[0-9]++)?)\s*+([억만천])", normalized):
        matched_unit = True
        total += float(number_text) * KOREAN_MONEY_UNITS[unit]

    if matched_unit:
        return float(total)

    number_match = re.search(r"-?[0-9]+(?:\.[0-9]+)?", normalized)
    if number_match:
        return safe_float(number_match.group(0), default)

    return default



def stringify_unique_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            parts.append(f"{key}: {stringify_unique_value(item)}")
        return " | ".join(parts)
    if isinstance(value, list):
        return " | ".join(stringify_unique_value(item) for item in value)
    return str(value)


def find_keyword_window(text: str, keywords: List[str], radius: int = 90) -> str:
    lower_text = text.lower()
    for keyword in keywords:
        index = lower_text.find(keyword.lower())
        if index >= 0:
            start = max(index - radius, 0)
            end = min(index + len(keyword) + radius, len(text))
            return text[start:end]
    return ""



def truncate_at_stop_keywords(text: str, stop_keywords: List[str]) -> str:
    lower_text = text.lower()
    cut_points = [
        lower_text.find(keyword.lower())
        for keyword in stop_keywords
        if lower_text.find(keyword.lower()) > 0
    ]
    if not cut_points:
        return text
    return text[: min(cut_points)]


def find_account_segment(
    text: str,
    keywords: List[str],
    stop_keywords: List[str],
    radius_before: int = 0,
    radius_after: int = 140,
) -> str:
    lower_text = text.lower()
    indexes = [
        lower_text.find(keyword.lower())
        for keyword in keywords
        if lower_text.find(keyword.lower()) >= 0
    ]
    if not indexes:
        return ""

    index = min(indexes)
    start = max(index - radius_before, 0)
    end = min(index + radius_after, len(text))

    stop_indexes = [
        lower_text.find(stop.lower(), index + 1)
        for stop in stop_keywords
        if lower_text.find(stop.lower(), index + 1) > index
    ]
    if stop_indexes:
        end = min(end, min(stop_indexes))

    return text[start:end]


def parse_start_year_from_text(text: str) -> Optional[int]:
    for pattern in (
        r"(19[0-9]{2}|20[0-9]{2})\s*년\s*(?:에\s*)?(?:가입|개설|시작)",
        r"(?:가입|개설|시작)\s*(?:연도|년도)?\s*[:=]?\s*(19[0-9]{2}|20[0-9]{2})",
    ):
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None


def calculate_account_age_years_from_start_year(start_year: Optional[int]) -> float:
    if start_year is None:
        return 0.0
    current_year = datetime.now(KST).year
    return float(max(current_year - int(start_year), 0))


def parse_relative_years_from_text(text: str) -> Optional[float]:
    match = re.search(
        r"([0-9]++(?:\.[0-9]++)?)\s*+년\s*+(?:후|뒤|내|안|이내)",
        text[:_MAX_TEXT_PARSE_LEN],
    )
    if match:
        return safe_float(match.group(1), 0.0)
    return None


def parse_amount_near_keywords(text: str, keywords: List[str]) -> float:
    window = find_keyword_window(text, keywords)
    if not window:
        return 0.0
    return parse_amount_krw(window)



def parse_explicit_money_amount_krw(value: Any) -> float:
    text_value = stringify_unique_value(value).replace(",", "").strip()[:_MAX_TEXT_PARSE_LEN]
    if not text_value:
        return 0.0

    total = 0.0
    matched_unit = False
    for number_text, unit in re.findall(r"([0-9]++(?:\.[0-9]++)?)\s*+([억만천])", text_value):
        matched_unit = True
        total += float(number_text) * KOREAN_MONEY_UNITS[unit]
    if matched_unit:
        return float(total)

    won_match = re.search(r"([0-9]++(?:\.[0-9]++)?)\s*+원", text_value)
    if won_match:
        return safe_float(won_match.group(1), 0.0)

    return 0.0


def parse_current_year_contribution(text: str, keywords: List[str]) -> Optional[float]:
    window = find_keyword_window(text, keywords, radius=120)
    if not window:
        return None

    if re.search(r"(?:올해|금년|당해).{0,30}(?:납입|입금).{0,30}(?:없|무|0원|0\s*원)", window):
        return 0.0
    if re.search(r"(?:납입|입금).{0,30}(?:없|무|0원|0\s*원)", window):
        return 0.0

    current_year_match = re.search(
        r"(?:올해|금년|당해).{0,40}([0-9]++(?:\.[0-9]++)?\s*+[억만천]?)\s*+(?:원)?\s*+(?:납입|입금)",
        window,
    )
    if current_year_match:
        return parse_amount_krw(current_year_match.group(1))

    return None


def contains_negative_account_signal(text: str, keywords: List[str]) -> bool:
    window = find_keyword_window(text, keywords, radius=80)
    if not window:
        return False
    return bool(re.search(r"(?:미가입|없음|없다|안\s*만듦|안\s*만들)", window))



def parse_liquidity_need_amount(unique_value: Any, text: str) -> float:
    """Unique에서 별도 확보해야 하는 유동성 금액만 추출한다.

    ISA/IRP 납입액을 unique_need_amount로 오인하지 않도록,
    주거·전세·생활비·필요자금 등 개인 유동성 신호가 있거나
    명시 key가 있을 때만 우선 추출한다.
    """
    if isinstance(unique_value, dict):
        for key in (
            "unique_need_amount",
            "need_amount",
            "liquidity_need_amount",
            "required_amount",
            "personal_need_amount",
        ):
            if key in unique_value:
                return parse_amount_krw(unique_value.get(key))

    personal_liquidity_keywords = [
        "전세",
        "주거",
        "목돈",
        "필요자금",
        "필요 자금",
        "필요",
        "유동성",
        "생활비",
        "학자금",
        "결혼",
        "병원",
        "긴급",
    ]
    for keyword in personal_liquidity_keywords:
        window = find_keyword_window(text, [keyword], radius=120)
        window = truncate_at_stop_keywords(
            window,
            ["ISA", "isa", "IRP", "irp", "개인종합자산관리", "개인형퇴직연금", "퇴직연금"],
        )
        amount = parse_amount_krw(window)
        if amount > 0:
            return amount

    has_account_info = bool(
        find_keyword_window(text, ["isa", "개인종합자산관리"], radius=30)
        or find_keyword_window(text, ["irp", "개인형퇴직연금", "퇴직연금"], radius=30)
    )
    if has_account_info:
        return 0.0

    return parse_amount_krw(unique_value)


def extract_generic_client_context(unique_value: Any, text: str) -> Dict[str, Any]:
    """Extract only generic, auditable context flags; never persona-name rules."""
    lower = text.lower()
    has_corporation = bool(
        re.search(r"법인|회사\s*대표|기업\s*대표|사업체|오너|경영권", lower)
    )
    estate_succession_goal = bool(
        re.search(r"가업\s*승계|기업\s*승계|상속|증여|후계", lower)
    )
    corporate_liquidity_window = find_keyword_window(
        text, ["법인", "운전자금", "사업자금", "회사 자금"], radius=140
    )
    corporate_liquidity_window = truncate_at_stop_keywords(
        corporate_liquidity_window,
        ["ISA", "isa", "IRP", "irp", "개인종합자산관리", "개인형퇴직연금"],
    )
    corporate_liquidity_need = 0.0
    if corporate_liquidity_window and re.search(
        r"운전자금|사업자금|법인.{0,20}유동성|회사.{0,20}유동성",
        corporate_liquidity_window,
    ):
        corporate_liquidity_need = parse_amount_krw(corporate_liquidity_window)

    flags: List[str] = []
    if has_corporation:
        flags.append("corporate_finance_review_required")
    if estate_succession_goal:
        flags.append("estate_succession_review_required")

    return {
        "has_corporation": has_corporation,
        "estate_succession_goal": estate_succession_goal,
        "corporate_liquidity_need_amount": safe_round(
            corporate_liquidity_need, 0
        ),
        "advisory_flags": flags,
        "calculation_scope": (
            "개인 투자포트폴리오와 명시된 단기 필요자금만 계산. "
            "법인세·기업가치·지분이전 세액은 별도 법인/세무 모듈 검토 대상."
        ),
    }


def extract_unique_profile(unique_value: Any) -> Dict[str, Any]:
    """Unique 원문에서 현재 엔진이 안전하게 해석 가능한 정보만 추출한다.

    LLM을 붙이지 않는 이상 '무엇이든 의미까지 이해'할 수는 없으므로,
    원문은 raw/text로 보존하고 금액·상대시점·ISA·IRP 같은 명시 패턴만 반영한다.
    """
    text = stringify_unique_value(unique_value).strip()
    client_context = extract_generic_client_context(unique_value, text)
    liquidity_amount = parse_liquidity_need_amount(unique_value, text)
    corporate_need = safe_float(
        client_context.get("corporate_liquidity_need_amount")
    )
    # 동일 문구가 일반 유동성 파서와 법인 파서에 동시에 잡힐 수 있어 합산하지 않고
    # 더 큰 명시 금액을 사용한다. 구조화 입력이 있으면 unique_need_amount로 직접 전달한다.
    liquidity_amount = max(liquidity_amount, corporate_need)
    liquidity_years = parse_relative_years_from_text(text)

    isa_window = find_account_segment(
        text,
        ["isa", "개인종합자산관리"],
        ["irp", "개인형퇴직연금", "퇴직연금"],
    )
    irp_window = find_account_segment(
        text,
        ["irp", "개인형퇴직연금", "퇴직연금"],
        ["isa", "개인종합자산관리"],
    )

    isa_start_year = parse_start_year_from_text(isa_window)
    isa_contribution = parse_explicit_money_amount_krw(isa_window) if isa_window else 0.0
    isa_account_exists = bool(isa_window) and not bool(
        re.search(r"(?:(?:ISA|isa|IRP|irp|개인종합자산관리|개인형퇴직연금|퇴직연금)\s*(?:계좌\s*)?(?:없음|없다)|미가입|계좌\s*없|가입.{0,5}안|개설.{0,5}안|안\s*만듦|안\s*만들)", isa_window)
    )

    irp_start_year = parse_start_year_from_text(irp_window)
    irp_current_year_contribution = parse_current_year_contribution(
        irp_window,
        ["irp", "개인형퇴직연금", "퇴직연금"],
    )
    irp_cumulative_contribution = parse_explicit_money_amount_krw(irp_window) if irp_window else 0.0
    irp_account_exists = bool(irp_window) and not bool(
        re.search(r"(?:(?:ISA|isa|IRP|irp|개인종합자산관리|개인형퇴직연금|퇴직연금)\s*(?:계좌\s*)?(?:없음|없다)|미가입|계좌\s*없|가입.{0,5}안|개설.{0,5}안|안\s*만듦|안\s*만들)", irp_window)
    )

    items: List[Dict[str, Any]] = []
    if liquidity_amount > 0:
        items.append(
            {
                "type": "liquidity_need",
                "amount": safe_round(liquidity_amount, 0),
                "years_until_need": safe_round(liquidity_years, 2)
                if liquidity_years is not None
                else None,
                "source": "unique",
            }
        )
    if isa_window:
        items.append(
            {
                "type": "isa_account",
                "account_exists": isa_account_exists,
                "start_year": isa_start_year,
                "account_age_years": safe_round(
                    calculate_account_age_years_from_start_year(isa_start_year),
                    2,
                ),
                "cumulative_contribution": safe_round(isa_contribution, 0),
                "source": "unique",
            }
        )
    if irp_window:
        items.append(
            {
                "type": "irp_account",
                "account_exists": irp_account_exists,
                "start_year": irp_start_year,
                "account_age_years": safe_round(
                    calculate_account_age_years_from_start_year(irp_start_year),
                    2,
                ),
                "cumulative_contribution": safe_round(irp_cumulative_contribution, 0),
                "current_year_contribution": safe_round(
                    irp_current_year_contribution,
                    0,
                )
                if irp_current_year_contribution is not None
                else None,
                "source": "unique",
            }
        )

    if client_context["advisory_flags"]:
        items.append(
            {
                "type": "advisory_context",
                "flags": client_context["advisory_flags"],
                "source": "unique",
            }
        )

    return {
        "raw": unique_value,
        "text": text,
        "items": items,
        "client_context": client_context,
        "liquidity_need_amount": safe_round(liquidity_amount, 0),
        "liquidity_need_years": safe_round(liquidity_years, 2)
        if liquidity_years is not None
        else None,
        "isa": {
            "detected": bool(isa_window),
            "account_exists": isa_account_exists,
            "start_year": isa_start_year,
            "account_age_years": safe_round(
                calculate_account_age_years_from_start_year(isa_start_year),
                2,
            ),
            "cumulative_contribution": safe_round(isa_contribution, 0),
        },
        "irp": {
            "detected": bool(irp_window),
            "account_exists": irp_account_exists,
            "start_year": irp_start_year,
            "account_age_years": safe_round(
                calculate_account_age_years_from_start_year(irp_start_year),
                2,
            ),
            "cumulative_contribution": safe_round(irp_cumulative_contribution, 0),
            "current_year_contribution": safe_round(
                irp_current_year_contribution,
                0,
            )
            if irp_current_year_contribution is not None
            else None,
        },
        "parser_note": (
            "LLM 미사용 규칙 기반 파서. 금액·n년 후·ISA/IRP 가입연도/납입액처럼 "
            "명시된 패턴만 계산 입력에 반영하고, 그 외 자연어는 raw/text로 보존한다."
        ),
    }


def apply_unique_profile_to_ips_payload(
    ips_payload: Dict[str, Any],
    unique_value: Any,
    adapter_warnings: List[str],
) -> Dict[str, Any]:
    profile = extract_unique_profile(unique_value)
    result = dict(ips_payload)

    result["unique_profile"] = {
        **profile,
        **result.get("unique_profile", {}),
    }
    result["unique_items"] = result.get("unique_items") or profile["items"]
    result["client_context"] = {
        **profile.get("client_context", {}),
        **result.get("client_context", {}),
    }

    if safe_float(result.get("unique_need_amount")) <= 0:
        result["unique_need_amount"] = profile["liquidity_need_amount"]

    if not result.get("unique_asset"):
        result["unique_asset"] = normalize_unique_asset_value(unique_value)

    isa_info = profile["isa"]
    if isa_info["detected"]:
        if "isa_account_exists" not in result:
            result["isa_account_exists"] = isa_info["account_exists"]
        if safe_float(result.get("isa_account_age_years")) <= 0:
            result["isa_account_age_years"] = isa_info["account_age_years"]
        if safe_float(result.get("isa_cumulative_contribution")) <= 0:
            result["isa_cumulative_contribution"] = isa_info["cumulative_contribution"]

    irp_info = profile["irp"]
    if irp_info["detected"]:
        if "irp_account_exists" not in result:
            result["irp_account_exists"] = irp_info["account_exists"]
        if safe_float(result.get("irp_account_age_years")) <= 0:
            result["irp_account_age_years"] = irp_info["account_age_years"]
        if safe_float(result.get("irp_cumulative_contribution")) <= 0:
            result["irp_cumulative_contribution"] = irp_info["cumulative_contribution"]
        if irp_info["current_year_contribution"] is not None and safe_float(
            result.get("irp_current_year_contribution")
        ) <= 0:
            result["irp_current_year_contribution"] = irp_info[
                "current_year_contribution"
            ]

    if profile["text"] and not profile["items"]:
        adapter_warnings.append(
            "Unique 원문은 보존했지만 규칙 기반 파서가 계산에 반영할 수 있는 "
            "금액·시점·ISA·IRP 패턴을 찾지 못했습니다."
        )

    return result


def normalize_risk_profile_value(value: Any) -> str:
    text_value = str(value or "").strip().lower()
    mapping = {
        "안정형": "conservative",
        "보수형": "conservative",
        "conservative": "conservative",
        "균형형": "balanced",
        "중립형": "balanced",
        "balanced": "balanced",
        "공격형": "aggressive",
        "적극형": "aggressive",
        "aggressive": "aggressive",
    }
    if text_value in mapping:
        return mapping[text_value]
    raise ValueError(f"투자성향 값을 해석할 수 없습니다: {value}")


def normalize_liquidity_value(value: Any) -> str:
    text_value = str(value or "").strip().lower()
    mapping = {
        "낮음": "low",
        "낮은": "low",
        "low": "low",
        "중간": "mid",
        "보통": "mid",
        "중": "mid",
        "medium": "mid",
        "mid": "mid",
        "높음": "high",
        "높은": "high",
        "high": "high",
    }
    if text_value in mapping:
        return mapping[text_value]
    raise ValueError(f"유동성 값을 해석할 수 없습니다: {value}")


def normalize_tax_sensitivity_value(value: Any) -> str:
    text_value = str(value or "").strip().lower()
    mapping = {
        "낮음": "low",
        "낮은": "low",
        "low": "low",
        "중간": "medium",
        "보통": "medium",
        "중": "medium",
        "mid": "medium",
        "medium": "medium",
        "높음": "high",
        "높은": "high",
        "high": "high",
    }
    if text_value in mapping:
        return mapping[text_value]
    raise ValueError(f"세금 민감도 값을 해석할 수 없습니다: {value}")


def normalize_unique_asset_value(value: Any) -> str:
    if value is None:
        return "cash"

    if isinstance(value, dict):
        for key in ("unique_asset", "asset_class", "asset", "type"):
            if key in value:
                return normalize_unique_asset_value(value.get(key))
        return "cash"

    text_value = str(value).strip()
    canonical = canonicalize_asset_key(text_value)
    if canonical in UNIQUE_ASSETS:
        return canonical

    personal_liquidity_keywords = (
        "전세",
        "주거",
        "목돈",
        "필요",
        "유동성",
        "생활비",
        "학자금",
        "결혼",
        "병원",
        "긴급",
    )
    if any(keyword in text_value for keyword in personal_liquidity_keywords):
        return "cash"
    if "분리" in text_value:
        return "separate_tax_bond"
    if "저쿠폰" in text_value:
        return "low_coupon_bond"
    if "채" in text_value or "국채" in text_value:
        return "general_bond"
    return "cash"


def extract_flat_ips_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """상담 API 응답 또는 ips_json 자체에서 flat IPS dict를 꺼낸다."""
    candidate = payload

    if "ips_json" in candidate and isinstance(candidate["ips_json"], dict):
        candidate = candidate["ips_json"]
    elif "ips" in candidate and isinstance(candidate["ips"], dict):
        candidate = candidate["ips"]

    rrttllu = candidate.get("RRTTLLU")
    if isinstance(rrttllu, dict):
        flattened = {
            "Goal": candidate.get("Goal"),
            "Asset": candidate.get("Asset"),
        }
        flattened.update(rrttllu)
        candidate = flattened

    required_keys = {"Asset", "Risk", "Time", "Tax", "Liquidity"}
    if not required_keys.issubset(candidate.keys()):
        missing = sorted(required_keys - set(candidate.keys()))
        raise ValueError(
            "AnalysisRequest 또는 상담 IPS 형식으로 해석할 수 없습니다. "
            f"필수 IPS 키 누락: {missing}"
        )

    return candidate



def extract_request_metadata(payload: Dict[str, Any]) -> Dict[str, Any]:
    """명세서 ⑤ 요청에서 고객·상담 식별자를 추출한다."""
    client_id = payload.get("client_id") or payload.get("customer_id")
    consultation_id = payload.get("consultation_id")

    nested_consultation = payload.get("consultation")
    if not consultation_id and isinstance(nested_consultation, dict):
        consultation_id = nested_consultation.get("consultation_id")

    return {
        "client_id": str(client_id) if client_id else None,
        "consultation_id": str(consultation_id) if consultation_id else None,
    }


def extract_current_weights_from_portfolio(
    payload: Dict[str, Any],
    adapter_warnings: List[str],
) -> Optional[Dict[str, float]]:
    """명세서 current_portfolio 배열을 내부 current_weights dict로 변환한다."""
    current_portfolio = payload.get("current_portfolio")

    if current_portfolio is None:
        ips_payload = payload.get("ips")
        if isinstance(ips_payload, dict):
            current_portfolio = ips_payload.get("current_portfolio")

    if current_portfolio is None:
        explicit_weights = payload.get("current_weights")
        if explicit_weights is not None:
            return normalize_weights(explicit_weights)

        ips_payload = payload.get("ips")
        if isinstance(ips_payload, dict) and ips_payload.get("current_weights") is not None:
            return normalize_weights(ips_payload["current_weights"])

        adapter_warnings.append(
            "current_portfolio/current_weights 입력이 없어 현재 포트폴리오는 "
            "현금 100%로 계산했습니다."
        )
        return None

    if not isinstance(current_portfolio, list) or len(current_portfolio) == 0:
        raise ValueError("current_portfolio는 비어 있지 않은 배열이어야 합니다.")

    weights: Dict[str, float] = {}
    total_weight_percent = 0.0

    for item in current_portfolio:
        if not isinstance(item, dict):
            raise ValueError("current_portfolio의 각 항목은 객체여야 합니다.")

        asset_class = item.get("asset_class")
        if asset_class is None:
            raise ValueError("current_portfolio 항목에 asset_class가 필요합니다.")

        asset = canonicalize_asset_key(str(asset_class))
        if asset not in ASSET_TICKERS:
            raise ValueError(f"지원하지 않는 current_portfolio 자산군입니다: {asset_class}")

        weight_percent = safe_float(item.get("weight"), default=np.nan)
        if not np.isfinite(weight_percent) or weight_percent < 0:
            raise ValueError("current_portfolio.weight는 0 이상의 숫자여야 합니다.")

        total_weight_percent += weight_percent
        weights[asset] = weights.get(asset, 0.0) + weight_percent / 100.0

    if abs(total_weight_percent - 100.0) > 1e-6:
        raise ValueError(
            "current_portfolio weight 합계는 100이어야 합니다. "
            f"현재 합계: {total_weight_percent}"
        )

    return normalize_weights(weights)

def extract_optional_age(payload: Dict[str, Any]) -> Optional[int]:
    candidates: List[Any] = [
        payload.get("age"),
        payload.get("customer_age"),
        payload.get("client_age"),
    ]
    for nested_key in ("customer", "client", "persona", "profile", "ips"):
        nested = payload.get(nested_key)
        if isinstance(nested, dict):
            candidates.extend(
                [nested.get("age"), nested.get("customer_age"), nested.get("client_age")]
            )
    for value in candidates:
        if value is None or isinstance(value, bool):
            continue
        match = re.search(r"[0-9]{1,3}", str(value))
        if match:
            age = int(match.group(0))
            if 0 <= age <= 120:
                return age
    return None


def normalize_analysis_request_payload(
    payload: Dict[str, Any],
) -> Tuple[AnalysisRequest, Dict[str, Any]]:
    """명세서 ⑤용 payload를 내부 AnalysisRequest로 정규화한다.

    허용 입력:
    1. 기존 AnalysisRequest: {"ips": {...}, "scenario": {...}}
    2. 상담 API 응답: {"ips_json": {Goal, Asset, ...}, ...}
    3. flat IPS dict: {Goal, Asset, Return, Risk, Time, Tax, Liquidity, Legal, Unique}
    """
    adapter_warnings: List[str] = []
    request_metadata = extract_request_metadata(payload)
    current_weights_from_portfolio = extract_current_weights_from_portfolio(
        payload,
        adapter_warnings,
    )

    has_analysis_ips = (
        "ips" in payload
        and isinstance(payload.get("ips"), dict)
        and "total_asset" in payload["ips"]
    )
    if has_analysis_ips:
        normalized_payload = dict(payload)
        normalized_ips = dict(normalized_payload["ips"])
        normalized_ips["liquidity_need"] = normalize_liquidity_value(
            normalized_ips.get("liquidity_need")
        )
        if current_weights_from_portfolio is not None:
            normalized_ips["current_weights"] = current_weights_from_portfolio
        scenario_payload = normalized_payload.get("scenario")
        rrttllu_payload = (
            scenario_payload.get("rrttllu")
            if isinstance(scenario_payload, dict)
            else {}
        )
        unique_value = (
            normalized_ips.get("Unique")
            or normalized_ips.get("unique")
            or normalized_ips.get("unique_raw")
        )
        if unique_value is None and isinstance(rrttllu_payload, dict):
            unique_value = rrttllu_payload.get("Unique")
        if unique_value is not None:
            normalized_ips = apply_unique_profile_to_ips_payload(
                normalized_ips,
                unique_value,
                adapter_warnings,
            )
        normalized_payload["ips"] = normalized_ips
        return AnalysisRequest(**normalized_payload), {
            "source": "analysis_request",
            "client_id": request_metadata["client_id"],
            "consultation_id": request_metadata["consultation_id"],
            "warnings": adapter_warnings,
        }

    flat_ips = extract_flat_ips_payload(payload)

    total_asset = parse_amount_krw(flat_ips.get("Asset"))
    if total_asset <= 0:
        raise ValueError("IPS의 Asset 값을 총자산으로 해석할 수 없습니다.")

    investment_horizon = int(max(parse_amount_krw(flat_ips.get("Time")), 1))
    unique_value = flat_ips.get("Unique")
    unique_profile = extract_unique_profile(unique_value)
    unique_need_amount = safe_float(unique_profile.get("liquidity_need_amount"))
    if unique_need_amount <= 0:
        adapter_warnings.append(
            "IPS의 Unique 값에서 별도 필요자금을 숫자로 추출하지 못해 unique_need_amount=0으로 계산했습니다."
        )

    scenario_input = payload.get("scenario") if isinstance(payload.get("scenario"), dict) else {}
    if not scenario_input:
        adapter_warnings.append(
            "scenario 입력이 없어 stress shock은 0으로 두고, 기준 금리는 기본 risk_free_rate를 사용했습니다."
        )

    base_fx_rate = safe_float(
        scenario_input.get("base_fx_rate_krw_per_usd", payload.get("base_fx_rate_krw_per_usd")),
        1.0,
    )
    if base_fx_rate == 1.0 and "base_fx_rate_krw_per_usd" not in scenario_input:
        adapter_warnings.append(
            "base_fx_rate_krw_per_usd가 없어 1.0을 표시용 기본값으로 사용했습니다. 스트레스 테스트 화면에서는 실제 환율 입력을 넘겨야 합니다."
        )

    analysis_payload = {
        "ips": {
            "total_asset": total_asset,
            "unique_need_amount": unique_need_amount,
            "unique_asset": normalize_unique_asset_value(unique_value),
            "unique_items": unique_profile["items"],
            "unique_profile": unique_profile,
            "age": extract_optional_age(payload),
            "client_context": unique_profile.get("client_context", {}),
            "target_after_tax_return": normalize_target_after_tax_return(
                flat_ips.get("Return"),
                percent_input=True,
            ),
            "risk_profile": normalize_risk_profile_value(flat_ips.get("Risk")),
            "investment_horizon_years": investment_horizon,
            "tax_sensitivity": normalize_tax_sensitivity_value(flat_ips.get("Tax")),
            "liquidity_need": normalize_liquidity_value(flat_ips.get("Liquidity")),
            "current_weights": current_weights_from_portfolio,
            "risk_free_rate": safe_float(
                scenario_input.get("risk_free_rate", payload.get("risk_free_rate")),
                DEFAULT_RISK_FREE_RATE,
            ),
            "cash_return": safe_float(
                payload.get("cash_return"),
                DEFAULT_CASH_RETURN,
            ),
            "period": str(payload.get("period", "5y")),
            "benchmark_key": payload.get(
                "benchmark_key",
                payload.get("benchmark", DEFAULT_BENCHMARK_KEY),
            ),
            "num_simulations": int(safe_float(payload.get("num_simulations"), 5000)),
            "expected_return_haircut": safe_float(
                payload.get("expected_return_haircut"),
                0.75,
            ),
            "random_seed": int(
                safe_float(payload.get("random_seed"), DEFAULT_RANDOM_SEED)
            ),
            "overseas_realized_loss": safe_float(
                payload.get("overseas_realized_loss"), 0.0
            ),
            "other_financial_income": safe_float(
                payload.get("other_financial_income"), 0.0
            ),
            "external_financial_income_krw": (
                safe_float(payload.get("external_financial_income_krw"), 0.0)
                if payload.get("external_financial_income_krw") is not None
                else None
            ),
            "external_financial_income_manwon": (
                safe_float(payload.get("external_financial_income_manwon"), 0.0)
                if payload.get("external_financial_income_manwon") is not None
                else None
            ),
            "pension_tax_liability_sufficient": bool(
                payload.get("pension_tax_liability_sufficient", True)
            ),
            "isa_account_exists": unique_profile["isa"]["account_exists"],
            "isa_account_age_years": unique_profile["isa"]["account_age_years"],
            "isa_cumulative_contribution": unique_profile["isa"]["cumulative_contribution"],
            "isa_current_year_contribution": safe_float(
                payload.get("isa_current_year_contribution"), 0.0
            ),
            "irp_account_exists": unique_profile["irp"]["account_exists"],
            "irp_account_age_years": unique_profile["irp"]["account_age_years"],
            "irp_cumulative_contribution": unique_profile["irp"]["cumulative_contribution"],
            "irp_current_year_contribution": (
                unique_profile["irp"]["current_year_contribution"]
                if unique_profile["irp"]["current_year_contribution"] is not None
                else 0.0
            ),
        },
        "scenario": {
            "base_interest_rate": safe_float(
                scenario_input.get(
                    "base_interest_rate",
                    payload.get("base_interest_rate"),
                ),
                DEFAULT_RISK_FREE_RATE,
            ),
            "base_fx_rate_krw_per_usd": base_fx_rate,
            "stress_interest_rate_shock": safe_float(
                scenario_input.get(
                    "stress_interest_rate_shock",
                    payload.get("stress_interest_rate_shock"),
                ),
                0.0,
            ),
            "stress_fx_shock": safe_float(
                scenario_input.get("stress_fx_shock", payload.get("stress_fx_shock")),
                0.0,
            ),
            "rrttllu": payload.get("rrttllu") or payload.get("RRTTLLU") or {},
            "stress_affects_scoring": bool(
                scenario_input.get(
                    "stress_affects_scoring",
                    payload.get("stress_affects_scoring", False),
                )
            ),
        },
    }

    return AnalysisRequest(**analysis_payload), {
        "source": "consultation_ips_adapter",
        "client_id": request_metadata["client_id"],
        "consultation_id": request_metadata["consultation_id"],
        "flat_ips_keys_used": sorted(flat_ips.keys()),
        "warnings": adapter_warnings,
    }


# ============================================================
# 12-2. API 명세서 ⑤ 응답 포맷터
# ============================================================


def rate_to_percent(value: Any, digits: int = 2) -> float:
    return safe_round(safe_float(value) * 100.0, digits)


def build_allocation_payload(portfolio: Dict[str, Any]) -> List[Dict[str, Any]]:
    allocation = []
    for asset, info in portfolio["weights"].items():
        weight = safe_float(info.get("weight"))
        if weight <= 1e-12:
            continue
        allocation.append(
            {
                "asset_class": asset,
                "name": info.get("label", ASSET_NAMES_KR.get(asset, asset)),
                "weight": safe_round(weight * 100.0, 2),
            }
        )
    return allocation


def build_backtest_payload(
    cumulative_returns: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    monthly_points: Dict[str, Dict[str, Any]] = {}
    for point in cumulative_returns:
        date_text = str(point.get("date", ""))
        if not date_text:
            continue
        month_key = date_text[:7]
        value = safe_float(
            point.get("index_value"),
            (1.0 + safe_float(point.get("value"))) * BACKTEST_BASE_INDEX,
        )
        monthly_points[month_key] = {
            "date": month_key,
            "value": safe_round(value, 2),
            "base_index": BACKTEST_BASE_INDEX,
        }

    return list(monthly_points.values())


def build_metrics_payload(
    portfolio: Dict[str, Any],
) -> Dict[str, Any]:
    metrics = portfolio["metrics"]
    return {
        "expected_return": rate_to_percent(metrics["expected_return"]),
        "volatility": rate_to_percent(metrics["volatility"]),
        "sharpe": safe_round(metrics["sharpe_ratio"], 4),
        "sortino": safe_round(metrics["sortino_ratio"], 4),
        "mdd": rate_to_percent(metrics["mdd"]),
        "beta": safe_round(metrics.get("beta"), 4)
        if metrics.get("beta") is not None
        else None,
        "beta_benchmark": metrics.get("beta_benchmark"),
        "selected_benchmark_key": metrics.get(
            "selected_benchmark_key"
        ),
        "benchmark_comparisons": metrics.get(
            "benchmark_comparisons",
            {},
        ),
        "after_tax_return": rate_to_percent(metrics["after_tax_return"]),
    }


def build_metrics_krw_payload(
    portfolio: Dict[str, Any],
    total_asset: float,
) -> Dict[str, Any]:
    metrics = portfolio["metrics"]
    amount_metrics = metrics.get("krw") or portfolio.get("metric_amounts") or {}
    return {
        "basis": amount_metrics.get("basis", "portfolio_total_asset"),
        "total_asset": safe_round(total_asset, 0),
        "expected_return": safe_round(
            amount_metrics.get(
                "expected_return_amount",
                safe_float(metrics["expected_return"]) * total_asset,
            ),
            0,
        ),
        "after_tax_return": safe_round(
            amount_metrics.get(
                "after_tax_return_amount",
                safe_float(metrics["after_tax_return"]) * total_asset,
            ),
            0,
        ),
        "mdd": safe_round(
            amount_metrics.get(
                "mdd_amount",
                safe_float(metrics["mdd"]) * total_asset,
            ),
            0,
        ),
        "volatility_band": safe_round(
            amount_metrics.get(
                "volatility_band_amount",
                safe_float(metrics["volatility"]) * total_asset,
            ),
            0,
        ),
        "note": amount_metrics.get(
            "note",
            "원화 지표는 현재 총자산에 비율 지표를 곱한 값입니다.",
        ),
    }


def build_tax_summary(
    portfolio: Dict[str, Any],
    tax_saving: float,
) -> str:
    tax_breakdown = portfolio["tax_breakdown"]
    comprehensive_status = tax_breakdown["financial_income_comprehensive_tax"]

    if comprehensive_status["is_over_threshold"]:
        return "금융소득 2,000만원 초과 가능성이 있어 종합과세 검토가 필요합니다."

    if tax_saving > 0:
        return "ISA·IRP 배치 효과를 반영해 현재 대비 세후 결과가 개선됩니다."

    return "이자·배당 금융소득은 2,000만원 기준 이하로 간이 추정됩니다."


def build_tax_payload(
    portfolio: Dict[str, Any],
    current_portfolio: Dict[str, Any],
) -> Dict[str, Any]:
    tax_breakdown = portfolio["tax_breakdown"]
    current_tax = current_portfolio["tax_breakdown"]
    overseas_tax = tax_breakdown["overseas_stock_capital_gains_tax"]

    gross_profit = safe_float(tax_breakdown["gross_profit"])
    dividend_interest_tax = -safe_float(tax_breakdown["withholding_tax_estimate"])
    capital_gains_tax = -safe_float(overseas_tax["estimated_tax"])
    total_tax_after_saving = safe_float(tax_breakdown["total_tax_after_saving"])
    after_tax_profit = safe_float(tax_breakdown["after_tax_profit"])

    current_total_tax = safe_float(current_tax["total_tax_after_saving"])
    saved_vs_current = max(current_total_tax - total_tax_after_saving, 0.0)

    return {
        "waterfall": {
            "gross_return": safe_round(gross_profit, 0),
            "dividend_interest_tax": safe_round(dividend_interest_tax, 0),
            "capital_gains_tax": safe_round(capital_gains_tax, 0),
            "transaction_cost": 0.0,
            "fx_cost": 0.0,
            "after_tax": safe_round(after_tax_profit, 0),
        },
        "saved_vs_current": safe_round(saved_vs_current, 0),
        "summary": build_tax_summary(portfolio, saved_vs_current),
        "calculation_notes": [
            "transaction_cost와 fx_cost는 현재 계산 로직에 별도 모델이 없어 0으로 표시합니다.",
            "세금 계산은 하드코딩 규칙표 기반 간이 추정입니다.",
        ],
    }


def build_spec_portfolio_item(
    kind: str,
    rank: Optional[int],
    label: str,
    badge: Optional[str],
    portfolio: Dict[str, Any],
    current_portfolio: Dict[str, Any],
    total_asset: float,
) -> Dict[str, Any]:
    metrics_krw = build_metrics_krw_payload(portfolio, total_asset)
    current_metrics_krw = build_metrics_krw_payload(current_portfolio, total_asset)
    vs_current_krw = {
        "after_tax_return_delta": safe_round(
            safe_float(metrics_krw.get("after_tax_return"))
            - safe_float(current_metrics_krw.get("after_tax_return")),
            0,
        ),
        "mdd_loss_improvement": safe_round(
            safe_float(metrics_krw.get("mdd"))
            - safe_float(current_metrics_krw.get("mdd")),
            0,
        ),
        "basis": "portfolio_amount_minus_current_amount",
    }
    item = {
        "kind": kind,
        "rank": rank,
        "label": label,
        "badge": badge,
        "allocation": build_allocation_payload(portfolio),
        "metrics": build_metrics_payload(portfolio),
        "metrics_krw": metrics_krw,
        "vs_current_krw": vs_current_krw,
        "backtest": build_backtest_payload(portfolio["cumulative_returns"]),
        "benchmark": {
            "metadata": portfolio.get(
                "benchmark_backtest",
                {},
            ).get("metadata", {}),
            "backtest": build_backtest_payload(
                portfolio.get(
                    "benchmark_backtest",
                    {},
                ).get("series", [])
            ),
        },
        "benchmarks": {
            key: {
                "metadata": benchmark.get("metadata", {}),
                "backtest": build_backtest_payload(
                    benchmark.get("series", [])
                ),
            }
            for key, benchmark in portfolio.get(
                "benchmark_backtests",
                {},
            ).items()
        },
        "tax": build_tax_payload(portfolio, current_portfolio),
    }
    return item


def build_portfolio_calculate_response(
    full_response: Dict[str, Any],
    adapter_info: Dict[str, Any],
) -> Dict[str, Any]:
    portfolios = full_response["portfolios"]
    current = portfolios["current"]
    total_asset = safe_float(full_response["input_summary"]["total_asset"])
    calculation_session_id = full_response["session_id"]
    consultation_id = adapter_info.get("consultation_id") or calculation_session_id

    warnings = list(adapter_info.get("warnings", []))
    if not adapter_info.get("consultation_id"):
        warnings.append(
            "consultation_id가 없어 계산 session_id를 consultation_id 필드에 넣었습니다. "
            "실제 상담 ID가 필요하면 ④ 응답의 consultation_id를 함께 전달해야 합니다."
        )

    return {
        "client_id": adapter_info.get("client_id"),
        "consultation_id": consultation_id,
        "calculation_session_id": calculation_session_id,
        "as_of": datetime.now(KST).isoformat(timespec="seconds"),
        "risk_profile": full_response["input_summary"]["risk_profile"],
        "risk_profile_label": RISK_LEVEL_NAME[
            full_response["input_summary"]["client_risk_level"]
        ],
        "portfolios": [
            build_spec_portfolio_item(
                kind="current",
                rank=None,
                label="현재 포트폴리오",
                badge=None,
                portfolio=current,
                current_portfolio=current,
                total_asset=total_asset,
            ),
            build_spec_portfolio_item(
                kind="A",
                rank=1,
                label="포트폴리오 A",
                badge="베스트",
                portfolio=portfolios["recommended_1"],
                current_portfolio=current,
                total_asset=total_asset,
            ),
            build_spec_portfolio_item(
                kind="B",
                rank=2,
                label="포트폴리오 B",
                badge="추천",
                portfolio=portfolios["recommended_2"],
                current_portfolio=current,
                total_asset=total_asset,
            ),
        ],
        "search_summary": full_response["search_summary"],
        "scenario_summary": full_response["scenario_summary"],
        "data_snapshot": {
            **full_response["input_summary"].get("data_snapshot", {}),
            "backtest_data_snapshot": full_response["input_summary"].get(
                "backtest_data_snapshot", {}
            ),
        },
        "input_adapter": {
            **adapter_info,
            "warnings": warnings,
        },
        "methodology": full_response["methodology"],
        "notes": full_response["notes"],
    }



# ============================================================
# 13. API Endpoints
# ============================================================


@router.get("/")
def root():
    return {
        "message": "AI IPS Portfolio Analysis API - 8.0.0",
        "swagger": "/docs",
    }


@router.get("/assets")
def get_assets():
    return {
        asset: {
            "label": ASSET_NAMES_KR[asset],
            "ticker": ASSET_TICKERS[asset],
            "duration_years": ASSET_DURATION_YEARS.get(asset, 0.0),
            "income_taxable_asset": asset in INCOME_TAXABLE_ASSETS,
            "cash_like_asset": asset in CASH_LIKE_ASSETS,
            "stock_asset": asset in STOCK_ASSETS,
            "bond_cash_asset": asset in BOND_CASH_ASSETS,
            "alternative_asset": asset in ALTERNATIVE_ASSETS,
            "fx_sensitive_asset": asset in FX_SENSITIVE_ASSETS,
            "overseas_capital_gain_asset": asset in OVERSEAS_STOCK_CAPITAL_GAIN_ASSETS,
            "income_yield_assumption": ASSET_INCOME_YIELD_ASSUMPTIONS.get(asset),
        }
        for asset in ASSET_TICKERS
    }


@router.get("/guidelines")
def get_guidelines():
    return get_guideline_definition()


@router.get("/benchmarks", response_model=Dict[str, Any])
def get_benchmarks():
    """PB가 선택할 수 있는 비교용 벤치마크 메타데이터."""
    return get_benchmark_catalog()


@router.post("/portfolio/calculate", response_model=PortfolioCalculateResponse)
def portfolio_calculate(request: Dict[str, Any]):
    """API 명세서 ⑤ 포트폴리오 계산."""
    try:
        normalized_request, adapter_info = normalize_analysis_request_payload(request)
        full = run_full_analysis(normalized_request)
        return build_portfolio_calculate_response(full, adapter_info)
    except Exception as e:
        raise public_http_exception(e)


@router.post("/portfolio/stress-test", response_model=PortfolioStressTestResponse)
def portfolio_stress_test(request: Dict[str, Any]):
    """API 명세서 ⑥ 스트레스 테스트."""
    try:
        normalized_request, adapter_info = normalize_analysis_request_payload(request)
        full = run_full_analysis(normalized_request)
        response = build_portfolio_calculate_response(full, adapter_info)
        return {
            "consultation_id": response["consultation_id"],
            "calculation_session_id": response["calculation_session_id"],
            "as_of": response["as_of"],
            "risk_profile": response["risk_profile"],
            "risk_profile_label": response["risk_profile_label"],
            "portfolios": response["portfolios"],
            "scenario_summary": response["scenario_summary"],
            "data_snapshot": response.get("data_snapshot", {}),
            "input_adapter": response["input_adapter"],
        }
    except Exception as e:
        raise public_http_exception(e)


class StressMetricsRequest(BaseModel):
    """충격 후 전체 지표 재계산용 입력. weights가 없으면 기본 현재 비중을 사용한다."""

    weights: Optional[Dict[str, float]] = Field(None)
    portfolio: PortfolioRequest
    # 위기 시나리오 버튼용. 지정 시 금리·환율 슬라이더 대신 해당 위기 충격 벡터를 주입한다.
    # None이면 슬라이더(금리·환율) 기반. Literal로 두어 Pydantic이 입구에서 값 검증·문서화.
    scenario: Optional[Literal["crisis_2008", "crisis_ru_war"]] = Field(None)


@router.post("/portfolio/stress-metrics", response_model=Dict[str, Any])
def portfolio_stress_metrics(request: StressMetricsRequest):
    """금리·환율 충격을 시계열에 주입해 기준/스트레스 지표를 함께 반환한다."""
    try:
        req = request.portfolio
        weights = canonicalize_weights(request.weights) or get_default_current_weights()
        weights = normalize_weights(weights)

        prices = download_price_data(period=req.period, cash_return=req.cash_return)
        returns = calculate_daily_returns(prices)
        benchmark_returns, _ = download_benchmark_returns(
            period=req.period,
        )
        analysis_returns = attach_benchmark_returns(
            returns,
            benchmark_returns,
        )
        expected_returns = calculate_expected_returns(
            returns=returns,
            expected_return_haircut=req.expected_return_haircut,
            enable_black_litterman=req.enable_black_litterman,
            view_expected_returns=req.view_expected_returns,
            view_weight=req.view_weight,
        )

        base = calculate_metrics(
            weights, analysis_returns, expected_returns, req, include_benchmark_metrics=True
        )
        assets = [
            asset
            for asset in weights
            if asset in returns.columns and weights[asset] > 1e-12
        ]
        # 위기 시나리오 버튼이면 해당 위기 충격 벡터, 아니면 금리·환율 슬라이더 충격.
        if request.scenario:
            asset_shocks = resolve_scenario_shocks(request.scenario, assets)
        else:
            asset_shocks = derive_asset_shocks_from_macro(assets, req)
        stressed = calculate_metrics(
            weights,
            analysis_returns,
            expected_returns,
            req,
            include_benchmark_metrics=True,
            shocks=asset_shocks,
        )

        return {
            "as_of": datetime.now(KST).isoformat(timespec="seconds"),
            "scenario": request.scenario,
            # 위기 시나리오일 땐 슬라이더 충격이 무시되므로 None으로 명시(오해 방지).
            "stress_interest_rate_shock": (
                None if request.scenario else req.stress_interest_rate_shock
            ),
            "stress_fx_shock": None if request.scenario else req.stress_fx_shock,
            "asset_shocks": {k: safe_round(v, 6) for k, v in asset_shocks.items()},
            "base": base,
            "stressed": stressed,
        }
    except Exception as e:
        raise public_http_exception(e)


@router.post(
    "/api/portfolio/all",
    response_model=Dict[str, Any],
    deprecated=True,
)
def api_portfolio_all(request: AnalysisRequest):
    """
    최초 대시보드용 전체 API.
    현재 포트폴리오 / 포트폴리오 A / 포트폴리오 B / 백테스트 / 절세 입력값을 한 번에 반환.
    """
    try:
        return run_full_analysis(request)
    except Exception as e:
        raise public_http_exception(e)


@router.post(
    "/api/portfolio/current",
    response_model=Dict[str, Any],
    deprecated=True,
)
def api_portfolio_current(request: AnalysisRequest):
    """
    현재 포트폴리오만 반환.
    """
    try:
        full = run_full_analysis(request)
        return {
            "session_id": full["session_id"],
            "portfolio": full["portfolios"]["current"],
        }
    except Exception as e:
        raise public_http_exception(e)


@router.post(
    "/api/portfolio/a",
    response_model=Dict[str, Any],
    deprecated=True,
)
def api_portfolio_a(request: AnalysisRequest):
    """
    포트폴리오 A만 반환.
    """
    try:
        full = run_full_analysis(request)
        return {
            "session_id": full["session_id"],
            "portfolio": full["portfolios"]["recommended_1"],
        }
    except Exception as e:
        raise public_http_exception(e)


@router.post(
    "/api/portfolio/b",
    response_model=Dict[str, Any],
    deprecated=True,
)
def api_portfolio_b(request: AnalysisRequest):
    """
    포트폴리오 B만 반환.
    """
    try:
        full = run_full_analysis(request)
        return {
            "session_id": full["session_id"],
            "portfolio": full["portfolios"]["recommended_2"],
        }
    except Exception as e:
        raise public_http_exception(e)


@router.post(
    "/api/portfolio/bundle",
    response_model=Dict[str, Any],
    deprecated=True,
)
def api_portfolio_bundle(request: AnalysisRequest):
    """
    현재 / 포트폴리오 A / 포트폴리오 B 묶음만 반환.
    차트 카드 갱신용.
    """
    try:
        full = run_full_analysis(request)
        return {
            "session_id": full["session_id"],
            "portfolios": full["portfolios"],
            "search_summary": full["search_summary"],
            "scenario_summary": full["scenario_summary"],
        }
    except Exception as e:
        raise public_http_exception(e)


@router.post(
    "/api/backtest",
    response_model=Dict[str, Any],
    deprecated=True,
)
def api_backtest(request: AnalysisRequest):
    """
    현재 / 포트폴리오 A / 포트폴리오 B 백테스트 데이터만 반환.
    """
    try:
        full = run_full_analysis(request)
        return extract_backtest_payload(full)
    except Exception as e:
        raise public_http_exception(e)


@router.post(
    "/api/tax-inputs",
    response_model=Dict[str, Any],
    deprecated=True,
)
def api_tax_inputs(request: AnalysisRequest):
    """
    절세 최적화 파트에 넘길 값만 반환.
    절세제안 문구는 제외하고, 종합과세 임계점/해외주식 양도세/ISA·IRP·일반계좌 정보만 반환.
    """
    try:
        full = run_full_analysis(request)
        return extract_tax_inputs_payload(full)
    except Exception as e:
        raise public_http_exception(e)


@router.post(
    "/api/tax-optimizer",
    response_model=Dict[str, Any],
    deprecated=True,
)
def api_tax_optimizer(request: AnalysisRequest):
    """
    절세 최적화 화면 전용 payload만 반환.
    ISA·IRP·일반계좌 카드와 최종 절세효과를 포함한다.
    """
    try:
        full = run_full_analysis(request)
        return {
            "session_id": full["session_id"],
            "tax_optimizer": full["tax_optimizer"],
            "common_tax_rules": get_common_tax_rules(),
        }
    except Exception as e:
        raise public_http_exception(e)


@router.get("/api/sessions/{session_id}/request")
def api_get_saved_request(session_id: str):
    """
    1회차 상담 request 조회.
    현재는 서버 메모리 저장이라 서버 재시작 시 사라짐.
    """
    saved = SESSION_REQUEST_STORE.get(session_id)
    if saved is None:
        raise HTTPException(status_code=404, detail="해당 session_id의 저장된 request가 없습니다.")

    return {
        "session_id": session_id,
        "request": saved,
    }


# ============================================================
# 14. Legacy Analyze API
# ============================================================
# 기존 프론트나 테스트 코드와의 호환을 위해 남김.
# 새 프론트는 /api/portfolio/all 등 분리 API를 사용하면 됨.


@router.post(
    "/analyze",
    response_model=Dict[str, Any],
    deprecated=True,
)
def analyze_portfolio(request: PortfolioRequest):
    try:
        return run_analysis_core(request)
    except Exception as e:
        raise public_http_exception(e)

