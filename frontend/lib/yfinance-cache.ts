// Yahoo Finance v8 API 직접 호출 — yahoo-finance2 라이브러리 rate limit 우회
import fs from 'fs';
import path from 'path';

const CACHE_TTL_MS = 5 * 60 * 1000; // 5분

interface CacheEntry<T> {
  data: T;
  expiresAt: number;
}

const cache = new Map<string, CacheEntry<unknown>>();

function getCache<T>(key: string): T | null {
  const entry = cache.get(key) as CacheEntry<T> | undefined;
  if (!entry || Date.now() > entry.expiresAt) return null;
  return entry.data;
}

function setCache<T>(key: string, data: T): void {
  cache.set(key, { data, expiresAt: Date.now() + CACHE_TTL_MS });
}

function sleep(ms: number) {
  return new Promise(res => setTimeout(res, ms));
}

// 타임아웃 방어: Yahoo Finance 응답 없을 때 무한 대기 방지
async function fetchWithTimeout(url: string, headers: Record<string, string>, timeoutMs = 4000): Promise<Response> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    return await fetch(url, { headers, signal: ctrl.signal });
  } finally {
    clearTimeout(timer);
  }
}

const YF_HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Accept': 'application/json',
};

// query1, query2 두 호스트를 번갈아 시도 — 한 쪽 차단 시 자동 전환
const YF_HOSTS = [
  'https://query1.finance.yahoo.com',
  'https://query2.finance.yahoo.com',
];

export interface QuoteResult {
  price: number;
  change: number;
  changePct: number;
}

// 단일 시도 — 429/에러 시 즉시 실패 (retry backoff는 캐시된 상황에서만 의미 있음)
async function fetchYFv8(symbol: string): Promise<QuoteResult> {
  for (let attempt = 0; attempt < 2; attempt++) {
    const host = YF_HOSTS[attempt % YF_HOSTS.length];
    const url = `${host}/v8/finance/chart/${encodeURIComponent(symbol)}?interval=1d&range=5d`;
    try {
      const res = await fetchWithTimeout(url, YF_HEADERS, 4000);
      if (res.status === 429) throw new Error('rate-limited');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json() as {
        chart: {
          result: Array<{
            meta: { regularMarketPrice: number; chartPreviousClose: number };
          }>;
          error: unknown;
        };
      };
      if (json.chart.error) throw new Error(String(json.chart.error));
      const meta  = json.chart.result[0].meta;
      const price = meta.regularMarketPrice;
      const prev  = meta.chartPreviousClose;
      return { price, change: price - prev, changePct: prev ? ((price - prev) / prev) * 100 : 0 };
    } catch {
      // query2로 재시도 후 실패하면 throw
    }
  }
  throw new Error('YF fetch failed');
}

// 심볼 병렬 호출 — 4초 timeout으로 최악의 경우에도 ~4s 이내 응답
export async function fetchQuotes(symbols: string[]): Promise<Record<string, QuoteResult>> {
  const cacheKey = `quotes:${symbols.slice().sort().join(',')}`;
  const cached = getCache<Record<string, QuoteResult>>(cacheKey);
  if (cached) return cached;

  const entries = await Promise.allSettled(
    symbols.map(async (symbol) => {
      const symKey = `quote:${symbol}`;
      const symCached = getCache<QuoteResult>(symKey);
      if (symCached) return { symbol, data: symCached };
      const data = await fetchYFv8(symbol);
      setCache(symKey, data);
      return { symbol, data };
    })
  );

  const result: Record<string, QuoteResult> = {};
  for (const entry of entries) {
    if (entry.status === 'fulfilled') {
      result[entry.value.symbol] = entry.value.data;
    } else {
      console.error(`[yfinance] failed:`, entry.reason?.message?.slice(0, 80));
    }
  }

  setCache(cacheKey, result);
  return result;
}

// ── 원/달러 전용: open.er-api.com (USDKRW=X는 YF에서 429 차단) ─────────

export interface ForexResult {
  price: number;
  change: number;
  changePct: number;
}

interface ForexHistory {
  today: { date: string; rate: number };
  yesterday: { date: string; rate: number } | null;
}

const FOREX_HISTORY_PATH = path.join(process.cwd(), 'private', 'forex-history.json');

function readForexHistory(): ForexHistory | null {
  try {
    return JSON.parse(fs.readFileSync(FOREX_HISTORY_PATH, 'utf-8')) as ForexHistory;
  } catch {
    return null;
  }
}

function writeForexHistory(history: ForexHistory): void {
  try {
    fs.writeFileSync(FOREX_HISTORY_PATH, JSON.stringify(history, null, 2));
  } catch {}
}

// 환율 price만 추출하는 소스별 fetch 함수들
async function fetchWiseRate(): Promise<number> {
  const res = await fetchWithTimeout(
    'https://wise.com/rates/live?source=USD&target=KRW',
    { 'Accept': 'application/json' },
    4000
  );
  if (!res.ok) throw new Error(`Wise HTTP ${res.status}`);
  const json = await res.json() as { value: number; time: number };
  if (!json.value || json.value <= 0) throw new Error('Wise: invalid value');
  return json.value;
}

async function fetchErApiRate(): Promise<number> {
  const res = await fetchWithTimeout(
    'https://open.er-api.com/v6/latest/USD',
    { 'Accept': 'application/json' },
    4000
  );
  if (!res.ok) throw new Error(`open.er-api HTTP ${res.status}`);
  const json = await res.json() as { result: string; rates: Record<string, number> };
  if (json.result !== 'success') throw new Error('open.er-api: API error');
  const price = json.rates['KRW'];
  if (!price || price <= 0) throw new Error('open.er-api: KRW missing');
  return price;
}

export async function fetchUsdKrw(): Promise<ForexResult> {
  const cacheKey = 'forex:USDKRW';
  const cached = getCache<ForexResult>(cacheKey);
  if (cached) return cached;

  // 1순위: Wise (~1분 실시간)
  // 2순위: open.er-api.com (하루 1회 고시환율)
  // 3순위: forex-history.json 마지막 저장값
  let price = 0;
  let source = '';

  try {
    price = await fetchWiseRate();
    source = 'wise';
  } catch (e1) {
    console.error('[forex] Wise failed:', (e1 as Error).message, '→ open.er-api 시도');
    try {
      price = await fetchErApiRate();
      source = 'open.er-api';
    } catch (e2) {
      console.error('[forex] open.er-api failed:', (e2 as Error).message, '→ 파일 캐시 사용');
    }
  }

  // 3순위: 파일에 저장된 마지막 값 사용
  if (price <= 0) {
    const history = readForexHistory();
    if (history) {
      price = history.today.rate;
      source = 'file-cache';
      console.error('[forex] 모든 소스 실패 — 마지막 저장값 사용:', price);
    } else {
      return { price: 0, change: 0, changePct: 0 };
    }
  }

  // 전일 대비 계산 + 파일 히스토리 업데이트 (live 소스일 때만 기록)
  const todayStr = new Date().toISOString().split('T')[0];
  const history = readForexHistory();
  let change = 0;
  let changePct = 0;

  if (!history) {
    if (source !== 'file-cache') writeForexHistory({ today: { date: todayStr, rate: price }, yesterday: null });
  } else if (history.today.date === todayStr) {
    if (history.yesterday) {
      change = price - history.yesterday.rate;
      changePct = (change / history.yesterday.rate) * 100;
    }
  } else {
    change = price - history.today.rate;
    changePct = (change / history.today.rate) * 100;
    if (source !== 'file-cache') writeForexHistory({ today: { date: todayStr, rate: price }, yesterday: history.today });
  }

  const entry: ForexResult = { price, change, changePct };
  setCache(cacheKey, entry);
  return entry;
}

// ── Historical (포트폴리오 백테스트용) ────────────────────────────────────

export interface HistoricalResult {
  ticker: string;
  prices: number[];
  dates: string[];
  annualReturn: number;
  annualVolatility: number;
}

const FALLBACKS: Record<string, { annualReturn: number; annualVolatility: number }> = {
  'TLT':       { annualReturn: 0.032, annualVolatility: 0.138 },
  '069500.KS': { annualReturn: 0.068, annualVolatility: 0.185 },
  'VYM':       { annualReturn: 0.091, annualVolatility: 0.148 },
  'GLD':       { annualReturn: 0.085, annualVolatility: 0.142 },
  'QQQ':       { annualReturn: 0.158, annualVolatility: 0.235 },
  'VNQ':       { annualReturn: 0.072, annualVolatility: 0.198 },
  'GSG':       { annualReturn: 0.045, annualVolatility: 0.220 },
};

export async function fetchHistorical(ticker: string, years = 5): Promise<HistoricalResult> {
  const cacheKey = `hist:${ticker}:${years}`;
  const cached = getCache<HistoricalResult>(cacheKey);
  if (cached) return cached;

  const endTs   = Math.floor(Date.now() / 1000);
  const startTs = endTs - years * 365 * 24 * 3600;
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker)}?interval=1wk&period1=${startTs}&period2=${endTs}`;

  try {
    await sleep(300);
    const res = await fetchWithTimeout(url, YF_HEADERS, 5000);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const json = await res.json() as {
      chart: {
        result: Array<{
          timestamp: number[];
          indicators: {
            adjclose?: Array<{ adjclose: (number | null)[] }>;
            quote: Array<{ close: (number | null)[] }>;
          };
        }>;
      };
    };

    const result = json.chart.result[0];
    const timestamps = result.timestamp;
    const adjCloses  = result.indicators.adjclose?.[0]?.adjclose ?? result.indicators.quote[0].close;

    const prices: number[] = [];
    const dates:  string[] = [];
    for (let i = 0; i < timestamps.length; i++) {
      const p = adjCloses[i];
      if (p != null && p > 0) {
        prices.push(p);
        dates.push(new Date(timestamps[i] * 1000).toISOString().split('T')[0]);
      }
    }

    if (prices.length < 10) throw new Error('Insufficient data');

    const weeklyReturns: number[] = [];
    for (let i = 1; i < prices.length; i++) {
      weeklyReturns.push((prices[i] - prices[i - 1]) / prices[i - 1]);
    }
    const mean              = weeklyReturns.reduce((s, r) => s + r, 0) / weeklyReturns.length;
    const annualReturn      = (1 + mean) ** 52 - 1;
    const variance          = weeklyReturns.reduce((s, r) => s + (r - mean) ** 2, 0) / weeklyReturns.length;
    const annualVolatility  = Math.sqrt(variance * 52);

    const entry: HistoricalResult = { ticker, prices, dates, annualReturn, annualVolatility };
    setCache(cacheKey, entry);
    return entry;
  } catch {
    const fb = FALLBACKS[ticker] ?? { annualReturn: 0.07, annualVolatility: 0.15 };
    return { ticker, prices: [], dates: [], ...fb };
  }
}
