"use client";

import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import { formatManwon } from "@/lib/format";
import { TAX_EFFECT } from "@/lib/mockData";

// 단계별 색상 — 세후수익(기존 회색 → 전환 → 최종 브랜드 블루), 세금(진한 빨강 → 옅게)
const AFTER_TAX_COLORS = ["#AEB5BD", "#5C9CFF", "#0064FF"];
const TAX_COLORS = ["#F04452", "#F4727D", "#F4A8AE"];

export type TaxFlowRow = { label: string; afterTax: number; tax: number };
export type TaxFlow = {
  pretaxLabel: string;
  rows: TaxFlowRow[];
  // 총 절세 효과(만원) 및 분해 — 없으면 rows로 계산/생략
  totalSavingManwon?: number;
  switchSavingManwon?: number;
  adviceSavingManwon?: number;
};

/**
 * ① 세금 흐름 비교 — 기존 자산 → 포트폴리오 전환 → + 절세 제안(최종)으로 이어지는
 * 세후수익·세금을 가로 누적 바로 비교한다. flow가 오면 라이브, 없으면 목데이터 폴백.
 */
export default function TaxWaterfall({ flow }: { flow?: TaxFlow }) {
  const f: TaxFlow = flow ?? TAX_EFFECT.flow;
  const data = f.rows.map((r) => ({
    name: r.label,
    afterTax: r.afterTax,
    tax: r.tax,
  }));
  const total =
    f.totalSavingManwon ??
    (f.rows.length > 1 ? f.rows[0].tax - f.rows[f.rows.length - 1].tax : 0);

  return (
    <div>
      <p className="mb-2 flex items-center gap-1.5 text-[11px] font-extrabold">
        <span className="flex size-4 items-center justify-center rounded-full bg-brand/10 text-[10px] text-brand-dark">
          1
        </span>
        세금 흐름 비교
        <span className="text-[9.5px] font-semibold text-muted-foreground">
          · {f.pretaxLabel}
        </span>
      </p>
      <div style={{ height: `${Math.max(data.length, 2) * 36}px` }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 0, right: 8, bottom: 0, left: 0 }}
            barSize={24}
          >
            <XAxis type="number" hide />
            <YAxis
              type="category"
              dataKey="name"
              width={70}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 10, fontWeight: 800, fill: "#4E5968" }}
            />
            <Bar dataKey="afterTax" stackId="flow" isAnimationActive={false}>
              {data.map((_, i) => (
                <Cell
                  key={i}
                  fill={AFTER_TAX_COLORS[Math.min(i, AFTER_TAX_COLORS.length - 1)]}
                  radius={8}
                />
              ))}
              <LabelList
                dataKey="afterTax"
                position="insideLeft"
                formatter={(v) => `세후 ${formatManwon(Number(v), { withWon: false })}`}
                style={{ fontSize: 10, fontWeight: 800, fill: "#fff" }}
              />
            </Bar>
            <Bar dataKey="tax" stackId="flow" isAnimationActive={false}>
              {data.map((_, i) => (
                <Cell
                  key={i}
                  fill={TAX_COLORS[Math.min(i, TAX_COLORS.length - 1)]}
                  radius={8}
                />
              ))}
              <LabelList
                dataKey="tax"
                position="insideRight"
                formatter={(v) => formatManwon(Number(v), { withWon: false })}
                style={{ fontSize: 9, fontWeight: 800, fill: "#fff" }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {total > 0 && (
        <div className="mt-1.5 flex items-baseline justify-between rounded-lg bg-muted/40 px-2 py-1">
          <span className="text-[9.5px] font-bold text-muted-foreground">
            총 절세 효과
            {f.switchSavingManwon != null && f.adviceSavingManwon != null && (
              <span className="ml-1 font-semibold text-muted-foreground/70">
                (전환 {formatManwon(f.switchSavingManwon, { withWon: false })} + 제안{" "}
                {formatManwon(f.adviceSavingManwon, { withWon: false })})
              </span>
            )}
          </span>
          <span className="text-[13px] font-extrabold tabular-nums text-up">
            +{formatManwon(total)}
          </span>
        </div>
      )}

      <div className="mt-1.5 flex flex-wrap gap-3">
        <LegendDot color="#0064FF" label="세후 수익" />
        <LegendDot color="#F04452" label="세금" />
      </div>
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5 text-[9.5px] font-bold text-muted-foreground">
      <span
        className="size-2 rounded-[3px]"
        style={{ backgroundColor: color }}
      />
      {label}
    </span>
  );
}
