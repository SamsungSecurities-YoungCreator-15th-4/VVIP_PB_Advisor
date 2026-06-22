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
import { TAX_EFFECT } from "@/lib/mockData";

const AFTER_TAX_COLORS = ["#AEB5BD", "#0064FF", "#0064FF"];
const TAX_COLORS = ["#F04452", "#F4A8AE", "transparent"];

/**
 * ① 세금 흐름 비교 — 기존 자산 / 포트폴리오 전환 / + 절세 제안을
 * 가로 누적 바로 비교한다. afterTaxManwon·taxManwon 기준.
 */
export default function TaxWaterfall() {
  const { rows, pretaxLabel, totalLabel, totalSavingManwon } =
    TAX_EFFECT.flow;

  const data = rows.map((r) => ({
    name: r.label,
    afterTax: r.afterTaxManwon,
    tax: r.taxManwon,
  }));

  return (
    <div>
      <p className="mb-2 flex items-center gap-1.5 text-[12px] font-extrabold">
        <span className="flex size-4 items-center justify-center rounded-full bg-brand/10 text-[10px] text-brand-dark">
          1
        </span>
        세금 흐름 비교
        <span className="text-[12px] font-semibold text-muted-foreground">
          · {pretaxLabel}
        </span>
      </p>
      <div className="h-30">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 0, right: 44, bottom: 0, left: 0 }}
            barSize={26}
          >
            <XAxis type="number" hide domain={[0, 27000]} />
            <YAxis
              type="category"
              dataKey="name"
              width={76}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 11, fontWeight: 800, fill: "#4E5968" }}
            />
            <Bar dataKey="afterTax" stackId="flow" isAnimationActive={false}>
              {data.map((_, i) => (
                <Cell key={i} fill={AFTER_TAX_COLORS[i]} radius={6} />
              ))}
              <LabelList
                dataKey="afterTax"
                position="insideLeft"
                formatter={(v: unknown) =>
                  `세후 ${(Number(v) / 10000).toFixed(2)}억`
                }
                style={{ fontSize: 11, fontWeight: 800, fill: "#fff" }}
              />
            </Bar>
            <Bar dataKey="tax" stackId="flow" isAnimationActive={false}>
              {data.map((_, i) => (
                <Cell key={i} fill={TAX_COLORS[i]} radius={6} />
              ))}
              <LabelList
                dataKey="tax"
                position="right"
                formatter={(v: unknown) =>
                  Number(v) > 0 ? `${Number(v).toLocaleString()}만` : ""
                }
                style={{ fontSize: 11, fontWeight: 800, fill: "#F04452" }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 총 절세 효과 요약 */}
      <div className="mt-1.5 flex items-center justify-between rounded-lg bg-muted/60 px-2.5 py-1.5">
        <span className="text-[11px] font-semibold text-muted-foreground">
          {totalLabel}
        </span>
        <span className="text-[13px] font-extrabold tabular-nums text-up">
          +{totalSavingManwon.toLocaleString()}만원
        </span>
      </div>

      <div className="mt-1.5 flex gap-3">
        <LegendDot color="#0064FF" label="세후 수익" />
        <LegendDot color="#F04452" label="세금" />
      </div>
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5 text-[11px] font-bold text-muted-foreground">
      <span className="size-2 rounded-[3px]" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}
