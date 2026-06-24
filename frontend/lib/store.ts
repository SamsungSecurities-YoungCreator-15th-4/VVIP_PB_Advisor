/**
 * 대시보드 전역 상태 (Zustand).
 * 선택 고객 · IPS 조율기 값 · 시나리오 슬라이더만 담는 최소 골격.
 */

import { create } from "zustand";
import {
  type ConsultMessage,
  type Customer,
  CONSULT_LOG,
  CUSTOMERS,
  IPS_DEFAULT,
  SCENARIO_BASE,
  TAX_THRESHOLD,
} from "./mockData";
import type { DataSource } from "./api";

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
  /** 활성 위기 시나리오 버튼. null이면 슬라이더(금리·환율) 모드.
   *  버튼과 슬라이더는 상호 배타 — 둘은 따로 동작한다. */
  activeScenario: "crisis_2008" | "crisis_ru_war" | null;
  /** 분석하기로 "확정"된 스트레스 입력. 슬라이더·위기버튼은 pending(scenario/activeScenario)
   *  이고, 분석하기를 눌러야 여기로 커밋된다. 평가손익·6대 지표는 이 applied 값으로만 계산. */
  appliedScenario: { ratePct: number; fxKrw: number };
  appliedActiveScenario: "crisis_2008" | "crisis_ru_war" | null;
  /** 분석하기를 누를 때마다 +1. 같은 값이어도 재계산을 강제하는 토큰. */
  analysisNonce: number;
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

  helpMode: boolean;
  toggleHelpMode: () => void;

  addCustomer: (c: Customer) => void;
  setCustomers: (customers: Customer[]) => void;
  selectCustomer: (id: string) => void;
  selectPortfolio: (id: string) => void;
  setIps: (patch: Partial<IpsState>) => void;
  setScenario: (patch: Partial<DashboardState["scenario"]>) => void;
  resetScenario: () => void;
  /** 위기 프리셋 — 백엔드 시나리오를 켜고, 슬라이더는 그 시대 금리·환율로 이동(표시용).
   *  분석하기 시 백엔드엔 시나리오 충격벡터가 전송되고, 슬라이더 값은 표시 컨텍스트다.
   *  슬라이더를 직접 조정하면(setScenario) activeScenario가 해제돼 슬라이더 모드로 전환된다. */
  applyCrisisPreset: (
    key: "crisis_2008" | "crisis_ru_war",
    slider: { ratePct: number; fxKrw: number },
  ) => void;
  /** 분석하기 — 현재 pending(scenario/activeScenario)을 applied로 커밋하고 nonce++. */
  runAnalysis: () => void;
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
  activeScenario: null,
  appliedScenario: { ratePct: SCENARIO_BASE.ratePct, fxKrw: SCENARIO_BASE.fxKrw },
  appliedActiveScenario: null,
  analysisNonce: 0,
  liveBase: { ratePct: SCENARIO_BASE.ratePct, fxKrw: SCENARIO_BASE.fxKrw },
  liveBaseLoaded: false,
  otherIncomeManwon: TAX_THRESHOLD.otherIncomeDefault,

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
  // 슬라이더를 직접 조정하면 위기 버튼은 해제된다(상호 배타).
  setScenario: (patch) =>
    set((s) => ({ scenario: { ...s.scenario, ...patch }, activeScenario: null })),
  resetScenario: () =>
    set((s) => ({ scenario: { ...s.liveBase }, activeScenario: null })),
  // 위기 프리셋 — 시나리오를 켜고 슬라이더를 그 시대 값으로 이동(원자적, setScenario 안 거침).
  applyCrisisPreset: (key, slider) =>
    set({ activeScenario: key, scenario: { ...slider } }),
  // 분석하기 — pending을 applied로 커밋(평가손익·6대 지표는 이때만 갱신).
  runAnalysis: () =>
    set((s) => ({
      appliedScenario: { ...s.scenario },
      appliedActiveScenario: s.activeScenario,
      analysisNonce: s.analysisNonce + 1,
    })),
  setLiveBase: (base) =>
    set((s) => ({
      liveBase: base,
      // 최초 로드 시에만 슬라이더를 실시간 값으로 스냅 (이후엔 사용자 조작 보존)
      scenario: s.liveBaseLoaded ? s.scenario : { ...base },
      // applied도 최초 1회 같이 스냅 — 로드 직후 pending≠applied로 오인(가짜 '변경됨') 방지
      appliedScenario: s.liveBaseLoaded ? s.appliedScenario : { ...base },
      liveBaseLoaded: true,
    })),
  setOtherIncome: (manwon) => set({ otherIncomeManwon: Math.max(0, manwon) }),

  setTranscript: (transcript, source) => set({ transcript, transcriptSource: source }),
  setConsultationId: (id) => set({ consultationId: id }),
  setSttStatus: (status, note) => set({ sttStatus: status, sttNote: note }),
}));
