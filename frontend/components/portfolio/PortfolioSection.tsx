"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import AssetDonut from "@/components/portfolio/AssetDonut";
import CorrelationHeatmap from "@/components/portfolio/CorrelationHeatmap";
import { toDisplayAllocation } from "@/lib/assetMapping";
import { fetchPortfolioCalculate } from "@/lib/api";
import { type Portfolio } from "@/lib/mockData";
import { useDashboardStore } from "@/lib/store";
import HelpTooltip from "@/components/common/HelpTooltip";

const METRIC_HELP: Record<string, string> = {
  기대수익률:
    "연간 기대 수익률입니다. 과거 수익률과 자산별 위험 프리미엄을 바탕으로 추정한 값으로, 실제 수익을 보장하지 않습니다.",
  샤프지수:
    "위험 1단위당 초과 수익을 나타냅니다. 값이 클수록 위험 대비 수익이 높으며, 1.0 이상이면 우수한 수준으로 평가합니다.",
  소르티노:
    "하락 위험(손실 변동성)만을 고려한 위험 조정 수익률입니다. 샤프지수보다 손실 가능성을 더 엄밀하게 반영합니다.",
  세후수익률:
    "세금 효과를 반영한 실질 수익률입니다. ISA·연금 계좌 활용 등 절세 전략 적용 시 수치가 높아집니다.",
  변동성:
    "포트폴리오 수익률의 표준편차로 측정한 위험 수준입니다. 값이 낮을수록 수익이 안정적입니다.",
  MDD: "분석 기간 중 고점 대비 최대 하락폭(Maximum Drawdown)입니다. 최악의 시나리오에서의 손실 규모를 나타냅니다.",
};

/** 중앙 상단: 현재 / 포트폴리오 A / 포트폴리오 B — 카드 클릭으로 선택 */
export default function PortfolioSection() {
  const {
    selectedPortfolioId, selectPortfolio,
    portfolios, portfolioSource, portfolioNote, setPortfolios,
    setCorrelationHeatmap, setPortfolioTax,
    selectedCustomerId, customers,
    ips, liveBase, consultationId,
    analyzing,
  } = useDashboardStore();
  const [calculating, setCalculating] = useState(false);

  // 고객 변경 시에만 자동 계산 — IPS 변경은 '분析하기' 버튼으로 수동 트리거
  useEffect(() => {
    const customer = customers.find((c) => c.id === selectedCustomerId) ?? customers[0];
    if (!customer) return;

    let cancelled = false;
    // 디바운스: 연속 입력 변경·effect 재실행이 calculate를 여러 번 동시에 쏘면 Render
    // 단일 워커에 쌓여 모두 느려진다. 마지막 변경만 300ms 뒤 1건 보낸다.
    const tid = setTimeout(() => {
      if (cancelled) return;
      setCalculating(true);
      fetchPortfolioCalculate({
        aumEokwon: customer.aumEokwon,
        returnPct: ips.returnPct,
        risk: ips.risk,
        timeYears: ips.timeYears,
        liquidity: ips.liquidity,
        tax: ips.tax,
        ratePct: liveBase.ratePct,
        fxKrw: liveBase.fxKrw,
        consultationId: consultationId || undefined,
        clientId: customer.id,
      }).then((result) => {
        if (!cancelled) {
          setPortfolios(result.data.portfolios, result.source, result.note);
          if (result.data.correlationHeatmap) setCorrelationHeatmap(result.data.correlationHeatmap);
          if (result.data.portfolioTax) setPortfolioTax(result.data.portfolioTax);
        }
      }).finally(() => {
        if (!cancelled) setCalculating(false);
      });
    }, 300);
    return () => { cancelled = true; clearTimeout(tid); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCustomerId]);

  const asOf = new Date().toLocaleDateString("ko-KR", {
    year: "numeric", month: "2-digit", day: "2-digit",
  }).replace(/\. /g, ".").replace(/\.$/, "");

  return (
    <section>
      <div className="mb-2 flex items-center justify-between px-0.5">
        <div className="flex items-center gap-2.5">
          <h2 className="text-lg font-extrabold">포트폴리오 대시보드</h2>
          {(calculating || analyzing) ? (
            <div className="flex items-center gap-1.5 rounded-lg bg-muted px-2 py-0.5 text-[10px] font-bold text-muted-foreground">
              <Loader2 className="size-3 animate-spin" />
              분석중...
            </div>
          ) : portfolioSource === "live" ? (
            <div className="flex items-center gap-1.5 rounded-lg bg-brand/5 px-2 py-0.5 text-[10px] font-bold text-brand-dark">
              <span className="size-1.5 rounded-full bg-positive shadow-[0_0_0_2px_rgba(22,180,122,0.18)]" />
              연동 완료
            </div>
          ) : (
            <div
              className="flex items-center gap-1.5 rounded-lg bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700"
              title={portfolioNote}
            >
              ⚠ 데모
            </div>
          )}
        </div>
        <span
          className="text-[11px] font-semibold text-muted-foreground"
          suppressHydrationWarning
        >
          {asOf} 기준
        </span>
      </div>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-3">
        {portfolios.map((pf) => (
          <PortfolioCard
            key={pf.id}
            pf={pf}
            isSelected={pf.id !== "current" && selectedPortfolioId === pf.id}
            onSelect={() => selectPortfolio(pf.id)}
            selectable={pf.id !== "current"}
          />
        ))}
      </div>
    </section>
  );
}

function PortfolioCard({
  pf,
  isSelected,
  onSelect,
  selectable,
}: {
  pf: Portfolio;
  isSelected: boolean;
  onSelect: () => void;
  selectable: boolean;
}) {
  const [view, setView] = useState<"donut" | "heatmap">("donut");
  const allocation = toDisplayAllocation(pf.weights);
  const m = pf.metrics;

  const portfolioType =
    pf.id === "a" ? "수익추구형" : pf.id === "b" ? "안정추구형" : null;

  return (
    <Card
      tabIndex={selectable ? 0 : undefined}
      className={`gap-0 p-3 transition-shadow focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-brand ${
        selectable ? "cursor-pointer" : "cursor-default"
      } ${
        isSelected && selectable
          ? "border-2 border-brand shadow-[0_6px_20px_rgba(0,100,255,0.14)]"
          : selectable
            ? "hover:shadow-md"
            : ""
      }`}
      onClick={selectable ? onSelect : undefined}
      onKeyDown={
        selectable
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect();
              }
            }
          : undefined
      }
    >
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-[13px] font-extrabold">
          {pf.name}
          {portfolioType && (
            <span className="rounded-md bg-[#DCE9FF] px-1.5 py-0.5 text-[9px] font-extrabold text-brand-dark">
              {portfolioType}
            </span>
          )}
        </div>
        <div
          className="flex rounded-lg bg-muted p-0.5"
          onClick={(e) => e.stopPropagation()}
        >
          {(["donut", "heatmap"] as const).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setView(v)}
              className={`rounded-md px-2 py-0.5 text-[9.5px] font-bold transition-colors ${
                view === v
                  ? "bg-white text-brand-dark shadow-sm"
                  : "text-muted-foreground/70 hover:text-foreground"
              }`}
            >
              {v === "donut" ? "자산배분" : "상관관계"}
            </button>
          ))}
        </div>
      </div>

      <div className="flex h-72 items-stretch gap-2.5">
        {view === "donut" ? (
          <div className="flex flex-1 flex-col items-center justify-center">
            <AssetDonut allocation={allocation} />
          </div>
        ) : (
          <CorrelationHeatmap portfolio={pf} />
        )}
      </div>

      <div className="mt-2.5 grid grid-cols-3 gap-px overflow-hidden rounded-lg bg-muted">
        <Metric k="기대수익률" v={`${m.expectedReturnPct}%`} />
        <Metric k="샤프지수" v={m.sharpe != null ? m.sharpe.toFixed(2) : "-"} />
        <Metric
          k="소르티노"
          v={m.sortino != null ? m.sortino.toFixed(2) : "-"}
        />
        <Metric
          k="세후수익률"
          v={`${m.afterTaxReturnPct.toFixed(1)}%`}
          sub={m.afterTaxAmountLabel}
          tone="up"
          value={m.afterTaxReturnPct}
        />
        <Metric
          k="변동성"
          v={`${m.volatilityPct}%`}
          sub={m.volatilityAmountLabel}
          value={m.volatilityPct}
        />
        <Metric k="MDD" v={`${m.mddPct}%`} sub={m.mddAmountLabel} tone="down" value={m.mddPct} />
      </div>
    </Card>
  );
}

function Metric({
  k,
  v,
  sub,
  tone,
  value,
}: {
  k: string;
  v: string;
  sub?: string;
  tone?: "up" | "down";
  value?: number;
}) {
  const helpMode = useDashboardStore((s) => s.helpMode);
  const effectiveTone = value === 0 ? undefined : tone;
  const toneCls =
    effectiveTone === "up" ? "text-up" : effectiveTone === "down" ? "text-down" : "";
  const arrow = effectiveTone === "up" ? "▲" : effectiveTone === "down" ? "▼" : null;
  return (
    <HelpTooltip text={METRIC_HELP[k] ?? ""}>
      <div className="h-full bg-card px-2 py-1.5">
        <div
          className={`w-fit text-[12px] font-bold text-muted-foreground ${
            helpMode
              ? "rounded border border-brand/40 bg-brand/[0.06] px-1"
              : ""
          }`}
        >
          {k}
        </div>
        <div
          className={`mt-1 text-[14px] font-extrabold leading-none tabular-nums ${toneCls}`}
        >
          {arrow && <span className="mr-0.5 text-[14px]">{arrow}</span>}
          {v}
        </div>
        {sub && (
          <div className={`mt-1 text-[12px] font-bold tabular-nums ${toneCls}`}>
            {value === 0 ? sub.replace(/^[+\-±]/, "") : sub}
          </div>
        )}
      </div>
    </HelpTooltip>
  );
}
