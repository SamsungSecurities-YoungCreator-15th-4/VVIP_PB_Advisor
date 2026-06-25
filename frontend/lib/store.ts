/**
 * 대시보드 전역 상태 (Zustand).
 * 선택 고객 · IPS 조율기 값 · 시나리오 슬라이더만 담는 최소 골격.
 */

import { create } from "zustand";
import {
  type ConsultMessage,
  type Customer,
  type MacroIndicator,
  type Portfolio,
  CONSULT_LOG,
  CUSTOMERS,
  IPS_DEFAULT,
  MACRO_INDICATORS,
  PORTFOLIOS,
  SCENARIO_BASE,
  TAX_THRESHOLD,
} from "./mockData";
import type {
  ApiResult,
  DataSource,
  InsightData,
  CorrelationHeatmapResponse,
  PortfolioTaxResponse,
  StressTaxData,
} from "./api";

export interface IpsState {
  returnPct: number;
  risk: "안정형" | "균형형" | "공격형";
  timeYears: number;
  liquidity: "낮음" | "중간" | "높음";
  goal: string;
  tax: string;
  legal: string;
  unique: string;
}

/** STT 상담 연동 상태(비동기 흐름·출처 표시용). */
export type SttStatus = "idle" | "uploading" | "done" | "error";

interface DashboardState {
  customers: Customer[];
  selectedCustomerId: string;
  selectedPortfolioId: string;
  ips: IpsState;
  scenario: { ratePct: number; fxKrw: number };
  /** 실시간 현재값 (금리·환율) — 슬라이더 기준점·델타 계산의 기준.
   *  백엔드 /api/macro-indicators 로드 전엔 목 기준값으로 시작한다. */
  liveBase: { ratePct: number; fxKrw: number };
  liveBaseLoaded: boolean;
  /** 고객의 다른 금융소득(연 이자·배당, 만원) — 종합과세 기준선 점검 입력값 */
  otherIncomeManwon: number;

  // ── STT/상담 연동 상태 ──
  /** 화면에 표시하는 상담 전사. 초기값은 mock(CONSULT_LOG). */
  transcript: ConsultMessage[];
  /** 전사 데이터 출처(mock 초기 표시 = fallback). */
  transcriptSource: DataSource;
  /** STT 로 확보한 실 consultation_id(RAG·tax 재사용). 없으면 빈 문자열. */
  consultationId: string;
  sttStatus: SttStatus;
  sttNote?: string;

  // ── 포트폴리오 계산 결과 ──
  /** 항상 화면에 표시되는 단일 포트폴리오 배열 (base·stress 모드 모두 여기서 읽는다) */
  portfolios: Portfolio[];
  /** 마지막 /portfolio/calculate 결과 — stress PnL 델타 계산의 기준선 */
  basePortfolios: Portfolio[];
  portfolioSource: DataSource;
  portfolioNote?: string;
  /** calculate 결과로 portfolios·basePortfolios 동시 갱신, isStressMode: false */
  setPortfolios: (
    portfolios: Portfolio[],
    source: DataSource,
    note?: string,
  ) => void;
  /** stress-metrics 결과를 portfolios에 반영 (basePortfolios는 유지), isStressMode: true */
  setStressPortfolios: (portfolios: Portfolio[]) => void;

  // ── 스트레스 모드 상태 ──
  isStressMode: boolean;
  stressPreset: "current" | "crisis" | "war" | null;
  setStressPreset: (preset: "current" | "crisis" | "war" | null) => void;
  /** portfolios를 basePortfolios로 복원, isStressMode: false */
  clearStressMode: () => void;

  // ── 히트맵·절세 데이터 ──
  correlationHeatmap: CorrelationHeatmapResponse | null;
  setCorrelationHeatmap: (h: CorrelationHeatmapResponse | null) => void;
  /** 포트폴리오 kind("current" | "A" | "B") 별 절세 데이터 */
  portfolioTax: Record<string, PortfolioTaxResponse> | null;
  setPortfolioTax: (tax: Record<string, PortfolioTaxResponse>) => void;
  /** stress-metrics 응답의 base_tax/stressed_tax 쌍 — TaxSection 연동용 */
  stressTax: { base: StressTaxData; stressed: StressTaxData } | null;
  setStressTax: (
    tax: { base: StressTaxData; stressed: StressTaxData } | null,
  ) => void;
  /** calculate 응답의 tax_optimizer — 스트레스 미진입 시 절세 제안·종합과세 게이지 소스 */
  taxOptimizer: Record<string, StressTaxData> | null;
  setTaxOptimizer: (tax: Record<string, StressTaxData> | null) => void;

  // ── 분석하기 버튼 상태 ──
  analyzing: boolean;
  setAnalyzing: (v: boolean) => void;
  /** IPS·시나리오 기준선 — 마지막 분석 시점을 기록해 다음 분석 시 변화 여부 판단에 사용 */
  lastAnalyzedIps: IpsState | null;
  lastAnalyzedScenario: { ratePct: number; fxKrw: number } | null;
  setAnalysisBaseline: (
    ips: IpsState,
    scenario: { ratePct: number; fxKrw: number },
  ) => void;

  // ── 상단바 실시간 시장 지표 ──
  // MacroTicker 가 /api/macro-indicators 로 받은 실데이터를 여기에 올려, PDF 등
  // 다른 화면이 같은 값을 읽게 한다(미로드·실패 시엔 목 기준값으로 시작).
  macroIndicators: MacroIndicator[];
  setMacroIndicators: (rows: MacroIndicator[]) => void;

  // ── AI 인사이트 결과 ──
  insightResult: ApiResult<InsightData> | null;
  setInsightResult: (result: ApiResult<InsightData>) => void;

  helpMode: boolean;
  toggleHelpMode: () => void;

  addCustomer: (c: Customer) => void;
  setCustomers: (customers: Customer[]) => void;
  selectCustomer: (id: string) => void;
  selectPortfolio: (id: string) => void;
  setIps: (patch: Partial<IpsState>) => void;
  setScenario: (patch: Partial<DashboardState["scenario"]>) => void;
  resetScenario: () => void;
  /** 실시간 현재값 주입 — 최초 1회는 슬라이더(scenario)도 실시간 값으로 맞춘다. */
  setLiveBase: (base: { ratePct: number; fxKrw: number }) => void;
  setOtherIncome: (manwon: number) => void;

  setTranscript: (transcript: ConsultMessage[], source: DataSource) => void;
  setConsultationId: (id: string) => void;
  setSttStatus: (status: SttStatus, note?: string) => void;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  customers: [...CUSTOMERS],
  selectedCustomerId: CUSTOMERS[0].id,
  selectedPortfolioId: "a",
  ips: {
    returnPct: IPS_DEFAULT.returnPct,
    risk: IPS_DEFAULT.risk,
    timeYears: IPS_DEFAULT.timeYears,
    liquidity: IPS_DEFAULT.liquidity,
    goal: IPS_DEFAULT.goal,
    tax: IPS_DEFAULT.tax,
    legal: IPS_DEFAULT.legal,
    unique: IPS_DEFAULT.unique,
  },
  scenario: { ratePct: SCENARIO_BASE.ratePct, fxKrw: SCENARIO_BASE.fxKrw },
  liveBase: { ratePct: SCENARIO_BASE.ratePct, fxKrw: SCENARIO_BASE.fxKrw },
  liveBaseLoaded: false,
  otherIncomeManwon: TAX_THRESHOLD.otherIncomeDefault,

  // 초기 포트폴리오는 mock(데모) — 출처를 fallback 으로 둬 배지로 명시한다.
  portfolios: PORTFOLIOS,
  basePortfolios: PORTFOLIOS,
  portfolioSource: "fallback" as DataSource,
  portfolioNote: "포트폴리오를 계산 중입니다.",
  setPortfolios: (portfolios, source, note) =>
    set({
      portfolios,
      basePortfolios: portfolios,
      portfolioSource: source,
      portfolioNote: note,
      isStressMode: false,
    }),
  setStressPortfolios: (portfolios) => set({ portfolios, isStressMode: true }),

  isStressMode: false,
  stressPreset: "current",
  setStressPreset: (preset) => set({ stressPreset: preset }),
  clearStressMode: () =>
    set((s) => ({ portfolios: s.basePortfolios, isStressMode: false })),

  correlationHeatmap: null,
  setCorrelationHeatmap: (h) => set({ correlationHeatmap: h }),
  portfolioTax: null,
  setPortfolioTax: (tax) => set({ portfolioTax: tax }),
  stressTax: null,
  setStressTax: (tax) => set({ stressTax: tax }),
  taxOptimizer: null,
  setTaxOptimizer: (tax) => set({ taxOptimizer: tax }),

  analyzing: false,
  setAnalyzing: (v) => set({ analyzing: v }),
  lastAnalyzedIps: null,
  lastAnalyzedScenario: null,
  setAnalysisBaseline: (ips, scenario) =>
    set({ lastAnalyzedIps: ips, lastAnalyzedScenario: scenario }),

  macroIndicators: MACRO_INDICATORS,
  setMacroIndicators: (rows) => set({ macroIndicators: rows }),

  insightResult: null,
  setInsightResult: (result) => set({ insightResult: result }),

  // 초기 상담 전사는 mock(데모) — 출처를 fallback 으로 둬 배지로 명시한다.
  transcript: CONSULT_LOG,
  transcriptSource: "fallback",
  consultationId: "",
  sttStatus: "idle",
  sttNote: undefined,
  helpMode: false,

  toggleHelpMode: () => set((s) => ({ helpMode: !s.helpMode })),
  addCustomer: (c) => set((s) => ({ customers: [...s.customers, c] })),
  setCustomers: (customers) =>
    set((s) => ({
      customers,
      selectedCustomerId: customers.some((c) => c.id === s.selectedCustomerId)
        ? s.selectedCustomerId
        : (customers[0]?.id ?? s.selectedCustomerId),
    })),
  selectCustomer: (id) =>
    set((s) => ({
      selectedCustomerId: id,
      // 고객 전환 시 이전 고객의 분석 결과·스트레스 상태 전체 초기화
      portfolioSource: "fallback" as DataSource,
      portfolios: PORTFOLIOS,
      basePortfolios: PORTFOLIOS,
      portfolioNote: undefined,
      correlationHeatmap: null,
      portfolioTax: null,
      stressTax: null,
      taxOptimizer: null,
      insightResult: null,
      isStressMode: false,
      stressPreset: "current",
      scenario: { ...s.liveBase }, // 슬라이더도 live 기준으로 초기화 → 자동분석는 항상 calculate
    })),
  selectPortfolio: (id) => set({ selectedPortfolioId: id }),
  setIps: (patch) => set((s) => ({ ips: { ...s.ips, ...patch } })),
  setScenario: (patch) =>
    set((s) => ({ scenario: { ...s.scenario, ...patch } })),
  resetScenario: () => set((s) => ({ scenario: { ...s.liveBase } })),
  setLiveBase: (base) =>
    set((s) => ({
      liveBase: base,
      // 최초 로드 시에만 슬라이더를 실시간 값으로 스냅 (이후엔 사용자 조작 보존)
      scenario: s.liveBaseLoaded ? s.scenario : { ...base },
      liveBaseLoaded: true,
    })),
  setOtherIncome: (manwon) => set({ otherIncomeManwon: Math.max(0, manwon) }),

  setTranscript: (transcript, source) =>
    set({ transcript, transcriptSource: source }),
  setConsultationId: (id) => set({ consultationId: id }),
  setSttStatus: (status, note) => set({ sttStatus: status, sttNote: note }),
}));
