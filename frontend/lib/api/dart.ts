/**
 * DART 재무 인사이트 연동 — POST /dart/insight.
 *
 * AI 인사이트 검색이 "<회사명> 재무제표/실적/매출…"처럼 기업 재무를 묻는 질의면
 * RAG(/rag/insight) 대신 이 엔드포인트로 라우팅한다(RAG 코퍼스엔 재무제표가 없음).
 * 수치는 DART 전자공시 원문에서 그대로 가져오고(접수번호로 감사추적), LLM 은 요약·
 * 해설만 한다. 결과는 RAG 와 동일한 InsightData 모양으로 매핑해 같은 UI 가 렌더한다.
 */

import { ApiError, apiPost } from "@/lib/api";
import { type ApiResult, empty, live } from "./result";
import type { InsightCitation, InsightData } from "./rag";
import type { DartInsightRequest, DartInsightResponse } from "./types";

// 기업 재무 의도를 나타내는 키워드. 하나라도 포함되면 DART 라우팅 후보다.
// (오탐을 줄이려 'V자산'·'V자본' 같은 단어 일부가 아니라 구체 항목명만 둔다.)
const FINANCIAL_KEYWORDS = [
  "재무제표",
  "재무상태",
  "재무",
  "실적",
  "매출",
  "영업이익",
  "순이익",
  "당기순이익",
  "총자산",
  "총부채",
  "자기자본",
  "손익",
];

// 회사명 후보 추출 시 제거할 군말(재무 키워드 + 흔한 요청 표현).
// 한 글자 조사(은/는/이/가…)는 회사명 중간 음절을 깨뜨릴 수 있어 전역 제거하지 않고,
// 아래 TRAILING_JOSA 로 '문자열 끝'에서만 떼어낸다.
const NOISE_PATTERN =
  /재무제표|재무상태표?|재무|실적|매출액?|영업이익|당기순이익|순이익|총자산|총부채|자기자본|자본총계|손익계산서?|손익|에\s*대해서?|관련(?:해서)?|알려\s*줘|보여\s*줘|분석(?:해\s*줘)?|요약(?:해\s*줘)?|궁금(?:해|합니다)?|좀|어때/g;

const TRAILING_JOSA = /(?:의|은|는|이|가|을|를|에|에서)\s*$/;

/** 질의가 기업 재무 의도면 회사명 후보를 담아 반환하고, 아니면 null. */
export function detectFinancialQuery(
  query: string,
): { corpName: string } | null {
  const q = query.trim();
  if (!FINANCIAL_KEYWORDS.some((k) => q.includes(k))) return null;
  const corpName = q
    .replace(NOISE_PATTERN, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(TRAILING_JOSA, "")
    .trim();
  return { corpName };
}

function formatWon(v: number | null | undefined): string {
  return v == null ? "제공되지 않음" : `${v.toLocaleString("ko-KR")}원`;
}

function mapResponse(res: DartInsightResponse): InsightData {
  const fin = res.financials;
  const src = res.source;

  let answer = res.summary ?? "";
  if (fin && src) {
    const rows = [
      `[주요 재무 · ${src.bsns_year}년 ${src.fs_label} · 단위 ${src.currency}]`,
      `매출액: ${formatWon(fin.revenue)}`,
      `영업이익: ${formatWon(fin.operating_income)}`,
      `당기순이익: ${formatWon(fin.net_income)}`,
      `총자산: ${formatWon(fin.total_assets)}`,
      `총부채: ${formatWon(fin.total_liabilities)}`,
      `총자본: ${formatWon(fin.total_equity)}`,
    ];
    answer = `${res.summary}\n\n${rows.join("\n")}`;
  }

  const citations: InsightCitation[] =
    src != null
      ? [
          {
            title: `DART 전자공시 · ${res.corp_name ?? ""} ${src.bsns_year}년 ${src.fs_label} (접수번호 ${src.rcept_no})`,
            date: String(src.bsns_year),
            sourceType: "dart",
          },
        ]
      : [];

  return {
    answer,
    summary:
      fin && src
        ? `${res.corp_name ?? ""} ${src.bsns_year}년 ${src.fs_label} 재무 요약`
        : (res.summary ?? ""),
    citations,
    asOf: res.as_of,
  };
}

/** 회사명으로 DART 재무 인사이트를 조회한다. 가짜 수치는 절대 만들지 않는다. */
export async function fetchDartInsight(
  corpName: string,
): Promise<ApiResult<InsightData>> {
  const name = corpName.trim();
  if (!name) {
    return empty<InsightData>(
      { answer: "", summary: "", citations: [] },
      "회사명을 함께 입력해 주세요. 예: 삼성전자 재무제표",
    );
  }

  const body: DartInsightRequest = { corp_name: name };
  try {
    const res = await apiPost<DartInsightResponse>("/dart/insight", body);
    // 재무를 못 찾은 정상 응답(상장폐지·중복매칭·미발견)은 empty 로 사유를 명시한다.
    if (!res.financials || !res.source) {
      return empty<InsightData>(
        { answer: res.summary ?? "", summary: "", citations: [] },
        res.resolve_reason || `${name} 의 재무 정보를 찾지 못했습니다.`,
      );
    }
    return live(mapResponse(res));
  } catch (err) {
    // 실패 시 가짜 재무를 보여주면 안 되므로(금융 도메인 원칙) empty + 사유로 끝낸다.
    const note =
      err instanceof ApiError && err.status === 404
        ? `${name} 의 확정 사업보고서 재무를 찾지 못했습니다.`
        : err instanceof ApiError && err.isTimeout
          ? "DART 응답 시간 초과로 재무를 표시하지 못했습니다."
          : "DART 연결 실패로 재무를 표시하지 못했습니다.";
    return empty<InsightData>({ answer: "", summary: "", citations: [] }, note);
  }
}
