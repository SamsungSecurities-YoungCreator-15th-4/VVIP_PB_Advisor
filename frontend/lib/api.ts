/**
 * FastAPI 백엔드 fetch 헬퍼 골격. 아직 실제 연동은 하지 않는다.
 * 사용 예: const data = await apiGet<PortfolioResponse>("/portfolio/simulate");
 */
import type {
  HistoricalCrisis,
  MacroIndicators,
  PortfolioProposal,
  StressedPortfolio,
  StressScenario,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!BASE_URL) {
    throw new Error(
      "NEXT_PUBLIC_API_BASE_URL이 설정되지 않았습니다 (.env.local 참고)",
    );
  }
  // init.headers가 Headers 인스턴스·배열이어도 안전하게 병합
  const headers = new Headers(init?.headers);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${path}`);
  }
  return res.json() as Promise<T>;
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body) });
}

// ── 시장 데이터·포트폴리오 지표 (realtime market 백엔드) ────────────────────
// 데이터 fetch·계산은 모두 백엔드(app/market)에서 수행하고 프론트는 결과만 받는다.
// develop 컴포넌트(StressTestSection 등)의 목데이터를 실데이터로 교체할 때 사용.
const MARKET_API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function getMarketJson<T>(path: string): Promise<T> {
  const res = await fetch(`${MARKET_API_BASE_URL}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export function fetchMacroIndicators(): Promise<MacroIndicators> {
  return getMarketJson<MacroIndicators>("/api/macro-indicators");
}

export function fetchPortfolios(): Promise<PortfolioProposal[]> {
  return getMarketJson<PortfolioProposal[]>("/api/portfolios");
}

export function fetchStressScenarios(): Promise<StressScenario[]> {
  return getMarketJson<StressScenario[]>("/api/stress-scenarios");
}

// 과거 주요 경제 위기(2008·2020·2022) 재현 시 포트폴리오별 예상 손실률(P&L)
export function fetchHistoricalCrises(): Promise<HistoricalCrisis[]> {
  return getMarketJson<HistoricalCrisis[]>("/api/historical-crises");
}

// 스트레스 조율기(슬라이더) 충격값으로 포트폴리오 전체 지표를 재계산해 받아온다.
export function fetchStressedPortfolios(
  baseRateDeltaBp: number,
  krwUsdDelta: number,
): Promise<StressedPortfolio[]> {
  const params = new URLSearchParams({
    base_rate_delta_bp: String(baseRateDeltaBp),
    krw_usd_delta: String(krwUsdDelta),
  });
  return getMarketJson<StressedPortfolio[]>(
    `/api/stressed-portfolios?${params}`,
  );
}
