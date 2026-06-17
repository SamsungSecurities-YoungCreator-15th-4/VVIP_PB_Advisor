"use client";

import { useState } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import AccountAllocation from "@/components/tax/AccountAllocation";
import TaxGauge from "@/components/tax/TaxGauge";
import TaxWaterfall from "@/components/tax/TaxWaterfall";
import DataSourceBadge from "@/components/common/DataSourceBadge";
import { PORTFOLIOS, TAX_ADVICE, TAX_EFFECT } from "@/lib/mockData";
import { useDashboardStore } from "@/lib/store";
import {
  type ApiResult,
  type TaxInsightData,
  buildTaxResultFromMock,
  fetchTaxInsight,
} from "@/lib/api";

/** 중앙 하단: 절세 최적화 시뮬레이터 (절세 효과 / 종합과세 임계선 / 절세 제안) */
export default function TaxSection() {
  const { selectedPortfolioId, selectedCustomerId, customers, consultationId } =
    useDashboardStore();
  const portfolio = PORTFOLIOS.find((p) => p.id === selectedPortfolioId);
  const customer =
    customers.find((c) => c.id === selectedCustomerId) ?? customers[0];
  const baseLabel = `기준 : ${portfolio?.name ?? "포트폴리오 A"} · ${customer?.aumEokwon ?? 0}억`;

  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summary, setSummary] = useState<ApiResult<TaxInsightData> | null>(null);

  async function handleSummarize() {
    if (summaryLoading) return;
    setSummaryLoading(true);
    try {
      // ⚠️ #30(절세 계산) 미머지 — 입력 숫자는 mock(TAX_EFFECT). 요약문만 실 LLM.
      const taxResult = buildTaxResultFromMock(
        portfolio?.name ?? "포트폴리오 A",
        customer?.aumEokwon ?? 0,
      );
      const res = await fetchTaxInsight(taxResult, consultationId || undefined);
      setSummary(res);
    } finally {
      setSummaryLoading(false);
    }
  }

  return (
    <Tabs defaultValue="effect">
      <div className="mb-2 flex items-center justify-between px-0.5">
        <h2 className="text-lg font-extrabold">절세 최적화 시뮬레이터</h2>
        <TabsList className="h-7">
          <TabsTrigger value="effect" className="px-2.5 text-[12px] font-bold">
            절세 효과
          </TabsTrigger>
          <TabsTrigger value="threshold" className="px-2.5 text-[12px] font-bold">
            종합과세 임계선
          </TabsTrigger>
          <TabsTrigger value="advice" className="px-2.5 text-[12px] font-bold">
            절세 제안
          </TabsTrigger>
        </TabsList>
      </div>

      <Card className="gap-0 p-3">
        {/* 탭 1: 절세 효과 */}
        <TabsContent value="effect" className="flex flex-col gap-3">
          <div className="flex items-center gap-4 rounded-xl border border-brand/20 bg-brand/5 px-3.5 py-3">
            <div className="flex-1">
              <div className="flex items-center gap-2 text-[12px] font-extrabold">
                <span className="flex size-5 items-center justify-center rounded-md bg-brand text-[13px] font-extrabold text-white">
                  $
                </span>
                절세 최적화 효과
                <span className="rounded-full border border-brand/20 bg-white px-2 py-0.5 text-[12px] font-bold text-muted-foreground">
                  {baseLabel}
                </span>
              </div>
              <p className="mt-1.5 flex items-baseline gap-1.5 text-[12px] font-bold text-up">
                연간 절세 효과
                <b className="text-3xl font-extrabold tabular-nums tracking-tight">
                  +{TAX_EFFECT.annualSavingManwon.toLocaleString()}
                </b>
                <span className="text-[12px] font-extrabold">만원</span>
              </p>
              <p className="mt-1 text-[12px] font-semibold text-muted-foreground">
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

          {/* AI 절세 요약 — POST /tax/insight 실연결 */}
          <div className="rounded-xl border border-brand/15 bg-brand/5 p-3">
            <div className="mb-2 flex items-center gap-2">
              <Sparkles className="size-3.5 text-brand" />
              <span className="text-[13px] font-extrabold text-brand-dark">
                AI 절세 요약
              </span>
              {summary && (
                <DataSourceBadge source={summary.source} note={summary.note} />
              )}
              {summary?.data.asOf && (
                <span className="text-[9px] font-semibold text-muted-foreground/70">
                  기준 {new Date(summary.data.asOf).toLocaleString("ko-KR")}
                </span>
              )}
              <Button
                size="sm"
                className="ml-auto h-7 font-bold"
                onClick={handleSummarize}
                disabled={summaryLoading}
              >
                {summaryLoading ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  "요약 생성"
                )}
              </Button>
            </div>
            {summary ? (
              <p className="whitespace-pre-line text-[12px] font-medium leading-relaxed text-foreground">
                {summary.data.summary}
              </p>
            ) : (
              <p className="text-[12px] font-medium text-muted-foreground">
                요약을 생성하면 위 절세 계산 결과를 PB 설명조로 정리합니다.
              </p>
            )}
            {/* 출처 명시: 계산(#30) 미연결 — 입력 숫자는 임시값. */}
            <p className="mt-2 text-[10px] font-semibold text-muted-foreground/70">
              ※ 절세 계산(#30) 연동 전이라 요약의 입력 수치는 임시값입니다.
            </p>
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
                  <span className="flex size-5 items-center justify-center rounded-md bg-brand/10 text-[12px] font-extrabold text-brand-dark">
                    {card.icon}
                  </span>
                  <span className="text-[12px] font-extrabold">
                    {card.title}
                  </span>
                </div>
                <p className="mt-1.5 flex-1 text-[12px] font-semibold leading-snug text-muted-foreground">
                  {card.body}
                </p>
                <p className="mt-1 text-[12px] font-bold text-muted-foreground/60">
                  {card.tag}
                </p>
                <p className="mt-0.5 text-[12px] font-extrabold tabular-nums text-up">
                  {card.saving}
                </p>
              </div>
            ))}
          </div>
          <div className="mt-2 flex items-center justify-between rounded-xl bg-brand px-3 py-2">
            <span className="text-[12px] font-bold text-white">
              {TAX_ADVICE.totalLabel}
            </span>
            <span className="text-[12px] font-extrabold tabular-nums text-white">
              {TAX_ADVICE.totalSaving}
            </span>
          </div>
        </TabsContent>
      </Card>
    </Tabs>
  );
}

function SummaryStat({ k, v, d }: { k: string; v: string; d: string }) {
  return (
    <div className="min-w-29.5 rounded-xl border bg-white px-3 py-2">
      <p className="text-[12px] font-bold text-muted-foreground">{k}</p>
      <p className="mt-1 text-[12px] font-extrabold tabular-nums">{v}</p>
      <p className="mt-0.5 text-[12px] font-extrabold tabular-nums text-up">
        {d}
      </p>
    </div>
  );
}
