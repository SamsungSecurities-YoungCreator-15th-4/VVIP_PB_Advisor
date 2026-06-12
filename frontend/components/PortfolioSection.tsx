"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import AssetDonut from "@/components/AssetDonut";
import CorrelationHeatmap from "@/components/CorrelationHeatmap";
import { DISPLAY_GROUP_COLORS, toDisplayAllocation } from "@/lib/assetMapping";
import { PORTFOLIOS, type Portfolio } from "@/lib/mockData";

/** 중앙 상단: 현재 / 포트폴리오 A(베스트) / 포트폴리오 B(추천) 3카드 */
export default function PortfolioSection() {
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
      <div className="grid grid-cols-3 gap-3">
        {PORTFOLIOS.map((pf) => (
          <PortfolioCard key={pf.id} pf={pf} />
        ))}
      </div>
    </section>
  );
}

const BADGE_STYLE: Record<Portfolio["badge"], string> = {
  현재: "bg-muted text-muted-foreground",
  베스트: "bg-brand text-white",
  추천: "bg-brand/10 text-brand-dark",
};

function PortfolioCard({ pf }: { pf: Portfolio }) {
  const [view, setView] = useState<"donut" | "heatmap">("donut");
  const allocation = toDisplayAllocation(pf.weights);
  const m = pf.metrics;

  return (
    <Card
      className={`gap-0 p-3 ${
        pf.badge === "베스트"
          ? "border-2 border-brand shadow-[0_6px_20px_rgba(0,100,255,0.14)]"
          : ""
      }`}
    >
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-[13px] font-extrabold">
          {pf.name}
          <span
            className={`rounded-md px-1.5 py-0.5 text-[9px] font-extrabold ${BADGE_STYLE[pf.badge]}`}
          >
            {pf.badge}
          </span>
        </div>
        <div className="flex gap-1">
          {(["donut", "heatmap"] as const).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setView(v)}
              className={`rounded-md px-2 py-0.5 text-[9.5px] font-bold ${
                view === v
                  ? "bg-foreground text-white"
                  : "text-muted-foreground/70"
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
                  className="flex items-center gap-1.5 text-[9.5px]"
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
          v={`▼${m.mddPct}%`}
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
  return (
    <div className="bg-card px-2 py-1.5">
      <div className="text-[8.5px] font-bold text-muted-foreground">{k}</div>
      <div
        className={`text-sm font-extrabold leading-none tabular-nums ${toneCls}`}
      >
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
