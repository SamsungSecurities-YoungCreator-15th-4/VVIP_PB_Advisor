"use client";

import { PanelRightClose, PanelRightOpen } from "lucide-react";
import InsightSection from "@/components/right-panel/InsightSection";
import { useAutoCollapse } from "@/lib/useAutoCollapse";

/** 우측 패널: 시나리오 Test + AI 인사이트 — 여닫기 토글 포함 */
export default function RightPanel() {
  const [isOpen, setIsOpen] = useAutoCollapse(1280);

  if (!isOpen) {
    return (
      <div className="flex w-10 shrink-0 flex-col items-center rounded-2xl bg-card py-3 ring-1 ring-foreground/10">
        <button
          onClick={() => setIsOpen(true)}
          title="우측 패널 열기"
          className="flex flex-col items-center gap-2 rounded-xl p-2 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <PanelRightOpen className="size-4" />
          <span
            className="text-[9px] font-bold leading-none text-muted-foreground"
            style={{ writingMode: "vertical-rl", textOrientation: "upright" }}
          >
            AI인사이트
          </span>
        </button>
      </div>
    );
  }

  return (
    <div className="flex w-[320px] shrink-0 flex-col gap-2.5 self-stretch rounded-2xl bg-card p-2.5 ring-1 ring-foreground/10">
      {/* 패널 헤더 */}
      <div className="flex items-center justify-between px-0.5 pb-0.5">
        <span className="text-[10px] font-bold tracking-wider text-muted-foreground">
          AI 인사이트
        </span>
        <button
          onClick={() => setIsOpen(false)}
          title="우측 패널 닫기"
          className="rounded p-0.5 text-muted-foreground hover:text-foreground"
        >
          <PanelRightClose className="size-4" />
        </button>
      </div>

      <InsightSection />
    </div>
  );
}
