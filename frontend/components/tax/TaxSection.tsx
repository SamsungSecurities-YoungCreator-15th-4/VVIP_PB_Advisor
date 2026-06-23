"use client";

import { useState } from "react";
import { ExternalLink } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import AccountAllocation from "@/components/tax/AccountAllocation";
import TaxGauge from "@/components/tax/TaxGauge";
import TaxWaterfall from "@/components/tax/TaxWaterfall";
import { PORTFOLIOS, TAX_ADVICE, TAX_EFFECT } from "@/lib/mockData";
import { PRODUCT_LINKS } from "@/lib/productLinks";
import { useDashboardStore } from "@/lib/store";

/** 중앙 하단: 절세 최적화 시뮬레이터 (절세 효과 / 종합과세 임계선 / 절세 제안) */
export default function TaxSection() {
  const { selectedPortfolioId, selectedCustomerId, customers } =
    useDashboardStore();
  const portfolio = PORTFOLIOS.find((p) => p.id === selectedPortfolioId);
  const customer =
    customers.find((c) => c.id === selectedCustomerId) ?? customers[0];
  const baseLabel = `${portfolio?.name ?? "포트폴리오 A"}`;

  return (
    <Tabs defaultValue="effect">
      <div className="mb-2 flex items-center justify-between px-0.5">
        <h2 className="text-lg font-extrabold">절세 최적화 시뮬레이터</h2>
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
              <div className="flex items-center gap-2 text-[13px] font-extrabold">
                <span className="rounded-full border border-brand/20 bg-white px-2 py-0.5 text-[13px] font-bold text-muted-foreground">
                  {baseLabel}
                </span>
              </div>
              <p className="mt-1.5 flex items-baseline gap-1.5 text-[13px] font-bold text-up">
                연간 절세 효과
                <b className="text-3xl font-extrabold tabular-nums tracking-tight">
                  +{TAX_EFFECT.annualSavingManwon.toLocaleString()}
                </b>
                <span className="text-[12px] font-extrabold">만원</span>
              </p>
              <p className="mt-1 text-[13px] font-semibold text-muted-foreground">
                {TAX_EFFECT.subNote}
              </p>
            </div>
            <SummaryStat
              k="세후 수익률"
              v={`${TAX_EFFECT.afterTaxReturn.from} → ${TAX_EFFECT.afterTaxReturn.to}`}
              d={TAX_EFFECT.afterTaxReturn.delta}
            />
            <SummaryStat
              k="실효세 절감"
              v={`${TAX_EFFECT.effectiveTax.from} → ${TAX_EFFECT.effectiveTax.to}`}
              d={TAX_EFFECT.effectiveTax.delta}
            />
          </div>

          <div className="grid grid-cols-2 items-start gap-4">
            <TaxWaterfall portfolioName={baseLabel} />
            <AccountAllocation />
          </div>
        </TabsContent>

        {/* 탭 2: 종합과세 임계선 */}
        <TabsContent value="threshold">
          <TaxGauge />
        </TabsContent>

        {/* 탭 3: 절세 제안 */}
        <TabsContent value="advice">
          <AdviceCards />
        </TabsContent>
      </Card>
    </Tabs>
  );
}

type AdviceTab = "제안설명" | "상품추천";

function AdviceCards() {
  const [tabs, setTabs] = useState<Record<string, AdviceTab>>({});

  return (
    <>
      <div className="max-h-[520px] overflow-y-auto">
        <div className="grid grid-cols-2 gap-3">
        {TAX_ADVICE.cards.map((card) => {
          const active = tabs[card.title] ?? "제안설명";
          return (
            <div
              key={card.title}
              className="flex flex-col rounded-xl border p-2.5"
            >
              {/* 헤더: 제목 + 세그먼트 */}
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

              {/* 콘텐츠 — 두 탭 모두 h-[108px]으로 고정, 넘치면 스크롤 */}
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
                          className={`flex items-center gap-1.5 rounded-lg bg-brand/5 px-2 py-1.5 text-left transition-colors ${url ? "cursor-pointer hover:bg-brand/10" : "cursor-default opacity-50"}`}
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
          {TAX_ADVICE.totalSaving}
        </span>
      </div>
    </>
  );
}

function SummaryStat({ k, v, d }: { k: string; v: string; d: string }) {
  return (
    <div className="min-w-29.5 rounded-xl border bg-white px-3 py-2">
      <p className="text-[13px] font-bold text-muted-foreground">{k}</p>
      <p className="mt-1 text-[13px] font-extrabold tabular-nums">{v}</p>
      <p className="mt-0.5 text-[13px] font-extrabold tabular-nums text-up">
        {d}
      </p>
    </div>
  );
}
