// FastAPI 백엔드 클라이언트 — 데이터 fetch·계산은 모두 백엔드에서 수행하고
// 프론트는 결과만 받아 표시한다.
import type {
  HistoricalCrisis,
  MacroIndicators,
  PortfolioProposal,
  StressedPortfolio,
  StressScenario,
} from './types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export function fetchMacroIndicators(): Promise<MacroIndicators> {
  return getJson<MacroIndicators>('/api/macro-indicators');
}

export function fetchPortfolios(): Promise<PortfolioProposal[]> {
  return getJson<PortfolioProposal[]>('/api/portfolios');
}

export function fetchStressScenarios(): Promise<StressScenario[]> {
  return getJson<StressScenario[]>('/api/stress-scenarios');
}

// 과거 주요 경제 위기(2008·2020·2022) 재현 시 포트폴리오별 예상 손실률(P&L)
export function fetchHistoricalCrises(): Promise<HistoricalCrisis[]> {
  return getJson<HistoricalCrisis[]>('/api/historical-crises');
}

// 스트레스 조율기(슬라이더) 충격값으로 포트폴리오 전체 지표(기대수익률·변동성·
// 샤프·소르티노·MDD)를 재계산해 받아온다.
export function fetchStressedPortfolios(
  baseRateDeltaBp: number,
  krwUsdDelta: number,
): Promise<StressedPortfolio[]> {
  const params = new URLSearchParams({
    base_rate_delta_bp: String(baseRateDeltaBp),
    krw_usd_delta: String(krwUsdDelta),
  });
  return getJson<StressedPortfolio[]>(`/api/stressed-portfolios?${params}`);
}
