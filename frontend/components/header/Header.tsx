import { FileDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import LiveClock from "@/components/header/LiveClock";
import MacroTicker from "@/components/header/MacroTicker";

/** 상단 헤더: 로고 · 거시지표 6개 · PDF 추출 */
export default function Header() {
  return (
    <header className="flex h-14.5 items-center gap-3 rounded-2xl border bg-card px-4 shadow-sm">
      {/* 로고 — 항상 표시 */}
      <div className="flex shrink-0 items-center gap-3 border-r pr-4">
        <div className="flex size-9 items-center justify-center rounded-lg bg-linear-to-br from-[#2C7BFF] to-[#0050D6] text-lg font-extrabold text-white">
          V
        </div>
        <div>
          <h1 className="text-[15px] font-extrabold leading-tight">
            VVIP PB Advisor
          </h1>
          <p className="text-[9px] font-bold tracking-[0.12em] text-muted-foreground">
            PORTFOLIO ADVISORY
          </p>
        </div>
      </div>

      {/* 시각 — md 이상에서만 표시 */}
      <div className="hidden md:flex">
        <LiveClock />
      </div>

      {/* 거시지표 — md 이상에서 가로 스크롤 ticker (실시간 백엔드 연동) */}
      <div className="hidden min-w-0 flex-1 overflow-x-auto scrollbar-none md:flex">
        <MacroTicker />
      </div>

      {/* 모바일에서 버튼을 오른쪽으로 밀기 */}
      <div className="flex-1 md:hidden" />

      {/* PDF 버튼 — 항상 표시, 텍스트는 sm 이상에서만 */}
      <Button className="shrink-0 font-bold">
        <FileDown className="size-4" />
        <span className="hidden sm:inline">PDF 추출</span>
      </Button>
    </header>
  );
}
