/**
 * STT 상담 연동 — POST /consultations/stt (multipart).
 *
 * 음성(.wav) 업로드 → 전사·화자매핑 → RRTTLLU(IPS) 추출까지 백엔드가 수행.
 * 처리 시간이 길어 타임아웃을 넉넉히 잡는다(Whisper/Azure + Supabase RPC).
 *
 * 성공: 실 전사/IPS 로 화면 갱신. 실패: mock 상담(CONSULT_LOG/IPS_DEFAULT)으로 폴백(배지).
 * client_id 는 백엔드가 DB(client.id)로 검증한다 — 등록되지 않은 고객이면 404.
 */

import { ApiError, apiPostForm } from "@/lib/api";
import {
  type ConsultMessage,
  CONSULT_LOG,
  IPS_DEFAULT,
} from "@/lib/mockData";
import { type ApiResult, fallback, live } from "./result";
import type { ConsultationResponse, IpsJson, TranscriptItem } from "./types";

/** STT 처리 타임아웃(ms). 텍스트 API 보다 훨씬 길게. */
const STT_TIMEOUT_MS = 180_000;

/** store.ips 에 적용 가능한 IPS 부분 패치(추출된 값만). */
export interface IpsPatch {
  goal?: string;
  returnPct?: number;
  risk?: "안정형" | "균형형" | "공격형";
  timeYears?: number;
  tax?: string;
  liquidity?: "낮음" | "중간" | "높음";
  legal?: string;
  unique?: string;
}

export interface SttConsultationData {
  consultationId: string;
  transcript: ConsultMessage[];
  ips: IpsPatch;
  transcriptTitle: string;
  consultationDate: string;
}

function mapTranscript(
  items: TranscriptItem[] | null | undefined,
): ConsultMessage[] {
  if (!items) return [];
  return items.map((it) => ({
    // 백엔드 화자값은 "PB"/"고객". 그 외 값이 오면 일단 고객으로 표기.
    speaker: it.speaker_role === "PB" ? "PB" : "고객",
    text: it.text ?? "",
    time: it.utterance_time ?? "",
  }));
}

function toNumber(value: number | string | null): number | undefined {
  if (value === null) return undefined;
  const n = typeof value === "number" ? value : parseFloat(value);
  return Number.isFinite(n) ? n : undefined;
}

function coerceRisk(value: string | null): IpsPatch["risk"] {
  return value === "안정형" || value === "균형형" || value === "공격형"
    ? value
    : undefined;
}

function coerceLiquidity(value: string | null): IpsPatch["liquidity"] {
  return value === "낮음" || value === "중간" || value === "높음"
    ? value
    : undefined;
}

/** flatten IPS JSON → store 적용 가능한 패치(키 매핑 + 타입 정합). */
function mapIps(ips: IpsJson | null | undefined): IpsPatch {
  const patch: IpsPatch = {};
  if (!ips) return patch;
  if (ips.Goal != null) patch.goal = ips.Goal;
  const ret = toNumber(ips.Return);
  if (ret !== undefined) patch.returnPct = ret;
  const risk = coerceRisk(ips.Risk);
  if (risk) patch.risk = risk;
  const time = toNumber(ips.Time);
  if (time !== undefined) patch.timeYears = time;
  if (ips.Tax != null) patch.tax = ips.Tax;
  const liq = coerceLiquidity(ips.Liquidity);
  if (liq) patch.liquidity = liq;
  if (ips.Legal != null) patch.legal = ips.Legal;
  if (ips.Unique != null) patch.unique = ips.Unique;
  return patch;
}

function mockConsultation(): SttConsultationData {
  return {
    consultationId: "",
    transcript: CONSULT_LOG,
    ips: {
      goal: IPS_DEFAULT.goal,
      returnPct: IPS_DEFAULT.returnPct,
      risk: IPS_DEFAULT.risk,
      timeYears: IPS_DEFAULT.timeYears,
      tax: IPS_DEFAULT.tax,
      liquidity: IPS_DEFAULT.liquidity,
      legal: IPS_DEFAULT.legal,
      unique: IPS_DEFAULT.unique,
    },
    transcriptTitle: "데모 상담 기록",
    consultationDate: "",
  };
}

export async function uploadSttConsultation(
  clientId: string | undefined,
  file: File,
): Promise<ApiResult<SttConsultationData>> {
  if (!clientId) {
    return fallback(
      mockConsultation(),
      "DB에 저장된 고객만 STT 처리를 할 수 있습니다. 데모 상담을 표시합니다.",
    );
  }

  const form = new FormData();
  form.append("client_id", clientId);
  form.append("audio_file", file);

  try {
    const res = await apiPostForm<ConsultationResponse>(
      "/consultations/stt",
      form,
      { timeoutMs: STT_TIMEOUT_MS },
    );
    return live({
      consultationId: res.consultation_id,
      transcript: mapTranscript(res.transcript_json),
      ips: mapIps(res.ips_json),
      transcriptTitle: res.transcript_title,
      consultationDate: res.consultation_date,
    });
  } catch (err) {
    let note = "백엔드 연결 실패로 데모 상담을 표시합니다.";
    if (err instanceof ApiError) {
      if (err.isTimeout) note = "STT 처리 시간 초과로 데모 상담을 표시합니다.";
      else if (err.status === 404)
        note = "등록되지 않은 client_id입니다. 데모 상담을 표시합니다.";
      else if (err.status === 400)
        note = "오디오 파일을 처리할 수 없습니다(.wav 확인). 데모 상담을 표시합니다.";
    }
    return fallback(mockConsultation(), note);
  }
}
