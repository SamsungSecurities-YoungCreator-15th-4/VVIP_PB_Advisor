import type { AssetAllocation, PortfolioMetrics, BacktestPoint, MarketDataPoint } from './types';

const RISK_FREE_RATE = 0.035; // 3.5% 국고채

export function calcPortfolioMetrics(
  allocations: AssetAllocation[],
  marketData: Record<string, MarketDataPoint>
): PortfolioMetrics {
  const weights = allocations.map(a => a.weight);
  const tickers = allocations.map(a => a.ticker);

  const returns = tickers.map(t => marketData[t]?.annualReturn ?? 0.06);
  const vols = tickers.map(t => marketData[t]?.annualVolatility ?? 0.15);

  const expectedReturn = weights.reduce((sum, w, i) => sum + w * returns[i], 0);

  // 자산 간 상관관계를 단순화하여 포트폴리오 변동성 계산
  // 실제 상관관계 행렬 대신 자산군별 대표 상관계수 사용
  let portfolioVariance = 0;
  for (let i = 0; i < weights.length; i++) {
    for (let j = 0; j < weights.length; j++) {
      const corr = getCorrelation(allocations[i].assetClass, allocations[j].assetClass);
      portfolioVariance += weights[i] * weights[j] * vols[i] * vols[j] * corr;
    }
  }
  const volatility = Math.sqrt(portfolioVariance);
  const sharpeRatio = (expectedReturn - RISK_FREE_RATE) / volatility;

  const backtestData = generateBacktest(allocations, marketData);
  const maxDrawdown = calcMDD(backtestData.map(d => d.value));

  return { expectedReturn, volatility, sharpeRatio, maxDrawdown, backtestData };
}

function getCorrelation(a: string, b: string): number {
  if (a === b) return 1.0;
  const key = [a, b].sort().join('-');
  const correlations: Record<string, number> = {
    'bond-domestic_equity': 0.1,
    'bond-us_equity': -0.05,
    'bond-gold': 0.1,
    'bond-reit': 0.2,
    'bond-commodity': 0.0,
    'bond-dividend': 0.15,
    'domestic_equity-us_equity': 0.65,
    'domestic_equity-gold': -0.05,
    'domestic_equity-reit': 0.5,
    'domestic_equity-commodity': 0.3,
    'domestic_equity-dividend': 0.6,
    'us_equity-gold': -0.1,
    'us_equity-reit': 0.55,
    'us_equity-commodity': 0.25,
    'us_equity-dividend': 0.75,
    'gold-reit': 0.1,
    'gold-commodity': 0.5,
    'gold-dividend': -0.05,
    'reit-commodity': 0.3,
    'reit-dividend': 0.5,
    'commodity-dividend': 0.2,
  };
  return correlations[key] ?? 0.3;
}

function generateBacktest(
  allocations: AssetAllocation[],
  marketData: Record<string, MarketDataPoint>
): BacktestPoint[] {
  // 각 티커를 date → price 맵으로 변환
  const priceMaps = allocations.flatMap(alloc => {
    const data = marketData[alloc.ticker];
    if (!data || data.dates.length === 0) return [];
    const map = new Map<string, number>();
    data.dates.forEach((date, i) => {
      if (data.prices[i] != null) map.set(date, data.prices[i]);
    });
    return [{ alloc, map }];
  });

  if (priceMaps.length === 0) return generateSyntheticBacktest(allocations);

  // 모든 티커에 데이터가 있는 날짜만 사용 (교집합) — 한·미 휴장일 차이 방어
  const allDateSets = priceMaps.map(({ map }) => new Set(map.keys()));
  const commonDates = [...allDateSets[0]]
    .filter(date => allDateSets.every(set => set.has(date)))
    .sort();

  if (commonDates.length < 10) return generateSyntheticBacktest(allocations);

  const result: BacktestPoint[] = [];
  let portfolioValue = 1.0;

  for (let i = 1; i < commonDates.length; i++) {
    const prevDate = commonDates[i - 1];
    const currDate = commonDates[i];
    let periodReturn = 0;

    for (const { alloc, map } of priceMaps) {
      const prev = map.get(prevDate);
      const curr = map.get(currDate);
      if (prev != null && curr != null && prev > 0) {
        periodReturn += alloc.weight * (curr - prev) / prev;
      }
    }

    portfolioValue *= 1 + periodReturn;
    result.push({ date: currDate, value: portfolioValue });
  }

  return result;
}

function generateSyntheticBacktest(allocations: AssetAllocation[]): BacktestPoint[] {
  const result: BacktestPoint[] = [];
  let value = 1.0;
  const annualReturn = allocations.reduce((sum, a) => sum + a.weight * 0.07, 0);
  const annualVol = 0.12;
  const dailyReturn = annualReturn / 252;
  const dailyVol = annualVol / Math.sqrt(252);

  const startDate = new Date('2020-01-01');
  for (let i = 0; i < 1260; i++) {
    const date = new Date(startDate);
    date.setDate(date.getDate() + i);
    const shock = (Math.random() - 0.5) * 2 * dailyVol;
    value *= 1 + dailyReturn + shock;
    if (i % 5 === 0) {
      result.push({ date: date.toISOString().split('T')[0], value });
    }
  }
  return result;
}

export function calcMDD(values: number[]): number {
  let maxDrawdown = 0;
  let peak = values[0] ?? 1;

  for (const v of values) {
    if (v > peak) peak = v;
    const drawdown = (peak - v) / peak;
    if (drawdown > maxDrawdown) maxDrawdown = drawdown;
  }
  return maxDrawdown;
}

export function calcAfterTaxReturn(
  grossReturn: number,
  portfolio: AssetAllocation[],
  totalAssets: number, // 억 원
  otherFinancialIncome: number // 억 원
): { afterTaxReturn: number; taxAmount: number; isComprehensive: boolean } {
  const annualGrossIncome = grossReturn * totalAssets;

  const dividendIncome = portfolio
    .filter(a => a.assetClass === 'dividend' || a.assetClass === 'bond')
    .reduce((sum, a) => sum + a.weight * grossReturn * totalAssets * 0.5, 0);

  const totalFinancialIncome = dividendIncome + otherFinancialIncome;
  const COMPREHENSIVE_TAX_THRESHOLD = 0.2; // 2천만원 = 0.2억

  const isComprehensive = totalFinancialIncome > COMPREHENSIVE_TAX_THRESHOLD;

  let taxRate: number;
  if (isComprehensive) {
    const taxableIncome = totalFinancialIncome * 100; // 백만원 단위
    if (taxableIncome <= 1400) taxRate = 0.066;
    else if (taxableIncome <= 5000) taxRate = 0.165;
    else if (taxableIncome <= 8800) taxRate = 0.264;
    else if (taxableIncome <= 15000) taxRate = 0.385;
    else taxRate = 0.495;
  } else {
    taxRate = 0.154; // 원천징수세율 15.4%
  }

  const taxAmount = annualGrossIncome * taxRate;
  const afterTaxReturn = grossReturn * (1 - taxRate);

  return { afterTaxReturn, taxAmount, isComprehensive };
}

export function applyStressScenario(
  portfolioReturn: number,
  allocations: AssetAllocation[],
  shocks: Record<string, number>
): number {
  let stressedReturn = 0;
  for (const alloc of allocations) {
    const shock = shocks[alloc.assetClass] ?? 0;
    const baseReturn = portfolioReturn * alloc.weight;
    stressedReturn += baseReturn + alloc.weight * shock;
  }
  return stressedReturn;
}
