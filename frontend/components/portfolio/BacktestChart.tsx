"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "@/components/ui/card";
import { BACKTEST_SERIES } from "@/lib/mockData";

const LINES = [
  { key: "current", name: "현재", color: "#8B95A1", width: 2 },
  { key: "a", name: "A", color: "#0064FF", width: 2.6 },
  { key: "b", name: "B", color: "#8FBCFF", width: 2 },
] as const;

const pctFmt = (v: number) => {
  const ret = v - 100;
  return `${ret >= 0 ? "+" : ""}${ret}%`;
};

/** 중앙 중단: 현재/A/B 백테스트 다중 선그래프 (최근 5년, 누적 수익률 표시) */
export default function BacktestChart() {
  return (
    <Card className="gap-0 p-3">
      <div className="mb-1 flex items-center justify-between">
        <p className="text-[14px] font-bold">
          백테스트{" "}
          <span className="text-[12px] font-semibold text-muted-foreground">
            최근 5년
          </span>
          <span className="ml-1.5 text-[11px] font-semibold text-muted-foreground/60">
            (누적 수익률, 2021년 기준)
          </span>
        </p>
        <div className="flex items-center gap-3">
          {LINES.map((l) => (
            <span
              key={l.key}
              className="flex items-center gap-1.5 text-[12px] font-bold text-muted-foreground"
            >
              <span
                className="h-0.75 w-3.5 rounded-sm"
                style={{ backgroundColor: l.color }}
              />
              {l.name}
            </span>
          ))}
        </div>
      </div>
      <div className="h-37.5">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={BACKTEST_SERIES}
            margin={{ top: 8, right: 8, bottom: 0, left: 8 }}
          >
            <CartesianGrid vertical={false} stroke="#F1F3F5" />
            <XAxis
              dataKey="year"
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 12, fill: "#B0B8C1", fontWeight: 600 }}
            />
            <YAxis hide domain={["dataMin - 6", "dataMax + 6"]} />
            <Tooltip
              formatter={(value, name) => [
                `${pctFmt(Number(value))} (${value})`,
                LINES.find((l) => l.key === name)?.name ?? String(name),
              ]}
              contentStyle={{ fontSize: 12, borderRadius: 8 }}
            />
            {LINES.map((l) => (
              <Line
                key={l.key}
                type="monotone"
                dataKey={l.key}
                stroke={l.color}
                strokeWidth={l.width}
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
