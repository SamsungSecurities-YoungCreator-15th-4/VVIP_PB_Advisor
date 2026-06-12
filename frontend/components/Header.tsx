import { FileDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { BASE_TIME, MACRO_INDICATORS } from "@/lib/mockData";

/** 상단 헤더: 로고 · 거시지표 6개 · 포트폴리오 연동 상태 · PDF 추출 */
export default function Header() {
  return (
    <header className="flex h-[58px] items-center gap-4 rounded-2xl border bg-card px-4 shadow-sm">
      <div className="flex items-center gap-3 border-r pr-4">
        <div className="flex size-9 items-center justify-center rounded-lg bg-gradient-to-br from-[#2C7BFF] to-[#0050D6] text-lg font-extrabold text-white">
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

      <div className="pr-1 text-right text-[11px] font-semibold text-muted-foreground">
        기준
        <b className="block text-sm font-bold tabular-nums text-foreground">
          {BASE_TIME}
        </b>
      </div>

      <div className="flex flex-1">
        {MACRO_INDICATORS.map((m) => (
          <div
            key={m.label}
            className="border-r px-4 last:border-none first:pl-2"
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

      <div className="flex items-center gap-2 rounded-lg bg-brand/5 px-3 py-2 text-xs font-bold text-brand-dark">
        <span className="size-2 rounded-full bg-positive shadow-[0_0_0_3px_rgba(22,180,122,0.18)]" />
        포트폴리오 연동 완료
      </div>
      <Button className="font-bold">
        <FileDown />
        PDF 추출
      </Button>
    </header>
  );
}
