"use client";

import { Cell, Pie, PieChart } from "recharts";
import { DISPLAY_GROUP_COLORS, type DisplayGroup } from "@/lib/assetMapping";

interface Props {
  allocation: { group: DisplayGroup; weight: number }[];
}

/** 포트폴리오 카드의 자산배분 도넛 (6분류 표시) */
export default function AssetDonut({ allocation }: Props) {
  return (
    <div className="relative size-[110px] shrink-0">
      <PieChart width={110} height={110}>
        <Pie
          data={allocation}
          dataKey="weight"
          nameKey="group"
          cx="50%"
          cy="50%"
          innerRadius={36}
          outerRadius={54}
          startAngle={90}
          endAngle={-270}
          isAnimationActive={false}
        >
          {allocation.map((d) => (
            <Cell key={d.group} fill={DISPLAY_GROUP_COLORS[d.group]} />
          ))}
        </Pie>
      </PieChart>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-[9px] font-bold text-muted-foreground">
          자산배분
        </span>
        <span className="text-[13px] font-extrabold">
          {allocation.length}개 군
        </span>
      </div>
    </div>
  );
}
