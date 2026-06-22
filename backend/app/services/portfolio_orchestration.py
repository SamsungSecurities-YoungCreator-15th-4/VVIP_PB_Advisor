"""PR #74 계산 엔진을 감싸는 정리된 포트폴리오 오케스트레이션 계층.

기존 portfolio_logic.py의 세금·지표·스트레스 계산은 그대로 재사용한다.
이 모듈에서 추가하는 것은 다음뿐이다.

1. 벤치마크 3종(KOSPI, S&P 500, MSCI ACWI)을 추천 데이터와 분리해 조회
2. 선택 벤치마크에 따른 beta/백테스트 비교선 제공
3. A: 공통 리스크 기준 통과 후보 중 세후수익률 최대
4. B: PB 승인 목표 세후수익률을 우선 충족하면서 위험기여 집중 최소
5. LLM Unique 구조화 결과를 기존 계산 입력으로 안전하게 연결
6. AI 인사이트 의미 매핑은 advisory로만 반환하고 계산에는 미반영

기존 엔드포인트와 하위호환을 깨지 않기 위해 원본 파일을 직접 갈아엎지 않고,
새 canonical API가 이 계층을 사용한다.
"""

from __future__ import annotations

from typing import Any, Iterable, Literal
import uuid

import numpy as np
import pandas as pd
import yfinance as yf

from app.portfolio_logic import portfolio_logic as legacy


BenchmarkKey = Literal["kospi", "sp500", "msci_acwi"]

BENCHMARK_SPECS: dict[str, dict[str, Any]] = {
    "kospi": {
        "key": "kospi",
        "ticker": "^KS11",
        "label": "KOSPI",
        "official_index_series": True,
        "proxy_note": None,
    },
    "sp500": {
        "key": "sp500",
        "ticker": "^GSPC",
        "label": "S&P 500",
        "official_index_series": True,
        "proxy_note": None,
    },
    "msci_acwi": {
        "key": "msci_acwi",
        "ticker": "ACWI",
        "label": "MSCI ACWI (ACWI ETF proxy)",
        "official_index_series": False,
        "proxy_note": (
            "공식 MSCI 지수 원시계열이 아니라 iShares MSCI ACWI ETF의 "
            "수정주가 수익률을 글로벌 시장 대용치로 사용합니다."
        ),
    },
}

DEFAULT_BENCHMARK_KEY: BenchmarkKey = "msci_acwi"
BENCHMARK_POLICY_VERSION = "selectable-three-benchmarks-display-only-v1"


def get_benchmark_catalog() -> dict[str, Any]:
    return {
        "policy": BENCHMARK_POLICY_VERSION,
        "default_key": DEFAULT_BENCHMARK_KEY,
        "selection_scope": ["backtest_chart", "beta"],
        "affects_portfolio_recommendation": False,
        "items": [dict(spec) for spec in BENCHMARK_SPECS.values()],
    }


def normalize_benchmark_key(value: Any) -> BenchmarkKey:
    key = str(value or DEFAULT_BENCHMARK_KEY).strip().lower()
    if key not in BENCHMARK_SPECS:
        return DEFAULT_BENCHMARK_KEY
    return key  # type: ignore[return-value]


def _close_prices_from_yfinance(
    tickers: list[str],
    *,
    period: str,
) -> pd.DataFrame:
    raw = yf.download(
        tickers,
        period=period,
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=True,
    )
    if raw.empty:
        raise RuntimeError("벤치마크 가격 데이터를 가져오지 못했습니다.")

    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" not in raw.columns.get_level_values(0):
            raise RuntimeError("벤치마크 응답에서 Close 가격을 찾지 못했습니다.")
        close = raw["Close"].copy()
    else:
        if "Close" not in raw.columns:
            raise RuntimeError("벤치마크 응답에서 Close 가격을 찾지 못했습니다.")
        close = raw[["Close"]].copy()
        if len(tickers) == 1:
            close.columns = tickers

    if isinstance(close, pd.Series):
        close = close.to_frame(name=tickers[0])
    return close.dropna(how="all").sort_index()


def download_benchmark_returns(
    *,
    period: str,
) -> tuple[dict[str, pd.Series], dict[str, dict[str, Any]]]:
    ticker_to_key = {
        spec["ticker"]: key
        for key, spec in BENCHMARK_SPECS.items()
    }
    close = _close_prices_from_yfinance(
        list(ticker_to_key.keys()),
        period=period,
    )
    close = close.rename(columns=ticker_to_key)

    returns: dict[str, pd.Series] = {}
    metadata: dict[str, dict[str, Any]] = {}

    for key, spec in BENCHMARK_SPECS.items():
        if key not in close.columns:
            metadata[key] = {
                **spec,
                "policy": BENCHMARK_POLICY_VERSION,
                "available": False,
                "reason": "benchmark_data_missing",
                "data_start": None,
                "data_end": None,
                "observations": 0,
            }
            continue

        prices = close[key].replace([np.inf, -np.inf], np.nan).dropna()
        series = (
            prices.pct_change(fill_method=None)
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )
        if series.empty:
            metadata[key] = {
                **spec,
                "policy": BENCHMARK_POLICY_VERSION,
                "available": False,
                "reason": "benchmark_data_empty",
                "data_start": None,
                "data_end": None,
                "observations": 0,
            }
            continue

        series.name = key
        returns[key] = series
        metadata[key] = {
            **spec,
            "policy": BENCHMARK_POLICY_VERSION,
            "available": True,
            "reason": None,
            "data_start": series.index[0].strftime("%Y-%m-%d"),
            "data_end": series.index[-1].strftime("%Y-%m-%d"),
            "observations": int(len(series)),
        }

    return returns, metadata


def _investable_prices_only(prices: pd.DataFrame) -> pd.DataFrame:
    """원본 데이터에서 추천 가능 자산만 남긴다.

    벤치마크 열의 결측치나 시작일이 추천·공분산·기대수익률 기간을 바꾸지 않도록
    물리적으로 분리한다.
    """
    columns = [
        asset
        for asset in legacy.ASSET_TICKERS
        if asset in prices.columns
    ]
    if not columns:
        raise RuntimeError("추천 계산에 사용할 투자 자산 가격 데이터가 없습니다.")

    result = prices[columns].copy()
    result.attrs.update(prices.attrs)
    return result


def _unique_weight_signature(weights: dict[str, float]) -> tuple[tuple[str, float], ...]:
    normalized = legacy.normalize_weights(weights)
    return tuple(
        sorted((asset, round(weight, 10)) for asset, weight in normalized.items())
    )


def _a_rank(metrics: dict[str, Any]) -> tuple[Any, ...]:
    """A: 공통 기준 통과 후보 중 세후수익률 최대."""
    return (
        legacy.safe_float(metrics.get("after_tax_return")),
        legacy.safe_float(metrics.get("expected_return")),
        legacy.safe_float(metrics.get("sharpe_ratio")),
        -legacy.safe_float(metrics.get("historical_var_95_daily_loss")),
        -legacy.safe_float(metrics.get("risk_contribution_max_share")),
        legacy.safe_float(metrics.get("mdd")),
    )


def _b_rank(
    metrics: dict[str, Any],
    target_after_tax_return: float | None,
) -> tuple[Any, ...]:
    """B: 목표 세후수익률을 우선 충족하면서 위험기여 집중 최소."""
    after_tax = legacy.safe_float(metrics.get("after_tax_return"))
    if target_after_tax_return is None:
        target_met = True
        shortfall = 0.0
    else:
        target_met = after_tax >= target_after_tax_return
        shortfall = max(target_after_tax_return - after_tax, 0.0)

    risk_contribution = metrics.get("risk_contribution") or {}
    hhi = legacy.safe_float(risk_contribution.get("hhi"))
    max_share = legacy.safe_float(metrics.get("risk_contribution_max_share"))
    var_loss = legacy.safe_float(metrics.get("historical_var_95_daily_loss"))

    return (
        1 if target_met else 0,
        -shortfall,
        -hhi,
        -max_share,
        -var_loss,
        legacy.safe_float(metrics.get("mdd")),
        after_tax,
    )


def _selection_summary(
    *,
    kind: Literal["A", "B"],
    metrics: dict[str, Any],
    target_after_tax_return: float | None,
) -> dict[str, Any]:
    if kind == "A":
        return {
            "portfolio_kind": "A",
            "primary_objective": "after_tax_return_max",
            "ranking_basis": [
                "suitability_filter",
                "historical_var_95_filter",
                "risk_contribution_filter",
                "after_tax_return_desc",
                "expected_return_desc",
                "sharpe_ratio_desc",
                "historical_var_95_asc",
                "risk_contribution_max_share_asc",
                "mdd_desc",
            ],
            "risk_control": metrics.get("selection_risk_control", {}),
            "target_after_tax_return": target_after_tax_return,
            "note": (
                "고객 적합성·95% Historical VaR·위험기여 집중 기준을 모두 "
                "통과한 후보 중 세후수익률이 가장 높은 안입니다."
            ),
        }

    after_tax = legacy.safe_float(metrics.get("after_tax_return"))
    return {
        "portfolio_kind": "B",
        "primary_objective": "target_return_then_risk_contribution_balance",
        "ranking_basis": [
            "suitability_filter",
            "historical_var_95_filter",
            "risk_contribution_filter",
            "target_after_tax_return_met",
            "target_shortfall_asc",
            "risk_contribution_hhi_asc",
            "risk_contribution_max_share_asc",
            "historical_var_95_asc",
            "mdd_desc",
            "after_tax_return_desc",
        ],
        "risk_control": metrics.get("selection_risk_control", {}),
        "target_after_tax_return": target_after_tax_return,
        "target_met": (
            after_tax >= target_after_tax_return
            if target_after_tax_return is not None
            else None
        ),
        "target_shortfall": (
            max(target_after_tax_return - after_tax, 0.0)
            if target_after_tax_return is not None
            else None
        ),
        "note": (
            "PB가 승인한 목표 세후수익률을 우선 충족하고, 그 안에서 "
            "위험기여 HHI와 단일 자산 최대 위험기여 비중이 낮은 안입니다."
        ),
    }


def find_recommended_portfolios_ab(
    *,
    returns: pd.DataFrame,
    expected_returns: pd.Series,
    request: legacy.PortfolioRequest,
    cov_matrix: pd.DataFrame | None,
    target_after_tax_return: float | None,
    excluded_assets: Iterable[str] = (),
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rng = np.random.default_rng(request.random_seed)

    raw_available_assets = [
        asset
        for asset in legacy.ASSET_TICKERS
        if asset in returns.columns
    ]
    eligible_assets = legacy.get_recommendation_eligible_assets(
        raw_available_assets,
        request,
    )

    excluded = {
        legacy.canonicalize_asset_key(str(asset))
        for asset in excluded_assets
    }
    # 유동성 필요자금 배치 자산은 고객의 필수 reserve이므로 exclusion보다 우선한다.
    effective_unique_asset = legacy.get_effective_unique_asset(request)
    excluded.discard(effective_unique_asset)
    eligible_assets = [
        asset
        for asset in eligible_assets
        if asset not in excluded
    ]
    if not eligible_assets:
        raise RuntimeError("자산 제외 조건 적용 후 추천 가능한 자산이 없습니다.")

    legacy.validate_required_assets_available(
        {effective_unique_asset: 1.0},
        raw_available_assets,
        "unique_asset",
    )

    generated_count = request.num_simulations
    guideline_pass_count = 0
    suitable_count = 0
    risk_control_pass_count = 0
    candidates: list[dict[str, Any]] = []

    for _ in range(request.num_simulations):
        base_weights = legacy.generate_random_weights(
            assets=eligible_assets,
            rng=rng,
        )
        final_weights = legacy.apply_unique_constraint(
            base_weights=base_weights,
            total_asset=request.total_asset,
            unique_need_amount=request.unique_need_amount,
            unique_asset=effective_unique_asset,
        )
        metrics = legacy.calculate_metrics(
            weights=final_weights,
            returns=returns,
            expected_returns=expected_returns,
            request=request,
            cov_matrix=cov_matrix,
            include_benchmark_metrics=False,
        )

        if metrics.get("risk_level") is not None:
            guideline_pass_count += 1
        if not legacy.is_suitable_for_client(metrics, request.risk_profile):
            continue

        suitable_count += 1
        risk_control = metrics.get("selection_risk_control") or {}
        if not bool(risk_control.get("passed")):
            continue

        risk_control_pass_count += 1
        candidates.append(
            {
                "weights": final_weights,
                "metrics": metrics,
            }
        )

    if not candidates:
        raise RuntimeError(
            "고객 적합성·VaR·위험기여 기준을 모두 통과한 후보가 없습니다. "
            "num_simulations 또는 리스크 기준을 검토해야 합니다."
        )

    portfolio_a = max(candidates, key=lambda item: _a_rank(item["metrics"]))
    a_signature = _unique_weight_signature(portfolio_a["weights"])

    b_candidates = [
        item
        for item in candidates
        if _unique_weight_signature(item["weights"]) != a_signature
    ]
    if not b_candidates:
        portfolio_b = portfolio_a
        duplicate_fallback = True
    else:
        portfolio_b = max(
            b_candidates,
            key=lambda item: _b_rank(
                item["metrics"],
                target_after_tax_return,
            ),
        )
        duplicate_fallback = False

    correlation = legacy.calculate_portfolio_return_correlation(
        portfolio_a["weights"],
        portfolio_b["weights"],
        returns,
    )

    portfolio_a = {
        **portfolio_a,
        "selection_summary": _selection_summary(
            kind="A",
            metrics=portfolio_a["metrics"],
            target_after_tax_return=target_after_tax_return,
        ),
    }
    portfolio_b = {
        **portfolio_b,
        "selection_summary": _selection_summary(
            kind="B",
            metrics=portfolio_b["metrics"],
            target_after_tax_return=target_after_tax_return,
        ),
        "correlation_with_recommended_1": correlation,
    }

    search_summary = {
        "generated_portfolios": generated_count,
        "guideline_pass_portfolios": guideline_pass_count,
        "suitable_portfolios": suitable_count,
        "risk_control_pass_portfolios": risk_control_pass_count,
        "filtered_out_portfolios": generated_count - risk_control_pass_count,
        "selection_method": "shared_filters_then_separate_A_B_objectives",
        "portfolio_a_objective": "after_tax_return_max",
        "portfolio_b_objective": "target_return_then_risk_contribution_balance",
        "target_after_tax_return": target_after_tax_return,
        "random_seed": request.random_seed,
        "eligible_assets": eligible_assets,
        "excluded_assets": sorted(excluded),
        "excluded_by_horizon": (
            ["separate_tax_bond"]
            if "separate_tax_bond" in raw_available_assets
            and "separate_tax_bond" not in eligible_assets
            and "separate_tax_bond" not in excluded
            else []
        ),
        "portfolio_b_duplicate_fallback": duplicate_fallback,
        "correlation_a_b": legacy.safe_round(correlation, 6),
    }
    return [portfolio_a, portfolio_b], search_summary


def _benchmark_backtest_payload(
    *,
    portfolio_daily_returns: pd.Series,
    benchmark_daily_returns: pd.Series,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    aligned = pd.concat(
        [
            portfolio_daily_returns.rename("portfolio"),
            benchmark_daily_returns.rename("benchmark"),
        ],
        axis=1,
        join="inner",
    ).replace([np.inf, -np.inf], np.nan).dropna()

    if aligned.empty:
        return {
            "metadata": {
                **metadata,
                "available": False,
                "reason": "no_common_observations",
            },
            "series": [],
            "beta": None,
        }

    beta = legacy.calculate_beta(
        aligned["portfolio"],
        aligned["benchmark"],
    )
    cumulative = (1 + aligned["benchmark"]).cumprod() - 1
    series = [
        {
            "date": date.strftime("%Y-%m-%d"),
            "value": legacy.safe_round(value, 6),
            "index_value": legacy.safe_round(
                (1 + value) * legacy.BACKTEST_BASE_INDEX,
                4,
            ),
            "base_index": legacy.BACKTEST_BASE_INDEX,
        }
        for date, value in cumulative.items()
    ]
    return {
        "metadata": {
            **metadata,
            "available": True,
            "reason": None,
            "common_data_start": aligned.index[0].strftime("%Y-%m-%d"),
            "common_data_end": aligned.index[-1].strftime("%Y-%m-%d"),
            "common_observations": int(len(aligned)),
        },
        "series": series,
        "beta": legacy.safe_round(beta, 6) if beta is not None else None,
    }


def attach_benchmark_outputs(
    *,
    portfolio: dict[str, Any],
    weights: dict[str, float],
    analysis_returns: pd.DataFrame,
    backtest_returns: pd.DataFrame,
    analysis_benchmarks: dict[str, pd.Series],
    analysis_metadata: dict[str, dict[str, Any]],
    backtest_benchmarks: dict[str, pd.Series],
    backtest_metadata: dict[str, dict[str, Any]],
    selected_benchmark: BenchmarkKey,
) -> None:
    analysis_portfolio_returns = legacy.calculate_portfolio_return_series(
        weights,
        analysis_returns,
    )
    backtest_portfolio_returns = legacy.calculate_portfolio_return_series(
        weights,
        backtest_returns,
    )

    beta_by_benchmark: dict[str, float | None] = {}
    benchmark_backtests: dict[str, dict[str, Any]] = {}

    for key in BENCHMARK_SPECS:
        analysis_series = analysis_benchmarks.get(key)
        analysis_meta = analysis_metadata.get(
            key,
            {**BENCHMARK_SPECS[key], "available": False},
        )
        if analysis_series is None:
            beta_by_benchmark[key] = None
        else:
            aligned = pd.concat(
                [
                    analysis_portfolio_returns.rename("portfolio"),
                    analysis_series.rename("benchmark"),
                ],
                axis=1,
                join="inner",
            ).replace([np.inf, -np.inf], np.nan).dropna()
            beta = (
                legacy.calculate_beta(
                    aligned["portfolio"],
                    aligned["benchmark"],
                )
                if not aligned.empty
                else None
            )
            beta_by_benchmark[key] = (
                legacy.safe_round(beta, 6)
                if beta is not None
                else None
            )

        backtest_series = backtest_benchmarks.get(key)
        backtest_meta = backtest_metadata.get(
            key,
            {**BENCHMARK_SPECS[key], "available": False},
        )
        if backtest_series is None:
            benchmark_backtests[key] = {
                "metadata": backtest_meta,
                "series": [],
                "beta": beta_by_benchmark[key],
            }
        else:
            payload = _benchmark_backtest_payload(
                portfolio_daily_returns=backtest_portfolio_returns,
                benchmark_daily_returns=backtest_series,
                metadata=backtest_meta,
            )
            # beta는 분석기간 기준 값을 사용한다. 차트 payload의 beta는 덮어쓴다.
            payload["beta"] = beta_by_benchmark[key]
            benchmark_backtests[key] = payload

    selected_payload = benchmark_backtests[selected_benchmark]
    selected_meta = {
        **analysis_metadata.get(
            selected_benchmark,
            BENCHMARK_SPECS[selected_benchmark],
        ),
        "selected": True,
        "selection_scope": ["backtest_chart", "beta"],
        "affects_portfolio_recommendation": False,
    }

    portfolio["metrics"]["beta_by_benchmark"] = beta_by_benchmark
    portfolio["metrics"]["beta"] = beta_by_benchmark[selected_benchmark]
    portfolio["metrics"]["beta_benchmark"] = selected_meta
    portfolio["benchmark_backtests"] = benchmark_backtests
    # 기존 응답 하위호환: 선택된 하나를 종전 필드에도 둔다.
    portfolio["benchmark_backtest"] = {
        "metadata": selected_payload["metadata"],
        "series": selected_payload["series"],
    }


def _apply_unique_semantic_mapping(
    request: legacy.PortfolioRequest,
    mapping: dict[str, Any] | None,
) -> tuple[legacy.PortfolioRequest, list[str], list[str]]:
    """LLM 구조화 결과 중 기존 엔진이 명확히 지원하는 필드만 적용한다."""
    if not mapping:
        return request, [], []

    warnings: list[str] = []
    excluded_assets: set[str] = set()
    liquidity_total = 0.0
    client_context = dict(request.client_context or {})
    existing_profile = dict(request.unique_profile or {})
    mapped_items = mapping.get("mappings")
    if not isinstance(mapped_items, list):
        mapped_items = []

    for item in mapped_items:
        if not isinstance(item, dict):
            continue
        status = item.get("mapping_status")
        calculation_field = item.get("calculation_field")
        assets = [
            legacy.canonicalize_asset_key(str(asset))
            for asset in item.get("canonical_assets", [])
            if str(asset)
        ]

        if status != "mapped":
            continue

        if calculation_field == "unique_need_amount":
            amount = legacy.safe_float(item.get("amount_krw"))
            if amount > 0:
                liquidity_total += amount

        elif calculation_field == "unique_asset":
            candidate = next(
                (asset for asset in assets if asset in legacy.UNIQUE_ASSETS),
                None,
            )
            if candidate:
                request.unique_asset = candidate

        elif calculation_field == "asset_exclusion":
            excluded_assets.update(
                asset
                for asset in assets
                if asset in legacy.ASSET_TICKERS
            )

        elif calculation_field == "isa_status":
            request.isa_account_exists = bool(
                item.get("account_exists")
                if item.get("account_exists") is not None
                else True
            )
            start_year = item.get("account_start_year")
            if start_year is not None:
                request.isa_account_age_years = (
                    legacy.calculate_account_age_years_from_start_year(
                        int(start_year)
                    )
                )
            cumulative = item.get("cumulative_contribution_krw")
            current_year = item.get("current_year_contribution_krw")
            if cumulative is not None:
                request.isa_cumulative_contribution = max(
                    legacy.safe_float(cumulative),
                    0.0,
                )
            if current_year is not None:
                request.isa_current_year_contribution = max(
                    legacy.safe_float(current_year),
                    0.0,
                )

        elif calculation_field == "irp_status":
            request.irp_account_exists = bool(
                item.get("account_exists")
                if item.get("account_exists") is not None
                else True
            )
            start_year = item.get("account_start_year")
            if start_year is not None:
                request.irp_account_age_years = (
                    legacy.calculate_account_age_years_from_start_year(
                        int(start_year)
                    )
                )
            cumulative = item.get("cumulative_contribution_krw")
            current_year = item.get("current_year_contribution_krw")
            if cumulative is not None:
                request.irp_cumulative_contribution = max(
                    legacy.safe_float(cumulative),
                    0.0,
                )
            if current_year is not None:
                request.irp_current_year_contribution = max(
                    legacy.safe_float(current_year),
                    0.0,
                )

        elif calculation_field == "client_context":
            category = str(item.get("category") or "")
            if category == "corporate_or_succession":
                client_context["manual_review_required"] = True

    if liquidity_total > 0:
        request.unique_need_amount = liquidity_total
        request.unique_asset = "cash"

    if mapping.get("unmapped_segments"):
        warnings.append(
            "Unique 의미 매핑에서 자동 계산 필드로 연결하지 못한 원문이 있습니다. "
            "응답의 semantic_mapping.unique.unmapped_segments를 PB가 확인해야 합니다."
        )
    if not mapping.get("coverage_complete", False):
        warnings.append(
            "Unique 원문의 모든 segment가 의미 매핑됐다고 확인되지 않았습니다."
        )

    request.client_context = client_context
    request.unique_items = mapped_items
    request.unique_profile = {
        **existing_profile,
        "semantic_mapping": mapping,
    }
    return request, sorted(excluded_assets), warnings


def run_analysis_core_v2(
    *,
    request: legacy.PortfolioRequest,
    target_after_tax_return: float | None,
    selected_benchmark: BenchmarkKey,
    unique_mapping: dict[str, Any] | None,
) -> dict[str, Any]:
    if request.unique_need_amount > request.total_asset:
        raise ValueError("Unique 필요금액은 총자산보다 클 수 없습니다.")

    request.unique_asset = legacy.validate_unique_asset(request.unique_asset)
    request, excluded_assets, semantic_warnings = _apply_unique_semantic_mapping(
        request,
        unique_mapping,
    )
    if request.unique_need_amount > request.total_asset:
        raise ValueError("Unique 필요금액은 총자산보다 클 수 없습니다.")

    constraint_warnings = legacy.build_constraint_warnings(request)
    constraint_warnings.extend(semantic_warnings)
    request.unique_asset = legacy.get_effective_unique_asset(request)
    request.current_weights = legacy.canonicalize_weights(request.current_weights)
    request.view_expected_returns = legacy.canonicalize_asset_return_map(
        request.view_expected_returns
    )

    raw_prices = legacy.download_price_data(
        period=request.period,
        cash_return=request.cash_return,
    )
    prices = _investable_prices_only(raw_prices)
    data_snapshot = dict(raw_prices.attrs.get("data_snapshot", {}))
    data_snapshot["benchmark_columns_excluded_from_recommendation"] = True

    returns = legacy.calculate_daily_returns(prices)
    cov_matrix = returns.cov() * legacy.TRADING_DAYS
    expected_returns = legacy.calculate_expected_returns(
        returns=returns,
        expected_return_haircut=request.expected_return_haircut,
        enable_black_litterman=request.enable_black_litterman,
        view_expected_returns=request.view_expected_returns,
        view_weight=request.view_weight,
    )

    raw_backtest_prices = legacy.download_backtest_price_data(
        period="5y",
        cash_return=request.cash_return,
    )
    backtest_prices = _investable_prices_only(raw_backtest_prices)
    backtest_data_snapshot = dict(
        raw_backtest_prices.attrs.get("data_snapshot", {})
    )
    backtest_data_snapshot["benchmark_columns_excluded_from_recommendation"] = True
    backtest_returns = legacy.calculate_daily_returns(backtest_prices)

    analysis_benchmarks, analysis_benchmark_meta = download_benchmark_returns(
        period=request.period
    )
    if request.period == "5y":
        backtest_benchmarks = analysis_benchmarks
        backtest_benchmark_meta = analysis_benchmark_meta
    else:
        backtest_benchmarks, backtest_benchmark_meta = download_benchmark_returns(
            period="5y"
        )

    legacy.validate_required_assets_available(
        {request.unique_asset: 1.0},
        list(returns.columns),
        "unique_asset",
    )

    if request.current_weights is None:
        current_weights = legacy.get_default_current_weights()
    else:
        legacy.validate_weights(request.current_weights)
        legacy.validate_required_assets_available(
            request.current_weights,
            list(returns.columns),
            "current_weights",
        )
        current_weights = legacy.normalize_weights(request.current_weights)

    recommendations, search_summary = find_recommended_portfolios_ab(
        returns=returns,
        expected_returns=expected_returns,
        request=request,
        cov_matrix=cov_matrix,
        target_after_tax_return=target_after_tax_return,
        excluded_assets=excluded_assets,
    )

    current_response = legacy.build_portfolio_response(
        name="현재 포트폴리오",
        api_key="current",
        weights=current_weights,
        returns=returns,
        expected_returns=expected_returns,
        request=request,
        cov_matrix=cov_matrix,
        backtest_returns=backtest_returns,
    )
    rec_1_response = legacy.build_portfolio_response(
        name="포트폴리오 A",
        api_key="portfolio_a",
        weights=recommendations[0]["weights"],
        returns=returns,
        expected_returns=expected_returns,
        request=request,
        selection_summary=recommendations[0]["selection_summary"],
        cov_matrix=cov_matrix,
        backtest_returns=backtest_returns,
    )
    rec_2_response = legacy.build_portfolio_response(
        name="포트폴리오 B",
        api_key="portfolio_b",
        weights=recommendations[1]["weights"],
        returns=returns,
        expected_returns=expected_returns,
        request=request,
        selection_summary=recommendations[1]["selection_summary"],
        correlation_with_recommended_1=(
            recommendations[1].get("correlation_with_recommended_1")
        ),
        cov_matrix=cov_matrix,
        backtest_returns=backtest_returns,
    )

    for portfolio, weights in (
        (current_response, current_weights),
        (rec_1_response, recommendations[0]["weights"]),
        (rec_2_response, recommendations[1]["weights"]),
    ):
        attach_benchmark_outputs(
            portfolio=portfolio,
            weights=weights,
            analysis_returns=returns,
            backtest_returns=backtest_returns,
            analysis_benchmarks=analysis_benchmarks,
            analysis_metadata=analysis_benchmark_meta,
            backtest_benchmarks=backtest_benchmarks,
            backtest_metadata=backtest_benchmark_meta,
            selected_benchmark=selected_benchmark,
        )

    unique_ratio = request.unique_need_amount / request.total_asset
    return {
        "input_summary": {
            "total_asset": request.total_asset,
            "unique_need_amount": request.unique_need_amount,
            "unique_ratio": legacy.safe_round(unique_ratio, 6),
            "unique_asset": request.unique_asset,
            "unique_asset_label": legacy.ASSET_NAMES_KR[request.unique_asset],
            "unique_items": request.unique_items,
            "unique_profile": request.unique_profile,
            "unique_engine_note": (
                "Azure OpenAI Structured Output으로 자유문장을 의미 매핑하고, "
                "기존 계산 엔진이 명확히 지원하는 필드만 적용합니다. "
                "지원하지 않는 항목은 advisory/unmapped로 보존합니다."
            ),
            "age": request.age,
            "client_context": request.client_context,
            "analysis_scope": request.client_context.get(
                "calculation_scope",
                "개인 투자포트폴리오 계산",
            ),
            "risk_profile": request.risk_profile,
            "client_risk_level": legacy.CLIENT_RISK_LEVEL[request.risk_profile],
            "investment_horizon_years": request.investment_horizon_years,
            "target_after_tax_return": target_after_tax_return,
            "target_after_tax_return_basis": (
                "PB가 승인한 IPS Return 입력"
                if target_after_tax_return is not None
                else "미입력"
            ),
            "tax_sensitivity": request.tax_sensitivity,
            "liquidity_need": request.liquidity_need,
            "risk_free_rate": request.risk_free_rate,
            "risk_free_rate_basis": (
                "미국 기준 무위험이자율. 시나리오 테스트 금리와 분리."
            ),
            "cash_return": request.cash_return,
            "period": request.period,
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
            "overseas_stock_realized_gain_rate": (
                request.overseas_stock_realized_gain_rate
            ),
            "overseas_realized_loss": request.overseas_realized_loss,
            "other_financial_income": request.other_financial_income,
            "external_financial_income_krw": (
                legacy.resolve_external_financial_income_krw(request)
            ),
            "external_financial_income_manwon": legacy.safe_round(
                legacy.resolve_external_financial_income_krw(request) / 10_000,
                0,
            ),
            "pension_tax_liability_sufficient": (
                request.pension_tax_liability_sufficient
            ),
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
            "isa_remaining_capacity_override": (
                request.isa_remaining_capacity_override
            ),
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
            "benchmark_data_snapshot": {
                "analysis": analysis_benchmark_meta,
                "backtest": backtest_benchmark_meta,
            },
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
        "correlation_matrix": returns.corr().round(4).to_dict(),
        "asset_summary": legacy.build_asset_summary(
            returns,
            expected_returns,
        ),
        "guideline_definition": legacy.get_guideline_definition(),
        "benchmark_catalog": get_benchmark_catalog(),
        "selected_benchmark": selected_benchmark,
        "methodology": {
            "portfolio_generation": (
                "동일 random_seed의 Monte Carlo 후보군을 한 번 생성해 A/B가 "
                "같은 데이터·같은 세금·같은 리스크 기준을 사용합니다."
            ),
            "portfolio_a_logic": (
                "적합성·VaR·위험기여 기준을 모두 통과한 후보 중 "
                "세후수익률이 가장 높은 후보입니다."
            ),
            "portfolio_b_logic": (
                "같은 기준을 통과한 후보 중 PB 승인 목표 세후수익률을 우선 "
                "충족하고 위험기여 HHI와 최대 위험기여 비중이 낮은 후보입니다."
            ),
            "benchmark_beta_logic": (
                "KOSPI·S&P 500·MSCI ACWI를 추천 데이터와 분리해 계산합니다. "
                "PB 선택은 백테스트 비교선과 beta 표시에만 영향을 주며 "
                "추천 비중에는 영향을 주지 않습니다."
            ),
            "selection_logic": (
                "A/B 모두 고객 적합성·95% Historical VaR·위험기여 집중 "
                "기준을 공통 필터로 사용합니다."
            ),
            "optimization_basis": (
                "실제 가격 데이터의 기대수익률·공분산·세후 추정치를 사용합니다."
            ),
            "backtest_basis": (
                "PR #74의 고정비중 수정주가 누적수익률 계산을 유지합니다."
            ),
            "ai_insight_logic": (
                "외부 AI 인사이트는 의미 매핑해 화면 연결용 advisory로만 반환하며 "
                "포트폴리오 선정에는 자동 반영하지 않습니다."
            ),
        },
        "notes": [
            "본 결과는 정보제공 목적이며 투자 판단과 책임은 투자자 본인에게 있습니다.",
            "기대수익률은 과거 일별 수익률을 연율화한 뒤 보수 조정한 추정값입니다.",
            (
                "세금 계산은 간이 추정입니다. 실제 세액은 전체 소득, "
                "실현손익, 보유계좌, 상품별 요건에 따라 달라집니다."
            ),
        ],
    }


def run_full_analysis_v2(
    *,
    request: legacy.AnalysisRequest,
    target_after_tax_return: float | None,
    selected_benchmark: BenchmarkKey,
    unique_mapping: dict[str, Any] | None,
) -> dict[str, Any]:
    session_id = str(uuid.uuid4())
    legacy.save_session_request(
        session_id,
        {
            "ips": legacy.model_to_dict(request.ips),
            "scenario": legacy.model_to_dict(request.scenario),
            "selected_benchmark": selected_benchmark,
            "target_after_tax_return": target_after_tax_return,
        },
    )

    portfolio_request = legacy.convert_analysis_to_portfolio_request(request)
    core = run_analysis_core_v2(
        request=portfolio_request,
        target_after_tax_return=target_after_tax_return,
        selected_benchmark=selected_benchmark,
        unique_mapping=unique_mapping,
    )
    core["session_id"] = session_id
    core["scenario_summary"] = {
        "base_interest_rate": request.scenario.base_interest_rate,
        "base_fx_rate_krw_per_usd": (
            request.scenario.base_fx_rate_krw_per_usd
        ),
        "stressed_interest_rate": (
            request.scenario.base_interest_rate
            + request.scenario.stress_interest_rate_shock
        ),
        "stressed_fx_rate_krw_per_usd": (
            request.scenario.base_fx_rate_krw_per_usd
            * (1 + request.scenario.stress_fx_shock)
        ),
        "stress_interest_rate_shock": (
            request.scenario.stress_interest_rate_shock
        ),
        "stress_fx_shock": request.scenario.stress_fx_shock,
        "stress_affects_scoring": request.scenario.stress_affects_scoring,
        "risk_free_rate_used_for_sharpe_sortino": (
            core["input_summary"]["risk_free_rate"]
        ),
        "risk_free_rate_note": (
            "Sharpe/Sortino 기준 금리는 scenario.base_interest_rate와 분리됨."
        ),
        "rrttllu": request.scenario.rrttllu,
        "unique_profile": core["input_summary"].get("unique_profile", {}),
    }

    core["backtest"] = legacy.extract_backtest_payload(core)
    core["tax_optimizer"] = legacy.build_tax_optimizer_map(
        core,
        portfolio_request,
    )
    core["tax_inputs"] = legacy.extract_tax_inputs_payload(core)
    return core
