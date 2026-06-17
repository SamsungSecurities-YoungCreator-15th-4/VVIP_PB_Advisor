"use client";

import { DISPLAY_GROUPS, type DisplayGroup } from "@/lib/assetMapping";
import { CORRELATION_MATRIX } from "@/lib/mockData";

const GROUP_ABBR: Record<DisplayGroup, string> = {
  국내주식: "국내",
  해외배당주: "배당",
  해외성장주: "성장",
  일반채권: "일반",
  저쿠폰채: "저쿠",
  분리과세: "분리",
};

export default function CorrelationHeatmap() {
  return (
    <div className="flex flex-1 flex-col">
      <div
        className="flex-1 grid gap-px"
        style={{
          gridTemplateColumns: `44px repeat(${DISPLAY_GROUPS.length}, 1fr)`,
          gridTemplateRows: `auto repeat(${DISPLAY_GROUPS.length}, 1fr)`,
        }}
      >
        <span />
        {DISPLAY_GROUPS.map((g) => (
          <span
            key={g}
            className="truncate text-center text-[10px] font-semibold text-muted-foreground"
            title={g}
          >
            {GROUP_ABBR[g]}
          </span>
        ))}
        {CORRELATION_MATRIX.map((row, i) => (
          <Row key={DISPLAY_GROUPS[i]} label={DISPLAY_GROUPS[i]} row={row} />
        ))}
      </div>
      <p className="mt-1 text-right text-[8px] font-semibold text-muted-foreground">
        상관계수
      </p>
    </div>
  );
}

function Row({ label, row }: { label: string; row: number[] }) {
  return (
    <>
      <span className="flex items-center truncate pr-1 text-[10px] font-semibold text-muted-foreground">
        {label}
      </span>
      {row.map((v, j) => (
        <span
          key={j}
          className="flex items-center justify-center rounded-[3px] text-[7.5px] font-bold tabular-nums"
          style={{
            backgroundColor: `rgba(0, 100, 255, ${0.06 + v * 0.8})`,
            color: v > 0.55 ? "#fff" : "#0050D6",
          }}
        >
          {v.toFixed(2)}
        </span>
      ))}
    </>
  );
}
