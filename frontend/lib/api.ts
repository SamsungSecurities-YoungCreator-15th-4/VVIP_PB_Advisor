// FastAPI 백엔드 클라이언트 — 데이터 fetch·계산은 모두 백엔드에서 수행하고
// 프론트는 결과만 받아 표시한다.
import type { MacroIndicators, PortfolioProposal, StressScenario } from './types';

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
