/**
 * 지난 상담 내역 연동 — GET /consultations, GET /consultations/detail.
 *
 * 백엔드는 pb_id(JWT)로 본인 담당 고객의 상담만 반환한다(소유권 격리).
 * 목록은 요약(제목·일자)만, 상세는 전사·IPS 까지 내려준다. 상세는 STT 업로드와
 * 동일한 SttConsultationData 모양으로 매핑해, 불러오기 시 같은 store 갱신을 재사용한다.
 */

import { ApiError, apiGet } from "@/lib/api";
import { type ApiResult, empty, live } from "./result";
import {
  type IpsPatch,
  type SttConsultationData,
  mapIps,
  mapTranscript,
} from "./stt";
import type {
  ConsultationListResponse,
  ConsultationResponse,
  InitialIpsResponse,
} from "./types";

export type { IpsPatch, SttConsultationData };

/** 모달에 뿌릴 지난 상담 요약 항목. */
export interface ConsultationSummaryItem {
  consultationId: string;
  transcriptTitle: string;
  consultationDate: string;
}

/** 선택 고객의 지난 상담 목록(최신순). 실패 시 빈 목록 + 사유. */
export async function listConsultations(
  clientId: string,
): Promise<ApiResult<ConsultationSummaryItem[]>> {
  try {
    const res = await apiGet<ConsultationListResponse>(
      `/consultations?client_id=${encodeURIComponent(clientId)}`,
    );
    const items = (res.consultations ?? []).map((c) => ({
      consultationId: c.consultation_id,
      transcriptTitle: c.transcript_title || c.consultation_date || "상담 기록",
      consultationDate: c.consultation_date,
    }));
    return live(items);
  } catch (err) {
    const note =
      err instanceof ApiError && err.isTimeout
        ? "상담 목록 조회 시간이 초과되었습니다."
        : "상담 목록을 불러오지 못했습니다.";
    return empty<ConsultationSummaryItem[]>([], note);
  }
}

/**
 * 신규/미상담 고객의 최초(initial) IPS 를 불러온다.
 * 고객 생성 시 백엔드가 DEFAULT_IPS_TEMPLATE 로 저장한 initial 스냅샷을 읽어,
 * IPS 조율기가 이전 고객·페르소나 값으로 남지 않게 한다. 없으면 null(정상).
 */
export async function fetchInitialIps(
  clientId: string,
): Promise<ApiResult<IpsPatch | null>> {
  const params = new URLSearchParams({ client_id: clientId });
  try {
    const res = await apiGet<InitialIpsResponse>(
      `/consultations/initial-ips?${params.toString()}`,
    );
    return live(mapIps(res.ips_json as unknown as Parameters<typeof mapIps>[0]));
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      return live(null); // 최초 IPS 미저장 — 정상
    }
    return empty<IpsPatch | null>(null, "최초 IPS를 불러오지 못했습니다.");
  }
}

/** 특정 상담의 전사·IPS 상세를 불러온다(STT 업로드 결과와 동일 모양). */
export async function loadConsultationDetail(
  clientId: string,
  consultationId: string,
): Promise<ApiResult<SttConsultationData>> {
  const params = new URLSearchParams({
    client_id: clientId,
    consultation_id: consultationId,
  });
  try {
    const res = await apiGet<ConsultationResponse>(
      `/consultations/detail?${params.toString()}`,
    );
    return live({
      consultationId: res.consultation_id,
      transcript: mapTranscript(res.transcript_json),
      ips: mapIps(res.ips_json),
      transcriptTitle: res.transcript_title,
      consultationDate: res.consultation_date,
    });
  } catch (err) {
    const note =
      err instanceof ApiError && err.status === 404
        ? "상담 내역을 찾을 수 없습니다."
        : "상담 내역을 불러오지 못했습니다.";
    return empty<SttConsultationData>(
      {
        consultationId: "",
        transcript: [],
        ips: {} as IpsPatch,
        transcriptTitle: "",
        consultationDate: "",
      },
      note,
    );
  }
}
