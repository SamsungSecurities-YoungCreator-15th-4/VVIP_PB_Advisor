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

const AFTER_TAX_COLORS = ["#AEB5BD", "#0064FF"]; // 일반과세(회색) / 절세전략(브랜드 블루)
const TAX_COLORS = ["#F04452", "#F4A8AE"]; // 세금 누수(빨강) / 절세 후 잔여 세금

/**
 * ① 세금 흐름 비교 — 일반과세 vs 절세전략의 세후수익·세금을
 * 가로 누적 바(워터폴 바)로 비교한다. recharts BarChart 사용.
 */
export default function TaxWaterfall() {
  const data = TAX_EFFECT.flow.rows.map((r) => ({
    name: r.label,
    afterTax: r.afterTax,
    tax: r.tax,
  }));

  return (
    <div>
      <p className="mb-2 flex items-center gap-1.5 text-[12px] font-extrabold">
        <span className="flex size-4 items-center justify-center rounded-full bg-brand/10 text-[10px] text-brand-dark">
          1
        </span>
        세금 흐름 비교
        <span className="text-[12px] font-semibold text-muted-foreground">
          · {TAX_EFFECT.flow.pretaxLabel}
        </span>
      </p>
      <div className="h-27.5">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 0, right: 40, bottom: 0, left: 0 }}
            barSize={28}
          >
            <XAxis type="number" hide />
            <YAxis
              type="category"
              dataKey="name"
              width={52}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 12, fontWeight: 800, fill: "#4E5968" }}
            />
            <Bar dataKey="afterTax" stackId="flow" isAnimationActive={false}>
              {data.map((_, i) => (
                <Cell key={i} fill={AFTER_TAX_COLORS[i]} radius={8} />
              ))}
              <LabelList
                dataKey="afterTax"
                position="insideLeft"
                formatter={(v) => `세후 ${Number(v).toLocaleString()}만`}
                style={{ fontSize: 12, fontWeight: 800, fill: "#fff" }}
              />
            </Bar>
            <Bar dataKey="tax" stackId="flow" isAnimationActive={false}>
              {data.map((_, i) => (
                <Cell key={i} fill={TAX_COLORS[i]} radius={8} />
              ))}
              <LabelList
                dataKey="tax"
                position="right"
                formatter={(v) => Number(v).toLocaleString()}
                style={{ fontSize: 11, fontWeight: 800, fill: "#F04452" }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-1.5 flex flex-wrap gap-3">
        <LegendDot color="#0064FF" label="세후 수익(절세전략)" />
        <LegendDot color="#AEB5BD" label="세후 수익(일반)" />
        <LegendDot color="#F04452" label="세금 누수" />
      </div>
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5 text-[12px] font-bold text-muted-foreground">
      <span
        className="size-2 rounded-[3px]"
        style={{ backgroundColor: color }}
      />
      {label}
    </span>
  );
}
