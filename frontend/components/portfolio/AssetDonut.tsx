"use client";

import { Pie, PieChart, ResponsiveContainer } from "recharts";
import { DISPLAY_GROUP_COLORS, type DisplayGroup } from "@/lib/assetMapping";

interface Props {
  allocation: { group: DisplayGroup; weight: number }[];
}

const RADIAN = Math.PI / 180;

function SliceLabel(props: Record<string, unknown>) {
  const cx = Number(props.cx ?? 0);
  const cy = Number(props.cy ?? 0);
  const midAngle = Number(props.midAngle ?? 0);
  const outerRadius = Number(props.outerRadius ?? 0);
  const name = String(props.name ?? "");
  const value = Number(props.value ?? 0);

  const r = outerRadius + 13;
  const x = cx + r * Math.cos(-midAngle * RADIAN);
  const y = cy + r * Math.sin(-midAngle * RADIAN);
  const anchor = x > cx ? "start" : "end";
  return (
    <text fill="#4E5968" textAnchor={anchor} fontSize={11} fontWeight={600}>
      <tspan x={x} y={y - 5}>
        {name}
      </tspan>
      <tspan x={x} dy={11}>
        {value}%
      </tspan>
    </text>
  );
}

/** 포트폴리오 카드 자산배분 파이차트 — 슬라이스별 외부 레이블 */
export default function AssetDonut({ allocation }: Props) {
  return (
    <div className="w-full flex-1">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={allocation.map((d) => ({
              ...d,
              fill: DISPLAY_GROUP_COLORS[d.group],
            }))}
            dataKey="weight"
            nameKey="group"
            cx="50%"
            cy="50%"
            innerRadius={0}
            outerRadius="56%"
            startAngle={90}
            endAngle={-270}
            isAnimationActive={false}
            label={(props) => <SliceLabel {...props} />}
            labelLine={{ stroke: "#CBD5E1", strokeWidth: 1 }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
