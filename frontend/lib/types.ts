// 백엔드(FastAPI) market API 응답 타입 — backend/app/market/schemas.py 와 1:1 대응

export interface IndicatorData {
  price: number;
  change: number;
  changePct: number;
  /** 발표 시에만 수동 갱신하는 정적 지표 (기준금리·CPI) */
  isStatic?: boolean;
  /** 실시간 조회 실패 → 마지막 확인값(종가/캐시). "지연 시세"로 표시할 것 */
  isFallback?: boolean;
}

export interface MacroIndicators {
  baseRate: IndicatorData;
  treasuryYield: IndicatorData;
  krwUsd: IndicatorData;
  cpi: IndicatorData;
  kospi: IndicatorData;
  sp500: IndicatorData;
  fetchedAt: string;
}

// 자산 분류 11종 (2026-06-10 회의 확정) — backend AssetClass Literal과 1:1 동기화
// 주식 4 / 채권 3(과세 구조 기준: 일반채·분리과세채·저쿠폰채) / 대체자산 4
export type AssetClass =
  | 'domestic_equity'
  | 'overseas_dividend'
  | 'overseas_blue_chip'
  | 'overseas_growth'
  | 'general_bond'
  | 'separate_tax_bond'
  | 'low_coupon_bond'
  | 'reit'
  | 'dollar'
  | 'gold'
  | 'commodity';

export interface AssetAllocation {
  ticker: string;
  name: string;
  nameKr: string;
  weight: number; // 0~1
  assetClass: AssetClass;
  color: string;
}

export interface BacktestPoint {
  date: string;
  value: number; // 누적 수익률 (1.0 = 0%)
}

export interface PortfolioMetrics {
  expectedReturn: number; // % per year
  volatility: number; // % per year
  sharpeRatio: number;
  sortinoRatio: number | null; // 실측 하방편차 부족 시 null(N/A)
  maxDrawdown: number | null; // % — 실측 백테스트가 부족하면 null(N/A)
  afterTaxReturn: number | null; // 세후 기대수익률(소수). 총자산 필요 → 미계산 시 null
  backtestData: BacktestPoint[];
}

export interface PortfolioProposal {
  id: 'current' | 'proposalA' | 'proposalB';
  name: string;
  nameKr: string;
  description: string;
  theme: string;
  allocations: AssetAllocation[];
  metrics: PortfolioMetrics | null;
}

// 스트레스 조율기(슬라이더) 적용 결과 — 기준/충격 적용 후 전체 지표 쌍
export interface StressedPortfolio {
  id: 'current' | 'proposalA' | 'proposalB';
  nameKr: string;
  base: PortfolioMetrics;
  stressed: PortfolioMetrics;
  dividendIncome: number; // 포트폴리오 연간 이자·배당 금융소득(억). 종합과세 기준선 점검용
  // 절세 계좌 배치 활용도(법정 한도 대비 기납입액, 만원) — backend tax_optimizer
  accountAllocation?: AccountSlot[];
  // 절세 제안 4종의 실제 절감액(만원) — backend tax_optimizer
  taxAdvice?: TaxAdviceCard[];
}

// 절세 계좌 배치 한 칸 — backend AccountSlot과 1:1. used/limit가 null이면 한도 개념 없음.
export interface AccountSlot {
  key: "isa" | "pension" | "general";
  usedManwon: number | null;
  limitManwon: number | null;
}

// 절세 제안 한 건 — backend TaxAdviceCard와 1:1.
// applicable=false면 합산 제외. ineligibleReason 있으면 제도상 부적합(사유 표시),
// 없으면 절감 효과 없음/한도 소진(비노출 권장).
export type TaxAdviceKey =
  | "isa"
  | "pension_credit"
  | "separate_bond"
  | "low_tax_dividend"
  | "overseas_exemption"
  | "tax_loss";

export interface TaxAdviceCard {
  key: TaxAdviceKey;
  savingManwon: number;
  applicable: boolean;
  transferableManwon: number; // ISA·연금 등 이전/납입 가능 금액(만원)
  ineligibleReason?: string | null; // 제도상 부적합 사유
}

// 과거 주요 경제 위기 재현 시나리오 — 위기 기간 실제 수익률 기반 예상 P&L
export interface HistoricalCrisis {
  id: string;
  name: string;
  nameKr: string;
  period: string; // 예: "2008-09 ~ 2009-03"
  description: string;
  icon: string;
  assetReturns: Record<string, number>; // asset class → 위기 기간 실현 수익률
  results: Record<string, number>; // portfolio id → 예상 P&L (기간 수익률, 음수 = 손실)
}

export interface StressScenario {
  id: string;
  name: string;
  nameKr: string;
  description: string;
  icon: string;
  shocks: Record<string, number>; // asset class → shock multiplier
  results: Record<string, number>; // portfolio id → expected return change (p.p.)
}
