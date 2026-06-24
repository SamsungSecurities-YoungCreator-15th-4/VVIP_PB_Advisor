# ruff: noqa: E501
"""portfolio_logic.py 분할: prices 모듈."""

import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf
from typing import Any, Dict, List, Optional, Tuple

from .assets import ASSET_TICKERS
from .constants import BENCHMARK_CONFIGS, BENCHMARK_POLICY_VERSION, DEFAULT_BENCHMARK_KEY, MIN_COMMON_PRICE_OBSERVATIONS, PRICE_SNAPSHOT_DIR, PRICE_SNAPSHOT_PATH, PRICE_SNAPSHOT_VERSION, TRADING_DAYS, _PRICE_SNAPSHOT_LOCK

KST = ZoneInfo("Asia/Seoul")
logger = logging.getLogger(__name__)

# ============================================================
# 5. 가격 데이터
# ============================================================


def _empty_benchmark_snapshot(reason: str) -> Dict[str, Any]:
    return {
        "policy": BENCHMARK_POLICY_VERSION,
        "default_key": DEFAULT_BENCHMARK_KEY,
        "affects_portfolio_recommendation": False,
        "options": {
            key: {
                "key": key,
                "ticker": config["ticker"],
                "label": config["label"],
                "official_index_series": config["official_index_series"],
                "proxy_note": config["proxy_note"],
                "available": False,
                "reason": reason,
                "data_start": None,
                "data_end": None,
                "observations": 0,
            }
            for key, config in BENCHMARK_CONFIGS.items()
        },
    }


def download_benchmark_returns(
    period: str,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """비교용 벤치마크 수익률을 투자자산 데이터와 별도로 조회한다.

    이 함수의 결과는 베타와 비교 차트에만 사용한다.
    추천 후보 생성, 기대수익률, 공분산, VaR, ERC, 순위에는 전달하지 않는다.
    """
    tickers = [config["ticker"] for config in BENCHMARK_CONFIGS.values()]

    try:
        raw = yf.download(
            tickers,
            period=period,
            auto_adjust=True,
            progress=False,
            group_by="column",
            threads=True,
        )
    except Exception:
        logger.warning("벤치마크 시세 조회 실패", exc_info=True)
        return pd.DataFrame(), _empty_benchmark_snapshot("download_failed")

    if raw.empty:
        return pd.DataFrame(), _empty_benchmark_snapshot("download_empty")

    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" not in raw.columns.get_level_values(0):
            return pd.DataFrame(), _empty_benchmark_snapshot("close_price_missing")
        close = raw["Close"].copy()
    else:
        if "Close" not in raw.columns:
            return pd.DataFrame(), _empty_benchmark_snapshot("close_price_missing")
        close = raw[["Close"]].copy()
        if len(tickers) == 1:
            close.columns = tickers

    if isinstance(close, pd.Series):
        close = close.to_frame(name=tickers[0])

    close = close.dropna(how="all").sort_index()

    series_map: Dict[str, pd.Series] = {}
    option_meta: Dict[str, Any] = {}

    for key, config in BENCHMARK_CONFIGS.items():
        ticker = config["ticker"]
        base_meta = {
            "key": key,
            "ticker": ticker,
            "label": config["label"],
            "official_index_series": config["official_index_series"],
            "proxy_note": config["proxy_note"],
        }

        if ticker not in close.columns:
            option_meta[key] = {
                **base_meta,
                "available": False,
                "reason": "benchmark_data_missing",
                "data_start": None,
                "data_end": None,
                "observations": 0,
            }
            continue

        price_series = (
            close[ticker]
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )
        benchmark_return = (
            price_series
            .pct_change(fill_method=None)
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )

        if benchmark_return.empty:
            option_meta[key] = {
                **base_meta,
                "available": False,
                "reason": "benchmark_data_empty",
                "data_start": None,
                "data_end": None,
                "observations": 0,
            }
            continue

        series_key = config["series_key"]
        benchmark_return.name = series_key
        series_map[series_key] = benchmark_return

        option_meta[key] = {
            **base_meta,
            "series_key": series_key,
            "available": True,
            "reason": None,
            "data_start": benchmark_return.index[0].strftime("%Y-%m-%d"),
            "data_end": benchmark_return.index[-1].strftime("%Y-%m-%d"),
            "observations": int(len(benchmark_return)),
        }

    benchmark_frame = (
        pd.concat(series_map.values(), axis=1)
        if series_map
        else pd.DataFrame()
    )

    snapshot = {
        "policy": BENCHMARK_POLICY_VERSION,
        "default_key": DEFAULT_BENCHMARK_KEY,
        "affects_portfolio_recommendation": False,
        "options": option_meta,
    }
    return benchmark_frame, snapshot


def _price_snapshot_key(
    kind: str,
    period: str,
    cash_return: float,
) -> str:
    return f"{kind}|{period}|cash={float(cash_return):.8f}"


def _read_price_snapshot_store() -> Dict[str, Any]:
    with _PRICE_SNAPSHOT_LOCK:
        try:
            with open(
                PRICE_SNAPSHOT_PATH,
                encoding="utf-8",
            ) as file:
                payload = json.load(file)
        except (
            OSError,
            json.JSONDecodeError,
            TypeError,
        ):
            return {
                "version": PRICE_SNAPSHOT_VERSION,
                "snapshots": {},
            }

    if not isinstance(payload, dict):
        return {
            "version": PRICE_SNAPSHOT_VERSION,
            "snapshots": {},
        }

    payload.setdefault(
        "version",
        PRICE_SNAPSHOT_VERSION,
    )
    payload.setdefault("snapshots", {})
    return payload


def _frame_to_snapshot_payload(
    frame: pd.DataFrame,
) -> Dict[str, Any]:
    return {
        "saved_at": datetime.now(KST).isoformat(),
        "index": [
            pd.Timestamp(value).isoformat()
            for value in frame.index
        ],
        "columns": [
            str(column)
            for column in frame.columns
        ],
        "data": [
            [
                None
                if pd.isna(value)
                else float(value)
                for value in row
            ]
            for row in frame.to_numpy()
        ],
        "attrs": dict(frame.attrs),
    }


def _snapshot_payload_to_frame(
    payload: Dict[str, Any],
) -> pd.DataFrame:
    frame = pd.DataFrame(
        data=payload.get("data", []),
        index=pd.to_datetime(
            payload.get("index", [])
        ),
        columns=payload.get("columns", []),
        dtype=float,
    ).sort_index()
    frame.attrs.update(payload.get("attrs", {}))
    return frame


def _save_price_frame_snapshot(
    key: str,
    frame: pd.DataFrame,
) -> None:
    payload = _frame_to_snapshot_payload(frame)

    with _PRICE_SNAPSHOT_LOCK:
        store = _read_price_snapshot_store()
        store["version"] = PRICE_SNAPSHOT_VERSION
        store.setdefault("snapshots", {})[
            key
        ] = payload

        PRICE_SNAPSHOT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )
        temporary_path = (
            PRICE_SNAPSHOT_PATH.with_suffix(".tmp")
        )
        try:
            with open(
                temporary_path,
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    store,
                    file,
                    ensure_ascii=False,
                    default=str,
                )
            temporary_path.replace(
                PRICE_SNAPSHOT_PATH
            )
        except OSError:
            logger.warning(
                "가격 스냅샷 저장 실패: %s",
                PRICE_SNAPSHOT_PATH,
                exc_info=True,
            )


def _load_price_frame_snapshot(
    key: str,
) -> Optional[
    Tuple[pd.DataFrame, Dict[str, Any]]
]:
    payload = (
        _read_price_snapshot_store()
        .get("snapshots", {})
        .get(key)
    )
    if not isinstance(payload, dict):
        return None

    try:
        frame = _snapshot_payload_to_frame(
            payload
        )
    except (
        TypeError,
        ValueError,
        KeyError,
    ):
        logger.warning(
            "가격 스냅샷 복원 실패: %s",
            key,
            exc_info=True,
        )
        return None

    if frame.empty:
        return None

    return frame, {
        "saved_at": payload.get("saved_at"),
        "cache_key": key,
    }


def _apply_live_data_metadata(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    snapshot = dict(
        frame.attrs.get("data_snapshot", {})
    )
    snapshot.update(
        {
            "data_source": "yfinance_live",
            "fallback_used": False,
            "fallback_reason": None,
        }
    )
    frame.attrs["data_snapshot"] = snapshot
    return frame


def _apply_cached_data_metadata(
    frame: pd.DataFrame,
    *,
    cache_metadata: Dict[str, Any],
    error: Exception,
) -> pd.DataFrame:
    snapshot = dict(
        frame.attrs.get("data_snapshot", {})
    )
    snapshot.update(
        {
            "data_source": (
                "disk_last_success_snapshot"
            ),
            "fallback_used": True,
            "fallback_saved_at": (
                cache_metadata.get("saved_at")
            ),
            "fallback_reason": (
                f"{type(error).__name__}: "
                f"{str(error)}"
            )[:300],
            "note": (
                "실시간 조회 실패로 마지막 성공 "
                "스냅샷을 사용했습니다. 현재안과 "
                "추천안 A/B는 동일한 시계열로 "
                "계산됩니다."
            ),
        }
    )
    frame.attrs["data_snapshot"] = snapshot
    return frame

def _download_price_data_live(period: str, cash_return: float) -> pd.DataFrame:
    """추천·지표 계산용 투자자산 가격 데이터.

    벤치마크는 이 함수에서 조회하지 않는다. 따라서 벤치마크의 결측치,
    상장 이력, 데이터 시작일은 추천 포트폴리오에 영향을 주지 않는다.
    """
    tickers = {
        asset: ticker
        for asset, ticker in ASSET_TICKERS.items()
        if ticker != "CASH"
    }

    raw = yf.download(
        list(tickers.values()),
        period=period,
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=True,
    )

    if raw.empty:
        raise RuntimeError("yfinance에서 데이터를 가져오지 못했습니다.")

    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" not in raw.columns.get_level_values(0):
            raise RuntimeError("yfinance 응답에서 Close 가격을 찾지 못했습니다.")
        prices = raw["Close"].copy()
    else:
        prices = raw[["Close"]].copy()

    reverse_map = {ticker: asset for asset, ticker in tickers.items()}
    prices = prices.rename(columns=reverse_map)
    prices = prices.dropna(how="all").sort_index()

    available_assets = [
        asset
        for asset in ASSET_TICKERS.keys()
        if asset != "cash"
        and asset in prices.columns
        and prices[asset].notna().any()
    ]
    excluded_assets = [
        asset
        for asset in ASSET_TICKERS.keys()
        if asset != "cash" and asset not in available_assets
    ]

    if excluded_assets:
        raise RuntimeError(
            "확정 자산군 중 가격 데이터를 가져오지 못한 자산이 있습니다. "
            f"excluded_assets={excluded_assets}. "
            "티커, 상장일, yfinance 다운로드 상태를 확인해 주세요."
        )

    first_valid_dates = {
        asset: prices[asset].first_valid_index()
        for asset in available_assets
    }
    common_start = max(first_valid_dates.values())
    limiting_assets = [
        asset
        for asset, start_date in first_valid_dates.items()
        if start_date == common_start
    ]

    common_prices = (
        prices.loc[common_start:, available_assets]
        .ffill()
        .dropna(how="any")
    )

    if len(common_prices) < MIN_COMMON_PRICE_OBSERVATIONS:
        raise RuntimeError(
            "공통 실제 가격 데이터 구간이 너무 짧습니다. "
            f"observations={len(common_prices)}, "
            f"min_required={MIN_COMMON_PRICE_OBSERVATIONS}, "
            f"common_start={common_start.date() if common_start is not None else None}, "
            f"limiting_assets={limiting_assets}. "
            "최근 상장 ETF proxy를 더 긴 이력 proxy로 바꾸는지 검토해 주세요."
        )

    daily_cash_return = (1 + cash_return) ** (1 / TRADING_DAYS) - 1
    common_prices["cash"] = (
        (1 + daily_cash_return) ** np.arange(len(common_prices))
    )

    ordered_assets = [
        asset
        for asset in ASSET_TICKERS.keys()
        if asset in common_prices.columns
    ]
    common_prices = common_prices[ordered_assets]

    common_prices.attrs["data_snapshot"] = {
        "period_requested": period,
        "as_of": common_prices.index[-1].strftime("%Y-%m-%d"),
        "data_start": common_prices.index[0].strftime("%Y-%m-%d"),
        "data_end": common_prices.index[-1].strftime("%Y-%m-%d"),
        "observations": int(len(common_prices)),
        "available_assets": ordered_assets,
        "excluded_assets": excluded_assets,
        "first_valid_dates": {
            asset: date.strftime("%Y-%m-%d")
            for asset, date in first_valid_dates.items()
        },
        "limiting_assets": limiting_assets,
        "usage": "metrics_and_recommendation_investable_assets_only",
        "benchmark_included": False,
        "note": (
            "추천·기대수익률·공분산·위험지표 계산용 데이터. "
            "벤치마크는 포함하지 않으며, 전체 투자자산의 공통 실제 가격 구간만 사용."
        ),
    }

    return common_prices


def download_price_data(
    period: str,
    cash_return: float,
) -> pd.DataFrame:
    cache_key = _price_snapshot_key(
        "analysis_prices",
        period,
        cash_return,
    )
    try:
        prices = _download_price_data_live(
            period=period,
            cash_return=cash_return,
        )
        prices = _apply_live_data_metadata(
            prices
        )
        _save_price_frame_snapshot(
            cache_key,
            prices,
        )
        return prices
    except Exception as error:
        cached = _load_price_frame_snapshot(
            cache_key
        )
        if cached is None:
            raise

        cached_prices, metadata = cached
        logger.warning(
            "가격 조회 실패. 마지막 성공 "
            "스냅샷 사용: %s",
            cache_key,
            exc_info=True,
        )
        return _apply_cached_data_metadata(
            cached_prices,
            cache_metadata=metadata,
            error=error,
        )


def _download_backtest_price_data_live(
    period: str,
    cash_return: float,
) -> pd.DataFrame:
    """백테스트 차트 전용 투자자산 5년 가격 데이터.

    벤치마크는 별도 함수에서 조회하고 이 결과에는 포함하지 않는다.
    """
    period = "5y"

    tickers = {
        asset: ticker
        for asset, ticker in ASSET_TICKERS.items()
        if ticker != "CASH"
    }

    raw = yf.download(
        list(tickers.values()),
        period=period,
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=True,
    )

    if raw.empty:
        raise RuntimeError("yfinance에서 데이터를 가져오지 못했습니다.")

    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" not in raw.columns.get_level_values(0):
            raise RuntimeError("yfinance 응답에서 Close 가격을 찾지 못했습니다.")
        prices = raw["Close"].copy()
    else:
        prices = raw[["Close"]].copy()

    reverse_map = {ticker: asset for asset, ticker in tickers.items()}
    prices = prices.rename(columns=reverse_map)
    prices = prices.dropna(how="all").sort_index()

    if prices.empty:
        raise RuntimeError("가격 데이터가 비어 있습니다.")

    base_index = prices.index
    daily_cash_return = (1 + cash_return) ** (1 / TRADING_DAYS) - 1

    backtest_prices = pd.DataFrame(index=base_index)
    first_valid_dates: Dict[str, Any] = {}
    cash_substituted_assets: Dict[str, Any] = {}
    excluded_assets: List[str] = []

    for asset in ASSET_TICKERS.keys():
        if asset == "cash":
            continue

        if asset not in prices.columns or prices[asset].notna().sum() == 0:
            excluded_assets.append(asset)
            continue

        series = prices[asset].reindex(base_index).ffill()
        first_valid_date = series.first_valid_index()

        if first_valid_date is None:
            excluded_assets.append(asset)
            continue

        first_valid_dates[asset] = first_valid_date
        first_pos = base_index.get_loc(first_valid_date)

        if first_pos > 0:
            first_real_price = float(series.loc[first_valid_date])
            reverse_steps = np.arange(first_pos, 0, -1)
            pre_listing_values = first_real_price / (
                (1 + daily_cash_return) ** reverse_steps
            )
            series.iloc[:first_pos] = pre_listing_values

            cash_substituted_assets[asset] = {
                "substituted_from": base_index[0].strftime("%Y-%m-%d"),
                "substituted_until": base_index[first_pos - 1].strftime(
                    "%Y-%m-%d"
                ),
                "first_real_price_date": first_valid_date.strftime("%Y-%m-%d"),
                "method": (
                    "backtest_only_pre_listing_period_replaced_with_cash_return"
                ),
            }

        backtest_prices[asset] = series.ffill()

    if excluded_assets:
        raise RuntimeError(
            "확정 자산군 중 가격 데이터를 전혀 가져오지 못한 자산이 있습니다. "
            f"excluded_assets={excluded_assets}. "
            "티커 또는 yfinance 다운로드 상태를 확인해 주세요."
        )

    backtest_prices["cash"] = (
        (1 + daily_cash_return) ** np.arange(len(base_index))
    )

    ordered_assets = [
        asset
        for asset in ASSET_TICKERS.keys()
        if asset in backtest_prices.columns
    ]
    backtest_prices = backtest_prices[ordered_assets]

    if backtest_prices.isna().any().any():
        missing_assets = backtest_prices.columns[
            backtest_prices.isna().any()
        ].tolist()
        raise RuntimeError(
            "백테스트용 현금 대체 이후에도 결측치가 남아 있습니다. "
            f"missing_assets={missing_assets}"
        )

    if len(backtest_prices) < MIN_COMMON_PRICE_OBSERVATIONS:
        raise RuntimeError(
            "5년 백테스트 가격 데이터 구간이 너무 짧습니다. "
            f"observations={len(backtest_prices)}, "
            f"min_required={MIN_COMMON_PRICE_OBSERVATIONS}"
        )

    backtest_prices.attrs["data_snapshot"] = {
        "period_requested": period,
        "as_of": backtest_prices.index[-1].strftime("%Y-%m-%d"),
        "data_start": backtest_prices.index[0].strftime("%Y-%m-%d"),
        "data_end": backtest_prices.index[-1].strftime("%Y-%m-%d"),
        "observations": int(len(backtest_prices)),
        "available_assets": ordered_assets,
        "excluded_assets": excluded_assets,
        "first_valid_dates": {
            asset: date.strftime("%Y-%m-%d")
            for asset, date in first_valid_dates.items()
        },
        "cash_substituted_assets": cash_substituted_assets,
        "limiting_assets": [],
        "usage": "backtest_chart_investable_assets_only",
        "benchmark_included": False,
        "note": (
            "백테스트 차트 전용 투자자산 데이터. "
            "신규 상장 또는 데이터 시작 전 구간만 현금 수익률로 대체하며, "
            "벤치마크는 별도 조회."
        ),
    }

    return backtest_prices


def download_backtest_price_data(
    period: str,
    cash_return: float,
) -> pd.DataFrame:
    fixed_period = "5y"
    cache_key = _price_snapshot_key(
        "backtest_prices",
        fixed_period,
        cash_return,
    )
    try:
        prices = (
            _download_backtest_price_data_live(
                period=fixed_period,
                cash_return=cash_return,
            )
        )
        prices = _apply_live_data_metadata(
            prices
        )
        _save_price_frame_snapshot(
            cache_key,
            prices,
        )
        return prices
    except Exception as error:
        cached = _load_price_frame_snapshot(
            cache_key
        )
        if cached is None:
            raise

        cached_prices, metadata = cached
        logger.warning(
            "백테스트 조회 실패. 마지막 성공 "
            "스냅샷 사용: %s",
            cache_key,
            exc_info=True,
        )
        return _apply_cached_data_metadata(
            cached_prices,
            cache_metadata=metadata,
            error=error,
        )


def calculate_daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    returns = prices.pct_change().replace([np.inf, -np.inf], np.nan).dropna(how="any")
    if returns.empty:
        raise RuntimeError("수익률 계산 결과가 비어 있습니다.")
    returns.attrs["data_snapshot"] = prices.attrs.get("data_snapshot", {})
    return returns
