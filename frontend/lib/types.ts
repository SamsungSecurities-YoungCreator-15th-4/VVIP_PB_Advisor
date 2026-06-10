// 백엔드(FastAPI) market API 응답 타입 — backend/app/market/schemas.py 와 1:1 대응

export interface IndicatorData {
  price: number;
  change: number;
  changePct: number;
  isStatic?: boolean;
}

export interface MacroIndicators {
  baseRate: IndicatorData;
  treasuryYield: IndicatorData;
  krwUsd: IndicatorData;
  cpi: IndicatorData;
  kospi: IndicatorData;
  sp500: IndicatorData;
  fetchedAt: string;
}

export interface AssetAllocation {
  ticker: string;
  name: string;
  nameKr: string;
  weight: number; // 0~1
  assetClass: 'domestic_equity' | 'us_equity' | 'bond' | 'gold' | 'reit' | 'commodity' | 'dividend';
  color: string;
}

export interface BacktestPoint {
  date: string;
  value: number; // 누적 수익률 (1.0 = 0%)
}

export interface PortfolioMetrics {
  expectedReturn: number; // % per year
  volatility: number; // % per year
  sharpeRatio: number;
  maxDrawdown: number | null; // % — 실측 백테스트가 부족하면 null(N/A)
  backtestData: BacktestPoint[];
}

export interface PortfolioProposal {
  id: 'current' | 'proposalA' | 'proposalB';
  name: string;
  nameKr: string;
  description: string;
  theme: string;
  allocations: AssetAllocation[];
  metrics: PortfolioMetrics | null;
}

export interface StressScenario {
  id: string;
  name: string;
  nameKr: string;
  description: string;
  icon: string;
  shocks: Record<string, number>; // asset class → shock multiplier
  results: Record<string, number>; // portfolio id → expected return change (p.p.)
}
