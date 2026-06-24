"use client";

import { useState } from "react";
import { Download, Loader2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import DataSourceBadge from "@/components/common/DataSourceBadge";
import { INSIGHT, PORTFOLIOS } from "@/lib/mockData";
import { buildDashboardInsightContext } from "@/lib/dashboardInsightContext";
import {
  type InsightCitation,
  detectFinancialQuery,
  fetchDartInsight,
  fetchRagInsight,
} from "@/lib/api";
import { useDashboardStore } from "@/lib/store";

/** 우측 하단: AI 인사이트 검색(RAG /rag/insight 실연결) + 결과 + 요약 + 출처/인용 */
export default function InsightSection() {
  const {
    customers,
    ips,
    consultationId,
    liveBase,
    otherIncomeManwon,
    scenario,
    selectedCustomerId,
    selectedPortfolioId,
    insightResult,
    setInsightResult,
  } = useDashboardStore();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const result = insightResult;

  const selectedCustomer =
    customers.find((customer) => customer.id === selectedCustomerId) ??
    customers[0];
  const portfolioName = PORTFOLIOS.find(
    (p) => p.id === selectedPortfolioId,
  )?.name;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q || loading) return;
    setLoading(true);
    try {
      // "<회사명> 재무제표/실적/매출…" 류 기업 재무 질의는 RAG 코퍼스에 없으므로
      // DART 전자공시 실시간 조회(/dart/insight)로 라우팅한다. 그 외는 기존 RAG.
      const financial = detectFinancialQuery(q);
      const res = financial
        ? await fetchDartInsight(financial.corpName)
        : await fetchRagInsight(q, {
            consultationId: consultationId || undefined,
            riskProfile: ips.risk,
            selectedPortfolio: portfolioName,
            dashboard: buildDashboardInsightContext({
              selectedCustomer,
              selectedPortfolioId,
              ips,
              scenario,
              liveBase,
              otherIncomeManwon,
            }),
          });
      setInsightResult(res);
    } finally {
      setLoading(false);
    }
  }

  const showInitial = result === null;
  const answer = showInitial ? INSIGHT.defaultAnswer : result.data.answer;
  const citations: InsightCitation[] = showInitial
    ? INSIGHT.sources.map((s) => ({ title: s.title, date: s.date }))
    : result.data.citations;
  const source = showInitial ? "fallback" : result.source;
  const note = showInitial
    ? "검색 전 예시입니다. 질의하면 실데이터로 갱신됩니다."
    : result.note;
  const isEmpty = !showInitial && result.source === "empty";
  const summary = showInitial
    ? answer.split("\n\n")[0] ?? answer
    : result.data.summary || answer.split("\n\n")[0] || answer;

  return (
    <Card className="flex flex-col gap-0 p-3.5">
      {/* 헤더 */}
      <div className="mb-2.5 flex shrink-0 items-center justify-between">
        <p className="text-[14px] font-bold">AI 인사이트</p>
        <DataSourceBadge source={source} note={note} />
      </div>

      {/* 검색 폼 */}
      <form className="mb-2.5 flex shrink-0 gap-1.5" onSubmit={handleSubmit}>
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={INSIGHT.placeholder}
          className="h-8 text-[13px] md:text-[13px]"
          disabled={loading}
        />
        <Button
          type="submit"
          size="sm"
          className="font-bold"
          disabled={loading}
        >
          {loading ? <Loader2 className="size-3.5 animate-spin" /> : "검색"}
        </Button>
      </form>

      {/* 분석 결과 + 요약 + 출처 */}
      <div className="flex flex-col gap-2.5">

        {/* 분석 결과 */}
        <div className="flex flex-col rounded-xl border border-brand/15 bg-brand/5 p-3">
          <div className="mb-2 flex shrink-0 items-center gap-1.5">
            <Sparkles className="size-3 text-brand" />
            <span className="text-[13px] font-extrabold tracking-wide text-brand-dark">
              분석 결과
            </span>
            {result?.data?.asOf && (
              <span className="ml-auto text-[9px] font-semibold text-muted-foreground/70">
                기준{" "}
                {new Date(result.data.asOf).toLocaleString("ko-KR", {
                  timeZone: "Asia/Seoul",
                })}
              </span>
            )}
          </div>
          <div className="max-h-[260px] overflow-y-auto pr-1">
            {isEmpty ? (
              <p className="text-[13px] font-medium text-muted-foreground">
                {note ?? "관련 문서를 찾지 못했습니다."}
              </p>
            ) : (
              <p className="whitespace-pre-line text-[13px] font-medium leading-relaxed text-foreground">
                {answer}
              </p>
            )}
          </div>
        </div>

        {/* 분석 요약 */}
        <div className="flex flex-col rounded-xl border border-brand/15 bg-brand/5 p-3">
          <div className="mb-2 flex shrink-0 items-center gap-1.5">
            <Sparkles className="size-3 text-brand" />
            <span className="text-[13px] font-extrabold tracking-wide text-brand-dark">
              분석 요약
            </span>
          </div>
          <div className="max-h-[100px] overflow-y-auto pr-1">
            {isEmpty ? (
              <p className="text-[13px] font-medium text-muted-foreground">
                요약 정보가 없습니다.
              </p>
            ) : (
              <p className="whitespace-pre-line text-[13px] font-medium leading-relaxed text-foreground">
                {summary}
              </p>
            )}
          </div>
        </div>

        {/* 출처 / 인용 목록 — 5개까지 표시, 초과 시 스크롤 */}
        <div>
          <p className="mb-1 text-[14px] font-bold">출처 / 인용 목록</p>
          <div className="max-h-[160px] overflow-y-auto">
            {citations.length === 0 ? (
              <p className="py-1.5 text-[12px] font-medium text-muted-foreground">
                표시할 출처가 없습니다.
              </p>
            ) : (
              citations.map((src, i) => (
                <div
                  key={`${src.title}-${i}`}
                  className="flex items-center gap-2 border-b border-muted py-1.5 last:border-none"
                >
                  <Download className="size-3 shrink-0 text-muted-foreground/70" />
                  <span className="flex-1 truncate text-[13px] font-semibold text-muted-foreground/90">
                    {src.title}
                  </span>
                  {src.date && (
                    <span className="shrink-0 text-[8.5px] font-semibold tabular-nums text-muted-foreground/70">
                      {src.date}
                    </span>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

    </Card>
  );
}
