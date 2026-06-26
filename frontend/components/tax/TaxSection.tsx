"use client";

import { useState } from "react";
import { ExternalLink, Loader2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import AccountAllocation from "@/components/tax/AccountAllocation";
import TaxGauge from "@/components/tax/TaxGauge";
import TaxWaterfall from "@/components/tax/TaxWaterfall";
import { TAX_ADVICE } from "@/lib/mockData";
import { PRODUCT_LINKS } from "@/lib/productLinks";
import { useDashboardStore } from "@/lib/store";
import type { StressTaxStrategyCard } from "@/lib/api";

// portfolio id → backend kind key
const ID_TO_KIND: Record<string, string> = {
  current: "current",
  a: "A",
  b: "B",
};

// 백엔드 strategy key → 프론트 고정 카피 (spec §4)
type StrategyKey =
  | "isa"
  | "pension_credit"
  | "separate_bond"
  | "low_tax_dividend"
  | "overseas_exemption"
  | "tax_loss";

const STRATEGY_COPY: Record<
  StrategyKey,
  { body: string; tag: string; products: { name: string }[] }
> = {
  isa: TAX_ADVICE.cards[0]!,
  pension_credit: TAX_ADVICE.cards[1]!,
  separate_bond: TAX_ADVICE.cards[2]!,
  low_tax_dividend: TAX_ADVICE.cards[3]!,
  overseas_exemption: TAX_ADVICE.cards[4]!,
  tax_loss: TAX_ADVICE.cards[5]!,
};

/** 중앙 하단: 절세 최적화 시뮬레이터 */
// 백엔드 값이 문자열로 와도 산술 더하기가 문자열 연결로 변질되지 않도록 숫자로 강제
// 변환한다. number 거나 비어있지 않은 string 만 인정하고(빈문자열·boolean·배열이
// Number()로 0/1 둔갑하는 것 차단), 변환 불가(NaN)·그 외는 null 로 떨궈 폴백을 타게 한다.
function toFiniteNumber(v: unknown): number | null {
  if (typeof v !== "number" && (typeof v !== "string" || v.trim() === ""))
    return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export default function TaxSection() {
  const {
    selectedPortfolioId,
    portfolios,
    portfolioSource,
    portfolioNote,
    portfolioTax,
    stressTax,
    taxOptimizer,
    customers,
    selectedCustomerId,
    analyzing,
    isStressMode,
  } = useDashboardStore();

  const customer =
    customers.find((c) => c.id === selectedCustomerId) ?? customers[0];
  const selectedPortfolio = portfolios.find(
    (p) => p.id === selectedPortfolioId,
  );
  const currentPortfolio = portfolios.find((p) => p.id === "current");

  // 선택된 포트폴리오의 tax 데이터 (calculate 응답)
  const selectedKind = ID_TO_KIND[selectedPortfolioId] ?? "current";
  const selectedTax = portfolioTax?.[selectedKind] ?? null;

  // selectedPortfolioId → tax_optimizer 맵 키 (백엔드: current / portfolio_a / portfolio_b)
  const TAX_OPT_KEY: Record<string, string> = {
    current: "current",
    a: "portfolio_a",
    b: "portfolio_b",
  };
  const taxOptEntry = taxOptimizer
    ? (taxOptimizer[TAX_OPT_KEY[selectedPortfolioId] ?? "current"] ??
      taxOptimizer["portfolio_a"] ??
      Object.values(taxOptimizer)[0] ??
      null)
    : null;

  // 절세 화면 소스: 스트레스 모드면 taxOptimizer(포트폴리오별 stressed) 우선, 아니면 calculate 결과
  const taxSource = isStressMode
    ? (taxOptEntry ?? stressTax?.stressed ?? null)
    : taxOptEntry;

  const isLive =
    portfolioSource === "live" && selectedTax != null && taxSource != null;

  // 세후수익률 비교 — 현재 vs 선택 포트폴리오
  const currentAfterTax = currentPortfolio?.metrics.afterTaxReturnPct ?? null;
  const selectedAfterTax = selectedPortfolio?.metrics.afterTaxReturnPct ?? null;

  // 절세 효과 헤드라인: 실시간 추출/최적화 반영된 총 절세 효과 (만원)
  const annualSavingManwon =
    taxSource?.headline.annual_tax_saving != null
      ? Math.round(taxSource.headline.annual_tax_saving / 10000)
      : (selectedTax
          ? Math.round(selectedTax.saved_vs_current / 10000)
          : null);

  // 실효세 절감: taxSource.headline의 세전→세후 실효세 (만원)
  const effectiveTaxBeforeMan =
    taxSource?.headline.tax_amount_before != null
      ? Math.round(taxSource.headline.tax_amount_before / 10000)
      : null;
  const effectiveTaxAfterMan =
    taxSource?.headline.tax_amount_after != null
      ? Math.round(taxSource.headline.tax_amount_after / 10000)
      : null;
  const effectiveTaxDeltaPct =
    effectiveTaxBeforeMan != null &&
    effectiveTaxAfterMan != null &&
    effectiveTaxBeforeMan > 0
      ? ((effectiveTaxAfterMan - effectiveTaxBeforeMan) /
          effectiveTaxBeforeMan) *
        100
      : null;

  // TaxWaterfall에 넘길 waterfallData
  const waterfallData = selectedTax
    ? {
        waterfall: selectedTax.waterfall,
        savingManwon: annualSavingManwon ?? 0,
      }
    : null;

  // 종합과세 게이지: 스트레스 모드면 포트폴리오별 taxOptEntry gauge 우선, 아니면 calculate gauge
  const gaugeData =
    (isStressMode
      ? (taxOptEntry?.financial_income_tax_gauge ??
        stressTax?.stressed?.financial_income_tax_gauge)
      : null) ??
    selectedTax?.gauge ??
    null;

  // 실시간 추출/계산된 계좌 잔여 한도 및 사용액 반영 (IPS 실시간 연동)
  const isaLiveUsed = toFiniteNumber(taxSource?.account_cards?.isa?.used_capacity);
  const isaLiveRemaining = toFiniteNumber(taxSource?.account_cards?.isa?.remaining_capacity);
  const isaUsedManwon = isaLiveUsed != null ? Math.round(isaLiveUsed / 10000) : (customer?.isaUsedManwon ?? null);
  const isaLimitManwon = (isaLiveUsed != null && isaLiveRemaining != null)
    ? Math.round((isaLiveUsed + isaLiveRemaining) / 10000)
    : 2000;

  const irpLiveUsed = toFiniteNumber(taxSource?.account_cards?.irp?.used_capacity);
  const irpLiveRemaining = toFiniteNumber(taxSource?.account_cards?.irp?.remaining_capacity);
  const pensionUsedManwon = irpLiveUsed != null ? Math.round(irpLiveUsed / 10000) : (customer?.pensionUsedManwon ?? null);
  const pensionLimitManwon = (irpLiveUsed != null && irpLiveRemaining != null)
    ? Math.round((irpLiveUsed + irpLiveRemaining) / 10000)
    : 900;

  // 절세 제안 카드: 소스가 있으면 strategy_cards, 없으면 mock
  const liveStrategyCards = taxSource?.strategy_cards ?? null;

  const baseLabel = selectedPortfolio?.name ?? "포트폴리오";

  if (
    portfolioSource === "fallback" &&
    portfolioNote === undefined &&
    !analyzing
  ) {
    return (
      <section>
        <div className="mb-2 px-0.5">
          <h2 className="text-lg font-extrabold">절세 최적화 시뮬레이터</h2>
        </div>
        <div className="flex min-h-[200px] items-center justify-center rounded-2xl border border-dashed border-muted-foreground/20 bg-muted/30">
          <p className="text-[14px] font-semibold text-muted-foreground">
            분석 결과가 존재하지 않습니다
          </p>
        </div>
      </section>
    );
  }

  return (
    <Tabs defaultValue="effect">
      <div className="mb-2 flex items-center justify-between px-0.5">
        <div className="flex items-center gap-2.5">
          <h2 className="text-lg font-extrabold">절세 최적화 시뮬레이터</h2>
          {analyzing ? (
            <div className="flex items-center gap-1.5 rounded-lg bg-muted px-2 py-0.5 text-[10px] font-bold text-muted-foreground">
              <Loader2 className="size-3 animate-spin" />
              분석중...
            </div>
          ) : isLive ? (
            <div className="flex items-center gap-1.5 rounded-lg bg-brand/5 px-2 py-0.5 text-[10px] font-bold text-brand-dark">
              <span className="size-1.5 rounded-full bg-positive shadow-[0_0_0_2px_rgba(22,180,122,0.18)]" />
              연동 완료
            </div>
          ) : null}
        </div>
        <TabsList className="h-auto rounded-lg bg-muted p-0.5">
          <TabsTrigger
            value="effect"
            className="rounded-md px-2.5 py-0.5 text-[12px] font-bold data-[state=active]:bg-white data-[state=active]:text-brand-dark data-[state=active]:shadow-sm"
          >
            절세 효과
          </TabsTrigger>
          <TabsTrigger
            value="threshold"
            className="rounded-md px-2.5 py-0.5 text-[12px] font-bold data-[state=active]:bg-white data-[state=active]:text-brand-dark data-[state=active]:shadow-sm"
          >
            종합과세 임계선
          </TabsTrigger>
          <TabsTrigger
            value="advice"
            className="rounded-md px-2.5 py-0.5 text-[12px] font-bold data-[state=active]:bg-white data-[state=active]:text-brand-dark data-[state=active]:shadow-sm"
          >
            절세 제안
          </TabsTrigger>
        </TabsList>
      </div>

      <Card className="gap-0 p-3">
        {/* 탭 1: 절세 효과 */}
        <TabsContent value="effect" className="flex flex-col gap-2">
          <div className="flex items-center gap-4 rounded-xl border border-brand/20 bg-brand/5 px-3.5 py-3">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="rounded-full border border-brand/20 bg-white px-2 py-0.5 text-[13px] font-bold text-muted-foreground">
                  {baseLabel}
                </span>
              </div>
              {annualSavingManwon != null ? (
                <p
                  className={`mt-1.5 flex items-baseline gap-1.5 text-[13px] font-bold ${annualSavingManwon > 0 ? "text-up" : "text-foreground"}`}
                >
                  연간 절세 효과
                  <b className="text-3xl font-extrabold tabular-nums tracking-tight">
                    {annualSavingManwon > 0 ? "+" : ""}
                    {annualSavingManwon.toLocaleString()}
                  </b>
                  <span className="text-[12px] font-extrabold">만원</span>
                </p>
              ) : (
                <p className="mt-1.5 text-[13px] font-bold text-muted-foreground">
                  분석하기를 실행하면 실제 절세 효과를 계산합니다
                </p>
              )}
              {selectedTax?.summary && (
                <p className="mt-1 text-[13px] font-semibold text-muted-foreground">
                  {selectedTax.summary}
                </p>
              )}
            </div>
            {currentAfterTax != null && selectedAfterTax != null && (
              <>
                <SummaryStat
                  k="세후 수익률"
                  v={`${currentAfterTax.toFixed(1)}% → ${selectedAfterTax.toFixed(1)}%`}
                  d={`${selectedAfterTax - currentAfterTax > 0 ? "+" : ""}${(selectedAfterTax - currentAfterTax).toFixed(1)}%p`}
                  delta={selectedAfterTax - currentAfterTax}
                />
                {effectiveTaxBeforeMan != null &&
                effectiveTaxAfterMan != null ? (
                  <SummaryStat
                    k="실효세 절감"
                    v={`${effectiveTaxBeforeMan.toLocaleString()} → ${effectiveTaxAfterMan.toLocaleString()}만`}
                    d={
                      effectiveTaxDeltaPct != null
                        ? `${effectiveTaxDeltaPct >= 0 ? "+" : ""}${effectiveTaxDeltaPct.toFixed(1)}%`
                        : ""
                    }
                    delta={effectiveTaxDeltaPct ?? undefined}
                  />
                ) : annualSavingManwon != null ? (
                  <SummaryStat
                    k="절세 효과"
                    v={`${annualSavingManwon.toLocaleString()}만원`}
                    d="vs 현재 포트폴리오"
                  />
                ) : null}
              </>
            )}
          </div>

          <div className="grid grid-cols-2 items-start gap-4">
            <TaxWaterfall
              waterfallData={isStressMode ? null : waterfallData}
              liveHeadline={isStressMode ? (taxSource?.headline ?? null) : null}
              liveAumEokwon={customer?.aumEokwon}
            />
            <AccountAllocation
              accounts={[
                {
                  key: "isa",
                  usedManwon: isaUsedManwon,
                  limitManwon: isaLimitManwon,
                },
                {
                  key: "pension",
                  usedManwon: pensionUsedManwon,
                  limitManwon: pensionLimitManwon,
                },
              ]}
            />
          </div>
        </TabsContent>

        {/* 탭 2: 종합과세 임계선 */}
        <TabsContent value="threshold">
          <TaxGauge gaugeData={gaugeData} portfolioLabel={baseLabel} />
        </TabsContent>

        {/* 탭 3: 절세 제안 */}
        <TabsContent value="advice">
          <AdviceCards
            liveCards={liveStrategyCards?.cards ?? null}
            totalManwon={liveStrategyCards?.combined_total_manwon ?? null}
          />
        </TabsContent>
      </Card>
    </Tabs>
  );
}

type AdviceTab = "제안설명" | "상품추천";

interface AdviceCardsProps {
  liveCards: StressTaxStrategyCard[] | null;
  totalManwon: number | null;
}

function AdviceCards({ liveCards, totalManwon }: AdviceCardsProps) {
  const [tabs, setTabs] = useState<Record<string, AdviceTab>>({});

  const cards = liveCards
    ? [...liveCards]
        .sort((a, b) => a.priority_rank - b.priority_rank)
        .map((lc) => {
          const copy = STRATEGY_COPY[lc.key as StrategyKey];
          // 백엔드가 계산한 이전/납입 가능 금액(이미 만원 단위로 반환됨)
          const transferManwon = lc.transferableManwon ?? null;

          // ISA·연금 카드는 잔여 한도를 동적으로 표시
          let body = copy?.body ?? "";
          if (lc.key === "isa" && transferManwon != null) {
            body = `이자·배당 자산 ${transferManwon.toLocaleString()}만원을 ISA 잔여 한도로 이전 — 비과세 200만 + 초과분 9.9% 분리과세, 종합과세 합산 제외.`;
          } else if (lc.key === "pension_credit" && transferManwon != null) {
            body = `연금저축+IRP 잔여 한도 ${transferManwon.toLocaleString()}만원 납입 시 13.2% 세액공제 — 만 55세 이후 연금 수령.`;
          }

          return {
            title: lc.title,
            body,
            tag: copy?.tag ?? "",
            saving:
              lc.applicable && lc.combined_contribution_manwon > 0
                ? `+${lc.combined_contribution_manwon.toLocaleString()}만원`
                : "",
            products: copy?.products ?? [],
            applicable: lc.applicable,
          };
        })
    : TAX_ADVICE.cards.map((c) => ({ ...c, applicable: true }));

  const totalSaving =
    totalManwon != null
      ? `+${totalManwon.toLocaleString()}만원`
      : TAX_ADVICE.totalSaving;

  return (
    <>
      <div className="max-h-[520px] overflow-y-auto">
        <div className="grid grid-cols-2 gap-3">
          {cards.map((card) => {
            const active = tabs[card.title] ?? "제안설명";
            return (
              <div
                key={card.title}
                className={`flex flex-col rounded-xl border p-2.5 ${!card.applicable ? "opacity-50" : ""}`}
              >
                <div className="mb-1.5 flex items-center gap-1.5">
                  <span className="flex-1 text-[13px] font-extrabold leading-tight">
                    {card.title}
                  </span>
                  <div className="flex shrink-0 rounded-md bg-muted p-0.5">
                    {(["제안설명", "상품추천"] as AdviceTab[]).map((t) => (
                      <button
                        key={t}
                        type="button"
                        onClick={() =>
                          setTabs((prev) => ({ ...prev, [card.title]: t }))
                        }
                        className={`rounded-sm px-1.5 py-0.5 text-[10px] font-bold transition-colors ${
                          active === t
                            ? "bg-white text-brand-dark shadow-sm"
                            : "text-muted-foreground"
                        }`}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                </div>

                {active === "제안설명" ? (
                  <div className="flex h-[108px] flex-col overflow-y-auto pr-0.5">
                    <p className="pt-1.5 text-[13px] font-semibold leading-snug text-muted-foreground">
                      {card.body}
                    </p>
                    <div className="mt-auto pt-1">
                      <p className="text-[13px] font-bold text-muted-foreground/60">
                        {card.tag}
                      </p>
                      {card.saving && (
                        <p className="text-[13px] font-extrabold tabular-nums text-up">
                          {card.saving}
                        </p>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="h-[108px] overflow-y-auto pr-0.5">
                    <div className="flex flex-col gap-1.5">
                      {card.products.map((p) => {
                        const url = PRODUCT_LINKS[p.name] ?? "";
                        return (
                          <button
                            key={p.name}
                            type="button"
                            disabled={!url}
                            onClick={() =>
                              url &&
                              window.open(url, "_blank", "noopener,noreferrer")
                            }
                            className={`flex items-center gap-1.5 rounded-lg bg-brand/5 px-2 py-1.5 text-left transition-colors ${
                              url
                                ? "cursor-pointer hover:bg-brand/10"
                                : "cursor-default opacity-50"
                            }`}
                          >
                            <ExternalLink className="size-3 shrink-0 text-brand" />
                            <span className="text-[12px] font-extrabold text-brand-dark">
                              {p.name}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
      <div className="mt-2 flex items-center justify-between rounded-xl bg-brand/10 px-3 py-2">
        <span className="text-[13px] font-bold text-brand-dark">
          {TAX_ADVICE.totalLabel}
        </span>
        <span className="text-[13px] font-extrabold tabular-nums text-brand-dark">
          {totalSaving}
        </span>
      </div>
    </>
  );
}

function SummaryStat({
  k,
  v,
  d,
  delta,
}: {
  k: string;
  v: string;
  d: string;
  delta?: number;
}) {
  const dCls =
    delta === undefined || delta > 0
      ? "text-up"
      : delta < 0
        ? "text-down"
        : "text-foreground";
  return (
    <div className="min-w-29.5 rounded-xl border bg-white px-3 py-2">
      <p className="text-[13px] font-bold text-muted-foreground">{k}</p>
      <p className="mt-1 text-[13px] font-extrabold tabular-nums">{v}</p>
      <p className={`mt-0.5 text-[13px] font-extrabold tabular-nums ${dCls}`}>
        {d}
      </p>
    </div>
  );
}
