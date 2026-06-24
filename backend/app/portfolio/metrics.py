# ruff: noqa: E501
"""portfolio_logic.py 분할: metrics 모듈."""


import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional, Tuple

from .assets import ALTERNATIVE_ASSETS, ASSET_DURATION_YEARS, ASSET_TICKERS, BOND_ASSETS, BOND_CASH_ASSETS, CASH_LIKE_ASSETS, CLIENT_RISK_LEVEL, FX_SENSITIVE_ASSETS, INTEREST_RATE_SENSITIVE_ASSETS, RISK_LEVEL_NAME, STOCK_ASSETS
from .constants import BACKTEST_BASE_INDEX, BENCHMARK_CONFIGS, BENCHMARK_POLICY_VERSION, DEFAULT_RANDOM_SEED, GUIDELINE_RULES, MIN_BETA_OBSERVATIONS, MONTE_CARLO_METRIC_RANGE_DISPLAY_CENTER, MONTE_CARLO_METRIC_RANGE_DISPLAY_LOWER, MONTE_CARLO_METRIC_RANGE_DISPLAY_UPPER, MONTE_CARLO_METRIC_RANGE_MAX_HORIZON_YEARS, MONTE_CARLO_METRIC_RANGE_PERCENTILES, MONTE_CARLO_METRIC_RANGE_SEED_OFFSET, MONTE_CARLO_METRIC_RANGE_SIMULATIONS, MONTE_CARLO_METRIC_RANGE_STEPS_PER_YEAR, MONTE_CARLO_METRIC_RANGE_VERSION, SELECTION_RISK_CONTROLS, SORTINO_NO_DOWNSIDE_CAP, TRADING_DAYS, VOL_STRESS_BETA, VOL_STRESS_CAP
from .models import PortfolioRequest
from .tax_accounts import allocate_account_buckets, calculate_after_tax_return, estimate_taxable_financial_income
from .utils import cap01, get_benchmark_config, normalize_weights, safe_float, safe_round, validate_required_assets_available

# ============================================================
# 8. 지표 계산
# ============================================================


def calculate_mdd(portfolio_daily_returns: pd.Series) -> float:
    cumulative = (1 + portfolio_daily_returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    return float(drawdown.min())


def build_portfolio_benchmark(
    weights: Dict[str, float],
    returns: pd.DataFrame,
    benchmark_key: str,
) -> Tuple[
    Optional[pd.Series],
    Dict[str, Any],
]:
    config = get_benchmark_config(
        benchmark_key
    )
    series_key = config["series_key"]
    normalized = normalize_weights(weights)
    equity_exposure = sum(
        normalized.get(asset, 0.0)
        for asset in [*STOCK_ASSETS, "reit"]
    )

    base_meta = {
        "policy": BENCHMARK_POLICY_VERSION,
        "benchmark_key": benchmark_key,
        "series_key": series_key,
        "ticker": config["ticker"],
        "label": config["label"],
        "currency": config.get("currency"),
        "return_basis": (
            "native_currency_adjusted_close_"
            "price_return"
        ),
        "comparison_role": (
            "display_and_beta_only"
        ),
        "minimum_beta_observations": (
            MIN_BETA_OBSERVATIONS
        ),
        "official_index_series": config[
            "official_index_series"
        ],
        "proxy_note": config["proxy_note"],
        "equity_portfolio_weight": safe_round(
            equity_exposure,
            6,
        ),
        "affects_portfolio_recommendation": (
            False
        ),
    }

    if series_key not in returns.columns:
        return None, {
            **base_meta,
            "applicable": False,
            "reason": "benchmark_data_missing",
        }

    benchmark = (
        returns[series_key]
        .replace(
            [np.inf, -np.inf],
            np.nan,
        )
        .dropna()
    )
    if benchmark.empty:
        return None, {
            **base_meta,
            "applicable": False,
            "reason": "benchmark_data_empty",
        }

    return benchmark, {
        **base_meta,
        "applicable": True,
        "reason": None,
    }


def align_portfolio_and_benchmark_returns(
    portfolio_daily_returns: pd.Series,
    benchmark_daily_returns: Optional[
        pd.Series
    ],
) -> pd.DataFrame:
    if benchmark_daily_returns is None:
        return pd.DataFrame(
            columns=[
                "portfolio",
                "benchmark",
            ]
        )

    return (
        pd.concat(
            [
                portfolio_daily_returns.rename(
                    "portfolio"
                ),
                benchmark_daily_returns.rename(
                    "benchmark"
                ),
            ],
            axis=1,
        )
        .replace(
            [np.inf, -np.inf],
            np.nan,
        )
        .dropna(how="any")
        .sort_index()
    )


def calculate_benchmark_comparisons(
    portfolio_daily_returns: pd.Series,
    weights: Dict[str, float],
    returns: pd.DataFrame,
) -> Dict[str, Any]:
    comparisons: Dict[str, Any] = {}

    for benchmark_key in (
        BENCHMARK_CONFIGS.keys()
    ):
        benchmark_returns, metadata = (
            build_portfolio_benchmark(
                weights=weights,
                returns=returns,
                benchmark_key=benchmark_key,
            )
        )
        metadata = dict(metadata)

        if benchmark_returns is None:
            beta = None
            common_observations = 0
        else:
            aligned = (
                align_portfolio_and_benchmark_returns(
                    portfolio_daily_returns,
                    benchmark_returns,
                )
            )
            common_observations = len(
                aligned
            )
            metadata.update(
                {
                    "common_observations": (
                        common_observations
                    ),
                    "common_data_start": (
                        aligned.index[0].strftime(
                            "%Y-%m-%d"
                        )
                        if common_observations > 0
                        else None
                    ),
                    "common_data_end": (
                        aligned.index[-1].strftime(
                            "%Y-%m-%d"
                        )
                        if common_observations > 0
                        else None
                    ),
                }
            )

            if (
                common_observations
                < MIN_BETA_OBSERVATIONS
            ):
                beta = None
                metadata.update(
                    {
                        "applicable": False,
                        "reason": (
                            "insufficient_common_"
                            "observations"
                        ),
                    }
                )
            else:
                beta = calculate_beta(
                    portfolio_daily_returns,
                    benchmark_returns,
                )
                if beta is None:
                    metadata.update(
                        {
                            "applicable": False,
                            "reason": (
                                "benchmark_variance_"
                                "or_covariance_invalid"
                            ),
                        }
                    )

        comparisons[benchmark_key] = {
            "beta": (
                safe_round(beta, 6)
                if beta is not None
                else None
            ),
            "metadata": metadata,
        }

    return comparisons


def calculate_beta(
    portfolio_daily_returns: pd.Series,
    benchmark_daily_returns: Optional[
        pd.Series
    ],
) -> Optional[float]:
    aligned = (
        align_portfolio_and_benchmark_returns(
            portfolio_daily_returns,
            benchmark_daily_returns,
        )
    )
    if len(aligned) < MIN_BETA_OBSERVATIONS:
        return None

    benchmark_variance = float(
        aligned["benchmark"].var()
    )
    if (
        benchmark_variance < 1e-12
        or not np.isfinite(
            benchmark_variance
        )
    ):
        return None

    covariance = float(
        aligned["portfolio"].cov(
            aligned["benchmark"]
        )
    )
    if not np.isfinite(covariance):
        return None

    beta = (
        covariance / benchmark_variance
    )
    return (
        float(beta)
        if np.isfinite(beta)
        else None
    )


def calculate_sortino(
    portfolio_daily_returns: pd.Series,
    annual_return: float,
    risk_free_rate: float,
) -> float:
    daily_target = (1 + risk_free_rate) ** (1 / TRADING_DAYS) - 1
    downside_returns = portfolio_daily_returns[portfolio_daily_returns < daily_target]

    if len(downside_returns) == 0:
        return SORTINO_NO_DOWNSIDE_CAP

    downside_deviation = downside_returns.std() * np.sqrt(TRADING_DAYS)

    if downside_deviation < 1e-8 or np.isnan(downside_deviation):
        return SORTINO_NO_DOWNSIDE_CAP if annual_return > risk_free_rate else 0.0

    return float((annual_return - risk_free_rate) / downside_deviation)


def calculate_historical_var(
    portfolio_daily_returns: pd.Series,
    confidence_level: float = 0.95,
) -> Dict[str, Any]:
    if portfolio_daily_returns.empty:
        return {
            "confidence_level": confidence_level,
            "daily_return_quantile": 0.0,
            "daily_loss": 0.0,
            "annualized_loss_approx": 0.0,
            "method": "historical",
        }

    q = 1.0 - confidence_level
    daily_quantile = float(portfolio_daily_returns.quantile(q))
    daily_loss = max(-daily_quantile, 0.0)
    annualized_loss = daily_loss * np.sqrt(TRADING_DAYS)

    return {
        "confidence_level": confidence_level,
        "daily_return_quantile": safe_round(daily_quantile, 6),
        "daily_loss": safe_round(daily_loss, 6),
        "annualized_loss_approx": safe_round(annualized_loss, 6),
        "method": "historical_5_percentile",
    }


def calculate_risk_contribution(
    assets: List[str],
    weights_array: np.ndarray,
    cov_matrix: pd.DataFrame,
) -> Dict[str, Any]:
    if len(assets) == 0:
        return {
            "by_asset": {},
            "max_share": 0.0,
            "hhi": 0.0,
            "method": "variance_contribution",
        }

    selected_cov = cov_matrix.reindex(index=assets, columns=assets).fillna(0.0)
    cov_values = selected_cov.values
    variance = float(weights_array.T @ cov_values @ weights_array)

    if variance <= 1e-12 or not np.isfinite(variance):
        zero_map = {asset: 0.0 for asset in assets}
        return {
            "by_asset": zero_map,
            "max_share": 0.0,
            "hhi": 0.0,
            "method": "variance_contribution",
        }

    marginal = cov_values @ weights_array
    raw_contribution = weights_array * marginal
    shares = raw_contribution / variance
    positive_shares = np.maximum(shares, 0.0)

    return {
        "by_asset": {
            asset: safe_round(value, 6) for asset, value in zip(assets, shares)
        },
        "max_share": safe_round(float(positive_shares.max()), 6),
        "hhi": safe_round(float(np.square(positive_shares).sum()), 6),
        "method": "variance_contribution",
    }


def evaluate_selection_risk_controls(
    metrics: Dict[str, Any],
    client_risk_profile: str,
) -> Dict[str, Any]:
    rule = SELECTION_RISK_CONTROLS[client_risk_profile]
    var_loss = metrics["historical_var_95_daily_loss"]
    max_risk_share = metrics["risk_contribution_max_share"]

    checks = {
        "historical_var_95": (
            var_loss <= rule["historical_var_95_daily_max_loss"]
        ),
        "risk_contribution": (
            max_risk_share <= rule["risk_contribution_max_share"]
        ),
    }

    return {
        "profile": client_risk_profile,
        "passed": all(checks.values()),
        "checks": checks,
        "thresholds": rule,
    }


def calculate_asset_group_weights(weights: Dict[str, float]) -> Dict[str, float]:
    stock_weight = sum(weights.get(asset, 0.0) for asset in STOCK_ASSETS)
    bond_cash_weight = sum(weights.get(asset, 0.0) for asset in BOND_CASH_ASSETS)
    alternative_weight = sum(weights.get(asset, 0.0) for asset in ALTERNATIVE_ASSETS)

    return {
        "stock_weight": float(stock_weight),
        "bond_cash_weight": float(bond_cash_weight),
        "alternative_weight": float(alternative_weight),
    }


def calculate_portfolio_duration(weights: Dict[str, float]) -> float:
    bond_weight = sum(weights.get(asset, 0.0) for asset in BOND_ASSETS)
    if bond_weight <= 1e-8:
        return 0.0

    weighted_duration = sum(
        weights.get(asset, 0.0) * ASSET_DURATION_YEARS.get(asset, 0.0)
        for asset in BOND_ASSETS
    )

    return float(weighted_duration / bond_weight)


def target_duration_by_horizon(investment_horizon_years: int) -> float:
    if investment_horizon_years <= 3:
        return 1.5
    if investment_horizon_years <= 7:
        return 4.0
    return 7.0


def calculate_duration_fit_score(portfolio_duration: float, target_duration: float) -> float:
    if target_duration <= 0:
        return 1.0
    diff_ratio = abs(portfolio_duration - target_duration) / target_duration
    return cap01(1 - diff_ratio)


def calculate_isa_locked_amount(
    weights: Dict[str, float],
    total_asset: float,
    request: PortfolioRequest,
) -> float:
    if not request.isa_enabled or request.isa_years_until_liquid <= 0:
        return 0.0

    account_buckets = allocate_account_buckets(weights, total_asset, request)
    return float(account_buckets["isa"]["locked_amount_for_liquidity"])


def calculate_liquidity_coverage(
    weights: Dict[str, float],
    total_asset: float,
    unique_need_amount: float,
    request: PortfolioRequest,
) -> float:
    if unique_need_amount <= 0:
        return 1.0

    liquid_weight = sum(weights.get(asset, 0.0) for asset in CASH_LIKE_ASSETS)
    liquid_amount = liquid_weight * total_asset

    isa_locked_amount = calculate_isa_locked_amount(weights, total_asset, request)
    usable_liquid_amount = max(liquid_amount - isa_locked_amount, 0.0)

    return float(usable_liquid_amount / unique_need_amount)


def calculate_stress_test(
    weights: Dict[str, float],
    request: PortfolioRequest,
) -> Dict[str, Any]:
    interest_rate_effect = 0.0

    for asset in INTEREST_RATE_SENSITIVE_ASSETS:
        asset_weight = weights.get(asset, 0.0)
        duration = ASSET_DURATION_YEARS.get(asset, 0.0)
        interest_rate_effect += asset_weight * (-duration * request.stress_interest_rate_shock)

    fx_effect = (
        sum(weights.get(asset, 0.0) for asset in FX_SENSITIVE_ASSETS) * request.stress_fx_shock
    )

    total_stress_return = interest_rate_effect + fx_effect
    estimated_loss_ratio = min(total_stress_return, 0.0)

    return {
        "interest_rate_shock": request.stress_interest_rate_shock,
        "fx_shock": request.stress_fx_shock,
        "interest_rate_effect": round(float(interest_rate_effect), 6),
        "fx_effect": round(float(fx_effect), 6),
        "total_stress_return": round(float(total_stress_return), 6),
        "estimated_loss_ratio": round(float(estimated_loss_ratio), 6),
        "method": "금리효과는 -듀레이션×금리변화, 환율효과는 외화노출자산비중×환율변화로 단순 추정.",
    }


# ── 시계열 충격 주입 ──────────────────────────────────────────────────────────
# 기존 calculate_stress_test가 스트레스 수익률 한 값을 내는 것과 달리, 아래 헬퍼는
# 자산별 충격을 일별수익률에 주입해 기대수익률·변동성·샤프·소르티노·MDD·세후수익률을
# 동일한 계산 경로에서 재계산한다. PR #69의 하위호환 규약을 그대로 유지한다.


def _vol_multiplier(shock: float) -> float:
    """충격 절댓값에 따른 변동성 확대 계수."""
    return min(1.0 + VOL_STRESS_BETA * abs(float(shock)), VOL_STRESS_CAP)


def derive_asset_shocks_from_macro(
    assets: List[str],
    request: PortfolioRequest,
) -> Dict[str, float]:
    """금리·환율 입력을 자산별 연간 기대수익률 충격으로 환산한다."""
    shocks: Dict[str, float] = {}
    for asset in assets:
        shock = 0.0
        if asset in INTEREST_RATE_SENSITIVE_ASSETS:
            shock += -ASSET_DURATION_YEARS.get(asset, 0.0) * request.stress_interest_rate_shock
        if asset in FX_SENSITIVE_ASSETS:
            shock += request.stress_fx_shock
        if shock != 0.0:
            shocks[asset] = float(shock)
    return shocks


# ── 역사적 위기 시나리오 프리셋 (버튼식 재현용) ──────────────────────────────
# 자산군별 연간 충격(소수). calculate_metrics(shocks=...)에 그대로 주입한다.
# 금리·환율 2축 슬라이더로는 주식 급락·상관관계 붕괴를 표현 못 하므로, 위기는
# 자산군별 실측 충격 벡터로 별도 정의한다. 값은 각 위기 국면 실현 수익률 점추정.
#
# 출처(연간 실현 수익률 점추정):
#   2008 금융위기: KOSPI -41%, S&P500 -38.5%, Nasdaq100 -41%, 리츠(NAREIT) -37%,
#     美 종합채권 +5%(국채 강세), 금 +5.5%, 원자재/유가 폭락, 달러 강세.
#   2022 러우전쟁·인플레: KOSPI -25%, S&P500 -19.4%, Nasdaq100 -33%, 美 종합채권 -13%,
#     장기채 -30%대, 리츠 -25%, 금 -0.3%, Bloomberg 원자재 +16%, 달러지수 +8%.
# ※ 점추정이며 실측 회귀계수 아님. 환헤지 여부·국면에 따라 실제값은 달라질 수 있다.
CRISIS_SCENARIO_SHOCKS: Dict[str, Dict[str, float]] = {
    "crisis_2008": {
        "domestic_equity": -0.40,
        "overseas_blue_chip": -0.38,
        "overseas_growth": -0.42,
        "overseas_dividend": -0.30,
        "general_bond": 0.08,
        "separate_tax_bond": 0.12,
        "low_coupon_bond": 0.10,
        "reit": -0.40,
        "gold": 0.05,
        "commodity": -0.40,
        "dollar": 0.15,
        "cash": 0.0,
    },
    "crisis_ru_war": {
        "domestic_equity": -0.25,
        "overseas_blue_chip": -0.19,
        "overseas_growth": -0.33,
        "overseas_dividend": -0.05,
        "general_bond": -0.13,
        "separate_tax_bond": -0.25,
        "low_coupon_bond": -0.12,
        "reit": -0.25,
        "gold": 0.0,
        "commodity": 0.20,
        "dollar": 0.08,
        "cash": 0.0,
    },
}


def resolve_scenario_shocks(scenario: str, assets: List[str]) -> Dict[str, float]:
    """위기 시나리오 키 → 보유 자산에 해당하는 충격 벡터(0 제외)."""
    preset = CRISIS_SCENARIO_SHOCKS.get(scenario)
    if preset is None:
        raise ValueError(
            f"알 수 없는 시나리오: {scenario}. 지원: {sorted(CRISIS_SCENARIO_SHOCKS)}"
        )
    return {a: preset[a] for a in assets if a in preset and preset[a] != 0.0}


def apply_return_shocks(
    selected_returns: pd.DataFrame,
    selected_expected_returns: pd.Series,
    shocks: Dict[str, float],
) -> Tuple[pd.DataFrame, pd.Series]:
    """자산별 연간 충격을 일별수익률과 기대수익률에 주입한다(원본 비변형)."""
    stressed_returns = selected_returns.copy()
    stressed_expected = selected_expected_returns.copy()
    for asset in stressed_returns.columns:
        shock = float(shocks.get(asset, 0.0))
        if shock == 0.0:
            continue
        column = stressed_returns[asset]
        mean = float(column.mean())
        multiplier = _vol_multiplier(shock)
        stressed_returns[asset] = (
            mean + (column - mean) * multiplier + shock / TRADING_DAYS
        )
        if asset in stressed_expected.index:
            stressed_expected[asset] = float(stressed_expected[asset]) + shock
    return stressed_returns, stressed_expected


def shift_expected_returns(
    expected_returns: pd.Series,
    shocks: Dict[str, float],
) -> pd.Series:
    """세금 계산용 전체 기대수익률 시리즈에도 같은 충격을 반영한다."""
    shifted = expected_returns.copy()
    for asset, shock in shocks.items():
        if asset in shifted.index:
            shifted[asset] = float(shifted[asset]) + float(shock)
    return shifted




def _nearest_positive_semidefinite(
    matrix: np.ndarray,
) -> np.ndarray:
    clean = np.nan_to_num(
        np.asarray(matrix, dtype=float),
        nan=0.0,
        posinf=0.0,
        neginf=0.0,
    )
    symmetric = (clean + clean.T) / 2.0

    try:
        eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
        eigenvalues = np.clip(eigenvalues, 0.0, None)
        corrected = (
            eigenvectors
            @ np.diag(eigenvalues)
            @ eigenvectors.T
        )
        return (corrected + corrected.T) / 2.0
    except np.linalg.LinAlgError:
        return np.diag(
            np.clip(np.diag(symmetric), 0.0, None)
        )


def _metric_percentile_payload(
    values: np.ndarray,
    *,
    digits: int,
    unit: str,
) -> Dict[str, Any]:
    levels = list(MONTE_CARLO_METRIC_RANGE_PERCENTILES)
    percentile_values = np.percentile(values, levels)
    mapped = {
        f"p{level}": safe_round(value, digits)
        for level, value in zip(levels, percentile_values)
    }

    return {
        **mapped,
        "lower": mapped[
            f"p{MONTE_CARLO_METRIC_RANGE_DISPLAY_LOWER}"
        ],
        "center": mapped[
            f"p{MONTE_CARLO_METRIC_RANGE_DISPLAY_CENTER}"
        ],
        "upper": mapped[
            f"p{MONTE_CARLO_METRIC_RANGE_DISPLAY_UPPER}"
        ],
        "lower_percentile": (
            MONTE_CARLO_METRIC_RANGE_DISPLAY_LOWER
        ),
        "center_percentile": (
            MONTE_CARLO_METRIC_RANGE_DISPLAY_CENTER
        ),
        "upper_percentile": (
            MONTE_CARLO_METRIC_RANGE_DISPLAY_UPPER
        ),
        "unit": unit,
        "direction": "higher_is_better",
    }


def _effective_tax_rate_from_breakdown(
    tax_breakdown: Optional[Dict[str, Any]],
) -> float:
    """세금 상세가 없거나 잘못된 형식이면 세율 0으로 안전하게 처리한다."""
    if not isinstance(tax_breakdown, dict):
        return 0.0

    gross_profit = safe_float(
        tax_breakdown.get("gross_profit")
    )
    total_tax_after_saving = safe_float(
        tax_breakdown.get("total_tax_after_saving")
    )
    if gross_profit <= 1e-12:
        return 0.0

    return float(
        np.clip(
            total_tax_after_saving / gross_profit,
            0.0,
            1.0,
        )
    )


def calculate_monte_carlo_metric_ranges(
    weights: Dict[str, float],
    returns: pd.DataFrame,
    expected_returns: pd.Series,
    total_asset: float,
    investment_horizon_years: float,
    tax_breakdown: Dict[str, Any],
    random_seed: int = DEFAULT_RANDOM_SEED,
    num_simulations: Optional[int] = None,
) -> Dict[str, Any]:
    # 세후수익률과 MDD를 동일한 미래 시장 경로에서 계산한다.
    normalized_weights = normalize_weights(weights)
    total_asset = safe_float(total_asset)

    if total_asset <= 0:
        return {
            "available": False,
            "reason": "total_asset_must_be_positive",
        }

    try:
        requested_years = float(investment_horizon_years)
    except (TypeError, ValueError):
        requested_years = 1.0

    horizon_years = max(
        1,
        min(
            int(round(requested_years)),
            MONTE_CARLO_METRIC_RANGE_MAX_HORIZON_YEARS,
        ),
    )
    months = (
        horizon_years
        * MONTE_CARLO_METRIC_RANGE_STEPS_PER_YEAR
    )
    simulations = max(
        int(
            num_simulations
            if num_simulations is not None
            else MONTE_CARLO_METRIC_RANGE_SIMULATIONS
        ),
        100,
    )

    # 비중과 무관한 공통 자산 순서와 시드를 사용하므로
    # 현재안/A/B에 같은 시장 시나리오가 적용된다.
    assets = [
        asset
        for asset in ASSET_TICKERS.keys()
        if (
            asset in returns.columns
            and asset in expected_returns.index
        )
    ]

    missing_weighted_assets = [
        asset
        for asset, weight in normalized_weights.items()
        if (
            safe_float(weight) > 1e-12
            and asset not in assets
        )
    ]
    if missing_weighted_assets:
        return {
            "available": False,
            "reason": "weighted_asset_data_missing",
            "missing_assets": missing_weighted_assets,
        }

    if not assets:
        return {
            "available": False,
            "reason": "no_common_assets",
        }

    clean_returns = (
        returns[assets]
        .replace([np.inf, -np.inf], np.nan)
        .dropna(how="any")
    )
    if len(clean_returns) < MIN_BETA_OBSERVATIONS:
        return {
            "available": False,
            "reason": "insufficient_return_observations",
            "observations": len(clean_returns),
            "minimum_observations": MIN_BETA_OBSERVATIONS,
        }

    daily_log_returns = np.log1p(
        clean_returns.clip(lower=-0.999999)
    )
    monthly_covariance = (
        daily_log_returns.cov().to_numpy(dtype=float)
        * TRADING_DAYS
        / MONTE_CARLO_METRIC_RANGE_STEPS_PER_YEAR
    )
    monthly_covariance = _nearest_positive_semidefinite(
        monthly_covariance
    )

    annual_expected = (
        expected_returns
        .reindex(assets)
        .fillna(0.0)
        .to_numpy(dtype=float)
    )
    annual_expected = np.clip(
        annual_expected,
        -0.95,
        None,
    )

    # 로그정규 모형에서 단순수익률 기대값이 기존 기대수익률과
    # 최대한 맞도록 분산 보정항을 차감한다.
    monthly_log_mean = (
        np.log1p(annual_expected)
        / MONTE_CARLO_METRIC_RANGE_STEPS_PER_YEAR
        - 0.5 * np.diag(monthly_covariance)
    )

    weight_vector = np.array(
        [
            safe_float(normalized_weights.get(asset))
            for asset in assets
        ],
        dtype=float,
    )
    weight_total = float(weight_vector.sum())
    if weight_total <= 0:
        return {
            "available": False,
            "reason": "portfolio_weight_sum_zero",
        }
    weight_vector = weight_vector / weight_total

    scenario_seed = (
        int(random_seed)
        + MONTE_CARLO_METRIC_RANGE_SEED_OFFSET
    )
    rng = np.random.default_rng(scenario_seed)

    # 모든 월·경로의 자산별 로그수익률을 한 번에 생성한다.
    # 약 60개월 × 10,000경로 × 12자산 규모로,
    # 월별 Python 반복 호출보다 빠르면서 메모리 사용도 제한적이다.
    monthly_log_draws = rng.multivariate_normal(
        mean=monthly_log_mean,
        cov=monthly_covariance,
        size=(months, simulations),
        check_valid="ignore",
    )

    # Buy & Hold: 누적 로그수익률을 자산별 초기 금액에 적용한다.
    np.cumsum(
        monthly_log_draws,
        axis=0,
        out=monthly_log_draws,
    )
    np.exp(
        monthly_log_draws,
        out=monthly_log_draws,
    )
    monthly_log_draws *= (
        weight_vector * total_asset
    )

    portfolio_value_history = (
        monthly_log_draws.sum(axis=2)
    )
    portfolio_value_history = np.vstack(
        [
            np.full(
                (1, simulations),
                total_asset,
                dtype=float,
            ),
            portfolio_value_history,
        ]
    )

    running_peak = np.maximum.accumulate(
        portfolio_value_history,
        axis=0,
    )
    drawdown = (
        portfolio_value_history / running_peak - 1.0
    )
    path_mdd = drawdown.min(axis=0)
    gross_portfolio_value = (
        portfolio_value_history[-1]
    )

    effective_tax_rate = _effective_tax_rate_from_breakdown(
        tax_breakdown
    )
    gross_gain = gross_portfolio_value - total_asset
    after_tax_terminal_asset = (
        total_asset
        + np.where(
            gross_gain > 0,
            gross_gain * (1.0 - effective_tax_rate),
            gross_gain,
        )
    )
    after_tax_terminal_asset = np.maximum(
        after_tax_terminal_asset,
        0.0,
    )
    after_tax_annualized_return = (
        np.power(
            np.maximum(
                after_tax_terminal_asset / total_asset,
                1e-12,
            ),
            1.0 / horizon_years,
        )
        - 1.0
    )

    start_index_value = clean_returns.index[0]
    end_index_value = clean_returns.index[-1]

    start_formatter = getattr(
        start_index_value,
        "strftime",
        None,
    )
    end_formatter = getattr(
        end_index_value,
        "strftime",
        None,
    )

    start_date_str = (
        start_formatter("%Y-%m-%d")
        if callable(start_formatter)
        else str(start_index_value)
    )
    end_date_str = (
        end_formatter("%Y-%m-%d")
        if callable(end_formatter)
        else str(end_index_value)
    )

    scenario_basis_id = (
        f"{MONTE_CARLO_METRIC_RANGE_VERSION}:"
        f"{scenario_seed}:{simulations}:{horizon_years}:"
        f"{start_date_str}:{end_date_str}"
    )

    return {
        "available": True,
        "version": MONTE_CARLO_METRIC_RANGE_VERSION,
        "scenario_basis_id": scenario_basis_id,
        "simulation_count": simulations,
        "horizon_years": horizon_years,
        "time_step": "monthly",
        "rebalancing": "none_buy_and_hold",
        "common_market_scenarios": True,
        "random_seed": scenario_seed,
        "display_range": {
            "lower_percentile": (
                MONTE_CARLO_METRIC_RANGE_DISPLAY_LOWER
            ),
            "center_percentile": (
                MONTE_CARLO_METRIC_RANGE_DISPLAY_CENTER
            ),
            "upper_percentile": (
                MONTE_CARLO_METRIC_RANGE_DISPLAY_UPPER
            ),
            "central_coverage": 0.60,
            "label": "P20-P80",
        },
        "after_tax_return": _metric_percentile_payload(
            after_tax_annualized_return,
            digits=6,
            unit="rate",
        ),
        "mdd": _metric_percentile_payload(
            path_mdd,
            digits=6,
            unit="rate",
        ),
        "effective_tax_rate_proxy": safe_round(
            effective_tax_rate,
            6,
        ),
        "assumptions": {
            "path_model": (
                "correlated_multivariate_log_returns"
            ),
            "drift_source": "asset_expected_returns",
            "covariance_source": (
                "historical_daily_log_return_covariance"
            ),
            "after_tax_method": (
                "positive_terminal_gain_adjusted_by_"
                "current_effective_tax_rate_proxy"
            ),
            "mdd_method": (
                "minimum_drawdown_of_same_simulated_"
                "gross_portfolio_path"
            ),
            "tax_on_loss": False,
            "fees_in_simulated_paths": False,
            "range_note": (
                "세후수익률과 MDD는 동일한 10,000개 "
                "Buy & Hold 시장 경로에서 계산하며, "
                "P20~P80은 경로의 중앙 60% 범위입니다."
            ),
            "disclaimer": (
                "시뮬레이션 결과는 실제 수익을 보장하지 않습니다."
            ),
        },
    }


def calculate_metric_amounts(
    metrics: Dict[str, Any],
    total_asset: float,
    tax_breakdown: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """비율 지표를 프론트 표기용 원화 금액으로 환산한다.

    - after_tax_return_amount: 세후 기대수익률 × 현재 총자산. 연간 세후 기대 이익이다.
    - mdd_amount: 백테스트 일별 수익률 기준 최대낙폭 × 현재 총자산. 세금 반영값이 아니다.
    - volatility_band_amount: 연율화 변동성 × 현재 총자산. 손익 확정값이 아니라 변동 폭 근사다.
    """
    total_asset = safe_float(total_asset)
    after_tax_profit = None
    if tax_breakdown is not None:
        after_tax_profit = tax_breakdown.get("after_tax_profit")

    return {
        "basis": "portfolio_total_asset",
        "total_asset": safe_round(total_asset, 0),
        "expected_return_amount": safe_round(
            safe_float(metrics.get("expected_return")) * total_asset,
            0,
        ),
        "after_tax_return_amount": safe_round(
            safe_float(after_tax_profit)
            if after_tax_profit is not None
            else safe_float(metrics.get("after_tax_return")) * total_asset,
            0,
        ),
        "mdd_amount": safe_round(safe_float(metrics.get("mdd")) * total_asset, 0),
        "volatility_band_amount": safe_round(
            safe_float(metrics.get("volatility")) * total_asset,
            0,
        ),
        "historical_var_95_daily_loss_amount": safe_round(
            -safe_float(metrics.get("historical_var_95_daily_loss")) * total_asset,
            0,
        ),
        "note": (
            "원화 지표는 현재 총자산에 각 포트폴리오의 비율 지표를 곱한 값. "
            "after_tax_return_amount만 세후 기대 이익이며, MDD/VaR는 과거 수익률 기반 손실률의 원화 환산이다."
        ),
    }


def calculate_metrics(
    weights: Dict[str, float],
    returns: pd.DataFrame,
    expected_returns: pd.Series,
    request: PortfolioRequest,
    cov_matrix: Optional[pd.DataFrame] = None,
    include_benchmark_metrics: bool = False,
    shocks: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """포트폴리오 지표의 단일 계산 진입점.

    벤치마크 지표는 최종 결과 표시 단계에서만 계산한다.
    추천 후보 계산에서는 include_benchmark_metrics=False를 유지한다.
    """
    weights = normalize_weights(weights)
    validate_required_assets_available(
        weights,
        list(returns.columns),
        "portfolio_weights",
    )

    assets = [
        asset
        for asset in weights.keys()
        if asset in returns.columns and weights[asset] > 1e-12
    ]
    if not assets:
        raise ValueError("수익률 데이터에 포함된 자산의 비중이 없습니다.")

    w = np.array([weights[asset] for asset in assets], dtype=float)
    w = w / w.sum()

    selected_returns = returns[assets]
    selected_expected_returns = expected_returns.reindex(assets).fillna(0.0)

    expected_returns_for_tax = expected_returns
    if shocks:
        selected_returns, selected_expected_returns = apply_return_shocks(
            selected_returns,
            selected_expected_returns,
            shocks,
        )
        expected_returns_for_tax = shift_expected_returns(
            expected_returns,
            shocks,
        )
        cov_matrix = None

    if cov_matrix is None:
        selected_cov_matrix = selected_returns.cov() * TRADING_DAYS
    else:
        selected_cov_matrix = cov_matrix.reindex(
            index=assets,
            columns=assets,
        ).fillna(0.0)

    portfolio_return = float(np.dot(w, selected_expected_returns))
    variance = float(
        np.dot(w.T, np.dot(selected_cov_matrix.values, w))
    )
    portfolio_volatility = float(np.sqrt(max(variance, 0.0)))
    portfolio_daily_returns = selected_returns.dot(w)

    if portfolio_volatility < 1e-8 or np.isnan(portfolio_volatility):
        sharpe = 0.0
    else:
        sharpe = float(
            (portfolio_return - request.risk_free_rate)
            / portfolio_volatility
        )

    sortino = calculate_sortino(
        portfolio_daily_returns=portfolio_daily_returns,
        annual_return=portfolio_return,
        risk_free_rate=request.risk_free_rate,
    )
    mdd = calculate_mdd(portfolio_daily_returns)

    if include_benchmark_metrics:
        benchmark_comparisons = calculate_benchmark_comparisons(
            portfolio_daily_returns=portfolio_daily_returns,
            weights=weights,
            returns=returns,
        )
        selected_comparison = benchmark_comparisons[request.benchmark_key]
        beta = selected_comparison["beta"]
        benchmark_meta = selected_comparison["metadata"]
    else:
        benchmark_comparisons = {}
        beta = None
        benchmark_meta = {
            "policy": BENCHMARK_POLICY_VERSION,
            "benchmark_key": request.benchmark_key,
            "applicable": None,
            "reason": "deferred_until_final_portfolio",
            "affects_portfolio_recommendation": False,
        }

    after_tax_return, tax_breakdown = calculate_after_tax_return(
        weights=weights,
        expected_returns=expected_returns_for_tax,
        total_asset=request.total_asset,
        request=request,
    )

    taxable_financial_income = estimate_taxable_financial_income(
        weights=weights,
        expected_returns=expected_returns_for_tax,
        total_asset=request.total_asset,
    )

    liquidity_coverage = calculate_liquidity_coverage(
        weights=weights,
        total_asset=request.total_asset,
        unique_need_amount=request.unique_need_amount,
        request=request,
    )

    group_weights = calculate_asset_group_weights(weights)
    portfolio_duration = calculate_portfolio_duration(weights)
    target_duration = target_duration_by_horizon(
        request.investment_horizon_years
    )
    duration_fit_score = calculate_duration_fit_score(
        portfolio_duration,
        target_duration,
    )

    stress_test = calculate_stress_test(weights, request)
    historical_var = calculate_historical_var(portfolio_daily_returns)
    risk_contribution = calculate_risk_contribution(
        assets=assets,
        weights_array=w,
        cov_matrix=selected_cov_matrix,
    )

    temp_metrics = {
        "expected_return": portfolio_return,
        "after_tax_return": after_tax_return,
        "volatility": portfolio_volatility,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "mdd": mdd,
        "taxable_financial_income": taxable_financial_income,
        "liquidity_coverage": liquidity_coverage,
        "stock_weight": group_weights["stock_weight"],
        "bond_cash_weight": group_weights["bond_cash_weight"],
        "alternative_weight": group_weights["alternative_weight"],
        "historical_var_95_daily_loss": historical_var["daily_loss"],
        "risk_contribution_max_share": risk_contribution["max_share"],
    }

    metric_amounts = calculate_metric_amounts(
        temp_metrics,
        request.total_asset,
        tax_breakdown,
    )

    risk_level = classify_portfolio_by_guidelines(temp_metrics)
    selection_risk_control = evaluate_selection_risk_controls(
        temp_metrics,
        request.risk_profile,
    )

    return {
        "expected_return": safe_round(portfolio_return, 6),
        "after_tax_return": safe_round(after_tax_return, 6),
        "volatility": safe_round(portfolio_volatility, 6),
        "sharpe_ratio": safe_round(sharpe, 6),
        "sortino_ratio": safe_round(sortino, 6),
        "mdd": safe_round(mdd, 6),
        "beta": beta,
        "beta_benchmark": benchmark_meta,
        "selected_benchmark_key": request.benchmark_key,
        "benchmark_comparisons": benchmark_comparisons,
        "taxable_financial_income": safe_round(
            taxable_financial_income,
            0,
        ),
        "liquidity_coverage": safe_round(liquidity_coverage, 6),
        "stock_weight": safe_round(group_weights["stock_weight"], 6),
        "bond_cash_weight": safe_round(
            group_weights["bond_cash_weight"],
            6,
        ),
        "alternative_weight": safe_round(
            group_weights["alternative_weight"],
            6,
        ),
        "portfolio_duration": safe_round(portfolio_duration, 6),
        "target_duration": safe_round(target_duration, 6),
        "duration_fit_score": safe_round(duration_fit_score, 6),
        "historical_var_95": historical_var,
        "historical_var_95_daily_loss": historical_var["daily_loss"],
        "risk_contribution": risk_contribution,
        "risk_contribution_max_share": risk_contribution["max_share"],
        "selection_risk_control": selection_risk_control,
        "stress_test": stress_test,
        "risk_level": risk_level,
        "risk_level_label": RISK_LEVEL_NAME.get(
            risk_level,
            "기준 미충족",
        ),
        "metric_amounts": metric_amounts,
        "tax_breakdown": tax_breakdown,
    }


def calculate_cumulative_returns(
    weights: Dict[str, float],
    returns: pd.DataFrame,
) -> List[Dict[str, Any]]:
    weights = normalize_weights(weights)
    validate_required_assets_available(weights, list(returns.columns), "portfolio_weights")

    assets = [
        asset
        for asset in weights.keys()
        if asset in returns.columns and weights[asset] > 1e-12
    ]
    w = np.array([weights[asset] for asset in assets], dtype=float)
    w = w / w.sum()

    portfolio_daily_returns = returns[assets].dot(w)
    cumulative = (1 + portfolio_daily_returns).cumprod() - 1

    return [
        {
            "date": date.strftime("%Y-%m-%d"),
            "value": safe_round(value, 6),
            "index_value": safe_round((1.0 + value) * BACKTEST_BASE_INDEX, 4),
            "base_index": BACKTEST_BASE_INDEX,
        }
        for date, value in cumulative.items()
    ]


def build_stress_drawdown_series(
    base_series: List[Dict[str, Any]],
    portfolio_shock: float,
) -> List[Dict[str, Any]]:
    """과거 누적곡선은 그대로 두고, 끝에 위기 시점 급락 포인트 한 칸을 덧붙인다.

    설계 합의(A): 백테스트는 과거 실측 곡선이라 변형하지 않는다. 위기는 일회성
    drawdown 이벤트로만, 곡선 끝에 별도 포인트 한 칸으로 표시한다.
        portfolio_shock = Σ wᵢ·shockᵢ  (포트폴리오 단위 연간 충격; 위기 땐 음수)
    덧붙인 포인트는 stress_event=True와 label="위기"로 표시해 프런트가 구분한다.
    누적값은 (1+마지막누적)×(1+충격)−1 로 급락을 적용한다.
    """
    series = [dict(point) for point in base_series]
    if not series:
        return series
    last = series[-1]
    last_value = safe_float(last.get("value"))
    base_index = safe_float(last.get("base_index")) or BACKTEST_BASE_INDEX
    crisis_value = (1.0 + last_value) * (1.0 + float(portfolio_shock)) - 1.0
    series.append(
        {
            "date": last.get("date"),
            "label": "위기",
            "stress_event": True,
            "value": safe_round(crisis_value, 6),
            "index_value": safe_round((1.0 + crisis_value) * base_index, 4),
            "base_index": base_index,
        }
    )
    return series


def calculate_benchmark_cumulative_returns(
    weights: Dict[str, float],
    returns: pd.DataFrame,
    benchmark_key: str,
) -> Dict[str, Any]:
    benchmark_daily_returns, metadata = build_portfolio_benchmark(
        weights=weights,
        returns=returns,
        benchmark_key=benchmark_key,
    )
    if benchmark_daily_returns is None:
        return {
            "metadata": metadata,
            "series": [],
        }

    cumulative = (1 + benchmark_daily_returns).cumprod() - 1
    return {
        "metadata": metadata,
        "series": [
            {
                "date": date.strftime("%Y-%m-%d"),
                "value": safe_round(value, 6),
                "index_value": safe_round(
                    (1.0 + value) * BACKTEST_BASE_INDEX,
                    4,
                ),
                "base_index": BACKTEST_BASE_INDEX,
            }
            for date, value in cumulative.items()
        ],
    }


def calculate_all_benchmark_cumulative_returns(
    weights: Dict[str, float],
    returns: pd.DataFrame,
) -> Dict[str, Any]:
    return {
        benchmark_key: calculate_benchmark_cumulative_returns(
            weights=weights,
            returns=returns,
            benchmark_key=benchmark_key,
        )
        for benchmark_key in BENCHMARK_CONFIGS.keys()
    }


# ============================================================
# 9. 기준표 평가
# ============================================================


def evaluate_guideline_detail(metrics: Dict[str, Any], profile: str) -> Dict[str, Any]:
    rule = GUIDELINE_RULES[profile]

    expected_return = metrics["expected_return"]
    after_tax_return = metrics["after_tax_return"]
    volatility = metrics["volatility"]
    sharpe = metrics["sharpe_ratio"]
    sortino = metrics["sortino_ratio"]
    mdd = metrics["mdd"]
    taxable_income = metrics["taxable_financial_income"]
    liquidity_coverage = metrics["liquidity_coverage"]
    stock_weight = metrics["stock_weight"]
    bond_cash_weight = metrics["bond_cash_weight"]
    alternative_weight = metrics["alternative_weight"]

    tax_gap = expected_return - after_tax_return

    hard_checks = {}
    soft_checks = {}

    hard_checks["volatility"] = volatility <= rule["volatility_max"]
    hard_checks["mdd"] = mdd >= rule["mdd_min"]
    hard_checks["liquidity_coverage"] = liquidity_coverage >= rule["liquidity_coverage_min"]
    hard_checks["stock_weight"] = stock_weight <= rule["stock_weight_max"]
    hard_checks["alternative_weight"] = alternative_weight <= rule["alternative_weight_max"]
    hard_checks["bond_cash_weight"] = bond_cash_weight >= rule["bond_cash_weight_min"]

    soft_checks["expected_return_min"] = expected_return >= rule["expected_return_min"]

    if rule["expected_return_max"] is not None:
        soft_checks["expected_return_max"] = expected_return <= rule["expected_return_max"]
    else:
        soft_checks["expected_return_max"] = True

    soft_checks["sharpe"] = sharpe >= rule["sharpe_min"]

    if rule["sortino_min"] is not None:
        soft_checks["sortino"] = sortino >= rule["sortino_min"]
    else:
        soft_checks["sortino"] = True

    if rule["tax_gap_max"] is not None:
        soft_checks["tax_gap"] = tax_gap <= rule["tax_gap_max"]
    else:
        soft_checks["tax_gap"] = True

    if rule["taxable_income_max"] is not None:
        soft_checks["taxable_financial_income"] = taxable_income <= rule["taxable_income_max"]
    else:
        soft_checks["taxable_financial_income"] = True

    if rule["after_tax_retention_min"] is not None:
        if expected_return <= 0:
            soft_checks["after_tax_retention"] = False
        else:
            soft_checks["after_tax_retention"] = (
                after_tax_return / expected_return >= rule["after_tax_retention_min"]
            )
    else:
        soft_checks["after_tax_retention"] = True

    hard_passed = all(hard_checks.values())
    soft_passed_count = sum(1 for passed in soft_checks.values() if passed)
    soft_total_count = len(soft_checks)
    soft_pass_ratio = soft_passed_count / soft_total_count if soft_total_count > 0 else 1.0

    return {
        "profile": profile,
        "level": rule["level"],
        "label": rule["label"],
        "passed": hard_passed,
        "hard_checks": hard_checks,
        "soft_checks": soft_checks,
        "soft_pass_ratio": round(float(soft_pass_ratio), 4),
    }


def check_guideline(metrics: Dict[str, Any], profile: str) -> bool:
    return evaluate_guideline_detail(metrics, profile)["passed"]


def classify_portfolio_by_guidelines(metrics: Dict[str, Any]) -> Optional[int]:
    if check_guideline(metrics, "conservative"):
        return 1
    if check_guideline(metrics, "balanced"):
        return 2
    if check_guideline(metrics, "aggressive"):
        return 3
    return None


def is_suitable_for_client(metrics: Dict[str, Any], client_risk_profile: str) -> bool:
    client_level = CLIENT_RISK_LEVEL[client_risk_profile]
    portfolio_level = metrics["risk_level"]

    if portfolio_level is None:
        return False

    return portfolio_level <= client_level
