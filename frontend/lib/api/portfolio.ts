/**
 * 포트폴리오 계산 연동 — POST /portfolio/calculate.
 *
 * store IPS + liveBase(금리·환율) → 백엔드 계산 → Portfolio[] 반환.
 * 실패 시 mock PORTFOLIOS 폴백(배지 표시).
 */

import { ApiError, apiPost } from "@/lib/api";
import { PORTFOLIOS, type BacktestPoint, type Portfolio, type PortfolioMetrics } from "@/lib/mockData";
import type { CalcUnitWeights } from "@/lib/assetMapping";
import { type ApiResult, fallback, live } from "./result";
import type { CorrelationHeatmapResponse, PortfolioTaxResponse, StressTaxData, StressTaxGauge, TaxWaterfallResponse } from "./types";

// ── 백엔드 응답 타입 ───────────────────────────────────────────
interface BackendAllocationItem {
  asset_class: string;
  name: string;
  weight: number; // 이미 % 단위
}

interface BackendMetricsRange {
  lower: number;
  center: number;
  upper: number;
  unit: string;
}

interface BackendMetrics {
  expected_return: number | null;
  volatility: number | null;
  sharpe: number | null;
  sortino: number | null;
  mdd: number | null; // % (음수, 예: -11.2)
  after_tax_return: number | null;
  after_tax_return_range?: BackendMetricsRange | null;
  mdd_range?: BackendMetricsRange | null;
}

interface BackendMetricsKrw {
  total_asset?: number;
  volatility_band?: number; // 원 (양수)
  mdd?: number;             // 원 (음수)
  after_tax_return?: number; // 원 (양수)
}

interface BackendBacktestPoint {
  date: string;
  value: number;
  base_index: number;
}

interface BackendBenchmarkItem {
  metadata: Record<string, unknown>;
  backtest: BackendBacktestPoint[];
}

interface BackendPortfolioTax {
  waterfall?: {
    gross_return: number;
    dividend_interest_tax: number;
    capital_gains_tax: number;
    transaction_cost: number;
    fx_cost: number;
    after_tax: number;
  };
  saved_vs_current?: number;
  summary?: string;
  calculation_notes?: string[];
  financial_income_tax_gauge?: StressTaxGauge | null;
}

interface BackendPortfolioItem {
  kind: string; // "current" | "A" | "B"
  label: string;
  badge: string | null;
  allocation: BackendAllocationItem[];
  metrics: BackendMetrics;
  metrics_krw?: BackendMetricsKrw;
  backtest?: BackendBacktestPoint[];
  benchmarks?: {
    kospi?: BackendBenchmarkItem;
    sp500?: BackendBenchmarkItem;
    msci_acwi?: BackendBenchmarkItem;
  };
  tax?: BackendPortfolioTax;
}

interface PortfolioCalculateResponse {
  portfolios: BackendPortfolioItem[];
  calculation_session_id: string;
  risk_profile: string;
  as_of: string;
  correlation_heatmap?: {
    assets: { asset_class: string; name: string }[];
    matrix: number[][];
    value_type?: string;
  };
  // 포트폴리오별 절세 맵 {current, portfolio_a, portfolio_b} — 각 값은 build_tax_optimizer_payload 출력.
  tax_optimizer?: Record<string, StressTaxData>;
}

// ── IPS 값 변환 ────────────────────────────────────────────────
type RiskProfile = "conservative" | "balanced" | "aggressive";
type TaxSensitivity = "low" | "medium" | "high";
type LiquidityNeed = "low" | "mid" | "high";

function mapRisk(risk: string): RiskProfile {
  if (risk === "안정형") return "conservative";
  if (risk === "공격형") return "aggressive";
  return "balanced";
}

function mapTax(tax: string): TaxSensitivity {
  if (tax.includes("낮") || tax.includes("저")) return "low";
  if (tax.includes("높") || tax.includes("고")) return "high";
  return "medium";
}

function mapLiquidity(liquidity: string): LiquidityNeed {
  if (liquidity === "낮음") return "low";
  if (liquidity === "높음") return "high";
  return "mid";
}

// ── 자산군 매핑 (백엔드 snake_case → CalcUnitId) ────────────────
// overseas_blue_chip(S&P500)·overseas_growth(NASDAQ) 모두 해외성장주 버킷으로 합산.
// 두 CalcUnitId 모두 CALC_TO_DISPLAY에서 "해외성장주"로 묶이므로 도넛 표시는 동일.
const ASSET_TO_CALC_UNIT: Record<string, keyof CalcUnitWeights> = {
  domestic_equity:   "domesticEquity",
  overseas_dividend: "overseasDividendEquity",
  overseas_blue_chip:"overseasGrowthEquity",
  overseas_growth:   "emergingEquity",
  general_bond:      "domesticBond",
  separate_tax_bond: "separateTaxBond",
  low_coupon_bond:   "lowCouponBond",
  reit:              "reits",
  gold:              "gold",
  commodity:         "infraFund",
  dollar:            "overseasBond",
  cash:              "domesticBond",
};

function mapAllocationToWeights(allocation: BackendAllocationItem[]): CalcUnitWeights {
  const weights: CalcUnitWeights = {
    domesticEquity: 0, overseasDividendEquity: 0, overseasGrowthEquity: 0,
    emergingEquity: 0, domesticBond: 0, overseasBond: 0, lowCouponBond: 0,
    separateTaxBond: 0, reits: 0, gold: 0, infraFund: 0,
  };
  for (const item of allocation) {
    const key = ASSET_TO_CALC_UNIT[item.asset_class];
    if (key) weights[key] += item.weight;
  }
  return weights;
}

// ── 범위 데이터가 붙은 확장 메트릭 타입 (mockData 미수정, 캐스트용) ──
type MetricsWithRange = PortfolioMetrics & {
  afterTaxReturnRangeLabel?: string;
  mddRangeLabel?: string;
};

// ── 원화 금액 레이블 포맷 ─────────────────────────────────────
function formatKrwLabel(amount: number | undefined | null, sign: string): string {
  if (amount == null || !Number.isFinite(amount)) return "–";
  const abs = Math.abs(amount);
  // 실제 값이 음수이면 sign 파라미터를 무시하고 "-"로 덮어쓴다
  const effectiveSign = amount < 0 ? "-" : sign;
  if (abs >= 100_000_000) return `${effectiveSign}${(abs / 100_000_000).toFixed(2)}억원`;
  return `${effectiveSign}${Math.round(abs / 10_000).toLocaleString()}만원`;
}

// ── 응답 → Portfolio 매핑 ──────────────────────────────────────
function mapPortfolioItem(item: BackendPortfolioItem): Portfolio {
  const id =
    item.kind === "current" ? "current" : item.kind === "A" ? "a" : "b";
  const badge =
    item.badge != null
      ? (item.badge as Portfolio["badge"])
      : id === "current"
        ? "현재"
        : id === "a"
          ? "베스트"
          : "추천";

  const m = item.metrics;
  const krw = item.metrics_krw ?? {};

  const afterTaxRange = m.after_tax_return_range ?? null;
  const mddRange = m.mdd_range ?? null;

  const toRangeLabel = (range: BackendMetricsRange | null): string | undefined => {
    if (!range) return undefined;
    const half = Math.abs(range.upper - range.lower) / 2;
    return `±${half.toFixed(1)}%p`;
  };

  const metrics: MetricsWithRange = {
    expectedReturnPct:    m.expected_return ?? 0,
    volatilityPct:        m.volatility ?? 0,
    sharpe:               m.sharpe ?? 0,
    sortino:              m.sortino ?? 0,
    mddPct:               Math.abs(mddRange?.center ?? m.mdd ?? 0),
    afterTaxReturnPct:    afterTaxRange?.center ?? m.after_tax_return ?? 0,
    volatilityAmountLabel: formatKrwLabel(krw.volatility_band, "±"),
    mddAmountLabel:        formatKrwLabel(krw.mdd, "-"),
    afterTaxAmountLabel:   formatKrwLabel(krw.after_tax_return, "+"),
    afterTaxReturnRangeLabel: toRangeLabel(afterTaxRange),
    mddRangeLabel: toRangeLabel(mddRange),
  };

  const toPoints = (arr?: BackendBacktestPoint[]): BacktestPoint[] =>
    (arr ?? []).map((p) => ({ date: p.date, value: p.value }));

  return {
    id,
    name: id === "current" ? "현재" : item.label,
    badge,
    allocation: item.allocation,           // 백엔드 8개 자산군 원본 (도넛용)
    weights: mapAllocationToWeights(item.allocation), // 구형 CalcUnitWeights (히트맵 필터링용)
    metrics,
    backtest: toPoints(item.backtest),
    benchmarks: item.benchmarks
      ? {
          kospi: toPoints(item.benchmarks.kospi?.backtest),
          sp500: toPoints(item.benchmarks.sp500?.backtest),
          msciAcwi: toPoints(item.benchmarks.msci_acwi?.backtest),
        }
      : undefined,
  };
}

// ── stress-test 응답 타입 (calculate와 portfolios 구조 동일) ──
interface PortfolioStressTestResponse {
  portfolios: BackendPortfolioItem[];
  calculation_session_id: string;
  risk_profile: string;
  as_of: string;
}


// ── 요청 옵션 ─────────────────────────────────────────────────
export interface PortfolioCalcOptions {
  aumEokwon: number;
  returnPct: number;
  risk: "안정형" | "균형형" | "공격형";
  timeYears: number;
  liquidity: "낮음" | "중간" | "높음";
  tax: string;
  ratePct: number;
  fxKrw: number;
  consultationId?: string;
  clientId?: string;
}

export interface PortfolioCalcData {
  portfolios: Portfolio[];
  calculationSessionId: string;
  correlationHeatmap: CorrelationHeatmapResponse | null;
  portfolioTax: Record<string, PortfolioTaxResponse> | null;
  // 포트폴리오별 절세 맵 {current, portfolio_a, portfolio_b}. 스트레스 미진입 시 절세 화면 소스.
  taxOptimizer: Record<string, StressTaxData> | null;
}

function extractPortfolioTax(
  items: BackendPortfolioItem[],
): Record<string, PortfolioTaxResponse> | null {
  const result: Record<string, PortfolioTaxResponse> = {};
  let hasAny = false;
  for (const item of items) {
    if (item.tax?.waterfall) {
      result[item.kind] = {
        waterfall: item.tax.waterfall as TaxWaterfallResponse,
        saved_vs_current: item.tax.saved_vs_current ?? 0,
        summary: item.tax.summary ?? "",
        calculation_notes: item.tax.calculation_notes ?? [],
        gauge: item.tax.financial_income_tax_gauge ?? null,
      };
      hasAny = true;
    }
  }
  return hasAny ? result : null;
}

// ── 메인 함수 ─────────────────────────────────────────────────
export async function fetchPortfolioCalculate(
  opts: PortfolioCalcOptions,
): Promise<ApiResult<PortfolioCalcData>> {
  const body = {
    client_id: opts.clientId ?? null,
    consultation_id: opts.consultationId ?? null,
    ips: {
      total_asset: opts.aumEokwon * 100_000_000,
      unique_need_amount: 0,
      unique_asset: "general_bond",
      target_after_tax_return: opts.returnPct > 0 ? opts.returnPct / 100 : undefined,
      risk_profile: mapRisk(opts.risk),
      investment_horizon_years: Math.max(1, Math.min(50, opts.timeYears)),
      tax_sensitivity: mapTax(opts.tax),
      liquidity_need: mapLiquidity(opts.liquidity),
    },
    scenario: {
      base_interest_rate: opts.ratePct / 100,
      base_fx_rate_krw_per_usd: opts.fxKrw,
      stress_interest_rate_shock: 0.01,
      stress_fx_shock: 0.1,
      rrttllu: {},
    },
  };

  try {
    const res = await apiPost<PortfolioCalculateResponse>(
      "/portfolio/calculate",
      body,
      // Render Free의 약한 CPU에서 시뮬레이션이 60초를 넘겨 취소되던 문제 → 여유 상향.
      { timeoutMs: 120_000 },
    );
    return live({
      portfolios: res.portfolios.map(mapPortfolioItem),
      calculationSessionId: res.calculation_session_id,
      correlationHeatmap: (res.correlation_heatmap as CorrelationHeatmapResponse) ?? null,
      portfolioTax: extractPortfolioTax(res.portfolios),
      taxOptimizer: res.tax_optimizer ?? null,
    });
  } catch (err) {
    const note =
      err instanceof ApiError && err.isTimeout
        ? "응답 시간 초과로 데모 포트폴리오를 표시합니다."
        : "백엔드 연결 실패로 데모 포트폴리오를 표시합니다.";
    return fallback(
      { portfolios: PORTFOLIOS, calculationSessionId: "", correlationHeatmap: null, portfolioTax: null, taxOptimizer: null },
      note,
    );
  }
}

// ── stress-metrics (금리·환율 충격 → 기준/스트레스 지표 비교) ──
interface StressMetricsBackendMetrics {
  expected_return?: number | null;
  mdd?: number | null;
  after_tax_return?: number | null;
  volatility?: number | null;
  sharpe?: number | null;
  sortino?: number | null;
}

interface StressMetricsBackendResponse {
  // calculate와 동일한 전체 포트폴리오 데이터
  portfolios?: BackendPortfolioItem[];
  correlation_heatmap?: PortfolioCalculateResponse["correlation_heatmap"];
  tax_optimizer?: Record<string, StressTaxData>;
  // 구형 충격 지표 (portfolios 없을 때 폴백용)
  base?: StressMetricsBackendMetrics;
  stressed?: StressMetricsBackendMetrics;
  portfolio_shock?: number;
  base_tax?: StressTaxData | null;
  stressed_tax?: StressTaxData | null;
  // 구형 응답에서의 current 포트폴리오 스트레스 백테스트
  stressed_backtest?: BackendBacktestPoint[];
}

/** fetchStressMetrics 반환값 — calculate와 동일한 전체 대시보드 데이터 */
export interface StressMetricsResult {
  portfolios: Portfolio[];
  stressTax: { base: StressTaxData; stressed: StressTaxData } | null;
  correlationHeatmap: PortfolioCalcData["correlationHeatmap"];
  portfolioTax: PortfolioCalcData["portfolioTax"];
  taxOptimizer: PortfolioCalcData["taxOptimizer"];
}

export interface StressMetricsOptions {
  aumEokwon: number;
  returnPct: number;
  risk: "안정형" | "균형형" | "공격형";
  timeYears: number;
  liquidity: "낮음" | "중간" | "높음";
  tax: string;
  /** 현재 시나리오 슬라이더 값 */
  ratePct: number;
  fxKrw: number;
  /** 실시간 기준값 — 슬라이더 충격 계산의 기준점 */
  liveRatePct: number;
  liveFxKrw: number;
  /** 프리셋 버튼 선택 여부: crisis → crisis_2008, war → crisis_ru_war, null → 슬라이더 */
  stressPreset: "current" | "crisis" | "war" | null;
}

/** CalcUnitWeights(% 단위) → 백엔드 stress-metrics weights(소수 단위) 변환 */
function mapFrontendWeightsToBackend(weights: CalcUnitWeights): Record<string, number> {
  return {
    domestic_equity:    weights.domesticEquity         / 100,
    overseas_dividend:  weights.overseasDividendEquity / 100,
    overseas_blue_chip: weights.overseasGrowthEquity   / 100,
    overseas_growth:    weights.emergingEquity          / 100,
    general_bond:       weights.domesticBond            / 100,
    separate_tax_bond:  weights.separateTaxBond         / 100,
    low_coupon_bond:    weights.lowCouponBond           / 100,
    reit:               weights.reits                   / 100,
    gold:               weights.gold                    / 100,
    commodity:          weights.infraFund               / 100,
    dollar:             weights.overseasBond            / 100,
  };
}

/**
 * POST /portfolio/stress-metrics
 * 충격 후 기준/스트레스 지표를 받아 stressedPortfolios(Portfolio[])로 변환한다.
 * weights 미전송 시 백엔드가 cash 100%로 폴백해 충격량이 0이 되므로 반드시 전송.
 */
export async function fetchStressMetrics(
  opts: StressMetricsOptions,
  currentPortfolios: Portfolio[],
): Promise<StressMetricsResult> {
  const scenarioKey =
    opts.stressPreset === "crisis"
      ? ("crisis_2008" as const)
      : opts.stressPreset === "war"
        ? ("crisis_ru_war" as const)
        : null;

  // 슬라이더 모드: 슬라이더 값과 실시간 기준값의 차이를 충격으로 변환
  const rateShock = scenarioKey
    ? 0
    : (opts.ratePct - opts.liveRatePct) / 100; // %p → 소수
  const fxShock = scenarioKey
    ? 0
    : (opts.fxKrw - opts.liveFxKrw) / Math.max(opts.liveFxKrw, 1); // 상대 변화율

  // 현재 포트폴리오 비중을 백엔드 포맷으로 변환해서 전송 — 없으면 백엔드가 cash 100% 폴백
  const currentPortfolio = currentPortfolios.find((p) => p.id === "current");
  const backendWeights = currentPortfolio
    ? mapFrontendWeightsToBackend(currentPortfolio.weights)
    : undefined;

  const body = {
    weights: backendWeights,
    portfolio: {
      total_asset: opts.aumEokwon * 100_000_000,
      unique_need_amount: 0,
      unique_asset: "general_bond",
      target_after_tax_return:
        opts.returnPct > 0 ? opts.returnPct / 100 : undefined,
      risk_profile: mapRisk(opts.risk),
      investment_horizon_years: Math.max(1, Math.min(50, opts.timeYears)),
      tax_sensitivity: mapTax(opts.tax),
      liquidity_need: mapLiquidity(opts.liquidity),
      stress_interest_rate_shock: rateShock,
      stress_fx_shock: fxShock,
    },
    scenario: scenarioKey,
  };

  const res = await apiPost<StressMetricsBackendResponse>(
    "/portfolio/stress-metrics",
    body,
    // stress-metrics는 calculate의 추천 엔진(find_recommended_portfolios)을 그대로
    // 돌린 뒤 base/stressed 지표·벤치마크까지 추가 계산해 calculate보다 무겁다.
    // Render Free 약한 CPU에서 60초를 넘겨 끊기던 문제 → calculate(120s)와 동일하게 상향.
    { timeoutMs: 120_000 },
  );

  // 백엔드가 calculate와 동일한 전체 portfolios를 반환하면 그대로 사용.
  // 구형 응답(portfolio_shock 근사)은 portfolios 필드가 없을 때만 폴백.
  let portfolios: Portfolio[];
  if (res.portfolios?.length) {
    portfolios = res.portfolios.map(mapPortfolioItem);
  } else {
    const stressed = res.stressed ?? {};
    const portfolioShockDeltaPct = (res.portfolio_shock ?? 0) * 100;
    portfolios = currentPortfolios.map((p) => {
      if (p.id === "current") {
        return {
          ...p,
          metrics: {
            ...p.metrics,
            expectedReturnPct: stressed.expected_return ?? p.metrics.expectedReturnPct,
            mddPct: Math.abs(stressed.mdd ?? -p.metrics.mddPct),
            afterTaxReturnPct: stressed.after_tax_return ?? p.metrics.afterTaxReturnPct,
            volatilityPct: stressed.volatility ?? p.metrics.volatilityPct,
            sharpe: stressed.sharpe ?? p.metrics.sharpe,
            sortino: stressed.sortino ?? p.metrics.sortino,
          },
          backtest: res.stressed_backtest
            ? res.stressed_backtest.map((pt) => ({ date: pt.date, value: pt.value }))
            : p.backtest,
        };
      }
      // 구형 응답에서 A/B는 per-portfolio 값이 없으므로 current 기준 충격 비율로 근사
      const shockRatio = (res.portfolio_shock ?? 0); // 소수 단위
      return {
        ...p,
        metrics: {
          ...p.metrics,
          expectedReturnPct: p.metrics.expectedReturnPct + portfolioShockDeltaPct,
          afterTaxReturnPct: p.metrics.afterTaxReturnPct + portfolioShockDeltaPct,
          volatilityPct: p.metrics.volatilityPct * (1 + Math.abs(shockRatio)),
          mddPct: p.metrics.mddPct * (1 + Math.abs(shockRatio)),
        },
      };
    });
  }

  const stressTax =
    res.base_tax && res.stressed_tax
      ? { base: res.base_tax, stressed: res.stressed_tax }
      : null;

  return {
    portfolios,
    stressTax,
    correlationHeatmap: (res.correlation_heatmap as PortfolioCalcData["correlationHeatmap"]) ?? null,
    portfolioTax: res.portfolios ? extractPortfolioTax(res.portfolios) : null,
    taxOptimizer: res.tax_optimizer ?? null,
  };
}

// ── 스트레스 테스트 (슬라이더 시나리오 값으로 전체 재계산) ──────
export async function fetchPortfolioStressTest(
  opts: PortfolioCalcOptions,
): Promise<Portfolio[]> {
  const body = {
    client_id: opts.clientId ?? null,
    consultation_id: opts.consultationId ?? null,
    ips: {
      total_asset: opts.aumEokwon * 100_000_000,
      unique_need_amount: 0,
      unique_asset: "general_bond",
      target_after_tax_return: opts.returnPct > 0 ? opts.returnPct / 100 : undefined,
      risk_profile: mapRisk(opts.risk),
      investment_horizon_years: Math.max(1, Math.min(50, opts.timeYears)),
      tax_sensitivity: mapTax(opts.tax),
      liquidity_need: mapLiquidity(opts.liquidity),
    },
    scenario: {
      base_interest_rate: opts.ratePct / 100,
      base_fx_rate_krw_per_usd: opts.fxKrw,
      stress_interest_rate_shock: 0.01,
      stress_fx_shock: 0.1,
      rrttllu: {},
    },
  };

  const res = await apiPost<PortfolioStressTestResponse>(
    "/portfolio/stress-test",
    body,
    { timeoutMs: 90_000 },
  );
  return res.portfolios.map(mapPortfolioItem);
}
