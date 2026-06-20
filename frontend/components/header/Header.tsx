import { MACRO_INDICATORS } from "@/lib/mockData";
import LiveClock from "@/components/header/LiveClock";
import PdfExportButton from "@/components/header/PdfExportButton";

/** 상단 헤더: 로고 · 거시지표 6개 · PDF 추출 */
export default function Header() {
  return (
    <header className="flex h-14.5 items-center gap-3 rounded-2xl border bg-card px-4 shadow-sm">
      {/* 로고 — 항상 표시 */}
      <div className="flex shrink-0 items-center gap-3 border-r pr-4">
        <div className="flex size-9 items-center justify-center rounded-lg bg-linear-to-br from-[#2C7BFF] to-[#0050D6] text-lg font-extrabold text-white">
          S
        </div>
        <div>
          <h1 className="text-[15px] font-extrabold leading-tight">
            S.upervisor
          </h1>
          <p className="text-[9px] font-bold tracking-[0.12em] text-muted-foreground">
            VVIP PB Advisor
          </p>
        </div>
      </div>

      {/* 시각 — md 이상에서만 표시 */}
      <div className="hidden md:flex">
        <LiveClock />
      </div>

      {/* 거시지표 — md 이상에서 가로 스크롤 ticker */}
      <div className="hidden min-w-0 flex-1 overflow-x-auto scrollbar-none md:flex">
        {MACRO_INDICATORS.map((m) => (
          <div
            key={m.label}
            className="shrink-0 border-r px-4 last:border-none first:pl-2"
          >
            <div className="text-[10px] font-semibold text-muted-foreground">
              {m.label}
            </div>
            <div className="text-base font-extrabold leading-none tabular-nums">
              {m.value}
            </div>
            <div
              className={`mt-0.5 text-[10px] font-bold tabular-nums ${
                m.direction === "up" ? "text-up" : "text-down"
              }`}
            >
              {m.direction === "up" ? "▲" : "▼"} {m.change}
            </div>
          </div>
        ))}
      </div>

      {/* 모바일에서 버튼을 오른쪽으로 밀기 */}
      <div className="flex-1 md:hidden" />

      {/* PDF 버튼 — 클릭 시 PB용/고객용 선택 드롭다운 */}
      <PdfExportButton />
    </header>
  );
}
