"use client";

import { useEffect, useState, useCallback } from "react";
import { RefreshCw } from "lucide-react";

function now(): string {
  return new Date().toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export default function LiveClock() {
  const [time, setTime] = useState<string | null>(null);

  const refresh = useCallback(() => setTime(now()), []);

  // SSR 하이드레이션 안전: 마운트 시 1회만 시각 설정
  // 이후 갱신은 새로고침 버튼 클릭(refresh)으로만 가능
  useEffect(() => {
    setTime(now());
  }, []);

  return (
    <div className="flex items-center gap-1 pr-1 text-[11px] font-semibold text-muted-foreground">
      <b className="text-sm font-bold tabular-nums text-foreground">
        {time ?? "--:--"}
      </b>
      <span>기준</span>
      <button
        onClick={refresh}
        aria-label="현재 시각 새로고침"
        className="ml-0.5 rounded p-0.5 text-muted-foreground transition-colors hover:text-foreground"
      >
        <RefreshCw size={11} />
      </button>
    </div>
  );
}
