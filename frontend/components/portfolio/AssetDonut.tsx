"use client";

import { Pie, PieChart, ResponsiveContainer } from "recharts";

interface Props {
  allocation: { label: string; weight: number; color: string }[];
}

/** 포트폴리오 카드 자산배분 도넛 차트 + 하단 2열 범례
 *  - 도넛은 항상 h-40 고정 → 아이템 수 무관하게 같은 크기
 *  - 범례는 justify-between으로 항상 하단 고정
 */
export default function AssetDonut({ allocation }: Props) {
  const data = allocation
    .filter((d) => d.weight > 0)
    .map((d) => ({ ...d, fill: d.color }));

  return (
    <div className="flex h-full w-full flex-col justify-between py-1">
      {/* 도넛: 항상 고정 높이 */}
      <div className="h-40 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="weight"
              nameKey="label"
              cx="50%"
              cy="50%"
              innerRadius="42%"
              outerRadius="78%"
              startAngle={90}
              endAngle={-270}
              isAnimationActive={false}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* 범례: 항상 하단 */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 px-2">
        {data.map((d) => {
          const rounded = Math.round(d.weight * 100) / 100;
          const displayWeight = rounded % 1 === 0 ? rounded.toFixed(0) : rounded.toFixed(2);
          return (
            <div key={d.label} className="flex min-w-0 items-center gap-1.5">
              <span
                className="size-2 shrink-0 rounded-full"
                style={{ backgroundColor: d.fill }}
              />
              <span className="flex-1 truncate text-[11px] font-semibold text-muted-foreground">
                {d.label}
              </span>
              <span className="shrink-0 text-[11px] font-bold tabular-nums">
                {displayWeight}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
