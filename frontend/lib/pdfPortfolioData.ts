/**
 * PDF 포트폴리오·성과·자산배분·거시지표 섹션 어댑터
 * store 데이터를 PDF 렌더링 shape으로 변환한다. pdfTaxData.ts와 동일한 패턴.
 *
 * 추적성: 모든 값은 useDashboardStore의 실시간 데이터 소스다.
 *   - 자산배분 → Portfolio.allocation(백엔드 실데이터) 또는 toDisplayAllocation 폴백
 *   - 거시지표 → MacroIndicator.direction/change (MacroTicker가 올린 실데이터)
 *   - 성과지표 → Portfolio.metrics (calculate 응답)
 */
import type { Portfolio, MacroIndicator } from "@/lib/mockData";
import type { CorrelationHeatmapResponse } from "@/lib/api/types";
import {
  BACKEND_ASSET_COLORS,
  DISPLAY_GROUP_COLORS,
  DISPLAY_GROUPS,
  toDisplayAllocation,
} from "@/lib/assetMapping";

const TEXT = "#111827";
const UP = "#F04452";
const BRAND = "#0050D6";

// ── 자산 배분 ──────────────────────────────────────────────────────────────────

export type PdfAssetSlice = { label: string; weight: number; color: string };

/**
 * 포트폴리오 자산 배분 슬라이스.
 * PortfolioSection과 동일하게 pf.allocation(백엔드 실데이터) 우선,
 * 없으면 toDisplayAllocation(6-그룹 변환) 폴백. 비중 0 항목 제외.
 */
export function buildPdfAllocation(pf: Portfolio): PdfAssetSlice[] {
  if (pf.allocation?.length) {
    return pf.allocation
      .filter((a) => a.weight > 0)
      .map((a) => ({
        label: a.name,
        weight: a.weight,
        color: BACKEND_ASSET_COLORS[a.asset_class] ?? "#8899AA",
      }));
  }
  return toDisplayAllocation(
    pf.weights ?? ({} as Parameters<typeof toDisplayAllocation>[0]),
  )
    .filter((d) => d.weight > 0)
    .map((d) => ({
      label: d.group,
      weight: d.weight,
      color: DISPLAY_GROUP_COLORS[d.group] ?? "#8899AA",
    }));
}

// ── 거시지표 ──────────────────────────────────────────────────────────────────

export type PdfMacroCell = {
  label: string;
  value: string;
  changeText: string;
  arrow: "▲" | "▼" | null;
  color: string;
};

/** change 문자열에서 숫자만 파싱해 0 여부 판단 */
function isZeroOrNeutral(m: MacroIndicator): boolean {
  if ((m as { direction: string }).direction === "neutral") return true;
  const num = parseFloat(m.change.replace(/[^0-9.-]/g, ""));
  return isNaN(num) || num === 0;
}

/**
 * 거시지표 셀.
 * 변화량 0(또는 neutral) → 삼각형 없이 검은색.
 * 상승 → ▲ 빨강 / 하락 → ▼ 파랑.
 */
export function buildPdfMacroCell(m: MacroIndicator): PdfMacroCell {
  const neutral = isZeroOrNeutral(m);
  const isUp = m.direction === "up";
  return {
    label: m.label,
    value: m.value,
    changeText: m.change,
    arrow: neutral ? null : isUp ? "▲" : "▼",
    color: neutral ? TEXT : isUp ? UP : BRAND,
  };
}

// ── 성과 지표 ─────────────────────────────────────────────────────────────────

export type PdfPerfRow = {
  label: string;
  vals: string[];
  /** 세후 수익률 행은 UP(빨강)으로 표시 */
  upColor?: string;
};

function fmtMdd(pct: number | null | undefined, label: string | null | undefined): string {
  if (pct == null) return "-";
  const arrow = pct !== 0 ? "▼" : "";
  return `${arrow}${pct}%\n(${label ?? "-"})`;
}

function fmtAfterTax(pct: number | null | undefined, label: string | null | undefined): string {
  if (pct == null) return "-";
  const arrow = pct !== 0 ? "▲" : "";
  return `${arrow}${pct}%\n(${label ?? "-"})`;
}

/**
 * 성과 지표 비교 행.
 * - 0 값: 삼각형·기호 없음
 * - 세후 수익률: upColor = UP(빨강) override
 * - 모든 값이 "-"인 행은 필터링
 */
export function buildPdfPerfRows(portfolios: Portfolio[]): PdfPerfRow[] {
  const cur = portfolios.find((p) => p.id === "current");
  const a = portfolios.find((p) => p.id === "a");
  const b = portfolios.find((p) => p.id === "b");
  if (!cur || !a || !b) return [];

  const fmtN = (v: number | null | undefined): string =>
    v == null ? "-" : String(v);

  const rows: PdfPerfRow[] = [
    {
      label: "기대수익률 (연)",
      vals: [
        `${cur.metrics.expectedReturnPct}%`,
        `${a.metrics.expectedReturnPct}%`,
        `${b.metrics.expectedReturnPct}%`,
      ],
    },
    {
      label: "변동성 (표준편차)",
      vals: [
        `${cur.metrics.volatilityPct}%`,
        `${a.metrics.volatilityPct}%`,
        `${b.metrics.volatilityPct}%`,
      ],
    },
    {
      label: "샤프 지수",
      vals: [
        fmtN(cur.metrics.sharpe),
        fmtN(a.metrics.sharpe),
        fmtN(b.metrics.sharpe),
      ],
    },
    {
      label: "소르티노 지수",
      vals: [
        fmtN(cur.metrics.sortino),
        fmtN(a.metrics.sortino),
        fmtN(b.metrics.sortino),
      ],
    },
    {
      label: "최대낙폭 (MDD)",
      vals: [
        fmtMdd(cur.metrics.mddPct, cur.metrics.mddAmountLabel),
        fmtMdd(a.metrics.mddPct, a.metrics.mddAmountLabel),
        fmtMdd(b.metrics.mddPct, b.metrics.mddAmountLabel),
      ],
    },
    {
      label: "세후 수익률",
      upColor: UP,
      vals: [
        fmtAfterTax(cur.metrics.afterTaxReturnPct, cur.metrics.afterTaxAmountLabel),
        fmtAfterTax(a.metrics.afterTaxReturnPct, a.metrics.afterTaxAmountLabel),
        fmtAfterTax(b.metrics.afterTaxReturnPct, b.metrics.afterTaxAmountLabel),
      ],
    },
  ];

  return rows.filter((row) =>
    row.vals.some((v) => v !== "-" && !v.startsWith("-\n")),
  );
}

// ── 상관관계 히트맵 ───────────────────────────────────────────────────────────

// 백엔드 asset_class → DISPLAY_GROUPS 인덱스 매핑
const DISPLAY_GROUP_BACKEND: Record<string, string[]> = {
  국내주식: ["domestic_equity"],
  해외배당주: ["overseas_dividend"],
  해외성장주: ["overseas_blue_chip", "overseas_growth"],
  일반채권: ["general_bond", "cash"],
  저쿠폰채: ["low_coupon_bond"],
  분리과세: ["separate_tax_bond"],
};

// 분석 전 참고 상관계수 행렬 (DISPLAY_GROUPS 순서와 동일)
// 출처: 국내 금융시장 기반 학술 추정치 (주식-채권 상관관계 참고)
const FALLBACK_CORR: number[][] = [
  [ 1.00,  0.55,  0.60, -0.10, -0.35,  0.05], // 국내주식
  [ 0.55,  1.00,  0.65, -0.05, -0.25,  0.10], // 해외배당주
  [ 0.60,  0.65,  1.00, -0.15, -0.40,  0.00], // 해외성장주
  [-0.10, -0.05, -0.15,  1.00,  0.45,  0.30], // 일반채권
  [-0.35, -0.25, -0.40,  0.45,  1.00,  0.40], // 저쿠폰채
  [ 0.05,  0.10,  0.00,  0.30,  0.40,  1.00], // 분리과세
];

/**
 * correlationHeatmap(store) → 6×6 DISPLAY_GROUPS 기준 상관계수 행렬.
 * 실데이터가 없으면 학술 추정치 폴백을 사용하고 isFallback=true 를 반환한다.
 */
export function buildPdfCorrMatrix(
  heatmap: CorrelationHeatmapResponse | null,
): { matrix: number[][]; isFallback: boolean } {
  if (!heatmap) return { matrix: FALLBACK_CORR, isFallback: true };
  const matrix = DISPLAY_GROUPS.map((g1) => {
    const i1 = heatmap.assets.findIndex((a) =>
      (DISPLAY_GROUP_BACKEND[g1] ?? []).includes(a.asset_class),
    );
    return DISPLAY_GROUPS.map((g2) => {
      if (g1 === g2) return 1;
      const i2 = heatmap.assets.findIndex((a) =>
        (DISPLAY_GROUP_BACKEND[g2] ?? []).includes(a.asset_class),
      );
      if (i1 === -1 || i2 === -1) return 0;
      return heatmap.matrix[i1]?.[i2] ?? 0;
    });
  });
  return { matrix, isFallback: false };
}

/** 히트맵 셀 배경색 (CorrelationHeatmap.tsx와 동일 공식) */
export function heatBg(v: number): string {
  return `rgba(0, 100, 255, ${(0.06 + v * 0.8).toFixed(2)})`;
}

/** 히트맵 셀 텍스트 색상 */
export function heatTextColor(v: number): string {
  return v > 0.55 ? "#fff" : "#0050D6";
}
