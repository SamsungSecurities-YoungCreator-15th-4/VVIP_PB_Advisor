# ruff: noqa: E501
"""§12. 전체 분석 실행 — run_analysis_core / run_full_analysis."""

import uuid
from typing import Dict, Any

from .constants import TRADING_DAYS
from .assets import ASSET_NAMES_KR, CLIENT_RISK_LEVEL
from .models import AnalysisRequest, PortfolioRequest
from .utils import (
    model_to_dict,
    validate_unique_asset,
    canonicalize_weights,
    canonicalize_asset_return_map,
    validate_weights,
    validate_required_assets_available,
    normalize_weights,
    get_default_current_weights,
    safe_round,
    get_benchmark_catalog,
    attach_benchmark_returns,
    save_session_request,
    convert_analysis_to_portfolio_request,
)
from .tax_accounts import resolve_external_financial_income_krw
from .prices import (
    download_price_data,
    download_backtest_price_data,
    download_benchmark_returns,
    calculate_daily_returns,
)
from .expected_returns import calculate_expected_returns
from .generation import (
    build_constraint_warnings,
    get_effective_unique_asset,
    find_recommended_portfolios,
)
from .responses import (
    build_portfolio_response,
    build_asset_summary,
    get_guideline_definition,
    extract_backtest_payload,
    build_tax_optimizer_map,
    extract_tax_inputs_payload,
)


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
            "tax_text": request.tax_text,
            "tax_profile": request.tax_profile,
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
            "overseas_realized_gain_krw": request.overseas_realized_gain_krw,
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
