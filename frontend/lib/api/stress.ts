/**
 * 스트레스 6대 지표 재계산 연동 — POST /portfolio/stress-metrics.
 *
 * 비중(weights)은 고정한 채, 금리·환율 슬라이더 충격 또는 위기 시나리오 버튼
 * (crisis_2008 / crisis_ru_war)을 주입해 base/stressed 6대 지표를 함께 받는다.
 * 포트폴리오 재구성(리밸런싱)은 하지 않는다 — 분석하기 담당이 /portfolio/calculate로 별도 처리.
 *
 * weights는 백엔드 canonical 자산군 키(snake_case 12종)여야 한다. 분석하기 담당이
 * /portfolio/calculate 응답의 비중을 그대로 넘겨준다. (프런트 mock 11종과는 키가 다르니 주의)
 */

import { apiPost } from "@/lib/api";
import type { PortfolioMetrics } from "@/lib/types";

export type CrisisScenario = "crisis_2008" | "crisis_ru_war";

/** 충격 입력 모드 — 슬라이더(금리·환율)와 위기 버튼은 상호 배타. */
export type StressMode =
  | { kind: "slider"; rateShock: number; fxShock: number } // 소수: 0.01=+100bp, 0.10=+10%
  | { kind: "scenario"; scenario: CrisisScenario };

export interface StressMetricsResult {
  /** 위기 시나리오 모드면 해당 키, 슬라이더 모드면 null. */
  scenario: CrisisScenario | null;
  /** 충격 전 6대 지표. */
  base: PortfolioMetrics;
  /** 충격 후 6대 지표 — 이 값을 카드에 그린다. */
  stressed: PortfolioMetrics;
  /** 자산군별 적용 충격(디버그·표시용). */
  assetShocks: Record<string, number>;
}

/** 백엔드 calculate_metrics 응답(소수 단위). */
interface RawMetrics {
  expected_return: number;
  after_tax_return: number | null;
  volatility: number;
  sharpe_ratio: number;
  sortino_ratio: number | null;
  mdd: number | null;
}

interface RawStressResponse {
  scenario: CrisisScenario | null;
  base: RawMetrics;
  stressed: RawMetrics;
  asset_shocks: Record<string, number>;
}

/** 백엔드 지표 dict(소수) → 프런트 PortfolioMetrics(%). */
export function mapMetrics(m: RawMetrics): PortfolioMetrics {
  return {
    expectedReturn: m.expected_return * 100,
    volatility: m.volatility * 100,
    sharpeRatio: m.sharpe_ratio,
    sortinoRatio: m.sortino_ratio,
    // mdd는 음수로 올 수 있어 절댓값(%)으로 보관 — 표시 측에서 ▼ 접두.
    maxDrawdown: m.mdd == null ? null : Math.abs(m.mdd) * 100,
    // 세후수익률은 소수 그대로 유지(타입 계약: 소수).
    afterTaxReturn: m.after_tax_return,
    // stress-metrics는 백테스트 시계열을 주지 않는다.
    backtestData: [],
  };
}

export interface StressMetricsOptions {
  /** 총자산(억). 세후수익률 종합과세 구간 계산에 쓰임. 기본 50억. */
  totalAssetEok?: number;
  /** 위험성향. 기본 balanced. */
  riskProfile?: "conservative" | "balanced" | "aggressive";
}

/**
 * 현재 화면 비중을 고정한 채 6대 지표를 충격 후로 재계산해 받아온다.
 * @param weights 백엔드 canonical 자산군 비중(snake_case 12종)
 * @param mode 슬라이더 충격 또는 위기 시나리오 (상호 배타)
 */
export function fetchStressMetrics(
  weights: Record<string, number>,
  mode: StressMode,
  opts: StressMetricsOptions = {},
): Promise<StressMetricsResult> {
  const portfolio: Record<string, unknown> = {
    total_asset: opts.totalAssetEok ?? 50,
    risk_profile: opts.riskProfile ?? "balanced",
  };
  let scenario: CrisisScenario | null = null;
  if (mode.kind === "slider") {
    portfolio.stress_interest_rate_shock = mode.rateShock;
    portfolio.stress_fx_shock = mode.fxShock;
  } else {
    scenario = mode.scenario;
  }

  return apiPost<RawStressResponse>("/portfolio/stress-metrics", {
    weights,
    portfolio,
    scenario,
  }).then((r) => ({
    scenario: r.scenario,
    base: mapMetrics(r.base),
    stressed: mapMetrics(r.stressed),
    assetShocks: r.asset_shocks ?? {},
  }));
}
