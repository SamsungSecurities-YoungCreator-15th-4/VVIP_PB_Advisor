"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import AssetDonut from "@/components/portfolio/AssetDonut";
import CorrelationHeatmap from "@/components/portfolio/CorrelationHeatmap";
import { DISPLAY_GROUP_COLORS, toDisplayAllocation } from "@/lib/assetMapping";
import { PORTFOLIOS, type Portfolio, type PortfolioMetrics } from "@/lib/mockData";
import { useDashboardStore } from "@/lib/store";
import {
  BACKEND_PORTFOLIO_ID,
  useStressedPortfolios,
} from "@/lib/useStressedPortfolios";
import type { PortfolioMetrics as ApiMetrics } from "@/lib/types";

/** 카드에 표시할 지표 — 백엔드(실데이터) 또는 목데이터에서 동일 형태로 만든다. */
interface MetricView {
  expectedReturn: string;
  volatility: string;
  sharpe: string;
  sortino: string;
  mdd: string;
  mddSub: string;
  afterTax: string;
  afterTaxSub: string;
}

/** 억원 값을 "+7,200만원" / "-1.29억원" 형태로 포맷 */
function fmtEokAmount(eok: number): string {
  const man = Math.round(eok * 10000);
  if (man === 0) return "0원";
  const sign = man > 0 ? "+" : "-";
  const abs = Math.abs(man);
  return abs >= 10000
    ? `${sign}${(abs / 10000).toFixed(2)}억원`
    : `${sign}${abs.toLocaleString()}만원`;
}

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;

/** 백엔드 지표(소수)를 카드 표시용으로 변환. 총자산(억)으로 금액도 환산. */
function viewFromApi(m: ApiMetrics, aumEokwon: number): MetricView {
  return {
    expectedReturn: pct(m.expectedReturn),
    volatility: pct(m.volatility),
    sharpe: m.sharpeRatio.toFixed(2),
    sortino: m.sortinoRatio == null ? "N/A" : m.sortinoRatio.toFixed(2),
    mdd: m.maxDrawdown == null ? "N/A" : pct(m.maxDrawdown),
    mddSub: m.maxDrawdown == null ? "" : fmtEokAmount(-(m.maxDrawdown * aumEokwon)),
    afterTax: m.afterTaxReturn == null ? "N/A" : pct(m.afterTaxReturn),
    afterTaxSub:
      m.afterTaxReturn == null ? "" : fmtEokAmount(m.afterTaxReturn * aumEokwon),
  };
}

/** 목데이터 지표를 카드 표시용으로 변환 (백엔드 폴백). */
function viewFromMock(m: PortfolioMetrics): MetricView {
  return {
    expectedReturn: `${m.expectedReturnPct}%`,
    volatility: `${m.volatilityPct}%`,
    sharpe: m.sharpe.toFixed(2),
    sortino: m.sortino.toFixed(2),
    mdd: `${m.mddPct}%`,
    mddSub: m.mddAmountLabel,
    afterTax: `${m.afterTaxReturnPct.toFixed(1)}%`,
    afterTaxSub: m.afterTaxAmountLabel,
  };
}

/** 중앙 상단: 현재 / 포트폴리오 A / 포트폴리오 B — 카드 클릭으로 선택 */
export default function PortfolioSection() {
  const { selectedPortfolioId, selectPortfolio } = useDashboardStore();
  const { byId, loading, failed, aumEokwon, hasScenario } =
    useStressedPortfolios();

  // 백엔드 연결 상태 배지
  const live = !failed && Object.keys(byId).length > 0;
  const statusLabel = failed
    ? "예시 데이터 (백엔드 미연결)"
    : hasScenario
      ? "시나리오 반영 중"
      : "실시간 지표 연동";

  return (
    <section>
      <div className="mb-2 flex items-center justify-between px-0.5">
        <div className="flex items-center gap-2.5">
          <h2 className="text-lg font-extrabold">포트폴리오 대시보드</h2>
          <div
            className={`flex items-center gap-1.5 rounded-lg px-2 py-0.5 text-[10px] font-bold ${
              failed
                ? "bg-muted text-muted-foreground"
                : "bg-brand/5 text-brand-dark"
            }`}
          >
            <span
              className={`size-1.5 rounded-full ${
                failed
                  ? "bg-muted-foreground/50"
                  : "bg-positive shadow-[0_0_0_2px_rgba(22,180,122,0.18)]"
              } ${loading && !failed ? "animate-pulse" : ""}`}
            />
            {statusLabel}
          </div>
        </div>
        <span className="text-[11px] font-semibold text-muted-foreground">
          {live ? `운용자산 ${aumEokwon}억 기준` : "2026.06.08 기준"}
        </span>
      </div>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-3">
        {PORTFOLIOS.map((pf) => (
          <PortfolioCard
            key={pf.id}
            pf={pf}
            live={byId[BACKEND_PORTFOLIO_ID[pf.id]]?.stressed}
            aumEokwon={aumEokwon}
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
  live,
  aumEokwon,
  isSelected,
  onSelect,
}: {
  pf: Portfolio;
  live?: ApiMetrics;
  aumEokwon: number;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const [view, setView] = useState<"donut" | "heatmap">("donut");
  const allocation = toDisplayAllocation(pf.weights);
  // 백엔드 실데이터가 있으면 그 값을, 없으면 목데이터를 표시
  const m = live ? viewFromApi(live, aumEokwon) : viewFromMock(pf.metrics);

  // 선택된 카드에만 "선택됨" 배지 표시
  const badgeLabel = isSelected ? "선택됨" : null;

  return (
    <Card
      tabIndex={0}
      className={`gap-0 cursor-pointer p-3 transition-shadow focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-brand ${
        isSelected
          ? "border-2 border-brand shadow-[0_6px_20px_rgba(0,100,255,0.14)]"
          : "hover:shadow-md"
      }`}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
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
        <Metric k="기대수익률" v={m.expectedReturn} tone="up" />
        <Metric k="변동성" v={m.volatility} />
        <Metric k="샤프지수" v={m.sharpe} />
        <Metric k="소르티노" v={m.sortino} />
        <Metric k="MDD" v={m.mdd} sub={m.mddSub} tone="down" />
        <Metric k="세후수익률" v={m.afterTax} sub={m.afterTaxSub} tone="up" />
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
