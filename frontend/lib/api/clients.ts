/**
 * 고객 생성 연동 — POST /clients.
 *
 * 결과를 4가지로 구분한다(가짜를 실데이터인 척 두지 않기 위해):
 *  - live     : DB 저장 성공(실 client_id 확보)
 *  - conflict : 동명이인 거부(409) — 서버가 명시적으로 거절 → 로컬 추가하지 않음
 *  - invalid  : 입력값 오류(400/422) — 로컬 추가하지 않음
 *  - fallback : 저장 실패(네트워크/타임아웃/5xx) — 로컬에만 데모로 추가(배지로 명시)
 */

import { ApiError, apiGet, apiPost } from "@/lib/api";
import { type ApiResult, fallback, live } from "./result";

export interface CreatedClient {
  clientId: string; // DB UUID. fallback 시엔 빈 문자열(미저장).
  name: string;
  aumEokwon: number;
}

export interface ListedClient {
  clientId: string;
  name: string;
  aumEokwon: number;
  isPersona: boolean;
  createdAt: string;
}

interface ClientCreateResponseRaw {
  client_id: string;
  name: string;
  aum_eokwon: number;
  created_at: string;
}

interface ClientListItemRaw {
  client_id?: string | null;
  name?: string | null;
  aum_eokwon?: number | null;
  is_persona?: boolean | null;
  created_at?: string | null;
}

interface ClientListResponseRaw {
  clients?: ClientListItemRaw[] | null;
}

export type CreateClientResult =
  | { status: "live"; data: CreatedClient }
  | { status: "conflict"; message: string }
  | { status: "invalid"; message: string }
  | { status: "fallback"; data: CreatedClient; note: string };

export async function createClient(
  name: string,
  aumEokwon: number,
): Promise<CreateClientResult> {
  try {
    const res = await apiPost<ClientCreateResponseRaw>("/clients", {
      name,
      aum_eokwon: aumEokwon,
    });
    return {
      status: "live",
      data: { clientId: res.client_id, name: res.name, aumEokwon: res.aum_eokwon },
    };
  } catch (err) {
    if (err instanceof ApiError && err.status === 409) {
      return { status: "conflict", message: `이미 등록된 고객명입니다: ${name}` };
    }
    if (err instanceof ApiError && (err.status === 400 || err.status === 422)) {
      return { status: "invalid", message: "고객명·운용자산 입력값을 확인해주세요." };
    }
    // 네트워크/타임아웃/5xx — 저장은 실패했으나 화면은 죽지 않게 로컬 데모로 추가.
    const note =
      err instanceof ApiError && err.isTimeout
        ? "응답 시간 초과로 저장되지 않았습니다(데모로만 추가)."
        : "백엔드 저장 실패 — 데모로만 추가되었습니다(새로고침 시 사라짐).";
    return {
      status: "fallback",
      data: { clientId: "", name, aumEokwon },
      note,
    };
  }
}

export async function listClients(): Promise<ApiResult<ListedClient[]>> {
  try {
    const res = await apiGet<ClientListResponseRaw>("/clients");
    return live(
      (res.clients ?? []).map((client) => ({
        clientId: client.client_id ?? "",
        name: client.name ?? "",
        aumEokwon: client.aum_eokwon ?? 0,
        isPersona: client.is_persona ?? false,
        createdAt: client.created_at ?? "",
      })),
    );
  } catch {
    return fallback(
      [],
      "고객 목록을 DB에서 불러오지 못해 데모 고객 목록을 표시합니다.",
    );
  }
}

// ── 직전 상담 첫 분석 스냅샷 API ──

export interface DashboardSnapshot {
  /** true: 새 상담의 첫 분석을 저장함, false: 같은 상담이라 기존 첫 분석을 유지함 */
  saved: boolean;
  clientId: string;
  consultationId: string;
  calculationSessionId: string;
  dashboardResult: Record<string, unknown>;
  stressTestResult: Record<string, unknown>;
  savedAt: string;
  message: string;
}

interface DashboardSnapshotRaw {
  saved: boolean;
  client_id: string;
  consultation_id: string;
  calculation_session_id: string;
  dashboard_result: Record<string, unknown>;
  stress_test_result?: Record<string, unknown> | null;
  saved_at: string;
  message: string;
}

export interface SaveFirstDashboardSnapshotInput {
  clientId: string;
  consultationId: string;
  /** POST /portfolio/calculate 응답 전체 */
  dashboardResult: Record<string, unknown>;
  /** 첫 분석 시 스트레스 결과가 없다면 생략 */
  stressTestResult?: Record<string, unknown>;
}

function mapDashboardSnapshot(raw: DashboardSnapshotRaw): DashboardSnapshot {
  return {
    saved: raw.saved,
    clientId: raw.client_id,
    consultationId: raw.consultation_id,
    calculationSessionId: raw.calculation_session_id,
    dashboardResult: raw.dashboard_result,
    stressTestResult: raw.stress_test_result ?? {},
    savedAt: raw.saved_at,
    message: raw.message,
  };
}

/**
 * PB 접속 또는 고객 선택 직후 호출한다.
 * 저장값이 없으면 null, 있으면 예를 들어 3회차 상담 시작 시 2-1을 반환한다.
 */
export async function getPreviousDashboard(
  clientId: string,
): Promise<DashboardSnapshot | null> {
  if (!clientId) return null;

  try {
    const raw = await apiGet<DashboardSnapshotRaw>(
      `/clients/${encodeURIComponent(clientId)}/previous-dashboard`,
    );
    return mapDashboardSnapshot(raw);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

/**
 * 분석하기의 /portfolio/calculate 성공 직후 호출한다.
 * 같은 consultationId로 여러 번 호출되어도 백엔드는 첫 번째 결과만 유지한다.
 */
export async function saveFirstDashboardSnapshot(
  input: SaveFirstDashboardSnapshotInput,
): Promise<DashboardSnapshot> {
  const calculationSessionId = String(
    input.dashboardResult.calculation_session_id ?? "",
  );

  if (!input.clientId) {
    throw new Error("clientId가 없어 상담 첫 분석 결과를 저장할 수 없습니다.");
  }
  if (!input.consultationId) {
    throw new Error("consultationId가 없어 상담 첫 분석 결과를 저장할 수 없습니다.");
  }
  if (!calculationSessionId) {
    throw new Error(
      "dashboardResult.calculation_session_id가 없어 상담 첫 분석 결과를 저장할 수 없습니다.",
    );
  }

  const raw = await apiPost<DashboardSnapshotRaw>(
    `/clients/${encodeURIComponent(input.clientId)}/dashboard-snapshot`,
    {
      consultation_id: input.consultationId,
      calculation_session_id: calculationSessionId,
      dashboard_result: input.dashboardResult,
      stress_test_result: input.stressTestResult ?? {},
    },
  );

  return mapDashboardSnapshot(raw);
}

// ── 직전 상담 첫 분석 스냅샷 API 끝 ──
