"use client";

import { CircleHelp } from "lucide-react";
import { useDashboardStore } from "@/lib/store";

export default function HelpModeToggle() {
  const { helpMode, toggleHelpMode } = useDashboardStore();

  return (
    <label className="group relative flex cursor-pointer items-center gap-1.5">
      <CircleHelp className={`size-3.5 ${helpMode ? "text-brand" : "text-muted-foreground"}`} />
      <span className={`text-[11px] font-bold ${helpMode ? "text-brand" : "text-muted-foreground"}`}>
        가이드
      </span>
      {/* 호버 툴팁 */}
      <div className="pointer-events-none absolute -bottom-9 left-1/2 z-50 hidden -translate-x-1/2 whitespace-nowrap rounded-lg bg-foreground px-2.5 py-1.5 text-[11px] font-semibold text-background shadow-lg group-hover:block">
        ON으로 켜면 주요 지표에 마우스를 올려 설명을 볼 수 있어요
        <span className="absolute -top-1 left-1/2 -translate-x-1/2 border-4 border-transparent border-b-foreground" />
      </div>
      <button
        role="switch"
        aria-checked={helpMode}
        onClick={toggleHelpMode}
        className={`relative h-6 w-14 rounded-full transition-colors duration-200 ${
          helpMode ? "bg-brand" : "bg-muted"
        }`}
      >
        <span
          className={`absolute top-1/2 -translate-y-1/2 text-[10px] font-extrabold transition-all duration-200 ${
            helpMode ? "left-2.5 text-white" : "right-2 text-muted-foreground"
          }`}
        >
          {helpMode ? "ON" : "OFF"}
        </span>
        <span
          className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all duration-200 ${
            helpMode ? "left-[calc(100%-1.375rem)]" : "left-0.5"
          }`}
        />
      </button>
    </label>
  );
}
