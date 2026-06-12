import Header from "@/components/Header";
import Sidebar from "@/components/Sidebar";
import PortfolioSection from "@/components/PortfolioSection";
import BacktestChart from "@/components/BacktestChart";
import TaxSection from "@/components/TaxSection";
import RightPanel from "@/components/RightPanel";

/**
 * PB 대시보드 초안.
 * 레이아웃 정본: "(의견) V0.9 - 컴포넌트 분리" 이미지 기준
 * 헤더 / 좌측 Sidebar / 중앙(포트폴리오·백테스트·절세) / 우측(시나리오·인사이트)
 */
export default function Home() {
  return (
    <div className="flex min-h-screen min-w-345 flex-col gap-3 p-3.5">
      <Header />
      <div className="flex flex-1 items-start gap-3">
        <Sidebar />
        <main className="flex min-w-0 flex-1 flex-col gap-3">
          <PortfolioSection />
          <BacktestChart />
          <TaxSection />
        </main>
        <RightPanel />
      </div>
    </div>
  );
}
