"use client";

import { useState } from "react";
import { PanelRightClose, PanelRightOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import InsightSection from "@/components/right-panel/InsightSection";
import { useAutoCollapse } from "@/lib/useAutoCollapse";
import { useDashboardStore } from "@/lib/store";

/** 우측 패널: 시나리오 Test + AI 인사이트 — 여닫기 토글 포함 */
export default function RightPanel() {
  const [isOpen, setIsOpen] = useAutoCollapse(1280);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const { insightResult, ips, setIps } = useDashboardStore();

  const summary =
    insightResult?.source !== "empty" ? insightResult?.data?.summary : null;

  const handleIpsReflect = () => {
    if (!summary) return;
    setConfirmOpen(true);
  };

  const handleConfirm = () => {
    if (!summary) return;
    const prev = (ips.unique ?? "").trim();
    setIps({ unique: prev ? `${prev}\n${summary}` : summary });
    setConfirmOpen(false);
  };

  if (!isOpen) {
    return (
      <div className="flex w-10 self-start shrink-0 flex-col items-center rounded-2xl bg-card py-3 ring-1 ring-foreground/10">
        <button
          onClick={() => setIsOpen(true)}
          title="우측 패널 열기"
          className="flex flex-col items-center gap-2 rounded-xl p-2 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <PanelRightOpen className="size-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="flex w-[320px] shrink-0 self-start flex-col gap-2.5 rounded-2xl bg-card p-2.5 ring-1 ring-foreground/10">
      {/* 패널 헤더 */}
      <div className="flex items-center px-0.5 pb-0.5">
        <button
          onClick={() => setIsOpen(false)}
          title="우측 패널 닫기"
          className="rounded p-0.5 text-muted-foreground hover:text-foreground"
        >
          <PanelRightClose className="size-4" />
        </button>
      </div>

      <InsightSection />

      <Button
        size="lg"
        onClick={handleIpsReflect}
        disabled={!summary}
        className="w-full rounded-xl py-6 text-sm font-extrabold shadow-[0_4px_14px_rgba(0,100,255,0.28)]"
      >
        IPS 반영하기
      </Button>

      {confirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="w-80 rounded-2xl bg-card p-6 shadow-xl ring-1 ring-foreground/10">
            <p className="text-[15px] font-extrabold">IPS에 반영하시겠습니까?</p>
            <p className="mt-1.5 text-[13px] font-medium text-muted-foreground">
              AI 인사이트 요약을 IPS의 <b>Unique</b> 항목에 추가합니다.
            </p>
            <div className="mt-4 flex gap-2">
              <Button className="flex-1" onClick={handleConfirm}>
                승인
              </Button>
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => setConfirmOpen(false)}
              >
                거절
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
