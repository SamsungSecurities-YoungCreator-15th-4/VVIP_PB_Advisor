"use client";

import { DISPLAY_GROUPS } from "@/lib/assetMapping";
import { CORRELATION_MATRIX } from "@/lib/mockData";

/**
 * 6분류 자산군 상관관계 히트맵 (셀 그리드 응용).
 * 도넛 ↔ 히트맵 세그먼트 토글로 전환된다. 행렬은 더미 — 백엔드 연동 시 교체.
 */
export default function CorrelationHeatmap() {
  return (
    <div className="flex-1">
      <div
        className="grid gap-px"
        style={{
          gridTemplateColumns: `48px repeat(${DISPLAY_GROUPS.length}, 1fr)`,
        }}
      >
        <span />
        {DISPLAY_GROUPS.map((g) => (
          <span
            key={g}
            className="truncate text-center text-[7.5px] font-semibold text-muted-foreground"
            title={g}
          >
            {g.slice(0, 2)}
          </span>
        ))}
        {CORRELATION_MATRIX.map((row, i) => (
          <Row key={DISPLAY_GROUPS[i]} label={DISPLAY_GROUPS[i]} row={row} />
        ))}
      </div>
      <p className="mt-1 text-right text-[8px] font-semibold text-muted-foreground">
        상관계수 (더미)
      </p>
    </div>
  );
}

function Row({ label, row }: { label: string; row: number[] }) {
  return (
    <>
      <span className="flex items-center truncate pr-1 text-[8px] font-semibold text-muted-foreground">
        {label}
      </span>
      {row.map((v, j) => (
        <span
          key={j}
          className="flex aspect-square items-center justify-center rounded-[3px] text-[7.5px] font-bold tabular-nums"
          style={{
            // 상관 높음 → 진한 파랑, 낮음 → 연한 파랑
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
