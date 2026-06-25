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
import type { StressTaxHeadline, TaxWaterfallResponse } from "@/lib/api";

// 현재(회색) / 포폴A(원래 파랑) / 절세제안(약간 밝은 파랑)
const AFTER_TAX_COLORS = ["#AEB5BD", "#0064FF", "#3D8BFF"];
const TAX_COLORS = ["#F04452", "#F4A8AE", "transparent"];

interface Props {
  /**
   * POST /portfolio/calculate 응답의 portfolio.tax.waterfall — 최우선.
   * savingManwon: saved_vs_current / 10000 (최적화 전후 차이 행 계산용)
   */
  waterfallData?: { waterfall: TaxWaterfallResponse; savingManwon: number } | null;
  /** stressed_tax.headline + total_asset(억원) — waterfallData 없을 때 폴백 */
  liveHeadline?: StressTaxHeadline | null;
  liveAumEokwon?: number | null;
}

/**
 * 세금 흐름 비교 — 절세 전/후 세금·세후수익 가로 누적 바.
 * liveHeadline 제공 시 API 실데이터 사용, 없으면 mock 폴백.
 */
export default function TaxWaterfall({ waterfallData, liveHeadline, liveAumEokwon }: Props) {
  let data: { name: string; afterTax: number; tax: number }[];
  let totalSavingManwon: number;
  let pretaxLabel: string;
  let totalLabel: string;
  let domainMax: number;

  if (waterfallData) {
    // /portfolio/calculate tax.waterfall 실데이터
    const wf = waterfallData.waterfall;
    const grossManwon    = Math.round(wf.gross_return / 10000);
    const afterTaxManwon = Math.round(wf.after_tax / 10000);
    const actualTax      = grossManwon - afterTaxManwon;           // 실제 납부 세액(만원)
    const baselineTax    = actualTax + waterfallData.savingManwon; // 전략 없을 때 예상 세액
    const baselineAfter  = grossManwon - baselineTax;
    totalSavingManwon = waterfallData.savingManwon;
    pretaxLabel = `세전 총수익 ${grossManwon.toLocaleString()}만원`;
    totalLabel = "연간 절세 효과";
    domainMax = Math.max(grossManwon, afterTaxManwon + actualTax) * 1.15;
    data = [
      { name: "전략 전",       afterTax: baselineAfter,  tax: baselineTax },
      { name: "절세 전략 적용", afterTax: afterTaxManwon, tax: actualTax  },
    ];
  } else if (liveHeadline != null && liveAumEokwon != null && liveAumEokwon > 0) {
    // stress-metrics headline 폴백
    const aumManwon = liveAumEokwon * 10000;
    const beforeAfterTax = Math.round(liveHeadline.after_tax_return_before * aumManwon);
    const afterAfterTax  = Math.round(liveHeadline.after_tax_return_after  * aumManwon);
    const beforeTax = Math.round(liveHeadline.tax_amount_before / 10000);
    const afterTax  = Math.round(liveHeadline.tax_amount_after  / 10000);
    totalSavingManwon = Math.round(liveHeadline.annual_tax_saving / 10000);
    const pretaxManwon = beforeAfterTax + beforeTax;
    pretaxLabel = `세전 총수익 ${pretaxManwon.toLocaleString()}만원`;
    totalLabel = "연간 절세 효과";
    domainMax = Math.max(pretaxManwon, afterAfterTax + afterTax) * 1.15;
    data = [
      { name: "현재 포트폴리오", afterTax: beforeAfterTax, tax: beforeTax },
      { name: "절세 제안 적용",  afterTax: afterAfterTax,  tax: afterTax  },
    ];
  } else {
    const { rows, pretaxLabel: pl, totalLabel: tl, totalSavingManwon: ts } = TAX_EFFECT.flow;
    data = rows.map((r, i) => ({
      name: i === 1 ? "제안 포트폴리오" : r.label,
      afterTax: r.afterTaxManwon,
      tax: r.taxManwon,
    }));
    totalSavingManwon = ts;
    pretaxLabel = pl;
    totalLabel = tl;
    domainMax = 27000;
  }

  const isLiveData = waterfallData != null || (liveHeadline != null && liveAumEokwon != null);
  const colors = isLiveData
    ? { after: ["#AEB5BD", "#0064FF"], tax: ["#F04452", "#F4A8AE"] }
    : { after: AFTER_TAX_COLORS,        tax: TAX_COLORS              };

  return (
    <div className="flex flex-col">
      <p className="mb-2 flex items-center gap-1.5 text-[13px] font-extrabold">
        세금 흐름 비교
        <span className="text-[13px] font-semibold text-muted-foreground">
          {pretaxLabel}
        </span>
      </p>
      <div className="mb-2 flex items-center justify-between rounded-lg bg-muted/60 px-2.5 py-1.5">
        <span className="text-[12px] font-semibold text-muted-foreground">
          {totalLabel}
        </span>
        <span className="text-[13px] font-extrabold tabular-nums text-up">
          +{totalSavingManwon.toLocaleString()}만원
        </span>
      </div>

      <div className="h-32">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 0, right: 52, bottom: 0, left: 0 }}
            barSize={28}
          >
            <XAxis type="number" hide domain={[0, domainMax]} />
            <YAxis
              type="category"
              dataKey="name"
              width={90}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 12, fontWeight: 800, fill: "#4E5968" }}
            />
            <Bar dataKey="afterTax" stackId="flow" isAnimationActive={false}>
              {data.map((_, i) => (
                <Cell key={i} fill={colors.after[i] ?? "#3D8BFF"} radius={10} />
              ))}
              <LabelList
                dataKey="afterTax"
                position="insideLeft"
                formatter={(v: unknown) =>
                  `세후 ${(Number(v) / 10000).toFixed(2)}억`
                }
                style={{ fontSize: 12, fontWeight: 800, fill: "#fff" }}
              />
            </Bar>
            <Bar dataKey="tax" stackId="flow" isAnimationActive={false}>
              {data.map((_, i) => (
                <Cell
                  key={i}
                  fill={colors.tax[i] ?? "transparent"}
                  radius={10}
                />
              ))}
              <LabelList
                dataKey="tax"
                position="right"
                formatter={(v: unknown) =>
                  Number(v) > 0 ? `${Number(v).toLocaleString()}만` : ""
                }
                style={{ fontSize: 12, fontWeight: 800, fill: "#F04452" }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-8 flex gap-3">
        <LegendDot color="#0064FF" label="세후 수익" />
        <LegendDot color="#F04452" label="세금" />
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
