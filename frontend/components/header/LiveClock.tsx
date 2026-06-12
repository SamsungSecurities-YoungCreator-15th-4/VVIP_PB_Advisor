"use client";

import { useCallback, useEffect, useState } from "react";
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

  // setTimeout으로 감싸 setState를 콜백 내부에서 호출 — react-hooks/set-state-in-effect 규칙 준수
  useEffect(() => {
    const id = setTimeout(refresh, 0);
    return () => clearTimeout(id);
  }, [refresh]);

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
