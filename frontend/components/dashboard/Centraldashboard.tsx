"use client";

import PortfolioSection from "@/components/portfolio/PortfolioSection";
import BacktestChart from "@/components/portfolio/BacktestChart";
import TaxSection from "@/components/tax/TaxSection";
import { useDashboardStore } from "@/lib/store";

/**
 * 중앙 대시보드 영역.
 * 분석 결과가 없을 때(신규 고객 등)는 섹션을 각각 비우지 않고,
 * 중앙 영역 전체를 하나의 회색 빈 화면으로 덮어 "분석 결과가 존재하지 않습니다"만 보여준다.
 */
export default function CentralDashboard() {
  const { portfolioSource, portfolioNote, analyzing } = useDashboardStore();

  // PortfolioSection 의 빈 상태 판정과 동일한 조건(분석 전 = fallback·note 없음·분석 중 아님).
  const isEmpty =
    portfolioSource === "fallback" && portfolioNote === undefined && !analyzing;

  if (isEmpty) {
    return (
      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex flex-1 items-center justify-center rounded-2xl border border-dashed border-muted-foreground/20 bg-muted/30">
          <p className="text-[15px] font-semibold text-muted-foreground">
            분석 결과가 존재하지 않습니다
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-w-0 flex-1 flex-col gap-3">
      <PortfolioSection />
      <BacktestChart />
      <TaxSection />
    </main>
  );
}
