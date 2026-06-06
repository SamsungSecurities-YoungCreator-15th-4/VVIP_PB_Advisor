import type { PortfolioProposal, StressScenario } from './types';

export const DEFAULT_PORTFOLIOS: PortfolioProposal[] = [
  {
    id: 'current',
    name: 'Current Portfolio',
    nameKr: '현재 포트폴리오',
    description: '기존 보수적 자산 배분',
    theme: '안정형',
    allocations: [
      { ticker: 'TLT', name: 'US Long-Term Bond', nameKr: '미국 장기채', weight: 0.40, assetClass: 'bond', color: '#3B82F6' },
      { ticker: '069500.KS', name: 'KODEX 200', nameKr: '국내 주식(KOSPI200)', weight: 0.30, assetClass: 'domestic_equity', color: '#10B981' },
      { ticker: 'VYM', name: 'Vanguard High Dividend', nameKr: '미국 고배당주', weight: 0.20, assetClass: 'dividend', color: '#F59E0B' },
      { ticker: 'GLD', name: 'SPDR Gold', nameKr: '금', weight: 0.10, assetClass: 'gold', color: '#EF4444' },
    ],
    metrics: null,
  },
  {
    id: 'proposalA',
    name: 'Proposal A: Income',
    nameKr: '제안 A: 인컴/배당 중심',
    description: '안정적 현금흐름 극대화',
    theme: '고배당 인컴형',
    allocations: [
      { ticker: 'TLT', name: 'US Long-Term Bond', nameKr: '미국 장기채', weight: 0.30, assetClass: 'bond', color: '#3B82F6' },
      { ticker: '069500.KS', name: 'KODEX 200', nameKr: '국내 주식(KOSPI200)', weight: 0.25, assetClass: 'domestic_equity', color: '#10B981' },
      { ticker: 'VYM', name: 'Vanguard High Dividend', nameKr: '미국 고배당주', weight: 0.30, assetClass: 'dividend', color: '#F59E0B' },
      { ticker: 'GLD', name: 'SPDR Gold', nameKr: '금', weight: 0.15, assetClass: 'gold', color: '#EF4444' },
    ],
    metrics: null,
  },
  {
    id: 'proposalB',
    name: 'Proposal B: Growth',
    nameKr: '제안 B: 글로벌 성장형',
    description: '장기 자산 증식 극대화',
    theme: '글로벌 성장/대체자산',
    allocations: [
      { ticker: 'TLT', name: 'US Long-Term Bond', nameKr: '미국 장기채', weight: 0.10, assetClass: 'bond', color: '#3B82F6' },
      { ticker: '069500.KS', name: 'KODEX 200', nameKr: '국내 주식(KOSPI200)', weight: 0.10, assetClass: 'domestic_equity', color: '#10B981' },
      { ticker: 'QQQ', name: 'Nasdaq 100 ETF', nameKr: '미국 성장주(나스닥100)', weight: 0.30, assetClass: 'us_equity', color: '#8B5CF6' },
      { ticker: 'VNQ', name: 'Vanguard REIT', nameKr: '글로벌 리츠', weight: 0.20, assetClass: 'reit', color: '#06B6D4' },
      { ticker: 'GLD', name: 'SPDR Gold', nameKr: '금', weight: 0.15, assetClass: 'gold', color: '#EF4444' },
      { ticker: 'GSG', name: 'iShares Commodity', nameKr: '원자재', weight: 0.15, assetClass: 'commodity', color: '#F97316' },
    ],
    metrics: null,
  },
];

export const STRESS_SCENARIOS: StressScenario[] = [
  {
    id: 'rate_hike',
    name: 'Fed Rate Hike +100bps',
    nameKr: '미국 기준금리 100bp 급등',
    description: '채권 가격 급락, 성장주 하락',
    icon: '📈',
    shocks: {
      bond: -0.12,
      us_equity: -0.08,
      domestic_equity: -0.05,
      dividend: -0.04,
      gold: 0.02,
      reit: -0.10,
      commodity: 0.03,
    },
    results: {},
  },
  {
    id: 'krw_depreciation',
    name: 'KRW/USD +200won',
    nameKr: '원/달러 환율 급등 (+200원)',
    description: '환노출 해외주식 평가익↑, 국내주식 하락',
    icon: '💱',
    shocks: {
      bond: 0.08,
      us_equity: 0.10,
      domestic_equity: -0.07,
      dividend: 0.09,
      gold: 0.08,
      reit: 0.07,
      commodity: 0.06,
    },
    results: {},
  },
];

export const ALL_TICKERS = [
  'TLT', '069500.KS', 'VYM', 'GLD', 'QQQ', 'VNQ', 'GSG'
];
