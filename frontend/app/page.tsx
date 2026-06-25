import Header from "@/components/header/Header";
import Sidebar from "@/components/sidebar/Sidebar";
import CentralDashboard from "@/components/dashboard/Centraldashboard";
import RightPanel from "@/components/right-panel/RightPanel";
import AuthGuard from "@/components/common/AuthGuard";

/**
 * PB 대시보드 초안.
 * 레이아웃 정본: "(의견) V0.9 - 컴포넌트 분리" 이미지 기준
 * 헤더 / 좌측 Sidebar / 중앙(포트폴리오·백테스트·절세) / 우측(시나리오·인사이트)
 */
export default function Home() {
  return (
    <AuthGuard>
      <div className="flex min-h-screen flex-col gap-3 p-3.5">
        <Header />
        <div className="flex items-stretch gap-3 overflow-x-auto">
          <Sidebar />
          <CentralDashboard />
          <RightPanel />
        </div>
      </div>
    </AuthGuard>
  );
}
