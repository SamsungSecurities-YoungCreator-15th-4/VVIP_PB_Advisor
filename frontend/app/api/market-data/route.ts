import { NextRequest, NextResponse } from 'next/server';
import { fetchHistorical } from '@/lib/yfinance-cache';
import type { MarketDataPoint } from '@/lib/types';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const tickersParam = searchParams.get('tickers') ?? '';
  const tickers = tickersParam.split(',').filter(Boolean);

  if (tickers.length === 0) {
    return NextResponse.json({ error: 'No tickers provided' }, { status: 400 });
  }

  const result: Record<string, MarketDataPoint> = {};

  // 순차 처리로 rate limit 회피 (캐시 레이어 포함)
  for (const ticker of tickers) {
    const hist = await fetchHistorical(ticker);
    result[ticker] = {
      ticker: hist.ticker,
      prices: hist.prices,
      dates: hist.dates,
      annualReturn: hist.annualReturn,
      annualVolatility: hist.annualVolatility,
    };
  }

  return NextResponse.json(result);
}
