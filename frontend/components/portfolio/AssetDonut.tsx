"use client";

import { Cell, Pie, PieChart } from "recharts";
import { DISPLAY_GROUP_COLORS, type DisplayGroup } from "@/lib/assetMapping";

interface Props {
  allocation: { group: DisplayGroup; weight: number }[];
}

/** 포트폴리오 카드 자산배분 도넛 — 220×220px 고정 */
export default function AssetDonut({ allocation }: Props) {
  return (
    <div className="relative size-45 shrink-0">
      <PieChart width={180} height={180}>
        <Pie
          data={allocation}
          dataKey="weight"
          nameKey="group"
          cx="50%"
          cy="50%"
          innerRadius={57}
          outerRadius={86}
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
        <span className="text-[10px] font-bold text-muted-foreground">
          자산배분
        </span>
        <span className="text-[14px] font-extrabold">
          {allocation.length}개 군
        </span>
      </div>
    </div>
  );
}
