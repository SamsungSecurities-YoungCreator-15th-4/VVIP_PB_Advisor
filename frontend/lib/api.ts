/**
 * FastAPI 백엔드 호출 베이스 클라이언트.
 *
 * 공통 책임만 담는다: base URL(env), 타임아웃(AbortController), 에러 표준화(ApiError),
 * JSON·multipart 전송. 기능별 타입·폴백 로직은 lib/api/ 하위 모듈에서 이 헬퍼를 쓴다.
 *
 * 시크릿은 절대 여기서 다루지 않는다. NEXT_PUBLIC_API_BASE_URL(공개 가능한 base URL)만 읽는다.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

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
    if (err instanceof DOMException && err.name === "AbortError") {
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

export { createClient } from "./api/clients";
export type { CreatedClient, CreateClientResult } from "./api/clients";
