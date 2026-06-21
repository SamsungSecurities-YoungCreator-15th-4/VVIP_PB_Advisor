/**
 * 절세 요약 연동 — POST /tax/insight.
 *
 * ⚠️ 방향(준호님 확정): "계산은 #30 로직, AI 는 요약만". 이 엔드포인트는 tax_result(계산 결과)
 * 를 받아 LLM 이 PB 설명조로 요약만 한다.
 * ⚠️ #30(절세 계산) 미머지 상태라 입력 tax_result 숫자는 아직 mock(TAX_EFFECT)이다.
 *    따라서 요약문은 실 LLM 출력이지만 그 근거 숫자는 임시값 — UI 에 출처를 명시한다.
 *    #30 머지 시 buildTaxResultFromMock 을 실 계산 출력으로 교체한다.
 *
 * 실패: 클라이언트 폴백 요약(배지 표시).
 */

import { ApiError, apiPost } from "@/lib/api";
import { TAX_EFFECT } from "@/lib/mockData";
import { NIL_UUID } from "./constants";
import { type ApiResult, fallback, live } from "./result";
import type {
  TaxCalculationResult,
  TaxInsightRequest,
  TaxInsightResponse,
} from "./types";

export interface TaxInsightData {
  summary: string;
  asOf?: string;
}

/** "5.5%" → 0.055 (비율). 파싱 불가 시 null. */
function parsePercentToRatio(label: string): number | null {
  const n = parseFloat(label.replace(/[^0-9.\-]/g, ""));
  return Number.isFinite(n) ? n / 100 : null;
}

/** "1,620" / "540만" (만원 표기) → 원 단위. 파싱 불가 시 null. */
function parseManwonToWon(label: string): number | null {
  const n = parseFloat(label.replace(/[^0-9.\-]/g, ""));
  return Number.isFinite(n) ? n * 10_000 : null;
}

/**
 * mock TAX_EFFECT → 백엔드 tax_result 형태. (#30 머지 전 임시.)
 * 숫자 변환은 표시단위→백엔드단위 환산일 뿐, 새 값을 만들지 않는다.
 */
export function buildTaxResultFromMock(
  portfolioName: string,
  totalAssetEokwon: number,
): TaxCalculationResult {
  return {
    portfolio_name: portfolioName,
    total_asset: totalAssetEokwon * 100_000_000, // 억원 → 원
    headline: {
      annual_tax_saving: TAX_EFFECT.annualSavingManwon * 10_000, // 만원 → 원
      after_tax_return_before: parsePercentToRatio(TAX_EFFECT.afterTaxReturn.from),
      after_tax_return_after: parsePercentToRatio(TAX_EFFECT.afterTaxReturn.to),
      tax_amount_before: parseManwonToWon(TAX_EFFECT.effectiveTax.from),
      tax_amount_after: parseManwonToWon(TAX_EFFECT.effectiveTax.to),
    },
    notes: [TAX_EFFECT.subNote],
  };
}

/** 호출 실패 시 클라이언트 폴백 요약(숫자는 mock 그대로, 생성/변형 없음). */
function fallbackSummary(name: string): string {
  return [
    `[절세 요약(데모) · ${name}]`,
    `- 전략 적용 시 연간 약 ${TAX_EFFECT.annualSavingManwon.toLocaleString()}만원의 세금 절감이 추정됩니다.`,
    `- 세후수익률(추정): ${TAX_EFFECT.afterTaxReturn.from} → ${TAX_EFFECT.afterTaxReturn.to}`,
    "※ 백엔드 연결 실패로 데모 데이터를 표시합니다. 수치는 임시 추정값입니다.",
  ].join("\n");
}

export async function fetchTaxInsight(
  taxResult: TaxCalculationResult,
  consultationId?: string,
): Promise<ApiResult<TaxInsightData>> {
  const body: TaxInsightRequest = {
    consultation_id: consultationId || NIL_UUID,
    tax_result: taxResult,
  };
  try {
    const res = await apiPost<TaxInsightResponse>("/tax/insight", body);
    return live({ summary: res.summary, asOf: res.as_of });
  } catch (err) {
    const note =
      err instanceof ApiError && err.isTimeout
        ? "응답 시간 초과로 데모 요약을 표시합니다."
        : "백엔드 연결 실패로 데모 요약을 표시합니다.";
    return fallback(
      { summary: fallbackSummary(taxResult.portfolio_name ?? "선택 포트폴리오") },
      note,
    );
  }
}
