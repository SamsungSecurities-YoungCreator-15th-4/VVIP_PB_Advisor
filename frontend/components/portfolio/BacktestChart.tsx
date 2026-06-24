"use client";

import { useState } from "react";
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
import HelpTooltip from "@/components/common/HelpTooltip";
import { useDashboardStore } from "@/lib/store";

const BACKTEST_HELP =
  "과거 5년 시장 데이터를 기반으로 각 포트폴리오의 누적 수익률을 시뮬레이션한 결과입니다. 현재 포트폴리오(회색)와 제안 포트폴리오 A·B를 비교하며, 과거 성과가 미래 수익을 보장하지 않습니다.";

const BENCHMARKS = ["KOSPI", "S&P500", "MSCI ACWI"] as const;
type Benchmark = (typeof BENCHMARKS)[number];

const BENCHMARK_KEY: Record<Benchmark, string> = {
  KOSPI: "kospi",
  "S&P500": "sp500",
  "MSCI ACWI": "msciAcwi",
};

const LINES = [
  { key: "current", name: "현재", color: "#8B95A1", width: 2 },
  { key: "a", name: "A", color: "#0064FF", width: 2.6 },
  { key: "b", name: "B", color: "#5B9BFF", width: 2 },
] as const;

const BENCHMARK_COLOR = "#DC2626";

const pctFmt = (v: number) => {
  if (Number.isNaN(v)) return "";
  const ret = v - 100;
  return `${ret >= 0 ? "+" : ""}${ret}%`;
};

/** 중앙 중단: 현재/A/B 백테스트 다중 선그래프 (최근 5년, 누적 수익률 표시) */
export default function BacktestChart() {
  const [benchmark, setBenchmark] = useState<Benchmark>("KOSPI");
  const benchKey = BENCHMARK_KEY[benchmark];
  const helpMode = useDashboardStore((s) => s.helpMode);

  return (
    <Card className="gap-0 p-3">
      <div className="mb-1 flex items-center justify-between">
        <HelpTooltip text={BACKTEST_HELP}>
          <p className="cursor-default text-[14px] font-bold">
            <span
              className={
                helpMode
                  ? "rounded border border-brand/40 bg-brand/[0.06] px-1"
                  : ""
              }
            >
              백테스트
            </span>{" "}
            <span className="text-[12px] font-semibold text-muted-foreground">
              최근 5년
            </span>
            <span className="ml-1.5 text-[11px] font-semibold text-muted-foreground/60">
              (누적 수익률, 2021년 기준)
            </span>
          </p>
        </HelpTooltip>
        <div className="flex items-center gap-3">
          {/* 현재/A/B 범례 */}
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

          {/* 벤치마크 세그먼트 컨트롤 — 가장 오른쪽 */}
          <div className="flex items-center gap-1.5">
            <span
              className="h-0.75 w-3.5 rounded-sm"
              style={{ backgroundColor: BENCHMARK_COLOR }}
            />
            <div className="flex rounded-lg bg-muted p-0.5">
              {BENCHMARKS.map((b) => (
                <button
                  key={b}
                  type="button"
                  onClick={() => setBenchmark(b)}
                  className={`rounded-md px-2 py-0.5 text-[11px] font-bold transition-colors ${
                    benchmark === b
                      ? "bg-white text-brand-dark shadow-sm"
                      : "text-muted-foreground"
                  }`}
                >
                  {b}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
      <div className="h-60">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={BACKTEST_SERIES}
            margin={{ top: 8, right: 8, bottom: 0, left: 16 }}
          >
            <CartesianGrid vertical={false} stroke="#F1F3F5" />
            <XAxis
              dataKey="year"
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 12, fill: "#B0B8C1", fontWeight: 600 }}
              ticks={["2021", "2022", "2023", "2024", "2025", "2026"]}
            />
            <YAxis hide domain={["dataMin - 6", "dataMax + 6"]} />
            <Tooltip
              formatter={(value, name) => {
                if (name === benchKey)
                  return [
                    value != null ? `${pctFmt(Number(value))} (${value})` : "-",
                    benchmark,
                  ];
                return [
                  value != null ? `${pctFmt(Number(value))} (${value})` : "-",
                  LINES.find((l) => l.key === name)?.name ?? String(name),
                ];
              }}
              itemSorter={(item) => {
                const order: Record<string, number> = {
                  current: 0,
                  a: 1,
                  b: 2,
                  [benchKey]: 3,
                };
                return order[String(item.dataKey)] ?? 99;
              }}
              contentStyle={{ fontSize: 12, borderRadius: 8 }}
            />
            {/* 벤치마크 라인 */}
            <Line
              key={benchKey}
              type="monotone"
              dataKey={benchKey}
              stroke={BENCHMARK_COLOR}
              strokeWidth={1.8}
              strokeDasharray="4 3"
              dot={false}
              isAnimationActive={false}
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
