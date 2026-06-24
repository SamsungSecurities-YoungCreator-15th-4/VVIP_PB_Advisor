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

// ── 백엔드 응답 타입 ───────────────────────────────────────────
interface BackendAllocationItem {
  asset_class: string;
  name: string;
  weight: number; // 이미 % 단위
}

interface BackendMetrics {
  expected_return: number | null;
  volatility: number | null;
  sharpe: number | null;
  sortino: number | null;
  mdd: number | null; // % (음수, 예: -11.2)
  after_tax_return: number | null;
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
}

interface PortfolioCalculateResponse {
  portfolios: BackendPortfolioItem[];
  calculation_session_id: string;
  risk_profile: string;
  as_of: string;
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

// ── 원화 금액 레이블 포맷 ─────────────────────────────────────
function formatKrwLabel(amount: number | undefined | null, sign: string): string {
  if (amount == null || !Number.isFinite(amount)) return "–";
  const abs = Math.abs(amount);
  if (abs >= 100_000_000) return `${sign}${(abs / 100_000_000).toFixed(2)}억원`;
  return `${sign}${Math.round(abs / 10_000).toLocaleString()}만원`;
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

  const metrics: PortfolioMetrics = {
    expectedReturnPct:    m.expected_return ?? 0,
    volatilityPct:        m.volatility ?? 0,
    sharpe:               m.sharpe ?? 0,
    sortino:              m.sortino ?? 0,
    mddPct:               Math.abs(m.mdd ?? 0),
    afterTaxReturnPct:    m.after_tax_return ?? 0,
    volatilityAmountLabel: formatKrwLabel(krw.volatility_band, "±"),
    mddAmountLabel:        formatKrwLabel(krw.mdd, "-"),
    afterTaxAmountLabel:   formatKrwLabel(krw.after_tax_return, "+"),
  };

  const toPoints = (arr?: BackendBacktestPoint[]): BacktestPoint[] =>
    (arr ?? []).map((p) => ({ date: p.date, value: p.value }));

  return {
    id,
    name: id === "current" ? "현재" : item.label,
    badge,
    weights: mapAllocationToWeights(item.allocation),
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
      { timeoutMs: 60_000 },
    );
    return live({
      portfolios: res.portfolios.map(mapPortfolioItem),
      calculationSessionId: res.calculation_session_id,
    });
  } catch (err) {
    const note =
      err instanceof ApiError && err.isTimeout
        ? "응답 시간 초과로 데모 포트폴리오를 표시합니다."
        : "백엔드 연결 실패로 데모 포트폴리오를 표시합니다.";
    return fallback({ portfolios: PORTFOLIOS, calculationSessionId: "" }, note);
  }
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
