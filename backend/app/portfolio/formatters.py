# ruff: noqa: E501
"""§12-2. API 명세서 ⑤ 응답 포맷터."""

from datetime import datetime
from zoneinfo import ZoneInfo
import math
from typing import Dict, List, Optional, Any

from .constants import BACKTEST_BASE_INDEX
from .assets import RISK_LEVEL_NAME
from .utils import safe_float, safe_round
from .dashboard_views import build_dashboard_allocation_payload as build_grouped_allocation_payload
from .dashboard_views import build_common_correlation_heatmap_payload as build_grouped_correlation_payload

KST = ZoneInfo("Asia/Seoul")


def rate_to_percent(value: Any, digits: int = 2) -> float:
    return safe_round(safe_float(value) * 100.0, digits)


def round_allocation_percentages(
    asset_weights: List[tuple[str, float]],
) -> Dict[str, float]:
    """최대잔여법으로 소수점 둘째 자리 비중 합계를 정확히 100.00으로 맞춘다."""

    positive = [(asset, max(safe_float(weight), 0.0)) for asset, weight in asset_weights]
    positive = [(asset, weight) for asset, weight in positive if weight > 1e-12]
    total = sum(weight for _, weight in positive)
    if total <= 0:
        return {}

    raw_units = [
        (asset, weight / total * 10_000.0, index)
        for index, (asset, weight) in enumerate(positive)
    ]
    floor_units = {
        asset: int(math.floor(units + 1e-12))
        for asset, units, _ in raw_units
    }
    remaining = 10_000 - sum(floor_units.values())

    ranked = sorted(
        raw_units,
        key=lambda item: (-(item[1] - math.floor(item[1] + 1e-12)), item[2]),
    )
    for index in range(max(remaining, 0)):
        asset = ranked[index % len(ranked)][0]
        floor_units[asset] += 1

    return {
        asset: round(units / 100.0, 2)
        for asset, units in floor_units.items()
    }



def build_allocation_payload(
    portfolio: Dict[str, Any],
) -> List[Dict[str, Any]]:
    return build_grouped_allocation_payload(portfolio)

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
    benchmark_backtest = portfolio.get("benchmark_backtest") or {}
    benchmark_backtests = portfolio.get("benchmark_backtests") or {}

    item = {
        "kind": kind,
        "rank": rank,
        "label": label,
        "badge": badge,
        "allocation": build_allocation_payload(portfolio),
        "allocation_total": 100.0,
        "metrics": build_metrics_payload(portfolio),
        "metrics_krw": metrics_krw,
        "vs_current_krw": vs_current_krw,
        "backtest": build_backtest_payload(portfolio["cumulative_returns"]),
        "benchmark": {
            "metadata": benchmark_backtest.get("metadata", {}),
            "backtest": build_backtest_payload(
                benchmark_backtest.get("series", [])
            ),
        },
        "benchmarks": {
            key: {
                "metadata": benchmark.get("metadata", {}),
                "backtest": build_backtest_payload(
                    benchmark.get("series", [])
                ),
            }
            for key, benchmark in benchmark_backtests.items()
        },
        "tax": build_tax_payload(portfolio, current_portfolio),
    }
    risk_contribution_heatmap = (
        portfolio.get("risk_contribution_heatmap")
        or portfolio.get("dashboard_risk_contribution_heatmap")
    )
    if risk_contribution_heatmap is None:
        raise ValueError(
            "포트폴리오 응답에 risk_contribution_heatmap이 없습니다."
        )
    item["risk_contribution_heatmap"] = risk_contribution_heatmap
    return item



def build_correlation_heatmap_payload(
    full_response: Dict[str, Any],
) -> Dict[str, Any]:
    return build_grouped_correlation_payload(full_response)

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
        "correlation_heatmap": build_correlation_heatmap_payload(full_response),
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
        # 절세 최적화 화면(절세 6카드 = strategy_cards)용 페이로드.
        # run_full_analysis가 이미 core["tax_optimizer"]까지 계산하므로,
        # 별도 호출(deprecated /api/tax-optimizer = 분석 재실행) 없이 그대로 싣는다.
        # 구조는 stress-metrics의 base_tax/stressed_tax와 동일한
        # build_tax_optimizer_payload 출력이라 프런트가 같은 코드로 렌더한다.
        "tax_optimizer": full_response.get("tax_optimizer", {}),
        "notes": full_response["notes"],
    }
