/**
 * PDF 절세 섹션용 어댑터 — store의 live 절세 데이터(taxOptimizer = calculate의 tax_optimizer)를
 * 기존 mock(TAX_EFFECT / TAX_ADVICE)과 "동일한 shape"으로 변환한다.
 *
 * 목적: PDF 템플릿(PbPdf·ClientPdf)의 절세 JSX를 그대로 두고 데이터 소스만 교체하기 위함.
 *   - TAX_EFFECT  → buildPdfTaxEffect(taxOptimizer)
 *   - TAX_ADVICE  → buildPdfTaxAdvice(taxOptimizer)
 * live 데이터가 없으면(미분석·데모 폴백) 각 필드를 mock 값으로 폴백한다.
 *
 * 주의(추적성): live로 연결되는 값은 모두 calculate 응답(tax_optimizer)의 실제 수치다.
 *   - headline → 연간 절세액·세후수익률·실효세
 *   - strategy_cards → 절세 제안 6카드(제목·절감액·적용여부). 카피(body/tag/products)는 mock 출처 유지.
 *   - account_cards → 계좌 활용도(used/limit). 캡션 문구는 mock 유지.
 *   - flow(세금 흐름 3행 표)는 calculate에 3분할 소스가 없어 mock 유지 — 백엔드 분할 노출 후 연결 예정(TODO).
 */
import { TAX_ADVICE, TAX_EFFECT } from "@/lib/mockData";
import type { StressTaxData } from "@/lib/api/types";

// strategy_cards.key → mock TAX_ADVICE.cards 인덱스(카피·상품 출처).
const ADVICE_KEY_ORDER = [
  "isa",
  "pension_credit",
  "separate_bond",
  "low_tax_dividend",
  "overseas_exemption",
  "tax_loss",
] as const;

const wonToManwon = (won: number | null | undefined): number | null =>
  won == null ? null : Math.round(won / 10000);

const pct = (ratio: number): string => `${(ratio * 100).toFixed(1)}%`;

// 계좌 활용도 항목 — mock은 used/limit이 number 또는 null 유니온이라, 둘을 포괄하는 느슨한 타입으로 둔다.
type PdfTaxAccount = {
  name: string;
  tag: string;
  used: number | null;
  limit: number | null;
  caption: string;
};
type PdfTaxEffect = Omit<typeof TAX_EFFECT, "accounts"> & {
  accounts: PdfTaxAccount[];
};

/** 계좌 활용도 — live used/limit(만원)만 override, 캡션·태그·이름은 mock 유지. */
function buildAccounts(tax: StressTaxData): PdfTaxAccount[] {
  const ac = tax.account_cards;
  if (!ac) return TAX_EFFECT.accounts;

  // mock accounts 순서: [0] ISA, [1] 연금저축+IRP, [2] 일반계좌
  const liveByIndex = [ac.isa, ac.irp, ac.taxable_account];

  return TAX_EFFECT.accounts.map((acct, i) => {
    const live = liveByIndex[i];
    if (!live) return acct;
    const used = wonToManwon(live.used_capacity);
    const remaining = wonToManwon(live.remaining_capacity);
    const limit = used != null && remaining != null ? used + remaining : acct.limit;
    return {
      ...acct,
      used: used ?? acct.used,
      limit,
    };
  });
}

/** TAX_EFFECT(절세 효과) shape으로 변환. live 없으면 mock 그대로. */
export function buildPdfTaxEffect(
  taxOptimizer: StressTaxData | null,
): PdfTaxEffect {
  if (!taxOptimizer) return TAX_EFFECT;
  const h = taxOptimizer.headline;

  const beforeMan = wonToManwon(h.tax_amount_before) ?? 0;
  const afterMan = wonToManwon(h.tax_amount_after) ?? 0;
  const effectiveDeltaPct =
    beforeMan > 0 ? ((afterMan - beforeMan) / beforeMan) * 100 : 0;
  const improvementP = h.after_tax_return_improvement_p ?? 0;

  return {
    ...TAX_EFFECT, // baseLabel·subNote·flow(세금 흐름 표)는 mock 유지(TODO: flow 백엔드 분할 후 연결)
    annualSavingManwon: wonToManwon(h.annual_tax_saving) ?? TAX_EFFECT.annualSavingManwon,
    afterTaxReturn: {
      from: pct(h.after_tax_return_before),
      to: pct(h.after_tax_return_after),
      delta: `${improvementP >= 0 ? "+" : ""}${(improvementP * 100).toFixed(1)}%p`,
    },
    effectiveTax: {
      from: beforeMan.toLocaleString(),
      to: `${afterMan.toLocaleString()}만`,
      delta: `${effectiveDeltaPct >= 0 ? "+" : ""}${effectiveDeltaPct.toFixed(1)}%`,
    },
    accounts: buildAccounts(taxOptimizer),
  };
}

/** TAX_ADVICE(절세 제안) shape으로 변환. live 카드 제목·절감액·적용여부 override, 카피·상품은 mock 유지. */
export function buildPdfTaxAdvice(
  taxOptimizer: StressTaxData | null,
): typeof TAX_ADVICE {
  const live = taxOptimizer?.strategy_cards;
  if (!live?.cards?.length) return TAX_ADVICE;

  const cards = [...live.cards]
    .sort((a, b) => a.priority_rank - b.priority_rank)
    .map((lc) => {
      const idx = ADVICE_KEY_ORDER.indexOf(lc.key as (typeof ADVICE_KEY_ORDER)[number]);
      const base = TAX_ADVICE.cards[idx] ?? TAX_ADVICE.cards[0]!;
      const saving =
        lc.applicable && lc.combined_contribution_manwon > 0
          ? `+${lc.combined_contribution_manwon.toLocaleString()}만원`
          : "";
      return {
        ...base, // icon·body·tag·products(카피·상품 출처)는 mock 유지
        title: lc.title || base.title,
        saving,
      };
    });

  return {
    ...TAX_ADVICE,
    cards,
    totalSaving: `+${(live.combined_total_manwon ?? 0).toLocaleString()}만원`,
  };
}
