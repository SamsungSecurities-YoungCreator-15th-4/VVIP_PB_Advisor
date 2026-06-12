"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import AssetDonut from "@/components/portfolio/AssetDonut";
import CorrelationHeatmap from "@/components/portfolio/CorrelationHeatmap";
import { DISPLAY_GROUP_COLORS, toDisplayAllocation } from "@/lib/assetMapping";
import { PORTFOLIOS, type Portfolio } from "@/lib/mockData";
import { useDashboardStore } from "@/lib/store";

/** 중앙 상단: 현재 / 포트폴리오 A / 포트폴리오 B — 카드 클릭으로 선택 */
export default function PortfolioSection() {
  const { selectedPortfolioId, selectPortfolio } = useDashboardStore();

  return (
    <section>
      <div className="mb-2 flex items-center justify-between px-0.5">
        <div className="flex items-center gap-2.5">
          <h2 className="text-lg font-extrabold">포트폴리오 대시보드</h2>
          <div className="flex items-center gap-1.5 rounded-lg bg-brand/5 px-2 py-0.5 text-[10px] font-bold text-brand-dark">
            <span className="size-1.5 rounded-full bg-positive shadow-[0_0_0_2px_rgba(22,180,122,0.18)]" />
            포트폴리오 연동 완료
          </div>
        </div>
        <span className="text-[11px] font-semibold text-muted-foreground">
          2026.06.08 기준
        </span>
      </div>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-3">
        {PORTFOLIOS.map((pf) => (
          <PortfolioCard
            key={pf.id}
            pf={pf}
            isSelected={selectedPortfolioId === pf.id}
            onSelect={() => selectPortfolio(pf.id)}
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
}: {
  pf: Portfolio;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const [view, setView] = useState<"donut" | "heatmap">("donut");
  const allocation = toDisplayAllocation(pf.weights);
  const m = pf.metrics;

  // 선택된 카드에만 "선택됨" 배지 표시
  const badgeLabel = isSelected ? "선택됨" : null;

  return (
    <Card
      className={`gap-0 cursor-pointer p-3 transition-shadow ${
        isSelected
          ? "border-2 border-brand shadow-[0_6px_20px_rgba(0,100,255,0.14)]"
          : "hover:shadow-md"
      }`}
      onClick={onSelect}
    >
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-[13px] font-extrabold">
          {pf.name}
          {badgeLabel && (
            <span className="rounded-md bg-brand px-1.5 py-0.5 text-[9px] font-extrabold text-white">
              {badgeLabel}
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
                  ? "bg-[#DCE9FF] text-brand-dark shadow-sm"
                  : "text-muted-foreground/70 hover:text-foreground"
              }`}
            >
              {v === "donut" ? "도넛" : "히트맵"}
            </button>
          ))}
        </div>
      </div>

      <div className="flex min-h-[110px] items-center gap-2.5">
        {view === "donut" ? (
          <>
            <AssetDonut allocation={allocation} />
            <div className="grid flex-1 gap-1">
              {allocation.map((d) => (
                <div
                  key={d.group}
                  className="flex items-center gap-1.5 text-[11px]"
                >
                  <span
                    className="size-2 shrink-0 rounded-[3px]"
                    style={{ backgroundColor: DISPLAY_GROUP_COLORS[d.group] }}
                  />
                  <span className="flex-1 font-semibold text-muted-foreground">
                    {d.group}
                  </span>
                  <span className="font-extrabold tabular-nums">
                    {d.weight}%
                  </span>
                </div>
              ))}
            </div>
          </>
        ) : (
          <CorrelationHeatmap />
        )}
      </div>

      <div className="mt-2.5 grid grid-cols-3 gap-px overflow-hidden rounded-lg bg-muted">
        <Metric k="기대수익률" v={`${m.expectedReturnPct}%`} tone="up" />
        <Metric k="변동성" v={`${m.volatilityPct}%`} />
        <Metric k="샤프지수" v={m.sharpe.toFixed(2)} />
        <Metric k="소르티노" v={m.sortino.toFixed(2)} />
        <Metric
          k="MDD"
          v={`${m.mddPct}%`}
          sub={m.mddAmountLabel}
          tone="down"
        />
        <Metric
          k="세후수익률"
          v={`${m.afterTaxReturnPct.toFixed(1)}%`}
          sub={m.afterTaxAmountLabel}
          tone="up"
        />
      </div>
    </Card>
  );
}

function Metric({
  k,
  v,
  sub,
  tone,
}: {
  k: string;
  v: string;
  sub?: string;
  tone?: "up" | "down";
}) {
  const toneCls =
    tone === "up" ? "text-up" : tone === "down" ? "text-down" : "";
  const arrow = tone === "up" ? "▲" : tone === "down" ? "▼" : null;
  return (
    <div className="bg-card px-2 py-1.5">
      <div className="text-[8.5px] font-bold text-muted-foreground">{k}</div>
      <div
        className={`text-sm font-extrabold leading-none tabular-nums ${toneCls}`}
      >
        {arrow && <span className="mr-0.5 text-[10px]">{arrow}</span>}
        {v}
      </div>
      {sub && (
        <div
          className={`mt-0.5 text-[8.5px] font-bold tabular-nums ${toneCls}`}
        >
          {sub}
        </div>
      )}
    </div>
  );
}
