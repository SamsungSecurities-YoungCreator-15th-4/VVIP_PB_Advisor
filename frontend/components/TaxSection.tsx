"use client";

import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import AccountAllocation from "@/components/AccountAllocation";
import TaxGauge from "@/components/TaxGauge";
import TaxWaterfall from "@/components/TaxWaterfall";
import { TAX_ADVICE, TAX_EFFECT } from "@/lib/mockData";

/** 중앙 하단: 절세 최적화 시뮬레이터 (절세 효과 / 종합과세 임계선 / 절세 제안) */
export default function TaxSection() {
  return (
    <Card className="gap-0 p-3">
      <Tabs defaultValue="effect">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-[13px] font-bold">절세 최적화 시뮬레이터</p>
          <TabsList className="h-7">
            <TabsTrigger value="effect" className="px-2.5 text-[10px] font-bold">
              절세 효과
            </TabsTrigger>
            <TabsTrigger value="threshold" className="px-2.5 text-[10px] font-bold">
              종합과세 임계선
            </TabsTrigger>
            <TabsTrigger value="advice" className="px-2.5 text-[10px] font-bold">
              절세 제안
            </TabsTrigger>
          </TabsList>
        </div>

        {/* 탭 1: 절세 효과 */}
        <TabsContent value="effect" className="flex flex-col gap-3">
          <div className="flex items-center gap-4 rounded-xl border border-[#C9EFDD] bg-[#E8F8F1] px-3.5 py-3">
            <div className="flex-1">
              <div className="flex items-center gap-2 text-xs font-extrabold">
                <span className="flex size-5 items-center justify-center rounded-md bg-positive text-[13px] font-extrabold text-white">
                  $
                </span>
                절세 최적화 효과
                <span className="rounded-full border border-[#C9EFDD] bg-white px-2 py-0.5 text-[9.5px] font-bold text-muted-foreground">
                  {TAX_EFFECT.baseLabel}
                </span>
              </div>
              <p className="mt-1.5 flex items-baseline gap-1.5 text-[11px] font-bold text-positive-dark">
                연간 절세 효과
                <b className="text-3xl font-extrabold tabular-nums tracking-tight">
                  +{TAX_EFFECT.annualSavingManwon.toLocaleString()}
                </b>
                <span className="text-[13px] font-extrabold">만원</span>
              </p>
              <p className="mt-1 text-[9.5px] font-semibold text-muted-foreground">
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

          <div className="grid grid-cols-2 gap-4">
            <TaxWaterfall />
            <AccountAllocation />
          </div>
        </TabsContent>

        {/* 탭 2: 종합과세 임계선 */}
        <TabsContent value="threshold">
          <TaxGauge />
        </TabsContent>

        {/* 탭 3: 절세 제안 */}
        <TabsContent value="advice">
          <div className="grid grid-cols-2 gap-2">
            {TAX_ADVICE.cards.map((card) => (
              <div
                key={card.title}
                className="flex flex-col rounded-xl border p-2.5"
              >
                <div className="flex items-center gap-1.5">
                  <span className="flex size-5 items-center justify-center rounded-md bg-brand/10 text-[11px] font-extrabold text-brand-dark">
                    {card.icon}
                  </span>
                  <span className="text-[11px] font-extrabold">
                    {card.title}
                  </span>
                </div>
                <p className="mt-1.5 flex-1 text-[9px] font-semibold leading-snug text-muted-foreground">
                  {card.body}
                </p>
                <p className="mt-1 text-[8.5px] font-bold text-muted-foreground/60">
                  {card.tag}
                </p>
                <p className="mt-0.5 text-sm font-extrabold tabular-nums text-up">
                  {card.saving}
                </p>
              </div>
            ))}
          </div>
          <div className="mt-2 flex items-center justify-between rounded-xl bg-brand px-3 py-2">
            <span className="text-[11px] font-bold text-white">
              {TAX_ADVICE.totalLabel}
            </span>
            <span className="text-base font-extrabold tabular-nums text-white">
              {TAX_ADVICE.totalSaving}
            </span>
          </div>
        </TabsContent>
      </Tabs>
    </Card>
  );
}

function SummaryStat({ k, v, d }: { k: string; v: string; d: string }) {
  return (
    <div className="min-w-[118px] rounded-xl border bg-white px-3 py-2">
      <p className="text-[9.5px] font-bold text-muted-foreground">{k}</p>
      <p className="mt-1 text-sm font-extrabold tabular-nums">{v}</p>
      <p className="mt-0.5 text-[10px] font-extrabold tabular-nums text-positive-dark">
        {d}
      </p>
    </div>
  );
}
