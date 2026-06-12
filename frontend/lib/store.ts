/**
 * 대시보드 전역 상태 (Zustand).
 * 선택 고객 · IPS 조율기 값 · 시나리오 슬라이더만 담는 최소 골격.
 */

import { create } from "zustand";
import { type Customer, CUSTOMERS, IPS_DEFAULT, SCENARIO_BASE } from "./mockData";

interface IpsState {
  returnPct: number;
  risk: "안정형" | "균형형" | "공격형";
  timeYears: number;
  liquidity: "낮음" | "중간" | "높음";
  goal: string;
  tax: string;
  legal: string;
  unique: string;
}

interface DashboardState {
  customers: Customer[];
  selectedCustomerId: string;
  selectedPortfolioId: string;
  ips: IpsState;
  scenario: { ratePct: number; fxKrw: number };

  addCustomer: (c: Customer) => void;
  selectCustomer: (id: string) => void;
  selectPortfolio: (id: string) => void;
  setIps: (patch: Partial<IpsState>) => void;
  setScenario: (patch: Partial<DashboardState["scenario"]>) => void;
  resetScenario: () => void;
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

  addCustomer: (c) => set((s) => ({ customers: [...s.customers, c] })),
  selectCustomer: (id) => set({ selectedCustomerId: id }),
  selectPortfolio: (id) => set({ selectedPortfolioId: id }),
  setIps: (patch) => set((s) => ({ ips: { ...s.ips, ...patch } })),
  setScenario: (patch) =>
    set((s) => ({ scenario: { ...s.scenario, ...patch } })),
  resetScenario: () =>
    set({
      scenario: { ratePct: SCENARIO_BASE.ratePct, fxKrw: SCENARIO_BASE.fxKrw },
    }),
}));
