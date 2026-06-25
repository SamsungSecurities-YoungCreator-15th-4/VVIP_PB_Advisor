# ruff: noqa: E501
"""portfolio_logic.py 분할: responses 모듈."""

import logging

import numpy as np
import pandas as pd
from typing import Any, Dict, Optional

from .assets import ALTERNATIVE_ASSETS, ASSET_DURATION_YEARS, ASSET_INCOME_YIELD_ASSUMPTIONS, ASSET_NAMES_KR, ASSET_TICKERS, BOND_CASH_ASSETS, CASH_LIKE_ASSETS, FX_SENSITIVE_ASSETS, INCOME_TAXABLE_ASSETS, OVERSEAS_STOCK_CAPITAL_GAIN_ASSETS, STOCK_ASSETS
from .constants import BACKTEST_BASE_INDEX, BENCHMARK_POLICY_VERSION, GUIDELINE_RULES, SELECTION_RANKING_BASIS, SELECTION_RISK_CONTROLS, TRADING_DAYS
from .generation import build_selection_summary
from .metrics import calculate_all_benchmark_cumulative_returns, calculate_cumulative_returns, calculate_metrics, calculate_monte_carlo_metric_ranges, evaluate_guideline_detail
from .models import PortfolioRequest
from .tax_accounts import calculate_six_strategy_tax_model, get_common_tax_rules
from .utils import get_benchmark_catalog, safe_float, safe_round
from .dashboard_views import calculate_portfolio_risk_contribution_heatmap as build_dashboard_risk_heatmap

logger = logging.getLogger(__name__)

# ============================================================
# 11. 응답 생성
# ============================================================


def build_guideline_report(metrics: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "conservative": evaluate_guideline_detail(metrics, "conservative"),
        "balanced": evaluate_guideline_detail(metrics, "balanced"),
        "aggressive": evaluate_guideline_detail(metrics, "aggressive"),
    }


def build_portfolio_response(
    name: str,
    api_key: str,
    weights: Dict[str, float],
    returns: pd.DataFrame,
    expected_returns: pd.Series,
    request: PortfolioRequest,
    score: Optional[float] = None,
    selection_summary: Optional[Dict[str, Any]] = None,
    correlation_with_recommended_1: Optional[float] = None,
    cov_matrix: Optional[pd.DataFrame] = None,
    backtest_returns: Optional[pd.DataFrame] = None,
    monte_carlo_scenario_context: Optional[
        Dict[str, Any]
    ] = None,
) -> Dict[str, Any]:
    metrics = calculate_metrics(
        weights=weights,
        returns=returns,
        expected_returns=expected_returns,
        request=request,
        cov_matrix=cov_matrix,
        include_benchmark_metrics=True,
    )

    try:
        monte_carlo_metric_ranges = (
            calculate_monte_carlo_metric_ranges(
                weights=weights,
                returns=returns,
                expected_returns=expected_returns,
                total_asset=request.total_asset,
                investment_horizon_years=(
                    request.investment_horizon_years
                ),
                tax_breakdown=metrics.get(
                    "tax_breakdown"
                ),
                random_seed=request.random_seed,
                scenario_context=(
                    monte_carlo_scenario_context
                ),
            )
        )
    except Exception:
        # Range는 부가 지표이므로 계산 실패가 전체 추천 응답을
        # 중단시키지 않도록 안전하게 unavailable로 내린다.
        logger.exception(
            "Failed to calculate Monte Carlo metric ranges"
        )
        monte_carlo_metric_ranges = {
            "available": False,
            "reason": "unexpected_simulation_error",
        }

    cumulative_source_returns = (
        backtest_returns
        if backtest_returns is not None
        else returns
    )
    cumulative_returns = calculate_cumulative_returns(
        weights,
        cumulative_source_returns,
    )
    benchmark_backtests = calculate_all_benchmark_cumulative_returns(
        weights=weights,
        returns=cumulative_source_returns,
    )
    benchmark_backtest = benchmark_backtests[request.benchmark_key]

    response = {
        "api_key": api_key,
        "name": name,
        "weights": {
            asset: {
                "label": ASSET_NAMES_KR.get(asset, asset),
                "ticker": ASSET_TICKERS.get(asset, asset),
                "weight": round(float(weight), 6),
                "amount": round(
                    float(weight) * request.total_asset,
                    0,
                ),
            }
            for asset, weight in weights.items()
        },
        "asset_expected_returns": {
            asset: safe_round(expected_returns.get(asset), 6)
            for asset in weights
            if asset in expected_returns.index
        },
        "metrics": {
            "expected_return": metrics["expected_return"],
            "volatility": metrics["volatility"],
            "sharpe_ratio": metrics["sharpe_ratio"],
            "sortino_ratio": metrics["sortino_ratio"],
            "mdd": metrics["mdd"],
            "beta": metrics["beta"],
            "beta_benchmark": metrics["beta_benchmark"],
            "selected_benchmark_key": metrics[
                "selected_benchmark_key"
            ],
            "benchmark_comparisons": metrics[
                "benchmark_comparisons"
            ],
            "liquidity_coverage": metrics["liquidity_coverage"],
            "after_tax_return": metrics["after_tax_return"],
            "after_tax_return_range": (
                monte_carlo_metric_ranges.get(
                    "after_tax_return"
                )
                if monte_carlo_metric_ranges.get(
                    "available"
                )
                else None
            ),
            "mdd_range": (
                monte_carlo_metric_ranges.get("mdd")
                if monte_carlo_metric_ranges.get(
                    "available"
                )
                else None
            ),
            "monte_carlo_range_basis": (
                monte_carlo_metric_ranges
            ),
            "krw": metrics["metric_amounts"],
            "metric_amounts": metrics["metric_amounts"],
            "taxable_financial_income": metrics[
                "taxable_financial_income"
            ],
            "portfolio_financial_income": metrics["tax_breakdown"][
                "financial_income_comprehensive_tax"
            ]["portfolio_financial_income"],
            "total_financial_income": metrics["tax_breakdown"][
                "financial_income_comprehensive_tax"
            ]["total_financial_income"],
            "financial_income_comprehensive_tax_status": (
                metrics["tax_breakdown"][
                    "financial_income_comprehensive_tax"
                ]
            ),
            "financial_income_tax_gauge": metrics["tax_breakdown"][
                "financial_income_comprehensive_tax"
            ]["gauge"],
            "risk_level": metrics["risk_level"],
            "risk_level_label": metrics["risk_level_label"],
            "stock_weight": metrics["stock_weight"],
            "bond_cash_weight": metrics["bond_cash_weight"],
            "alternative_weight": metrics["alternative_weight"],
            "portfolio_duration": metrics["portfolio_duration"],
            "target_duration": metrics["target_duration"],
            "duration_fit_score": metrics["duration_fit_score"],
            "historical_var_95": metrics["historical_var_95"],
            "historical_var_95_daily_loss": metrics[
                "historical_var_95_daily_loss"
            ],
            "risk_contribution": metrics["risk_contribution"],
            "risk_contribution_max_share": metrics[
                "risk_contribution_max_share"
            ],
            "selection_risk_control": metrics[
                "selection_risk_control"
            ],
            "stress_test": metrics["stress_test"],
        },
        "metric_amounts": metrics["metric_amounts"],
        "tax_breakdown": metrics["tax_breakdown"],
        "financial_income_tax_gauge": metrics["tax_breakdown"][
            "financial_income_comprehensive_tax"
        ]["gauge"],
        "selection_summary": (
            selection_summary
            if selection_summary is not None
            else build_selection_summary(metrics)
        ),
        "guideline_report": build_guideline_report(metrics),
        "cumulative_returns": cumulative_returns,
        # 기존 프론트 호환: PB가 선택한 한 개
        "benchmark_backtest": benchmark_backtest,
        # 신규 계약: PB가 선택할 수 있는 전체 3종
        "benchmark_backtests": benchmark_backtests,
    }
    response["risk_contribution_heatmap"] = build_dashboard_risk_heatmap(
        weights=weights,
        returns=returns,
    )

    if score is not None:
        response["score"] = round(float(score), 6)

    if correlation_with_recommended_1 is not None:
        response["correlation_with_recommended_1"] = round(
            float(correlation_with_recommended_1),
            6,
        )

    return response


def build_asset_summary(
    returns: pd.DataFrame,
    expected_returns: pd.Series,
) -> Dict[str, Any]:
    summary = {}

    for asset in returns.columns:
        annual_volatility = returns[asset].std() * np.sqrt(TRADING_DAYS)

        summary[asset] = {
            "label": ASSET_NAMES_KR.get(asset, asset),
            "ticker": ASSET_TICKERS.get(asset, asset),
            "expected_return": safe_round(float(expected_returns[asset]), 6),
            "annual_volatility": safe_round(float(annual_volatility), 6),
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

    return summary


def get_guideline_definition() -> Dict[str, Any]:
    return {
        "verified_basis": {
            "financial_income_threshold": "금융소득종합과세 검토 기준 2,000만 원",
            "overseas_stock_deduction": "해외주식 양도소득 기본공제 250만 원",
            "isa": "ISA 의무보유기간 3년, 일반형 비과세 200만 원, 서민형 비과세 400만 원, 초과분 저율 분리과세 가정",
            "risk_suitability": "투자자성향보다 높은 위험도의 투자성 상품 권유 제한 원칙 반영",
            "risk_factors": "변동성, 최대손실가능성, 기초자산 구성, 유동성, 만기, 환율 변동성 등을 위험 판단 요소로 반영",
        },
        "project_assumptions": {
            "risk_profile_thresholds": "안정형/균형형/공격형별 변동성, MDD, 자산군 비중 한도는 프로젝트용 수치화 기준",
            "selection_risk_controls": SELECTION_RISK_CONTROLS,
            "selection_ranking_basis": SELECTION_RANKING_BASIS,
            "portfolio_b_target_source": "RRTTLLU.Return",
            "portfolio_b_objective": "target_return_then_risk_contribution_minimization",
            "portfolio_a_b_correlation_usage": "display_only",
            "benchmark_policy": BENCHMARK_POLICY_VERSION,
            "benchmark_policy_note": (
                "KOSPI, S&P 500, MSCI ACWI 3종을 비교용으로 제공. "
                "벤치마크는 베타·비교 차트에만 사용하며 추천 로직에는 미반영."
            ),
            "duration_source_note": (
                "듀레이션은 채권형 ETF proxy 기준으로만 적용. "
                "주식·리츠·현금·대체자산에는 0년을 적용."
            ),
            "duration_targets": {
                "short_horizon_1_to_3_years": 1.5,
                "middle_horizon_4_to_7_years": 4.0,
                "long_horizon_8_plus_years": 7.0,
            },
            "low_coupon_bond_proxy": "484790.KS를 저쿠폰 장기채 price proxy로 사용",
            "separate_tax_bond_proxy": "439870.KS를 분리과세 장기채 price proxy로 사용",
        },
        "guideline_rules": GUIDELINE_RULES,
    }


def extract_backtest_payload(
    full_response: Dict[str, Any],
) -> Dict[str, Any]:
    data_snapshot = full_response["input_summary"].get(
        "backtest_data_snapshot",
        full_response["input_summary"].get("data_snapshot", {}),
    )
    portfolios = full_response["portfolios"]

    return {
        "session_id": full_response["session_id"],
        "selected_benchmark_key": full_response["input_summary"][
            "benchmark_key"
        ],
        "benchmark_catalog": get_benchmark_catalog(),
        "basis": {
            "base_index": BACKTEST_BASE_INDEX,
            "base_date": data_snapshot.get("data_start"),
            "as_of": (
                data_snapshot.get("as_of")
                or data_snapshot.get("data_end")
            ),
            "note": (
                "백테스트 차트는 5년 구간을 100으로 둔 누적수익률 지수. "
                "벤치마크 3종은 추천 계산과 분리된 비교선."
            ),
        },
        "data_snapshot": data_snapshot,
        "backtest": {
            "current": portfolios["current"]["cumulative_returns"],
            "portfolio_a": portfolios["recommended_1"][
                "cumulative_returns"
            ],
            "portfolio_b": portfolios["recommended_2"][
                "cumulative_returns"
            ],
        },
        # 기존 호환: 선택된 벤치마크
        "benchmarks": {
            "current": portfolios["current"]["benchmark_backtest"],
            "portfolio_a": portfolios["recommended_1"][
                "benchmark_backtest"
            ],
            "portfolio_b": portfolios["recommended_2"][
                "benchmark_backtest"
            ],
        },
        # 신규: 전체 3종
        "benchmark_options": {
            "current": portfolios["current"]["benchmark_backtests"],
            "portfolio_a": portfolios["recommended_1"][
                "benchmark_backtests"
            ],
            "portfolio_b": portfolios["recommended_2"][
                "benchmark_backtests"
            ],
        },
        "summary_metrics": {
            "current": portfolios["current"]["metrics"],
            "portfolio_a": portfolios["recommended_1"]["metrics"],
            "portfolio_b": portfolios["recommended_2"]["metrics"],
        },
    }


def build_isa_tax_card(
    account_buckets: Dict[str, Any],
    tax_saving_effect: Dict[str, Any],
) -> Dict[str, Any]:
    isa = account_buckets["isa"]
    remaining_capacity = safe_float(isa.get("remaining_capacity"))
    used_capacity = safe_float(isa.get("used_capacity"))

    return {
        "enabled": isa["enabled"],
        "usable": isa["usable"],
        "account_type": isa["type"],
        "account_exists": isa["account_exists"],
        "account_age_years": isa["account_age_years"],
        "cumulative_contribution": isa["cumulative_contribution"],
        "remaining_capacity": safe_round(remaining_capacity, 0),
        "used_capacity": safe_round(used_capacity, 0),
        "utilization_ratio": isa["utilization_ratio"],
        "tax_free_limit": isa["tax_free_limit"],
        "low_tax_rate": isa["low_tax_rate_after_tax_free_limit"],
        "estimated_tax_saving": tax_saving_effect["estimated_isa_tax_saving"],
        "income_shifted_to_isa": (
            tax_saving_effect["estimated_income_shifted_to_isa"]
        ),
        "status_label": (
            "일반형 ISA 활용" if isa["usable"] else "ISA 활용 불가"
        ),
        "description": "비과세 한도와 초과분 9.9% 분리과세 간이 반영",
        "rule_keys": isa["rule_keys"],
    }


def build_irp_tax_card(
    account_buckets: Dict[str, Any],
    tax_saving_effect: Dict[str, Any],
) -> Dict[str, Any]:
    irp = account_buckets["irp"]

    return {
        "enabled": irp["enabled"],
        "eligible": irp["eligible"],
        "usable": irp["usable"],
        "current_year_contribution": irp["current_year_contribution"],
        "annual_tax_credit_limit": irp["annual_tax_credit_limit"],
        "remaining_tax_credit_capacity": irp["remaining_tax_credit_capacity"],
        "used_capacity": irp["used_capacity"],
        "utilization_ratio": irp["utilization_ratio"],
        "tax_credit_rate": irp["tax_credit_rate"],
        "estimated_tax_credit": tax_saving_effect["estimated_irp_tax_credit"],
        "years_until_access": irp["years_until_access"],
        "horizon_suitable": irp.get("horizon_suitable"),
        "reason": irp.get("reason"),
        "status_label": (
            "연금저축·IRP 세액공제 활용"
            if irp["usable"]
            else "IRP 세액공제 활용 불가"
        ),
        "description": "연금계좌 세액공제 한도 내 납입액에 공제율 적용",
        "rule_keys": irp["rule_keys"],
    }


def build_taxable_account_card(
    account_buckets: Dict[str, Any],
    tax_breakdown: Dict[str, Any],
) -> Dict[str, Any]:
    taxable = account_buckets["taxable_account"]

    return {
        "account_key": "taxable_account",
        "display_name": taxable.get("display_name", "일반과세 자산 운용"),
        "account_role": taxable.get("account_role", "residual_and_liquidity"),
        "allocated_amount": taxable["allocated_amount"],
        "liquidity_reserve_target": taxable.get("liquidity_reserve_target", 0.0),
        "liquidity_reserve_allocated": taxable.get("liquidity_reserve_allocated", 0.0),
        "liquidity_reserve_shortfall": taxable.get("liquidity_reserve_shortfall", 0.0),
        "estimated_tax_after_strategy": tax_breakdown["total_tax_after_saving"],
        "status_label": "세제계좌 외 자산 운용",
        "description": (
            "세제계좌 한도 초과 자산과 단기 유동성 자산을 일반과세계좌에서 운용합니다. "
            "손익통산·저회전·과세효율화 전략의 적용 대상이며, 미투자 현금 잔액을 뜻하지 않습니다."
        ),
        "allocations": taxable["allocations"],
    }


TAX_STRATEGY_META = {
    "isa": {
        "title": "ISA 계좌 활용",
        "calculation_order": 1,
        "rule_keys": ["isa_tax_exemption"],
    },
    "pension_credit": {
        "title": "연금계좌 세액공제",
        "calculation_order": 6,
        "rule_keys": ["pension_account_tax_credit"],
    },
    "separate_bond": {
        "title": "분리과세 채권",
        "calculation_order": 3,
        "rule_keys": [],
    },
    "low_tax_dividend": {
        "title": "저율과세 배당주",
        "calculation_order": 2,
        "rule_keys": [],
    },
    "overseas_exemption": {
        "title": "해외주식 양도 250만 공제",
        "calculation_order": 5,
        "rule_keys": ["overseas_stock_transfer_tax"],
    },
    "tax_loss": {
        "title": "Tax-loss Harvesting",
        "calculation_order": 4,
        "rule_keys": ["capital_loss_offset"],
    },
}


def build_tax_strategy_reason(
    strategy_key: str,
    raw_reason: Any,
    card: Dict[str, Any],
    contribution: float,
) -> Dict[str, Any]:
    """내부 부적합 사유를 화면에서 바로 이해할 수 있는 문구로 바꾼다."""
    raw_text = (
        str(raw_reason).strip()
        if raw_reason is not None and str(raw_reason).strip()
        else None
    )

    if contribution > 0:
        return {"reason": None, "reason_code": None, "raw_reason": raw_text}

    if raw_text and "상위 효율 전략 적용 후" in raw_text:
        return {
            "reason": (
                "중복 적용 가능한 과세소득이 앞선 절세 전략에서 모두 사용되어 "
                "이 전략의 추가 절감액은 0원입니다."
            ),
            "reason_code": "shared_tax_base_exhausted",
            "raw_reason": raw_text,
        }

    if strategy_key == "isa":
        if raw_text and "신규 개설 불가" in raw_text:
            reason = "ISA 신규 개설 적격성 조건을 충족하지 못해 이번 절세안에서 제외했습니다."
            code = "isa_new_account_ineligible"
        elif raw_text and "투자기간" in raw_text:
            reason = (
                f"{raw_text}. 고객의 투자기간보다 ISA 잔여 의무보유기간이 길어 "
                "단기 유동성 제약이 발생할 수 있습니다."
            )
            code = "isa_lockup_exceeds_horizon"
        elif raw_text and "적격성·잔여한도" in raw_text:
            reason = (
                "ISA 계좌 사용 요건을 충족하지 못했거나 사용 가능한 "
                "잔여 납입한도가 없어 적용하지 않았습니다."
            )
            code = "isa_ineligible_or_no_capacity"
        else:
            reason = (
                "ISA로 이전할 적격 자산 또는 사용 가능한 납입한도가 없어 "
                "예상 절감액이 없습니다."
            )
            code = "isa_no_transferable_amount"
        return {"reason": reason, "reason_code": code, "raw_reason": raw_text}

    if strategy_key == "pension_credit":
        if raw_text and "투자기간" in raw_text:
            reason = (
                f"{raw_text}. 연금 수령 가능 시점 전에 자금이 필요할 수 있어 "
                "IRP 배치 대상에서 제외했습니다."
            )
            code = "pension_lockup_exceeds_horizon"
        elif raw_text and "산출세액" in raw_text:
            reason = (
                "예상 산출세액이 세액공제액보다 작아 IRP 납입액 전부에 대한 "
                "공제 효과를 적용할 수 없습니다."
            )
            code = "insufficient_tax_liability"
        else:
            reason = (
                "IRP 사용 요건을 충족하지 못했거나 당해 연도 세액공제 한도를 "
                "이미 모두 사용했습니다."
            )
            code = "pension_ineligible_or_no_capacity"
        return {"reason": reason, "reason_code": code, "raw_reason": raw_text}

    if strategy_key == "separate_bond":
        if raw_text and "한계세율" in raw_text:
            reason = (
                "고객 한계세율이 분리과세 가정세율보다 높지 않아 "
                "분리과세 채권의 추가 절세 효과가 없습니다."
            )
            code = "marginal_rate_not_high_enough"
        elif raw_text and "초과분 없음" in raw_text:
            reason = (
                "예상 금융소득이 종합과세 기준을 초과하지 않아 "
                "분리과세 전환으로 줄일 추가 세금이 없습니다."
            )
            code = "no_comprehensive_tax_excess"
        else:
            reason = (
                "현재 포트폴리오에서 분리과세 전환 대상이 되는 "
                "채권 이자소득이 계산되지 않았습니다."
            )
            code = "no_eligible_bond_income"
        return {"reason": reason, "reason_code": code, "raw_reason": raw_text}

    if strategy_key == "low_tax_dividend":
        if raw_text and "초과분 없음" in raw_text:
            reason = (
                "예상 금융소득이 종합과세 기준을 초과하지 않아 "
                "배당소득 조정에 따른 추가 절세 효과가 없습니다."
            )
            code = "no_comprehensive_tax_excess"
        else:
            reason = (
                "현재 포트폴리오에 절세 대상으로 계산할 "
                "배당주·리츠의 예상 배당소득이 없습니다."
            )
            code = "no_eligible_dividend_income"
        return {"reason": reason, "reason_code": code, "raw_reason": raw_text}

    if strategy_key == "overseas_exemption":
        return {
            "reason": (
                "해외주식의 예상 가격차익이 없거나 기본공제를 적용할 "
                "양도차익이 없어 절세액이 계산되지 않았습니다."
            ),
            "reason_code": "no_overseas_capital_gain",
            "raw_reason": raw_text,
        }

    if strategy_key == "tax_loss":
        return {
            "reason": (
                "상계할 해외주식 양도차익 또는 확정 가능한 해외주식 손실이 없어 "
                "Tax-loss Harvesting 효과가 없습니다."
            ),
            "reason_code": "no_offsettable_gain_or_loss",
            "raw_reason": raw_text,
        }

    return {
        "reason": raw_text or "현재 입력 조건에서는 예상 절세 효과가 없습니다.",
        "reason_code": "not_applicable",
        "raw_reason": raw_text,
    }


def build_six_tax_strategy_cards(
    portfolio_response: Dict[str, Any],
    request: PortfolioRequest,
) -> Dict[str, Any]:
    stored_model = (
        portfolio_response
        .get("tax_breakdown", {})
        .get("six_strategy_tax_model")
    )
    if stored_model:
        standalone = stored_model.get(
            "standalone",
            [],
        )
        combined = stored_model.get(
            "combined",
            {},
        )
    else:
        weights = {
            asset: safe_float(
                info.get("weight")
            )
            for asset, info
            in portfolio_response[
                "weights"
            ].items()
        }
        expected_returns = pd.Series(
            {
                asset: safe_float(value)
                for asset, value
                in portfolio_response.get(
                    "asset_expected_returns",
                    {},
                ).items()
            },
            dtype=float,
        )
        fallback_model = (
            calculate_six_strategy_tax_model(
                weights=weights,
                expected_returns=(
                    expected_returns
                ),
                total_asset=(
                    request.total_asset
                ),
                request=request,
                account_buckets=(
                    portfolio_response[
                        "tax_breakdown"
                    ]["account_buckets"]
                ),
            )
        )
        standalone = (
            fallback_model.get(
                "standalone",
                [],
            )
        )
        combined = fallback_model.get(
            "combined",
            {},
        )
    standalone_map = {card["key"]: card for card in standalone}
    contribution_won = combined.get("contributionsWon", {})

    cards = []
    for key, meta in TAX_STRATEGY_META.items():
        card = standalone_map.get(key, {})
        contribution = safe_float(contribution_won.get(key))
        raw_reason = (
            combined.get("ineligible", {}).get(key)
            or combined.get("exhausted", {}).get(key)
            or card.get("ineligibleReason")
        )
        reason_payload = build_tax_strategy_reason(
            strategy_key=key,
            raw_reason=raw_reason,
            card=card,
            contribution=contribution,
        )
        cards.append(
            {
                "key": key,
                "title": meta["title"],
                "calculation_order": meta["calculation_order"],
                "rule_keys": meta.get("rule_keys", []),
                "standalone_saving": safe_round(
                    safe_float(card.get("savingWon")), 0
                ),
                "combined_contribution": safe_round(contribution, 0),
                "combined_contribution_manwon": int(round(contribution / 10_000)),
                "applicable": bool(card.get("applicable")) and contribution > 0,
                "transferable_amount": safe_round(
                    safe_float(card.get("transferableManwon")) * 10_000, 0
                ),
                "reason": reason_payload["reason"],
                "reason_code": reason_payload["reason_code"],
                "raw_reason": reason_payload["raw_reason"],
                # 프런트 TaxAdviceCard 타입과 1:1 정렬(스키마 통일).
                # calculate(tax_optimizer)·stress-metrics(base_tax/stressed_tax) 모두
                # 이 함수를 거치므로 두 엔드포인트가 동일 필드를 내보낸다 → 같은 렌더 코드.
                "savingManwon": int(round(contribution / 10_000)),
                "transferableManwon": int(
                    round(safe_float(card.get("transferableManwon")))
                ),
                "ineligibleReason": reason_payload["reason"],
            }
        )

    # 계산 순서와 화면 표시 순서는 분리한다.
    # 계산 엔진은 중복 과세소득을 제거하기 위한 calculation_order를 유지하고,
    # 화면 카드는 고객마다 위치가 바뀌지 않도록 TAX_STRATEGY_META의 고정 순서를 쓴다.
    for rank, card in enumerate(cards, start=1):
        card["priority_rank"] = rank

    return {
        "cards": cards,
        "combined_total": safe_round(combined.get("totalWon"), 0),
        "combined_total_manwon": combined.get("totalManwon", 0),
        "calculation_order": combined.get("calculationOrder", []),
        "display_order_basis": "fixed_strategy_order",
        "overlap_policy": (
            "종합과세 초과분은 ISA→저율배당→분리과세채 순으로 한 번만 사용하고, "
            "해외주식 손실과 250만원 기본공제는 같은 양도차익에 순차 적용합니다."
        ),
    }


def build_tax_optimizer_payload(
    portfolio_key: str,
    portfolio_response: Dict[str, Any],
    request: PortfolioRequest,
) -> Dict[str, Any]:
    tax_breakdown = portfolio_response["tax_breakdown"]
    account_buckets = tax_breakdown["account_buckets"]
    tax_saving_effect = tax_breakdown["tax_saving_effect"]

    gross_profit = safe_float(tax_breakdown["gross_profit"])
    tax_before = safe_float(tax_breakdown["total_tax_before_saving"])
    tax_after = safe_float(tax_breakdown["total_tax_after_saving"])
    tax_saving = max(tax_before - tax_after, 0.0)

    before_after_tax_profit = gross_profit - tax_before
    after_strategy_profit = gross_profit - tax_after
    before_after_tax_return = before_after_tax_profit / request.total_asset
    six_strategy = build_six_tax_strategy_cards(portfolio_response, request)
    combined_tax_saving = safe_float(six_strategy["combined_total"])
    modeled_tax_reduction = min(combined_tax_saving, max(tax_before, 0.0))
    combined_tax_after = max(tax_before - modeled_tax_reduction, 0.0)
    combined_after_tax_profit = gross_profit - combined_tax_after
    combined_after_tax_return = (
        combined_after_tax_profit / request.total_asset
        if request.total_asset > 0
        else 0.0
    )

    return {
        "portfolio_key": portfolio_key,
        "portfolio_name": portfolio_response["name"],
        "total_asset": safe_round(request.total_asset, 0),
        "headline": {
            "annual_tax_saving": safe_round(combined_tax_saving, 0),
            "tax_amount_before": safe_round(tax_before, 0),
            "tax_amount_after": safe_round(combined_tax_after, 0),
            "after_tax_return_before": safe_round(before_after_tax_return, 6),
            "after_tax_return_after": safe_round(combined_after_tax_return, 6),
            "after_tax_return_improvement_p": safe_round(
                combined_after_tax_return - before_after_tax_return, 6
            ),
            "modeled_tax_reduction": safe_round(modeled_tax_reduction, 0),
            "unapplied_credit_or_saving": safe_round(
                max(combined_tax_saving - modeled_tax_reduction, 0.0), 0
            ),
            "legacy_account_only_tax_saving": safe_round(tax_saving, 0),
        },
        "strategy_cards": six_strategy,
        "financial_income_tax_gauge": tax_breakdown[
            "financial_income_comprehensive_tax"
        ]["gauge"],
        "financial_income_comprehensive_tax_status": tax_breakdown[
            "financial_income_comprehensive_tax"
        ],
        "account_cards": {
            "isa": build_isa_tax_card(account_buckets, tax_saving_effect),
            "irp": build_irp_tax_card(account_buckets, tax_saving_effect),
            "taxable_account": build_taxable_account_card(
                account_buckets,
                tax_breakdown,
            ),
        },
        "tax_flow": {
            "general_tax_before_strategy": {
                "after_tax_profit": safe_round(before_after_tax_profit, 0),
                "tax_amount": safe_round(tax_before, 0),
            },
            "after_tax_strategy": {
                "after_tax_profit": safe_round(after_strategy_profit, 0),
                "tax_amount": safe_round(tax_after, 0),
                "tax_saving": safe_round(tax_saving, 0),
            },
        },
        "common_tax_rules": get_common_tax_rules(),
        "notes": [
            "세금 계산은 프로젝트용 간이 추정입니다.",
            "실제 세액은 전체 소득·실현손익·상품 요건에 따라 달라집니다.",
        ],
    }


def build_tax_optimizer_map(
    full_response: Dict[str, Any],
    request: PortfolioRequest,
) -> Dict[str, Any]:
    portfolios = full_response["portfolios"]

    return {
        "current": build_tax_optimizer_payload(
            "current",
            portfolios["current"],
            request,
        ),
        "portfolio_a": build_tax_optimizer_payload(
            "portfolio_a",
            portfolios["recommended_1"],
            request,
        ),
        "portfolio_b": build_tax_optimizer_payload(
            "portfolio_b",
            portfolios["recommended_2"],
            request,
        ),
    }


def extract_tax_inputs_payload(full_response: Dict[str, Any]) -> Dict[str, Any]:
    portfolios = full_response["portfolios"]

    return {
        "session_id": full_response["session_id"],
        "tax_inputs": {
            "current": {
                "name": portfolios["current"]["name"],
                "tax_breakdown": portfolios["current"]["tax_breakdown"],
            },
            "portfolio_a": {
                "name": portfolios["recommended_1"]["name"],
                "tax_breakdown": portfolios["recommended_1"]["tax_breakdown"],
            },
            "portfolio_b": {
                "name": portfolios["recommended_2"]["name"],
                "tax_breakdown": portfolios["recommended_2"]["tax_breakdown"],
            },
        },
        "tax_optimizer": full_response.get("tax_optimizer", {}),
        "common_tax_rules": get_common_tax_rules(),
        "note": "절세 화면용 계좌별 카드와 세금 흐름을 함께 반환.",
    }
