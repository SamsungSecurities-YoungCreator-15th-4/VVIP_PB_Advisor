"""Strict portfolio API service.

Public API models are converted once into PR #74's internal AnalysisRequest.
The legacy multi-shape adapter is not used by canonical endpoints.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.portfolio_logic import portfolio_logic as legacy
from app.schemas.portfolio_api import (
    AllocationItem,
    BacktestPoint,
    BenchmarkCatalog,
    BenchmarkMetadata,
    BenchmarkResult,
    PortfolioCalculationRequest,
    PortfolioCalculationResponse,
    PortfolioMetrics,
    PortfolioMoneyMetrics,
    PortfolioResult,
    PortfolioTaxResult,
    SemanticMappingResult,
    TargetReturnResult,
    TaxWaterfall,
)
from app.services.portfolio_orchestration import (
    DEFAULT_BENCHMARK_KEY,
    get_benchmark_catalog,
    run_full_analysis_v2,
)
from app.services.semantic_mapping import (
    empty_insight_mapping,
    empty_unique_mapping,
    map_ai_insight_answer,
    map_unique_text,
)

logger = logging.getLogger(__name__)


def _current_weights(request: PortfolioCalculationRequest) -> dict[str, float] | None:
    if not request.current_portfolio:
        return None
    return {
        item.asset_class: item.weight_rate
        for item in request.current_portfolio
    }


def _prepare_unique_mapping(request: PortfolioCalculationRequest) -> dict[str, Any]:
    unique = request.ips.unique
    if unique.structured_mapping is not None:
        return {
            **unique.structured_mapping,
            "status": "provided",
            "mapping_engine": unique.structured_mapping.get(
                "mapping_engine",
                "provided_structured_mapping",
            ),
        }
    raw_text = (unique.raw_text or "").strip()
    if not raw_text:
        return {
            **empty_unique_mapping(),
            "status": "not_provided",
        }
    if not request.semantic_mapping_enabled:
        return {
            **empty_unique_mapping(raw_text),
            "status": "disabled",
        }
    try:
        return {
            **map_unique_text(raw_text),
            "status": "mapped",
        }
    except Exception:
        logger.exception("Unique Azure Structured Output mapping failed")
        return {
            **empty_unique_mapping(raw_text),
            "status": "failed_fallback_to_explicit_fields",
            "error": "Unique 의미 매핑에 실패해 명시형 입력만 계산에 사용했습니다.",
        }


def _prepare_ai_insight_mapping(request: PortfolioCalculationRequest) -> dict[str, Any]:
    insight = request.ai_insight
    if insight is None:
        return {
            **empty_insight_mapping(),
            "status": "not_provided",
            "calculation_applied": False,
        }
    source = insight.model_dump(mode="json")
    if insight.structured_mapping is not None:
        return {
            **insight.structured_mapping,
            "status": "provided",
            "source": source,
            "calculation_applied": False,
        }
    if not request.semantic_mapping_enabled:
        return {
            **empty_insight_mapping(insight.answer),
            "status": "disabled",
            "source": source,
            "calculation_applied": False,
        }
    try:
        return {
            **map_ai_insight_answer(insight.answer),
            "status": "mapped",
            "source": source,
            "calculation_applied": False,
        }
    except Exception:
        logger.exception("AI insight Azure Structured Output mapping failed")
        return {
            **empty_insight_mapping(insight.answer),
            "status": "failed",
            "error": "AI 인사이트 의미 매핑에 실패했습니다.",
            "source": source,
            "calculation_applied": False,
        }


def to_legacy_analysis_request(
    request: PortfolioCalculationRequest,
) -> legacy.AnalysisRequest:
    """Convert one strict public request into PR #74's internal request."""
    ips = request.ips
    unique = ips.unique
    tax = ips.tax
    isa = ips.isa
    irp = ips.irp
    opt = ips.optimization
    scenario = request.scenario

    return legacy.AnalysisRequest(
        ips=legacy.IPSRequest(
            total_asset=ips.total_asset_krw,
            unique_need_amount=unique.need_amount_krw,
            unique_asset=unique.reserve_asset,
            unique_items=[],
            unique_profile={"raw_text": unique.raw_text} if unique.raw_text else {},
            age=ips.age,
            client_context=ips.client_context,
            risk_profile=ips.risk_profile,
            investment_horizon_years=ips.investment_horizon_years,
            tax_sensitivity=ips.tax_sensitivity,
            liquidity_need=ips.liquidity_need,
            current_weights=_current_weights(request),
            risk_free_rate=opt.risk_free_rate,
            cash_return=opt.cash_return,
            period=opt.period,
            num_simulations=opt.num_simulations,
            expected_return_haircut=opt.expected_return_haircut,
            random_seed=opt.random_seed,
            enable_black_litterman=opt.enable_black_litterman,
            view_expected_returns=opt.view_expected_returns,
            view_weight=opt.view_weight,
            marginal_income_tax_rate=tax.marginal_income_tax_rate,
            overseas_stock_realized_gain_rate=(
                tax.overseas_stock_realized_gain_rate
            ),
            overseas_realized_loss=tax.overseas_realized_loss_krw,
            other_financial_income=0.0,
            external_financial_income_krw=tax.external_financial_income_krw,
            external_financial_income_manwon=None,
            pension_tax_liability_sufficient=(
                tax.pension_tax_liability_sufficient
            ),
            isa_enabled=isa.enabled,
            isa_type=isa.isa_type,
            isa_account_exists=isa.account_exists,
            isa_account_age_years=isa.account_age_years,
            isa_cumulative_contribution=isa.cumulative_contribution_krw,
            isa_current_year_contribution=isa.current_year_contribution_krw,
            isa_recent_3yr_comprehensive_taxed=(
                isa.recent_3yr_comprehensive_taxed
            ),
            isa_existing_account_usable=isa.existing_account_usable,
            isa_remaining_capacity=isa.remaining_capacity_krw,
            isa_remaining_capacity_override=(
                isa.remaining_capacity_override_krw
            ),
            isa_years_until_liquid=isa.years_until_liquid,
            irp_enabled=irp.enabled,
            irp_eligible=irp.eligible,
            irp_account_exists=irp.account_exists,
            irp_account_age_years=irp.account_age_years,
            irp_cumulative_contribution=irp.cumulative_contribution_krw,
            irp_current_year_contribution=irp.current_year_contribution_krw,
            irp_remaining_tax_credit_capacity=(
                irp.remaining_tax_credit_capacity_krw
            ),
            irp_remaining_tax_credit_capacity_override=(
                irp.remaining_tax_credit_capacity_override_krw
            ),
            irp_tax_credit_rate=irp.tax_credit_rate,
            irp_years_until_access=irp.years_until_access,
        ),
        scenario=legacy.ScenarioRequest(
            base_interest_rate=scenario.base_interest_rate,
            base_fx_rate_krw_per_usd=scenario.base_fx_rate_krw_per_usd,
            stress_interest_rate_shock=(
                scenario.stress_interest_rate_shock_rate
            ),
            stress_fx_shock=scenario.stress_fx_shock_rate,
            rrttllu=scenario.rrttllu,
            stress_affects_scoring=scenario.stress_affects_scoring,
        ),
    )


def _backtest_points(raw: list[dict[str, Any]]) -> list[BacktestPoint]:
    points: list[BacktestPoint] = []
    for point in legacy.build_backtest_payload(raw):
        points.append(
            BacktestPoint(
                date=str(point["date"]),
                value=legacy.safe_float(point["value"]),
                base_index=legacy.safe_float(point["base_index"]),
            )
        )
    return points


def _benchmark_result(
    key: str,
    raw: dict[str, Any],
) -> BenchmarkResult:
    metadata = raw.get("metadata") or {}
    return BenchmarkResult(
        metadata=BenchmarkMetadata(
            key=key,
            ticker=str(metadata.get("ticker") or ""),
            label=str(metadata.get("label") or key),
            official_index_series=bool(metadata.get("official_index_series")),
            proxy_note=metadata.get("proxy_note"),
            policy=metadata.get("policy"),
            available=bool(metadata.get("available")),
            reason=metadata.get("reason"),
            data_start=metadata.get("data_start"),
            data_end=metadata.get("data_end"),
            observations=metadata.get("observations"),
            common_data_start=metadata.get("common_data_start"),
            common_data_end=metadata.get("common_data_end"),
            common_observations=metadata.get("common_observations"),
        ),
        series=_backtest_points(raw.get("series") or []),
        beta=(
            legacy.safe_float(raw.get("beta"))
            if raw.get("beta") is not None
            else None
        ),
    )


def _portfolio_result(
    *,
    kind: str,
    rank: int | None,
    label: str,
    badge: str | None,
    portfolio: dict[str, Any],
    current: dict[str, Any],
    total_asset_krw: float,
) -> PortfolioResult:
    allocation_raw = legacy.build_allocation_payload(portfolio)
    metrics = portfolio["metrics"]
    money = legacy.build_metrics_krw_payload(portfolio, total_asset_krw)
    tax = legacy.build_tax_payload(portfolio, current)
    waterfall = tax["waterfall"]
    benchmark_raw = portfolio.get("benchmark_backtests") or {}

    beta_map = {
        key: (
            legacy.safe_float(value) if value is not None else None
        )
        for key, value in (metrics.get("beta_by_benchmark") or {}).items()
    }
    for key in ("kospi", "sp500", "msci_acwi"):
        beta_map.setdefault(key, None)

    return PortfolioResult(
        kind=kind,
        rank=rank,
        label=label,
        badge=badge,
        allocation=[
            AllocationItem(
                asset_class=item["asset_class"],
                name=str(item["name"]),
                weight_rate=legacy.safe_float(item["weight"]) / 100.0,
            )
            for item in allocation_raw
        ],
        metrics=PortfolioMetrics(
            expected_return_rate=legacy.safe_float(metrics["expected_return"]),
            volatility_rate=legacy.safe_float(metrics["volatility"]),
            sharpe_ratio=legacy.safe_float(metrics["sharpe_ratio"]),
            sortino_ratio=legacy.safe_float(metrics["sortino_ratio"]),
            mdd_rate=legacy.safe_float(metrics["mdd"]),
            after_tax_return_rate=legacy.safe_float(metrics["after_tax_return"]),
            beta_by_benchmark=beta_map,
        ),
        metrics_krw=PortfolioMoneyMetrics(
            total_asset_krw=legacy.safe_float(money["total_asset"]),
            expected_return_amount_krw=legacy.safe_float(money["expected_return"]),
            after_tax_return_amount_krw=legacy.safe_float(
                money["after_tax_return"]
            ),
            mdd_amount_krw=legacy.safe_float(money["mdd"]),
            volatility_band_amount_krw=legacy.safe_float(
                money["volatility_band"]
            ),
        ),
        backtest=_backtest_points(portfolio.get("cumulative_returns") or []),
        benchmarks={
            key: _benchmark_result(key, benchmark_raw.get(key) or {})
            for key in ("kospi", "sp500", "msci_acwi")
        },
        tax=PortfolioTaxResult(
            waterfall=TaxWaterfall(
                gross_return_krw=legacy.safe_float(waterfall["gross_return"]),
                dividend_interest_tax_krw=legacy.safe_float(
                    waterfall["dividend_interest_tax"]
                ),
                capital_gains_tax_krw=legacy.safe_float(
                    waterfall["capital_gains_tax"]
                ),
                after_tax_profit_krw=legacy.safe_float(waterfall["after_tax"]),
            ),
            saved_vs_current_krw=legacy.safe_float(tax["saved_vs_current"]),
            summary=str(tax["summary"]),
        ),
        selection_summary=portfolio.get("selection_summary") or {},
    )


def calculate_portfolios(
    request: PortfolioCalculationRequest,
) -> PortfolioCalculationResponse:
    unique_mapping = _prepare_unique_mapping(request)
    ai_mapping = _prepare_ai_insight_mapping(request)
    analysis_request = to_legacy_analysis_request(request)

    full = run_full_analysis_v2(
        request=analysis_request,
        target_after_tax_return=request.ips.target_after_tax_return_rate,
        selected_benchmark=DEFAULT_BENCHMARK_KEY,
        unique_mapping=unique_mapping,
    )

    portfolios = full["portfolios"]
    current = portfolios["current"]
    session_id = str(full["session_id"])
    consultation_id = request.consultation_id or session_id
    total_asset = request.ips.total_asset_krw

    return PortfolioCalculationResponse(
        api_version="portfolio-api-v1",
        client_id=request.client_id,
        consultation_id=consultation_id,
        calculation_session_id=session_id,
        as_of=datetime.now(legacy.KST),
        risk_profile=request.ips.risk_profile,
        risk_profile_label=legacy.RISK_LEVEL_NAME[
            legacy.CLIENT_RISK_LEVEL[request.ips.risk_profile]
        ],
        target_after_tax_return=TargetReturnResult(
            annual_after_tax_rate=request.ips.target_after_tax_return_rate,
            source=(
                "ips.target_after_tax_return_rate"
                if request.ips.target_after_tax_return_rate is not None
                else "not_provided"
            ),
        ),
        benchmark_catalog=BenchmarkCatalog.model_validate(
            get_benchmark_catalog()
        ),
        portfolios=[
            _portfolio_result(
                kind="current",
                rank=None,
                label="현재 포트폴리오",
                badge=None,
                portfolio=current,
                current=current,
                total_asset_krw=total_asset,
            ),
            _portfolio_result(
                kind="A",
                rank=1,
                label="포트폴리오 A",
                badge="세후수익형",
                portfolio=portfolios["recommended_1"],
                current=current,
                total_asset_krw=total_asset,
            ),
            _portfolio_result(
                kind="B",
                rank=2,
                label="포트폴리오 B",
                badge="위험분산형",
                portfolio=portfolios["recommended_2"],
                current=current,
                total_asset_krw=total_asset,
            ),
        ],
        search_summary=full["search_summary"],
        scenario_summary=full["scenario_summary"],
        semantic_mapping=SemanticMappingResult(
            unique=unique_mapping,
            ai_insight=ai_mapping,
        ),
        data_snapshot={
            **full["input_summary"].get("data_snapshot", {}),
            "backtest": full["input_summary"].get(
                "backtest_data_snapshot",
                {},
            ),
            "benchmarks": full["input_summary"].get(
                "benchmark_data_snapshot",
                {},
            ),
        },
        methodology=full["methodology"],
        notes=full["notes"],
    )
