import { NextResponse } from 'next/server';
import { fetchQuotes, fetchUsdKrw } from '@/lib/yfinance-cache';

// 최근 확인된 실제값 (2026-06-06 금요일 종가 기준) — API 실패 시 빈 화면 방지용
const FALLBACKS: Record<string, { price: number; change: number; changePct: number; isStatic?: boolean }> = {
  baseRate:      { price: 2.75,    change: 0,      changePct: 0,     isStatic: true },
  treasuryYield: { price: 4.536,   change: +0.061, changePct: +1.36 },
  krwUsd:        { price: 1545.29, change: -9.70,  changePct: -0.62 },
  cpi:           { price: 2.6,     change: 0,      changePct: 0,     isStatic: true },
  kospi:         { price: 8160.59, change: -24.70, changePct: -0.30 },
  sp500:         { price: 7383.74, change: -196.32, changePct: -2.59 },
};

export async function GET() {
  // Yahoo Finance(KOSPI, S&P500, 미국채10년)와 open.er-api.com(원/달러)를 병렬 호출
  const [quotes, forexResult] = await Promise.all([
    fetchQuotes(['^KS11', '^GSPC', '^TNX']),
    fetchUsdKrw(),
  ]);

  function pick(symbol: string, key: string) {
    const live = quotes[symbol];
    if (live && live.price > 0) return live;
    return FALLBACKS[key];
  }

  const krwUsd = forexResult.price > 0 ? forexResult : FALLBACKS.krwUsd;

  return NextResponse.json({
    baseRate:      FALLBACKS.baseRate,
    treasuryYield: pick('^TNX',  'treasuryYield'),
    krwUsd,
    cpi:           FALLBACKS.cpi,
    kospi:         pick('^KS11', 'kospi'),
    sp500:         pick('^GSPC', 'sp500'),
    fetchedAt:     new Date().toISOString(),
  });
}
