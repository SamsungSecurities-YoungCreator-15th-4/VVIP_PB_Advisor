/**
 * FastAPI 백엔드 호출 베이스 클라이언트.
 *
 * 공통 책임만 담는다: base URL(env), 타임아웃(AbortController), 에러 표준화(ApiError),
 * JSON·multipart 전송. 기능별 타입·폴백 로직은 lib/api/ 하위 모듈에서 이 헬퍼를 쓴다.
 *
 * 시크릿은 절대 여기서 다루지 않는다. NEXT_PUBLIC_API_BASE_URL(공개 가능한 base URL)만 읽는다.
 */
import type {
  HistoricalCrisis,
  MacroIndicators,
  PortfolioProposal,
  StressedPortfolio,
  StressScenario,
} from "./types";
import { getSupabase } from "./supabaseClient";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

/**
 * 현재 Supabase 세션의 access_token 을 Authorization 헤더로 만들어 반환한다.
 * 로그인 전(세션 없음)에는 빈 객체 → 기존처럼 헤더 없이 호출(401 은 백엔드가 판단).
 */
async function authHeader(): Promise<Record<string, string>> {
  try {
    const {
      data: { session },
    } = await getSupabase().auth.getSession();
    const token = session?.access_token;
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

/** 텍스트 API 기본 타임아웃(ms). STT 등 긴 작업은 호출부에서 늘려 넘긴다. */
export const DEFAULT_TIMEOUT_MS = 30_000;

/** 백엔드 호출 실패를 표준화한 에러. status 0 = 네트워크/타임아웃(연결 자체 실패). */
export class ApiError extends Error {
  readonly status: number;
  readonly isTimeout: boolean;
  constructor(message: string, status: number, isTimeout = false) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.isTimeout = isTimeout;
  }
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  /** JSON 바디(직렬화해 전송). multipart 와 동시 사용 금지. */
  json?: unknown;
  /** multipart 바디(FormData). Content-Type 은 브라우저가 boundary 와 함께 설정. */
  form?: FormData;
  /** 타임아웃(ms). 미지정 시 DEFAULT_TIMEOUT_MS. */
  timeoutMs?: number;
}

function assertBaseUrl(): void {
  if (!BASE_URL) {
    throw new ApiError(
      "NEXT_PUBLIC_API_BASE_URL이 설정되지 않았습니다 (.env.local 참고)",
      0,
    );
  }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  assertBaseUrl();
  const { json, form, timeoutMs = DEFAULT_TIMEOUT_MS, ...init } = options;

  const headers = new Headers(init.headers);
  // 로그인 세션이 있으면 access_token 을 Bearer 로 첨부(이미 지정된 경우는 존중).
  if (!headers.has("Authorization")) {
    const auth = await authHeader();
    if (auth.Authorization) headers.set("Authorization", auth.Authorization);
  }
  let body: BodyInit | undefined;
  if (form) {
    body = form; // Content-Type 은 설정하지 않는다(boundary 자동).
  } else if (json !== undefined) {
    body = JSON.stringify(json);
    if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  }

  // Render Free 의 spin-down·콜드스타트로 무한 대기하지 않도록 타임아웃을 건다.
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      body,
      headers,
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new ApiError(`요청 시간 초과: ${path}`, 0, true);
    }
    // 네트워크 실패(백엔드 다운·CORS·DNS 등). 메시지에 민감정보 미포함.
    throw new ApiError(`네트워크 오류: ${path}`, 0);
  } finally {
    clearTimeout(timer);
  }

  if (!res.ok) {
    throw new ApiError(`API ${res.status}: ${path}`, res.status);
  }
  return res.json() as Promise<T>;
}

export function apiGet<T>(path: string, options?: RequestOptions): Promise<T> {
  return request<T>(path, { ...options, method: "GET" });
}

export function apiPost<T>(
  path: string,
  json: unknown,
  options?: RequestOptions,
): Promise<T> {
  return request<T>(path, { ...options, method: "POST", json });
}

// ── 시장 데이터·포트폴리오 지표 (realtime market 백엔드) ────────────────────
// 데이터 fetch·계산은 모두 백엔드(app/market)에서 수행하고 프론트는 결과만 받는다.
// develop 컴포넌트(StressTestSection 등)의 목데이터를 실데이터로 교체할 때 사용.
const MARKET_API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function getMarketJson<T>(path: string): Promise<T> {
  const res = await fetch(`${MARKET_API_BASE_URL}${path}`, {
    headers: await authHeader(),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

// force=true면 백엔드 5분 캐시를 무시하고 강제 재조회 (새로고침 버튼용)
export function fetchMacroIndicators(force = false): Promise<MacroIndicators> {
  return getMarketJson<MacroIndicators>(
    `/api/macro-indicators${force ? "?force=true" : ""}`,
  );
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
// totalAssets(억 원)는 세후수익률의 종합과세 구간 계산에 쓰인다.
export interface TaxAccountInputs {
  isaUsedManwon?: number;
  pensionUsedManwon?: number;
  realizedLossManwon?: number;
  marginalRatePct?: number; // 한계세율(%) — 백엔드는 소수(0~0.495)로 받는다
  // 적합성(lock-up) 게이팅 입력
  age?: number;
  horizonYears?: number;
  nearTermNeedManwon?: number;
  nearTermNeedYears?: number | null;
  isaOpened?: boolean;
}

export function fetchStressedPortfolios(
  baseRateDeltaBp: number,
  krwUsdDelta: number,
  totalAssets = 50,
  otherFinancialIncome = 0,
  tax: TaxAccountInputs = {},
): Promise<StressedPortfolio[]> {
  const params = new URLSearchParams({
    base_rate_delta_bp: String(baseRateDeltaBp),
    krw_usd_delta: String(krwUsdDelta),
    total_assets: String(totalAssets),
    other_financial_income: String(otherFinancialIncome),
    isa_used_manwon: String(tax.isaUsedManwon ?? 0),
    pension_used_manwon: String(tax.pensionUsedManwon ?? 0),
    realized_loss_manwon: String(tax.realizedLossManwon ?? 0),
    near_term_need_manwon: String(tax.nearTermNeedManwon ?? 0),
    isa_opened: String(tax.isaOpened ?? true),
    ...(tax.marginalRatePct != null
      ? { marginal_tax_rate: String(tax.marginalRatePct / 100) }
      : {}),
    ...(tax.age != null ? { age: String(tax.age) } : {}),
    ...(tax.horizonYears != null
      ? { horizon_years: String(tax.horizonYears) }
      : {}),
    ...(tax.nearTermNeedYears != null
      ? { near_term_need_years: String(tax.nearTermNeedYears) }
      : {}),
  });
  return getMarketJson<StressedPortfolio[]>(
    `/api/stressed-portfolios?${params}`,
  );
}

/** multipart/form-data 전송(파일 업로드용). */
export function apiPostForm<T>(
  path: string,
  form: FormData,
  options?: RequestOptions,
): Promise<T> {
  return request<T>(path, { ...options, method: "POST", form });
}

// ── 단일 진입점(barrel) ────────────────────────────────────────
// 기능별 타입·연동 함수는 lib/api/ 하위에 두고 여기서 다시 내보낸다.
// UI 는 항상 `@/lib/api` 에서만 가져온다. (하위 모듈은 위 base 헬퍼를 재사용)
export type { ApiResult, DataSource } from "./api/result";
export * from "./api/types";

export { fetchRagInsight } from "./api/rag";
export type { InsightData, InsightCitation, FetchInsightOptions } from "./api/rag";

export { fetchTaxInsight, buildTaxResultFromMock } from "./api/tax";
export type { TaxInsightData } from "./api/tax";

export { uploadSttConsultation } from "./api/stt";
export type { SttConsultationData, IpsPatch } from "./api/stt";

export { createClient, listClients } from "./api/clients";
export type {
  CreatedClient,
  CreateClientResult,
  ListedClient,
} from "./api/clients";

export { fetchPortfolioCalculate, fetchPortfolioStressTest } from "./api/portfolio";
export type { PortfolioCalcOptions, PortfolioCalcData } from "./api/portfolio";
