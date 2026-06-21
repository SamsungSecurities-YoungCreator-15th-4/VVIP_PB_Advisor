"""yfinance 기반 시세/환율/과거데이터 조회 — frontend/lib/yfinance-cache.ts 이식.

USD/KRW: yfinance의 USDKRW=X는 종종 차단되므로 Wise → open.er-api.com → 파일 캐시 순으로 조회한다.
"""
import asyncio
import json
import logging
import threading
from datetime import date, datetime, timezone
from pathlib import Path

import requests
import yfinance as yf

from app.market.cache import TTLCache
from app.market.schemas import ForexResult, MarketDataPoint, QuoteResult

logger = logging.getLogger(__name__)

_quote_cache: TTLCache[QuoteResult] = TTLCache()
_quotes_batch_cache: TTLCache[dict[str, QuoteResult]] = TTLCache()
_forex_cache: TTLCache[ForexResult] = TTLCache()
_hist_cache: TTLCache[MarketDataPoint] = TTLCache()

REQUEST_TIMEOUT = 4

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


# ── 마지막 성공값 디스크 스냅샷 ─────────────────────────────────────────────
# 실시간 조회 실패 시 하드코딩 fallback 대신 "직전에 성공한 값"을 쓴다.
# 인메모리 stale 캐시(TTLCache.get_stale)가 1차, 이 파일이 2차(서버 재시작 대비).
# 하드코딩 fallback은 첫 부팅부터 네트워크가 안 되는 경우에만 도달한다.

_SNAPSHOT_LOCK = threading.Lock()


def _snapshot_path() -> Path:
    return CACHE_DIR / "market_snapshot.json"


def _read_snapshot() -> dict:
    try:
        with open(_snapshot_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _write_snapshot_entry(section: str, key: str, data: dict) -> None:
    with _SNAPSHOT_LOCK:
        snapshot = _read_snapshot()
        snapshot.setdefault(section, {})[key] = {
            "savedAt": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(_snapshot_path(), "w", encoding="utf-8") as f:
                json.dump(snapshot, f)
        except OSError:
            pass


def _read_snapshot_entry(section: str, key: str) -> dict | None:
    entry = _read_snapshot().get(section, {}).get(key)
    return entry["data"] if entry else None


# ── 시세 (KOSPI/S&P500/미국채10년 등) ───────────────────────────────────────

def _fetch_quote_sync(symbol: str) -> QuoteResult:
    hist = yf.Ticker(symbol).history(period="5d", interval="1d")
    closes = hist["Close"].dropna()
    if closes.empty:
        raise RuntimeError(f"no data for {symbol}")

    price = float(closes.iloc[-1])
    prev = float(closes.iloc[-2]) if len(closes) >= 2 else price
    change = price - prev
    change_pct = (change / prev * 100) if prev else 0.0
    return QuoteResult(price=price, change=change, changePct=change_pct)


async def fetch_quotes(symbols: list[str], force: bool = False) -> dict[str, QuoteResult]:
    # force=True면 5분 캐시를 무시하고 강제 재조회한다(새로고침 버튼용).
    # 단 조회 성공값은 캐시에 다시 저장해, 이후 자동 갱신·일반 호출의 캐시 보호는 유지된다.
    cache_key = f"quotes:{','.join(sorted(symbols))}"
    if not force:
        cached = _quotes_batch_cache.get(cache_key)
        if cached is not None:
            return cached

    async def fetch_one(symbol: str) -> tuple[str, QuoteResult] | None:
        sym_key = f"quote:{symbol}"
        if not force:
            sym_cached = _quote_cache.get(sym_key)
            if sym_cached is not None:
                return symbol, sym_cached
        try:
            data = await asyncio.to_thread(_fetch_quote_sync, symbol)
        except Exception as exc:
            logger.warning("[yfinance] %s fetch failed: %s", symbol, exc)
            # 1차: TTL 만료된 인메모리 마지막 성공값
            stale = _quote_cache.get_stale(sym_key)
            if stale is not None:
                logger.info("[yfinance] %s → 메모리 마지막 성공값 사용 (지연 시세)", symbol)
                return symbol, stale.model_copy(update={"isFallback": True})
            # 2차: 디스크 스냅샷 (서버 재시작 후 첫 조회 실패 대비)
            snap = _read_snapshot_entry("quotes", symbol)
            if snap is not None:
                logger.info("[yfinance] %s → 디스크 스냅샷 사용 (지연 시세)", symbol)
                return symbol, QuoteResult(**{**snap, "isFallback": True})
            return None
        _quote_cache.set(sym_key, data)
        _write_snapshot_entry("quotes", symbol, data.model_dump(exclude_none=True))
        return symbol, data

    entries = await asyncio.gather(*(fetch_one(s) for s in symbols))

    result: dict[str, QuoteResult] = {}
    for entry in entries:
        if entry is not None:
            symbol, data = entry
            result[symbol] = data

    _quotes_batch_cache.set(cache_key, result)
    return result


# ── 원/달러 환율: Wise → open.er-api.com → 파일 캐시 ────────────────────────

CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache"
FOREX_HISTORY_PATH = CACHE_DIR / "forex_history.json"


def _read_forex_history() -> dict | None:
    try:
        with open(FOREX_HISTORY_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _write_forex_history(history: dict) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(FOREX_HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except OSError:
        pass


def _fetch_wise_rate() -> float:
    res = requests.get(
        "https://wise.com/rates/live",
        params={"source": "USD", "target": "KRW"},
        headers={"Accept": "application/json"},
        timeout=REQUEST_TIMEOUT,
    )
    res.raise_for_status()
    value = res.json().get("value")
    if not value or value <= 0:
        raise ValueError("Wise: invalid value")
    return float(value)


def _fetch_er_api_rate() -> float:
    res = requests.get(
        "https://open.er-api.com/v6/latest/USD",
        headers={"Accept": "application/json"},
        timeout=REQUEST_TIMEOUT,
    )
    res.raise_for_status()
    body = res.json()
    if body.get("result") != "success":
        raise ValueError("open.er-api: API error")
    price = body.get("rates", {}).get("KRW")
    if not price or price <= 0:
        raise ValueError("open.er-api: KRW missing")
    return float(price)


def _fetch_usd_krw_sync(force: bool = False) -> ForexResult:
    cache_key = "forex:USDKRW"
    if not force:
        cached = _forex_cache.get(cache_key)
        if cached is not None:
            return cached

    # 1순위: Wise (~1분 실시간) / 2순위: open.er-api.com (하루 1회 고시환율) / 3순위: 파일 캐시
    price = 0.0
    source = ""

    try:
        price = _fetch_wise_rate()
        source = "wise"
    except Exception as e1:
        logger.warning("[forex] Wise failed: %s → open.er-api 시도", e1)
        try:
            price = _fetch_er_api_rate()
            source = "open.er-api"
        except Exception as e2:
            logger.warning("[forex] open.er-api failed: %s → 파일 캐시 사용", e2)

    history = _read_forex_history()

    if price <= 0:
        if history:
            price = history["today"]["rate"]
            source = "file-cache"
            logger.warning("[forex] 모든 소스 실패 — 마지막 저장값 사용: %s", price)
        else:
            return ForexResult(price=0, change=0, changePct=0)

    # 전일 대비 계산 + 파일 히스토리 업데이트 (live 소스일 때만 기록)
    today_str = date.today().isoformat()
    change = 0.0
    change_pct = 0.0

    if not history:
        if source != "file-cache":
            _write_forex_history({"today": {"date": today_str, "rate": price}, "yesterday": None})
    elif history["today"]["date"] == today_str:
        if history.get("yesterday"):
            change = price - history["yesterday"]["rate"]
            change_pct = (change / history["yesterday"]["rate"]) * 100
    else:
        change = price - history["today"]["rate"]
        change_pct = (change / history["today"]["rate"]) * 100
        if source != "file-cache":
            _write_forex_history({
                "today": {"date": today_str, "rate": price},
                "yesterday": history["today"],
            })

    # live 소스가 아니라 파일 캐시에서 읽은 값이면 "지연 시세"로 표시
    entry = ForexResult(
        price=price, change=change, changePct=change_pct,
        isFallback=(source == "file-cache") or None,
    )
    _forex_cache.set(cache_key, entry)
    return entry


async def fetch_usd_krw(force: bool = False) -> ForexResult:
    return await asyncio.to_thread(_fetch_usd_krw_sync, force)


# ── 과거 데이터 (포트폴리오 백테스트용) ─────────────────────────────────────

# 첫 부팅부터 네트워크 불가 시에만 쓰는 대표 상수. 티커는 계산 로직 측
# (portfolio_logic_8th.py) ASSET_TICKERS와 동일하게 맞춘다.
FALLBACKS: dict[str, dict[str, float]] = {
    "TLT": {"annualReturn": 0.032, "annualVolatility": 0.138},
    # 일반채 프록시: KODEX 국고채10년액티브 — 5년 대표값 (듀레이션 ≈ 7.99년)
    "471230.KS": {"annualReturn": 0.034, "annualVolatility": 0.062},
    # 분리과세채 프록시: KODEX 국고채30년액티브 — 5년 대표값 (듀레이션 ≈ 19.53년)
    "439870.KS": {"annualReturn": 0.040, "annualVolatility": 0.165},
    # 저쿠폰채 프록시: KODEX 미국30년국채액티브(H) — 환헤지 (듀레이션 ≈ 15.39년)
    "484790.KS": {"annualReturn": 0.030, "annualVolatility": 0.140},
    # 국내주식 프록시: KOSPI 지수
    "^KS11": {"annualReturn": 0.060, "annualVolatility": 0.180},
    # 해외배당 프록시: SCHD
    "SCHD": {"annualReturn": 0.105, "annualVolatility": 0.150},
    "GLD": {"annualReturn": 0.085, "annualVolatility": 0.142},
    "QQQ": {"annualReturn": 0.158, "annualVolatility": 0.235},
    "VNQ": {"annualReturn": 0.072, "annualVolatility": 0.198},
    # 원자재 프록시: Invesco DB Commodity (DBC)
    "DBC": {"annualReturn": 0.045, "annualVolatility": 0.180},
}


def _fetch_historical_sync(ticker: str, years: int = 5) -> MarketDataPoint:
    cache_key = f"hist:{ticker}:{years}"
    cached = _hist_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        hist = yf.Ticker(ticker).history(period=f"{years}y", interval="1wk")
        closes = hist["Close"].dropna()
        if len(closes) < 10:
            raise ValueError("Insufficient data")

        prices = [float(p) for p in closes.tolist()]
        dates = [ts.strftime("%Y-%m-%d") for ts in closes.index]

        weekly_returns = [
            (prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))
        ]
        mean = sum(weekly_returns) / len(weekly_returns)
        annual_return = (1 + mean) ** 52 - 1
        variance = sum((r - mean) ** 2 for r in weekly_returns) / len(weekly_returns)
        annual_volatility = (variance * 52) ** 0.5

        result = MarketDataPoint(
            ticker=ticker, prices=prices, dates=dates,
            annualReturn=annual_return, annualVolatility=annual_volatility,
        )
        _hist_cache.set(cache_key, result)
        _write_snapshot_entry("historical", cache_key, result.model_dump())
        return result
    except Exception as exc:
        logger.warning("[yfinance] %s historical fetch failed: %s", ticker, exc)
        # 1차: TTL 만료된 인메모리 마지막 성공값 (실측 시계열 그대로 보존)
        stale = _hist_cache.get_stale(cache_key)
        if stale is not None:
            logger.info("[yfinance] %s historical → 메모리 마지막 성공값 사용", ticker)
            return stale
        # 2차: 디스크 스냅샷 (서버 재시작 대비)
        snap = _read_snapshot_entry("historical", cache_key)
        if snap is not None:
            logger.info("[yfinance] %s historical → 디스크 스냅샷 사용", ticker)
            return MarketDataPoint(**snap)
        # 최후: 대표 상수 (첫 부팅부터 네트워크 불가 시에만 — 시계열 없음 → 지표는 fallback 경로)
        fb = FALLBACKS.get(ticker, {"annualReturn": 0.07, "annualVolatility": 0.15})
        return MarketDataPoint(ticker=ticker, prices=[], dates=[], **fb)


async def fetch_historical(ticker: str, years: int = 5) -> MarketDataPoint:
    return await asyncio.to_thread(_fetch_historical_sync, ticker, years)
