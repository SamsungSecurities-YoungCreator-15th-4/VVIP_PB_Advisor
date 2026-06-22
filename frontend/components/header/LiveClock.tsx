"use client";

import { useEffect, useState } from "react";

function now(): string {
  return new Date().toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

/** 헤더의 현재 시각 — 30초마다 자동 갱신되는 실시간 시계.
 *  (데이터 '기준 시각'은 거시지표 갱신 시점에 맞춰 MacroTicker에서 표시한다.) */
export default function LiveClock() {
  const [time, setTime] = useState<string | null>(null);

  useEffect(() => {
    const tick = () => setTime(now());
    const first = setTimeout(tick, 0); // 마운트 직후 1회 (effect 본문 직접 setState 회피)
    const id = setInterval(tick, 30_000); // 30초마다 자동 갱신
    return () => {
      clearTimeout(first);
      clearInterval(id);
    };
  }, []);

  return (
    <div className="flex items-center gap-1 pr-1 text-[11px] font-semibold text-muted-foreground">
      <span>현재</span>
      <b className="text-sm font-bold tabular-nums text-foreground">
        {time ?? "--:--"}
      </b>
    </div>
  );
}
