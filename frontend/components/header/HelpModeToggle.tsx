"use client";

import { CircleHelp } from "lucide-react";
import { useDashboardStore } from "@/lib/store";

export default function HelpModeToggle() {
  const { helpMode, toggleHelpMode } = useDashboardStore();

  return (
    <button
      onClick={toggleHelpMode}
      title={helpMode ? "가이드 모드 끄기" : "가이드 모드 켜기"}
      className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] font-bold transition-colors ${
        helpMode
          ? "bg-brand text-white"
          : "text-muted-foreground hover:bg-muted hover:text-foreground"
      }`}
    >
      <CircleHelp className="size-3.5" />
      {helpMode ? "가이드 OFF" : "가이드 ON"}
    </button>
  );
}
