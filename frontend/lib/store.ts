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
import type { ApiResult, DataSource, InsightData } from "./api";
import { fetchPortfolioCalculate } from "./api";

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
  portfolios: Portfolio[];
  portfolioSource: DataSource;
  portfolioNote?: string;
  setPortfolios: (portfolios: Portfolio[], source: DataSource, note?: string) => void;

  // ── 분석 트리거 ──
  // '분석하기' 클릭 시에만 calculate를 돌린다(이벤트 기반). 마운트·입력 변경 자동
  // 계산은 하지 않는다 — Render 무료티어에서 첫 진입 시 불필요한 콜드 계산이 돌다
  // 120초 클라 타임아웃에 걸려 (canceled) 되던 문제를 막는다.
  calculating: boolean;
  requestAnalyze: () => void;

  // ── 스트레스 테스트 결과 ──
  stressedPortfolios: Portfolio[];
  isStressMode: boolean;
  stressAnalyzing: boolean;
  setStressedPortfolios: (portfolios: Portfolio[]) => void;
  setStressAnalyzing: (v: boolean) => void;
  clearStressMode: () => void;

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

export const useDashboardStore = create<DashboardState>((set, get) => ({
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
  portfolioSource: "fallback" as DataSource,
  portfolioNote: "포트폴리오를 계산 중입니다.",
  setPortfolios: (portfolios, source, note) =>
    set({ portfolios, portfolioSource: source, portfolioNote: note }),

  calculating: false,
  requestAnalyze: () => {
    const s = get();
    if (s.calculating) return; // 진행 중이면 중복 클릭 무시
    const customer =
      s.customers.find((c) => c.id === s.selectedCustomerId) ?? s.customers[0];
    if (!customer) return;

    set({ calculating: true });
    fetchPortfolioCalculate({
      aumEokwon: customer.aumEokwon,
      returnPct: s.ips.returnPct,
      risk: s.ips.risk,
      timeYears: s.ips.timeYears,
      liquidity: s.ips.liquidity,
      tax: s.ips.tax,
      ratePct: s.liveBase.ratePct,
      fxKrw: s.liveBase.fxKrw,
      consultationId: s.consultationId || undefined,
      clientId: customer.id,
    })
      .then((result) =>
        set({
          portfolios: result.data.portfolios,
          portfolioSource: result.source,
          portfolioNote: result.note,
        }),
      )
      .finally(() => set({ calculating: false }));
  },

  stressedPortfolios: [],
  isStressMode: false,
  stressAnalyzing: false,
  setStressedPortfolios: (portfolios) =>
    set({ stressedPortfolios: portfolios, isStressMode: true }),
  setStressAnalyzing: (v) => set({ stressAnalyzing: v }),
  clearStressMode: () =>
    set({ stressedPortfolios: [], isStressMode: false }),

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
  selectCustomer: (id) => set({ selectedCustomerId: id }),
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

  setTranscript: (transcript, source) => set({ transcript, transcriptSource: source }),
  setConsultationId: (id) => set({ consultationId: id }),
  setSttStatus: (status, note) => set({ sttStatus: status, sttNote: note }),
}));
