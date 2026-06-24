// 프론트 포트폴리오 id(current/a/b) → 백엔드 id(current/proposalA/proposalB)
// StressTestSection 등에서 공통으로 사용하는 매핑
export const BACKEND_PORTFOLIO_ID: Record<string, string> = {
  current: "current",
  a: "proposalA",
  b: "proposalB",
};
