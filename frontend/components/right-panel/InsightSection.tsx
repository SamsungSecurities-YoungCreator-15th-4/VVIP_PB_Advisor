"use client";

import { useState } from "react";
import { ExternalLink, Loader2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import DataSourceBadge from "@/components/common/DataSourceBadge";
import HelpTooltip from "@/components/common/HelpTooltip";

const INSIGHT_HELP =
  "질문을 입력하면 AI가 답합니다. ① 일반 질의(금리·세무·하우스뷰)는 사내 문서를 검색해 " +
  "출처와 함께 답하고, ② '삼성전자 재무제표'처럼 회사명을 넣으면 DART 전자공시에서 최신 재무를 " +
  "가져오며, ③ '분석 결과 요약'처럼 물으면 현재 대시보드를 요약합니다. 모든 수치는 출처가 " +
  "추적되고 AI가 임의로 지어내지 않습니다.";
import { buildDashboardInsightContext } from "@/lib/dashboardInsightContext";
import {
  type InsightCitation,
  detectFinancialQuery,
  fetchDartInsight,
  fetchRagInsight,
} from "@/lib/api";
import { useDashboardStore } from "@/lib/store";
import { DOCUMENT_LINKS } from "@/lib/documentLinks";

/** 우측 하단: AI 인사이트 검색(RAG /rag/insight 실연결) + 결과 + 요약 + 출처/인용 */
export default function InsightSection() {
  const {
    customers,
    portfolios,
    ips,
    consultationId,
    liveBase,
    otherIncomeManwon,
    scenario,
    selectedCustomerId,
    selectedPortfolioId,
    insightResult,
    setInsightResult,
    helpMode,
  } = useDashboardStore();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const result = insightResult;

  const selectedCustomer =
    customers.find((customer) => customer.id === selectedCustomerId) ??
    customers[0];
  const portfolioName = portfolios.find(
    (p) => p.id === selectedPortfolioId,
  )?.name;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q || loading) return;
    setLoading(true);
    try {
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
  const source = showInitial ? null : result.source;
  const note = showInitial ? null : result.note;
  const isEmpty = !showInitial && result.source === "empty";
  const answer = showInitial ? "" : result.data.answer;
  const summary = showInitial
    ? ""
    : result.data.summary || answer.split("\n\n")[0] || answer;
  const citations: InsightCitation[] = showInitial ? [] : result.data.citations;

  return (
    <Card className="flex flex-1 flex-col gap-0 p-3.5">
      {/* 헤더 */}
      <div className="mb-2.5 flex shrink-0 items-center justify-between">
        <HelpTooltip text={INSIGHT_HELP}>
          <p className="cursor-default text-[14px] font-bold">
            <span
              className={
                helpMode
                  ? "rounded border border-brand/40 bg-brand/[0.06] px-1"
                  : ""
              }
            >
              AI 인사이트
            </span>
          </p>
        </HelpTooltip>
        {source && <DataSourceBadge source={source} note={note ?? undefined} />}
      </div>

      {/* 검색 폼 */}
      <form className="mb-2.5 flex shrink-0 gap-1.5" onSubmit={handleSubmit}>
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="예: 재무제표, RAG 문서, 분석 결과 요약"
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
            {showInitial ? (
              <p className="text-[13px] font-medium text-muted-foreground">
                질문을 입력하면 AI가 실데이터로 답합니다.
              </p>
            ) : isEmpty ? (
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
            {showInitial || isEmpty ? (
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

        {/* 출처 / 인용 목록 */}
        <div>
          <p className="mb-1 text-[14px] font-bold">출처 / 인용 목록</p>
          <div className="max-h-[160px] overflow-y-auto">
            {citations.length === 0 ? (
              <p className="py-1.5 text-[12px] font-medium text-muted-foreground">
                표시할 출처가 없습니다.
              </p>
            ) : (
              citations.map((src, i) => {
                const docInfo = DOCUMENT_LINKS[src.title];
                const displayDate = docInfo?.date ?? src.date;
                const inner = (
                  <>
                    <ExternalLink
                      className={`size-3 shrink-0 ${docInfo ? "text-brand" : "text-muted-foreground/70"}`}
                    />
                    <span className="flex-1 truncate text-[13px] font-semibold text-muted-foreground/90">
                      {src.title}
                    </span>
                    {displayDate && (
                      <span className="shrink-0 text-[8.5px] font-semibold tabular-nums text-muted-foreground/70">
                        {displayDate}
                      </span>
                    )}
                  </>
                );
                return docInfo ? (
                  <a
                    key={`${src.title}-${i}`}
                    href={docInfo.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 border-b border-muted py-1.5 last:border-none hover:bg-brand/5 rounded transition-colors"
                  >
                    {inner}
                  </a>
                ) : (
                  <div
                    key={`${src.title}-${i}`}
                    className="flex items-center gap-2 border-b border-muted py-1.5 last:border-none"
                  >
                    {inner}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}
