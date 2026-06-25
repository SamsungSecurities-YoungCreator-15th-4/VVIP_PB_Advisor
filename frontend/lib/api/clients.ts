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
import { type ApiResult, empty, fallback, live } from "./result";

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
      data: {
        clientId: res.client_id,
        name: res.name,
        aumEokwon: res.aum_eokwon,
      },
    };
  } catch (err) {
    if (err instanceof ApiError && err.status === 409) {
      return {
        status: "conflict",
        message: `이미 등록된 고객명입니다: ${name}`,
      };
    }
    if (err instanceof ApiError && (err.status === 400 || err.status === 422)) {
      return {
        status: "invalid",
        message: "고객명·운용자산 입력값을 확인해주세요.",
      };
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

// ── 대시보드 스냅샷 ────────────────────────────────────────────
// POST /clients/{client_id}/dashboard-snapshot : 상담별 첫 분석(1-1) 저장
// GET  /clients/{client_id}/previous-dashboard : 가장 최근 저장된 분석 반환
// 백엔드가 consultation_id 기준 중복 방지 처리(같은 id 재요청 시 기존 반환)를 한다.

export interface DashboardSnapshotResult {
  saved: boolean;
  client_id: string;
  consultation_id: string;
  calculation_session_id: string;
  dashboard_result: Record<string, unknown>;
  stress_test_result?: Record<string, unknown> | null;
  saved_at: string;
  message?: string;
}

/** STT 완료 후 첫 분석하기 결과를 스냅샷으로 저장. 실패해도 UI를 막지 않는다(fire-and-forget). */
export async function saveDashboardSnapshot(
  clientId: string,
  payload: {
    consultation_id: string;
    calculation_session_id: string;
    dashboard_result: Record<string, unknown>;
  },
): Promise<void> {
  try {
    await apiPost<DashboardSnapshotResult>(
      `/clients/${encodeURIComponent(clientId)}/dashboard-snapshot`,
      payload,
    );
  } catch {
    // 저장 실패는 조용히 처리 — 화면 흐름을 막지 않는다
  }
}

/** 해당 고객의 가장 최근 저장된 대시보드 스냅샷을 반환. 없으면 null(정상). */
export async function getPreviousDashboard(
  clientId: string,
): Promise<ApiResult<DashboardSnapshotResult | null>> {
  try {
    const res = await apiGet<DashboardSnapshotResult>(
      `/clients/${encodeURIComponent(clientId)}/previous-dashboard`,
    );
    return live(res.saved ? res : null);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      return live(null); // 이전 분석 없음 — 정상
    }
    const note =
      err instanceof ApiError && err.isTimeout
        ? "이전 분석 결과 조회 시간이 초과되었습니다."
        : "이전 분석 결과를 불러오지 못했습니다.";
    return empty<DashboardSnapshotResult | null>(null, note);
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
