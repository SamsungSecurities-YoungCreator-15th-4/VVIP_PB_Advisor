/**
 * RAG 인사이트 연동 — POST /rag/insight.
 *
 * 성공: 실 answer + citations(감사추적: 출처·유사도·발췌·시점).
 * 404 : 관련 문서 없음 → empty(데이터 없음, 폴백 아님).
 * 실패: mock INSIGHT 로 폴백(배지 표시). 가짜를 실데이터인 척 두지 않는다.
 */

import { ApiError, apiPost } from "@/lib/api";
import { INSIGHT } from "@/lib/mockData";
import { NIL_UUID } from "./constants";
import { type ApiResult, empty, fallback, live } from "./result";
import type { RagInsightRequest, RagInsightResponse } from "./types";

export interface InsightCitation {
  title: string;
  date: string | null; // published_date 또는 "실시간" 등
  sourceType?: string;
  similarity?: number | null;
  chunk?: string;
}

export interface InsightData {
  answer: string;
  summary: string;
  citations: InsightCitation[];
  asOf?: string; // ISO datetime
}

/** mock INSIGHT → UI 데이터(폴백 표시용). */
function mockInsight(): InsightData {
  return {
    answer: INSIGHT.defaultAnswer,
    summary: INSIGHT.defaultAnswer.split("\n\n")[0] ?? INSIGHT.defaultAnswer,
    citations: INSIGHT.sources.map((s) => ({ title: s.title, date: s.date })),
  };
}

function mapResponse(res: RagInsightResponse): InsightData {
  return {
    answer: res.answer ?? "",
    summary: res.summary ?? "",
    citations: (res.citations ?? []).map((c) => ({
      title: c.title ?? "",
      date: c.published_date ?? null,
      sourceType: c.source_type,
      similarity: c.similarity,
      chunk: c.chunk,
    })),
    asOf: res.as_of,
  };
}

export interface FetchInsightOptions {
  consultationId?: string;
  riskProfile?: string | null;
  selectedPortfolio?: string | null;
  dashboard?: Record<string, unknown> | null;
}

export async function fetchRagInsight(
  query: string,
  options: FetchInsightOptions = {},
): Promise<ApiResult<InsightData>> {
  const body: RagInsightRequest = {
    // consultation_id 는 백엔드 필수(UUID)이나 존재검증은 라우터 TODO 상태.
    // STT 로 확보한 실 consultation_id 가 있으면 그것을, 없으면 placeholder 를 보낸다.
    consultation_id: options.consultationId || NIL_UUID,
    query,
    context: {
      risk_profile: options.riskProfile ?? null,
      selected_portfolio: options.selectedPortfolio ?? null,
      dashboard: options.dashboard ?? null,
    },
  };

  try {
    const res = await apiPost<RagInsightResponse>("/rag/insight", body);
    return live(mapResponse(res));
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      // 임계값 미달 — 정상 빈결과. 폴백(mock)이 아니라 "관련 문서 없음".
      return empty<InsightData>(
        { answer: "", summary: "", citations: [] },
        "관련 문서를 찾지 못했습니다(유사도 임계값 미달).",
      );
    }
    const note =
      err instanceof ApiError && err.isTimeout
        ? "응답 시간 초과로 데모 데이터를 표시합니다."
        : "백엔드 연결 실패로 데모 데이터를 표시합니다.";
    return fallback(mockInsight(), note);
  }
}
