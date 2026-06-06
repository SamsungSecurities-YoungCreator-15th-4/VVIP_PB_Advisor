export interface IPSProfile {
  clientName: string;
  totalAssets: number; // 억 원
  return: {
    targetReturn: number; // % per year
    description: string;
  };
  risk: {
    level: 'conservative' | 'moderate' | 'aggressive';
    maxDrawdownTolerance: number; // %
    description: string;
  };
  timeHorizon: {
    years: number;
    description: string;
  };
  tax: {
    comprehensiveTaxation: boolean; // 금융소득종합과세 해당 여부
    otherFinancialIncome: number; // 억 원
    description: string;
  };
  liquidity: {
    amount: number; // 억 원
    timeframe: string;
    description: string;
  };
  legal: {
    constraints: string[];
    description: string;
  };
  unique: {
    circumstances: string[];
    description: string;
  };
  rawText: string;
}

export interface AssetAllocation {
  ticker: string;
  name: string;
  nameKr: string;
  weight: number; // 0~1
  assetClass: 'domestic_equity' | 'us_equity' | 'bond' | 'gold' | 'reit' | 'commodity' | 'dividend';
  color: string;
}

export interface PortfolioMetrics {
  expectedReturn: number; // % per year
  volatility: number; // % per year
  sharpeRatio: number;
  maxDrawdown: number; // %
  backtestData: BacktestPoint[];
}

export interface BacktestPoint {
  date: string;
  value: number; // 누적 수익률 (1.0 = 0%)
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
  results: Record<string, number>; // portfolio id → expected loss %
}

export interface MarketDataPoint {
  ticker: string;
  prices: number[];
  dates: string[];
  annualReturn: number;
  annualVolatility: number;
}

export interface MacroReport {
  pbScript: string;
  clientLetter: string;
  generatedAt: string;
}

export interface DashboardState {
  clientMemo: string;
  ipsProfile: IPSProfile | null;
  portfolios: PortfolioProposal[];
  selectedPortfolioId: 'current' | 'proposalA' | 'proposalB';
  stressScenarios: StressScenario[];
  macroReport: MacroReport | null;
  uploadedDocText: string;
  isLoading: {
    ips: boolean;
    market: boolean;
    report: boolean;
  };
}
