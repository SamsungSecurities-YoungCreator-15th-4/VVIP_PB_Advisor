# ruff: noqa: E501
"""portfolio_logic.py 분할: generation 모듈."""


import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional, Tuple

from .assets import ASSET_TICKERS
from .constants import DEFAULT_RANDOM_SEED, PORTFOLIO_B_MIN_WEIGHT_DISTANCE, SEPARATE_TAX_BOND_MIN_HOLDING_YEARS
from .metrics import calculate_metrics, evaluate_guideline_detail, is_suitable_for_client
from .models import PortfolioRequest
from .utils import normalize_weights, safe_float, safe_round, validate_required_assets_available, validate_unique_asset
from .unique_semantic import (
    build_unique_constraint_warnings,
    calculate_soft_preference_alignment,
    evaluate_unique_constraints,
    get_excluded_assets,
    validate_unique_constraint_consistency,
)

# ============================================================
# 10. 포트폴리오 생성 / 점수화
# ============================================================



def is_separate_tax_bond_allowed(request: PortfolioRequest) -> bool:
    return request.investment_horizon_years >= SEPARATE_TAX_BOND_MIN_HOLDING_YEARS


def get_effective_unique_asset(request: PortfolioRequest) -> str:
    unique_asset = validate_unique_asset(request.unique_asset)
    if unique_asset == "separate_tax_bond" and not is_separate_tax_bond_allowed(request):
        return "cash"
    return unique_asset


def get_recommendation_eligible_assets(
    available_assets: List[str],
    request: PortfolioRequest,
) -> List[str]:
    eligible_assets = list(available_assets)
    if not is_separate_tax_bond_allowed(request):
        eligible_assets = [
            asset for asset in eligible_assets if asset != "separate_tax_bond"
        ]
    excluded_assets = get_excluded_assets(request.unique_profile)
    eligible_assets = [
        asset for asset in eligible_assets if asset not in excluded_assets
    ]
    return eligible_assets


def build_constraint_warnings(request: PortfolioRequest) -> List[str]:
    warnings = []
    if not is_separate_tax_bond_allowed(request):
        warnings.append(
            "investment_horizon_years가 3년 미만이므로 추천 포트폴리오에서는 "
            "분리과세채(separate_tax_bond)를 제외했습니다. 현재 포트폴리오에 이미 "
            "들어온 비중은 평가만 수행합니다."
        )
        if request.unique_asset == "separate_tax_bond":
            warnings.append(
                "unique_asset=separate_tax_bond 입력은 3년 미만 기간 조건과 맞지 않아 "
                "unique 필요자금 배치 자산을 cash로 대체했습니다."
            )
    warnings.extend(build_unique_constraint_warnings(request))
    return warnings


def generate_random_weights(
    assets: Optional[List[str]] = None,
    rng: Optional[np.random.Generator] = None,
) -> Dict[str, float]:
    assets = list(ASSET_TICKERS.keys()) if assets is None else list(assets)
    if not assets:
        raise ValueError("랜덤 포트폴리오를 생성할 자산 목록이 비어 있습니다.")

    rng = rng or np.random.default_rng(DEFAULT_RANDOM_SEED)
    alpha = np.ones(len(assets))
    sampled = rng.dirichlet(alpha)
    return {asset: float(weight) for asset, weight in zip(assets, sampled)}


def apply_unique_constraint(
    base_weights: Dict[str, float],
    total_asset: float,
    unique_need_amount: float,
    unique_asset: str,
) -> Dict[str, float]:
    unique_asset = validate_unique_asset(unique_asset)
    unique_ratio = min(max(unique_need_amount / total_asset, 0.0), 1.0)
    investable_ratio = 1.0 - unique_ratio

    final_weights = {asset: 0.0 for asset in ASSET_TICKERS.keys()}
    final_weights[unique_asset] += unique_ratio

    normalized_base = normalize_weights(base_weights)

    for asset, weight in normalized_base.items():
        final_weights[asset] += weight * investable_ratio

    return normalize_weights(final_weights)


# 프론트는 세후수익률을 % 기준 소수점 1자리로 보여준다.
# 내부 ratio에서는 소수점 3자리 반올림이 같은 화면 표시값을 뜻한다.
AFTER_TAX_RETURN_RATIO_TIE_PRECISION = 3

# 위험기여도 집중도는 1bp(0.01%p) 단위가 같은 후보에서만
# 정성 선호를 보조 기준으로 사용한다.
RISK_CONTRIBUTION_RATIO_TIE_PRECISION = 4


def build_selection_rank_tuple(
    metrics: Dict[str, Any],
    soft_preference_score: float = 0.0,
) -> Tuple[Any, ...]:
    """A: 화면상 세후수익률이 같은 후보에서만 약한 선호를 우선한다."""

    after_tax_return = safe_float(metrics.get("after_tax_return"))
    return (
        safe_round(after_tax_return, AFTER_TAX_RETURN_RATIO_TIE_PRECISION),
        safe_float(soft_preference_score),
        after_tax_return,
        safe_float(metrics.get("expected_return")),
        safe_float(metrics.get("sharpe_ratio")),
        -safe_float(metrics.get("historical_var_95_daily_loss")),
        -safe_float(metrics.get("risk_contribution_max_share")),
        safe_float(metrics.get("mdd")),
    )


def build_portfolio_b_rank_tuple(
    metrics: Dict[str, Any],
    soft_preference_score: float = 0.0,
) -> Tuple[Any, ...]:
    """B: 위험집중도가 1bp 단위로 같은 후보에서만 약한 선호를 우선한다."""

    risk_contribution = safe_float(
        metrics.get("risk_contribution_max_share")
    )
    return (
        safe_round(
            risk_contribution,
            RISK_CONTRIBUTION_RATIO_TIE_PRECISION,
        ),
        -safe_float(soft_preference_score),
        risk_contribution,
        safe_float(metrics.get("historical_var_95_daily_loss")),
        safe_float(metrics.get("volatility")),
        -safe_float(metrics.get("after_tax_return")),
        -safe_float(metrics.get("sharpe_ratio")),
    )


def build_portfolio_b_fallback_rank_tuple(
    metrics: Dict[str, Any],
    target_after_tax_return: float,
    soft_preference_score: float = 0.0,
) -> Tuple[Any, ...]:
    """목표 부족 폭의 화면 표시값이 같은 후보에서만 약한 선호를 우선한다."""

    after_tax_return = safe_float(metrics.get("after_tax_return"))
    target_shortfall = max(target_after_tax_return - after_tax_return, 0.0)
    return (
        safe_round(
            target_shortfall,
            AFTER_TAX_RETURN_RATIO_TIE_PRECISION,
        ),
        -safe_float(soft_preference_score),
        target_shortfall,
        safe_float(metrics.get("risk_contribution_max_share")),
        safe_float(metrics.get("historical_var_95_daily_loss")),
        safe_float(metrics.get("volatility")),
        -after_tax_return,
    )


def build_selection_summary(
    metrics: Dict[str, Any],
    portfolio_type: str = "current",
    target_after_tax_return: Optional[float] = None,
) -> Dict[str, Any]:
    after_tax_return = safe_float(metrics.get("after_tax_return"))
    risk_control = metrics.get("selection_risk_control", {})
    checks = risk_control.get("checks", {})

    common_filters = {
        "suitability": True,
        "liquidity": True,
        "historical_var_95": bool(checks.get("historical_var_95", False)),
        "risk_contribution": bool(checks.get("risk_contribution", False)),
    }

    if portfolio_type == "A":
        return {
            "portfolio_type": "A",
            "strategy_type": "return_seeking",
            "ranking_basis": [
                "after_tax_return_desc",
                "soft_preference_alignment_desc_within_primary_display_tie",
                "expected_return_desc",
                "sharpe_ratio_desc",
                "historical_var_95_asc",
                "risk_contribution_max_share_asc",
            ],
            "common_filters": common_filters,
            "risk_control": risk_control,
            "primary_objective": "after_tax_return_desc",
            "achieved_after_tax_return": safe_round(after_tax_return, 6),
            "note": (
                "고객 적합성·유동성·VaR·위험기여도 제한을 모두 통과한 후보 중 "
                "예상 세후수익률이 가장 높은 포트폴리오입니다."
            ),
        }

    if portfolio_type == "B":
        target = safe_float(target_after_tax_return)
        target_shortfall = max(target - after_tax_return, 0.0)
        target_met = after_tax_return >= target
        return {
            "portfolio_type": "B",
            "strategy_type": "target_return_risk_minimizing",
            "ranking_basis": (
                [
                    "target_after_tax_return_filter",
                    "risk_contribution_max_share_asc",
                    "soft_preference_alignment_desc_within_primary_display_tie",
                    "historical_var_95_asc",
                    "volatility_asc",
                    "after_tax_return_desc",
                ]
                if target_met
                else [
                    "target_shortfall_asc",
                    "soft_preference_alignment_desc_within_primary_display_tie",
                    "risk_contribution_max_share_asc",
                    "historical_var_95_asc",
                    "volatility_asc",
                    "after_tax_return_desc",
                ]
            ),
            "common_filters": common_filters,
            "risk_control": risk_control,
            "primary_objective": (
                "risk_contribution_max_share_asc"
                if target_met
                else "target_shortfall_asc"
            ),
            "target_after_tax_return": safe_round(target, 6),
            "achieved_after_tax_return": safe_round(after_tax_return, 6),
            "target_met": target_met,
            "target_shortfall": safe_round(target_shortfall, 6),
            "note": (
                "IPS 목표 세후수익률을 충족한 후보 중 위험기여도 집중도가 "
                "가장 낮은 포트폴리오입니다."
                if target_met
                else "IPS 목표 세후수익률 달성 후보가 없어 목표 부족 폭이 가장 작고 "
                "위험기여도 집중도가 낮은 대체 포트폴리오를 선택했습니다."
            ),
        }

    return {
        "portfolio_type": portfolio_type,
        "ranking_basis": [],
        "risk_control": risk_control,
        "note": "현재 포트폴리오는 추천 후보 선정 대상이 아닙니다.",
    }


def calculate_portfolio_return_series(
    weights: Dict[str, float],
    returns: pd.DataFrame,
) -> pd.Series:
    weights = normalize_weights(weights)
    validate_required_assets_available(weights, list(returns.columns), "portfolio_weights")
    assets = [
        asset
        for asset in weights.keys()
        if asset in returns.columns and weights[asset] > 1e-12
    ]
    w = np.array([weights[asset] for asset in assets], dtype=float)
    w = w / w.sum()
    return returns[assets].dot(w)


def calculate_portfolio_return_correlation(
    weights_a: Dict[str, float],
    weights_b: Dict[str, float],
    returns: pd.DataFrame,
    series_a: Optional[pd.Series] = None,
) -> float:
    if series_a is None:
        series_a = calculate_portfolio_return_series(
            weights_a,
            returns,
        )
    series_b = calculate_portfolio_return_series(
        weights_b,
        returns,
    )
    corr = series_a.corr(series_b)

    if corr is None or not np.isfinite(corr):
        return 0.0

    return float(corr)




def calculate_weight_distance(
    weights_a: Dict[str, float],
    weights_b: Dict[str, float],
) -> float:
    normalized_a = normalize_weights(
        weights_a
    )
    normalized_b = normalize_weights(
        weights_b
    )
    assets = (
        set(normalized_a)
        | set(normalized_b)
    )
    return float(
        0.5
        * sum(
            abs(
                normalized_a.get(
                    asset,
                    0.0,
                )
                - normalized_b.get(
                    asset,
                    0.0,
                )
            )
            for asset in assets
        )
    )

def find_recommended_portfolios(
    returns: pd.DataFrame,
    expected_returns: pd.Series,
    request: PortfolioRequest,
    cov_matrix: Optional[pd.DataFrame] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """공통 하드필터 후 A는 세후수익률 최대, B는 목표수익률 달성 후 위험 최소."""
    target_after_tax_return = safe_float(
        request.target_after_tax_return,
        default=np.nan,
    )
    if not np.isfinite(target_after_tax_return) or target_after_tax_return <= 0:
        raise ValueError(
            "포트폴리오 B 선정에 필요한 RRTTLLU.Return 목표 세후수익률이 없습니다."
        )

    rng = np.random.default_rng(request.random_seed)
    candidates: List[Dict[str, Any]] = []
    generated_count = request.num_simulations
    guideline_pass_count = 0
    suitable_count = 0
    liquidity_pass_count = 0
    risk_control_pass_count = 0
    unique_semantic_pass_count = 0
    common_filter_pass_count = 0
    rejection_counts = {
        "unique_semantic": 0,
        "suitability": 0,
        "liquidity": 0,
        "historical_var_95": 0,
        "risk_contribution": 0,
    }

    unique_constraint_conflicts = validate_unique_constraint_consistency(
        request.unique_profile
    )
    if unique_constraint_conflicts:
        raise ValueError(
            "Unique 의미 제약이 서로 충돌합니다: "
            + " ".join(unique_constraint_conflicts)
        )

    raw_available_assets = [
        asset for asset in ASSET_TICKERS.keys() if asset in returns.columns
    ]
    available_assets = get_recommendation_eligible_assets(
        raw_available_assets,
        request,
    )
    effective_unique_asset = get_effective_unique_asset(request)
    excluded_by_unique = get_excluded_assets(request.unique_profile)
    if request.unique_need_amount > 0 and effective_unique_asset in excluded_by_unique:
        raise ValueError(
            "Unique의 투자 제외 지시와 필요자금 배치 자산이 충돌합니다: "
            f"{effective_unique_asset}. unique_asset 또는 Unique 문장을 확인해 주세요."
        )
    validate_required_assets_available(
        {effective_unique_asset: 1.0},
        raw_available_assets,
        "unique_asset",
    )

    for _ in range(request.num_simulations):
        base_weights = generate_random_weights(assets=available_assets, rng=rng)
        final_weights = apply_unique_constraint(
            base_weights=base_weights,
            total_asset=request.total_asset,
            unique_need_amount=request.unique_need_amount,
            unique_asset=effective_unique_asset,
        )
        semantic_passed, _semantic_violations = evaluate_unique_constraints(
            candidate_weights=final_weights,
            unique_profile=request.unique_profile,
            current_weights=request.current_weights,
        )
        if not semantic_passed:
            rejection_counts["unique_semantic"] += 1
            continue
        unique_semantic_pass_count += 1

        metrics = calculate_metrics(
            weights=final_weights,
            returns=returns,
            expected_returns=expected_returns,
            request=request,
            cov_matrix=cov_matrix,
            candidate_mode=True,
        )

        if metrics["risk_level"] is not None:
            guideline_pass_count += 1

        suitability_passed = is_suitable_for_client(metrics, request.risk_profile)
        guideline_detail = evaluate_guideline_detail(metrics, request.risk_profile)
        liquidity_passed = bool(
            guideline_detail.get("hard_checks", {}).get("liquidity_coverage", False)
        )
        risk_control = metrics.get("selection_risk_control", {})
        risk_checks = risk_control.get("checks", {})
        var_passed = bool(risk_checks.get("historical_var_95", False))
        risk_contribution_passed = bool(
            risk_checks.get("risk_contribution", False)
        )

        if suitability_passed:
            suitable_count += 1
        else:
            rejection_counts["suitability"] += 1

        if liquidity_passed:
            liquidity_pass_count += 1
        else:
            rejection_counts["liquidity"] += 1

        if var_passed:
            pass
        else:
            rejection_counts["historical_var_95"] += 1

        if risk_contribution_passed:
            pass
        else:
            rejection_counts["risk_contribution"] += 1

        if risk_control.get("passed", False):
            risk_control_pass_count += 1

        common_filter_passed = all(
            (
                suitability_passed,
                liquidity_passed,
                var_passed,
                risk_contribution_passed,
            )
        )
        if not common_filter_passed:
            continue

        common_filter_pass_count += 1
        soft_preference_alignment = (
            calculate_soft_preference_alignment(
                candidate_weights=final_weights,
                unique_profile=request.unique_profile,
            )
        )
        candidates.append(
            {
                "weights": final_weights,
                "metrics": metrics,
                "soft_preference_alignment": soft_preference_alignment,
                "selection_rank": build_selection_rank_tuple(
                    metrics,
                    soft_preference_alignment.get("score", 0.0),
                ),
            }
        )

    portfolio_b_rescue_simulations = 0
    if len(candidates) == 1:
        portfolio_b_rescue_simulations = max(
            500,
            min(request.num_simulations, 3000),
        )
        generated_count += portfolio_b_rescue_simulations

        for _ in range(portfolio_b_rescue_simulations):
            base_weights = generate_random_weights(
                assets=available_assets,
                rng=rng,
            )
            final_weights = apply_unique_constraint(
                base_weights=base_weights,
                total_asset=request.total_asset,
                unique_need_amount=request.unique_need_amount,
                unique_asset=effective_unique_asset,
            )
            semantic_passed, _semantic_violations = (
                evaluate_unique_constraints(
                    candidate_weights=final_weights,
                    unique_profile=request.unique_profile,
                    current_weights=request.current_weights,
                )
            )
            if not semantic_passed:
                rejection_counts["unique_semantic"] += 1
                continue
            unique_semantic_pass_count += 1

            metrics = calculate_metrics(
                weights=final_weights,
                returns=returns,
                expected_returns=expected_returns,
                request=request,
                cov_matrix=cov_matrix,
                candidate_mode=True,
            )

            if metrics["risk_level"] is not None:
                guideline_pass_count += 1

            suitability_passed = is_suitable_for_client(
                metrics,
                request.risk_profile,
            )
            guideline_detail = evaluate_guideline_detail(
                metrics,
                request.risk_profile,
            )
            liquidity_passed = bool(
                guideline_detail
                .get("hard_checks", {})
                .get("liquidity_coverage", False)
            )
            risk_control = metrics.get(
                "selection_risk_control",
                {},
            )
            risk_checks = risk_control.get(
                "checks",
                {},
            )
            var_passed = bool(
                risk_checks.get(
                    "historical_var_95",
                    False,
                )
            )
            risk_contribution_passed = bool(
                risk_checks.get(
                    "risk_contribution",
                    False,
                )
            )

            if suitability_passed:
                suitable_count += 1
            else:
                rejection_counts["suitability"] += 1

            if liquidity_passed:
                liquidity_pass_count += 1
            else:
                rejection_counts["liquidity"] += 1

            if not var_passed:
                rejection_counts["historical_var_95"] += 1
            if not risk_contribution_passed:
                rejection_counts["risk_contribution"] += 1

            if risk_control.get("passed", False):
                risk_control_pass_count += 1

            common_filter_passed = all(
                (
                    suitability_passed,
                    liquidity_passed,
                    var_passed,
                    risk_contribution_passed,
                )
            )
            if not common_filter_passed:
                continue

            common_filter_pass_count += 1
            soft_preference_alignment = (
                calculate_soft_preference_alignment(
                    candidate_weights=final_weights,
                    unique_profile=request.unique_profile,
                )
            )
            candidates.append(
                {
                    "weights": final_weights,
                    "metrics": metrics,
                    "soft_preference_alignment": (
                        soft_preference_alignment
                    ),
                    "selection_rank": build_selection_rank_tuple(
                        metrics,
                        soft_preference_alignment.get(
                            "score",
                            0.0,
                        ),
                    ),
                }
            )

    if not candidates:
        raise RuntimeError(
            "Unique 의미 제약·고객 적합성·유동성·VaR·위험기여도 제한을 모두 통과한 "
            "포트폴리오가 없습니다. Unique의 명시 비중/제외 조건과 num_simulations를 검토해야 합니다."
        )

    candidates = sorted(
        candidates,
        key=lambda candidate: candidate["selection_rank"],
        reverse=True,
    )

    # 포트폴리오 A: 공통 필터 통과 후보 중 세후수익률 최대.
    recommendation_1 = candidates[0]
    recommendation_1["selection_summary"] = build_selection_summary(
        recommendation_1["metrics"],
        portfolio_type="A",
        target_after_tax_return=target_after_tax_return,
    )
    recommendation_1["selection_summary"]["soft_preference_alignment"] = (
        recommendation_1.get("soft_preference_alignment", {})
    )

    # B는 A와 최소 비중 차이가 있는
    # 별도 대안을 우선한다.
    raw_portfolio_b_pool = candidates[1:]
    portfolio_b_available = bool(
        raw_portfolio_b_pool
    )
    distance_pairs = [
        (
            candidate,
            calculate_weight_distance(
                recommendation_1["weights"],
                candidate["weights"],
            ),
        )
        for candidate in raw_portfolio_b_pool
    ]
    distinct_pairs = [
        (candidate, distance)
        for candidate, distance in distance_pairs
        if (
            distance
            >= PORTFOLIO_B_MIN_WEIGHT_DISTANCE
        )
    ]

    if distinct_pairs:
        portfolio_b_pool = []
        for candidate, distance in distinct_pairs:
            candidate[
                "_weight_distance_from_a"
            ] = distance
            portfolio_b_pool.append(candidate)
        portfolio_b_distinctness_mode = (
            "minimum_weight_distance_met"
        )
    elif distance_pairs:
        maximum_distance = max(
            distance
            for _, distance in distance_pairs
        )
        portfolio_b_pool = []
        for candidate, distance in distance_pairs:
            if abs(
                distance - maximum_distance
            ) <= 1e-12:
                candidate[
                    "_weight_distance_from_a"
                ] = distance
                portfolio_b_pool.append(candidate)
        portfolio_b_distinctness_mode = (
            "most_distinct_candidate_fallback"
        )
    else:
        copied = dict(recommendation_1)
        copied[
            "_weight_distance_from_a"
        ] = 0.0
        portfolio_b_pool = [copied]
        portfolio_b_distinctness_mode = (
            "no_alternative_candidate"
        )

    target_met_candidates = [
        candidate
        for candidate in portfolio_b_pool
        if safe_float(candidate["metrics"].get("after_tax_return"))
        >= target_after_tax_return
    ]

    if target_met_candidates:
        recommendation_2 = min(
            target_met_candidates,
            key=lambda candidate: build_portfolio_b_rank_tuple(
                candidate["metrics"],
                candidate.get("soft_preference_alignment", {}).get("score", 0.0),
            ),
        )
        portfolio_b_selection_mode = "target_met_risk_minimization"
    else:
        recommendation_2 = min(
            portfolio_b_pool,
            key=lambda candidate: build_portfolio_b_fallback_rank_tuple(
                candidate["metrics"],
                target_after_tax_return,
                candidate.get("soft_preference_alignment", {}).get("score", 0.0),
            ),
        )
        portfolio_b_selection_mode = "target_shortfall_fallback"

    recommendation_2["selection_summary"] = build_selection_summary(
        recommendation_2["metrics"],
        portfolio_type="B",
        target_after_tax_return=target_after_tax_return,
    )
    recommendation_2["selection_summary"]["soft_preference_alignment"] = (
        recommendation_2.get("soft_preference_alignment", {})
    )

    portfolio_b_weight_distance = safe_float(
        recommendation_2.get(
            "_weight_distance_from_a",
            calculate_weight_distance(
                recommendation_1["weights"],
                recommendation_2["weights"],
            ),
        )
    )
    recommendation_2[
        "selection_summary"
    ].update(
        {
            "portfolio_b_available": (
                portfolio_b_available
            ),
            "weight_distance_from_portfolio_a": (
                safe_round(
                    portfolio_b_weight_distance,
                    6,
                )
            ),
            "minimum_weight_distance_required": (
                PORTFOLIO_B_MIN_WEIGHT_DISTANCE
            ),
            "distinctness_threshold_met": (
                portfolio_b_weight_distance
                >= PORTFOLIO_B_MIN_WEIGHT_DISTANCE
            ),
            "distinctness_mode": (
                portfolio_b_distinctness_mode
            ),
        }
    )

    # A/B 상관계수는 선정 조건이 아니라 화면 참고값으로만 제공한다.
    recommendation_1_series = calculate_portfolio_return_series(
        recommendation_1["weights"],
        returns,
    )
    recommendation_2["correlation_with_recommended_1"] = (
        calculate_portfolio_return_correlation(
            recommendation_1["weights"],
            recommendation_2["weights"],
            returns,
            series_a=recommendation_1_series,
        )
    )

    search_summary = {
        "generated_portfolios": generated_count,
        "initial_generated_portfolios": request.num_simulations,
        "portfolio_b_rescue_simulations": (
            portfolio_b_rescue_simulations
        ),
        "guideline_pass_portfolios": guideline_pass_count,
        "suitable_portfolios": suitable_count,
        "liquidity_pass_portfolios": liquidity_pass_count,
        "risk_control_pass_portfolios": risk_control_pass_count,
        "unique_semantic_pass_portfolios": unique_semantic_pass_count,
        "common_filter_pass_portfolios": common_filter_pass_count,
        "filtered_out_portfolios": generated_count - common_filter_pass_count,
        "rejection_counts": rejection_counts,
        "selection_method": 'portfolio_a_max_after_tax_return_portfolio_b_target_risk_minimization',
        "portfolio_a_selection_mode": "max_after_tax_return",
        "portfolio_b_selection_mode": portfolio_b_selection_mode,
        "portfolio_b_available": portfolio_b_available,
        "portfolio_b_distinctness_mode": portfolio_b_distinctness_mode,
        "portfolio_b_weight_distance": safe_round(
            portfolio_b_weight_distance, 6
        ),
        "portfolio_b_min_weight_distance": (
            PORTFOLIO_B_MIN_WEIGHT_DISTANCE
        ),
        "target_after_tax_return": safe_round(target_after_tax_return, 6),
        "random_seed": request.random_seed,
        "eligible_assets": available_assets,
        "unique_semantic_constraints": (
            request.unique_profile.get("semantic_constraints", [])
            if isinstance(request.unique_profile, dict)
            else []
        ),
        "unique_soft_preferences": (
            request.unique_profile.get("soft_preferences", [])
            if isinstance(request.unique_profile, dict)
            else []
        ),
        "soft_preference_policy": (
            "secondary_ranking_only_within_display_or_1bp_tie"
        ),
        "excluded_by_unique": sorted(excluded_by_unique),
        "excluded_by_horizon": (
            ["separate_tax_bond"]
            if "separate_tax_bond" in raw_available_assets
            and not is_separate_tax_bond_allowed(request)
            else []
        ),
    }

    return [recommendation_1, recommendation_2], search_summary
