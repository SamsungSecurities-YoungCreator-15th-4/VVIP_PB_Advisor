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
const STRATEGY_KEY_ORDER = [
  "isa",
  "pension_credit",
  "separate_bond",
  "low_tax_dividend",
  "overseas_exemption",
  "tax_loss",
] as const;
type StrategyKey = (typeof STRATEGY_KEY_ORDER)[number];

const STRATEGY_COPY: Record<
  StrategyKey,
  { body: string; tag: string; products: { name: string }[] }
> = {
  isa:                TAX_ADVICE.cards[0]!,
  pension_credit:     TAX_ADVICE.cards[1]!,
  separate_bond:      TAX_ADVICE.cards[2]!,
  low_tax_dividend:   TAX_ADVICE.cards[3]!,
  overseas_exemption: TAX_ADVICE.cards[4]!,
  tax_loss:           TAX_ADVICE.cards[5]!,
};

/** 중앙 하단: 절세 최적화 시뮬레이터 */
export default function TaxSection() {
  const {
    selectedPortfolioId,
    portfolios,
    portfolioSource,
    portfolioTax,
    stressTax,
    customers,
    selectedCustomerId,
    analyzing,
  } = useDashboardStore();

  const customer = customers.find((c) => c.id === selectedCustomerId) ?? customers[0];
  const selectedPortfolio = portfolios.find((p) => p.id === selectedPortfolioId);
  const currentPortfolio  = portfolios.find((p) => p.id === "current");

  // 선택된 포트폴리오의 tax 데이터 (calculate 응답)
  const selectedKind = ID_TO_KIND[selectedPortfolioId] ?? "current";
  const selectedTax  = portfolioTax?.[selectedKind] ?? null;
  const isLive = portfolioSource === "live" && selectedTax != null;

  // 세후수익률 비교 — 현재 vs 선택 포트폴리오
  const currentAfterTax  = currentPortfolio?.metrics.afterTaxReturnPct ?? null;
  const selectedAfterTax = selectedPortfolio?.metrics.afterTaxReturnPct ?? null;

  // 절세 효과 헤드라인
  const annualSavingManwon = selectedTax
    ? Math.round(selectedTax.saved_vs_current / 10000)
    : null;

  // TaxWaterfall에 넘길 waterfallData
  const waterfallData = selectedTax
    ? { waterfall: selectedTax.waterfall, savingManwon: annualSavingManwon ?? 0 }
    : null;

  // 스트레스 모드의 게이지 데이터 (있을 때만)
  const gaugeData = stressTax?.stressed.financial_income_tax_gauge ?? null;

  // 절세 제안 카드: stressTax가 있으면 strategy_cards, 없으면 mock
  const liveStrategyCards = stressTax?.stressed.strategy_cards ?? null;

  const baseLabel = selectedPortfolio?.name ?? "포트폴리오";

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
          ) : (
            <div className="flex items-center gap-1.5 rounded-lg bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700">
              ⚠ 데모
            </div>
          )}
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
                <p className={`mt-1.5 flex items-baseline gap-1.5 text-[13px] font-bold ${annualSavingManwon > 0 ? "text-up" : "text-foreground"}`}>
                  연간 절세 효과
                  <b className="text-3xl font-extrabold tabular-nums tracking-tight">
                    {annualSavingManwon > 0 ? "+" : ""}{annualSavingManwon.toLocaleString()}
                  </b>
                  <span className="text-[12px] font-extrabold">만원</span>
                </p>
              ) : (
                <p className="mt-1.5 text-[13px] font-bold text-muted-foreground">
                  분析하기를 실행하면 실제 절세 효과를 계산합니다
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
                  d={`${(selectedAfterTax - currentAfterTax) > 0 ? "+" : ""}${(selectedAfterTax - currentAfterTax).toFixed(1)}%p`}
                  delta={selectedAfterTax - currentAfterTax}
                />
                {annualSavingManwon != null && (
                  <SummaryStat
                    k="절세 효과"
                    v={`${annualSavingManwon.toLocaleString()}만원`}
                    d={`vs 현재 포트폴리오`}
                  />
                )}
              </>
            )}
          </div>

          <div className="grid grid-cols-2 items-start gap-4">
            <TaxWaterfall
              waterfallData={waterfallData}
              liveAumEokwon={customer?.aumEokwon}
            />
            <AccountAllocation />
          </div>
        </TabsContent>

        {/* 탭 2: 종합과세 임계선 */}
        <TabsContent value="threshold">
          <TaxGauge gaugeData={gaugeData} />
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
          return {
            title: lc.title,
            body: copy?.body ?? "",
            tag: copy?.tag ?? "",
            saving: lc.applicable && lc.combined_contribution_manwon > 0
              ? `+${lc.combined_contribution_manwon.toLocaleString()}만원`
              : "",
            products: copy?.products ?? [],
            applicable: lc.applicable,
          };
        })
    : TAX_ADVICE.cards.map((c) => ({ ...c, applicable: true }));

  const totalSaving = totalManwon != null
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
                        onClick={() => setTabs((prev) => ({ ...prev, [card.title]: t }))}
                        className={`rounded-sm px-1.5 py-0.5 text-[10px] font-bold transition-colors ${
                          active === t ? "bg-white text-brand-dark shadow-sm" : "text-muted-foreground"
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
                      <p className="text-[13px] font-bold text-muted-foreground/60">{card.tag}</p>
                      {card.saving && (
                        <p className="text-[13px] font-extrabold tabular-nums text-up">{card.saving}</p>
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
                            onClick={() => url && window.open(url, "_blank", "noopener,noreferrer")}
                            className={`flex items-center gap-1.5 rounded-lg bg-brand/5 px-2 py-1.5 text-left transition-colors ${
                              url ? "cursor-pointer hover:bg-brand/10" : "cursor-default opacity-50"
                            }`}
                          >
                            <ExternalLink className="size-3 shrink-0 text-brand" />
                            <span className="text-[12px] font-extrabold text-brand-dark">{p.name}</span>
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
        <span className="text-[13px] font-bold text-brand-dark">{TAX_ADVICE.totalLabel}</span>
        <span className="text-[13px] font-extrabold tabular-nums text-brand-dark">{totalSaving}</span>
      </div>
    </>
  );
}

function SummaryStat({ k, v, d, delta }: { k: string; v: string; d: string; delta?: number }) {
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
      <p className={`mt-0.5 text-[13px] font-extrabold tabular-nums ${dCls}`}>{d}</p>
    </div>
  );
}
