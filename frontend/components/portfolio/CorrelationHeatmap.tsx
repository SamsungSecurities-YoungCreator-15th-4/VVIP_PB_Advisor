"use client";

import { DISPLAY_GROUPS, type DisplayGroup } from "@/lib/assetMapping";
import { CORRELATION_MATRIX, type Portfolio } from "@/lib/mockData";
import { useDashboardStore } from "@/lib/store";

const GROUP_ABBR: Record<DisplayGroup, string> = {
  국내주식: "국내",
  해외배당주: "배당",
  해외성장주: "성장",
  일반채권: "일반",
  저쿠폰채: "저쿠",
  분리과세: "분리",
};

// 백엔드 heatmap asset_class(snake_case) 별 약칭
const ASSET_ABBR: Record<string, string> = {
  domestic_equity:    "국내주",
  overseas_equity:    "해외주",
  overseas_dividend:  "해배주",
  overseas_blue_chip: "해성주",
  overseas_growth:    "신흥주",
  bond:               "채권",
  general_bond:       "국내채",
  dollar:             "해외채",
  low_coupon_bond:    "저쿠폰",
  separate_tax_bond:  "분리채",
  reit:               "리츠",
  gold:               "금",
  commodity:          "원자재",
  cash:               "현금",
};

// CalcUnitId(camelCase) → 백엔드 asset_class(snake_case) 역매핑
// (portfolio.ts의 ASSET_TO_CALC_UNIT 역방향)
const CALC_TO_BACKEND: Record<string, string[]> = {
  domesticEquity:         ["domestic_equity"],
  overseasDividendEquity: ["overseas_dividend"],
  overseasGrowthEquity:   ["overseas_blue_chip"],
  emergingEquity:         ["overseas_growth"],
  domesticBond:           ["general_bond", "cash"],
  overseasBond:           ["dollar"],
  lowCouponBond:          ["low_coupon_bond"],
  separateTaxBond:        ["separate_tax_bond"],
  reits:                  ["reit"],
  gold:                   ["gold"],
  infraFund:              ["commodity"],
};

export default function CorrelationHeatmap({ portfolio }: { portfolio?: Portfolio }) {
  const correlationHeatmap = useDashboardStore((s) => s.correlationHeatmap);

  if (correlationHeatmap && portfolio) {
    const nonZeroIds = portfolio.allocation
      ? new Set(
          portfolio.allocation
            .filter((a) => a.weight > 0)
            .map((a) => a.asset_class)
        )
      : new Set(
          Object.entries(portfolio.weights)
            .filter(([, w]) => w > 0)
            .flatMap(([calcId]) => {
              if (calcId === "domesticEquity") return ["domestic_equity"];
              if (calcId === "overseasDividendEquity" || calcId === "overseasGrowthEquity" || calcId === "emergingEquity") return ["overseas_equity"];
              if (calcId === "domesticBond") return ["bond", "cash"];
              if (calcId === "overseasBond") return ["dollar"];
              if (calcId === "lowCouponBond" || calcId === "separateTaxBond") return ["bond"];
              if (calcId === "reits") return ["reit"];
              if (calcId === "gold") return ["gold"];
              if (calcId === "infraFund") return ["commodity"];
              return [];
            })
        );

    const indices = correlationHeatmap.assets
      .map((a, i) => ({ ...a, i }))
      .filter(({ asset_class }) => nonZeroIds.has(asset_class));

    if (indices.length > 0) {
      const labels = indices.map(({ asset_class, name }) => ({
        key: asset_class,
        label: ASSET_ABBR[asset_class] ?? name.slice(0, 3),
        fullName: name,
      }));
      const matrix = indices.map(({ i }) =>
        indices.map(({ i: j }) => correlationHeatmap.matrix[i]?.[j] ?? 0),
      );

      return (
        <div className="flex flex-1 flex-col">
          <div
            className="flex-1 grid gap-px"
            style={{
              gridTemplateColumns: `44px repeat(${labels.length}, 1fr)`,
              gridTemplateRows: `auto repeat(${labels.length}, 1fr)`,
            }}
          >
            <span />
            {labels.map(({ key, label, fullName }) => (
              <span
                key={key}
                title={fullName}
                className="truncate text-center text-[10px] font-semibold text-muted-foreground"
              >
                {label}
              </span>
            ))}
            {matrix.map((row, i) => (
              <Row key={labels[i]!.key} label={labels[i]!.label} row={row} />
            ))}
          </div>
          <p className="mt-1 text-right text-[8px] font-semibold text-muted-foreground">
            상관계수
          </p>
        </div>
      );
    }
  }

  // fallback: mock 데이터
  return (
    <div className="flex flex-1 flex-col">
      <div
        className="flex-1 grid gap-px"
        style={{
          gridTemplateColumns: `44px repeat(${DISPLAY_GROUPS.length}, 1fr)`,
          gridTemplateRows: `auto repeat(${DISPLAY_GROUPS.length}, 1fr)`,
        }}
      >
        <span />
        {DISPLAY_GROUPS.map((g) => (
          <span
            key={g}
            className="truncate text-center text-[10px] font-semibold text-muted-foreground"
            title={g}
          >
            {GROUP_ABBR[g]}
          </span>
        ))}
        {CORRELATION_MATRIX.map((row, i) => (
          <Row key={DISPLAY_GROUPS[i]} label={DISPLAY_GROUPS[i]!} row={row} />
        ))}
      </div>
      <p className="mt-1 text-right text-[8px] font-semibold text-muted-foreground">
        상관계수
      </p>
    </div>
  );
}

function Row({ label, row }: { label: string; row: number[] }) {
  return (
    <>
      <span className="flex items-center truncate pr-1 text-[10px] font-semibold text-muted-foreground">
        {label}
      </span>
      {row.map((v, j) => (
        <span
          key={j}
          className="flex items-center justify-center rounded-[3px] text-[7.5px] font-bold tabular-nums"
          style={{
            backgroundColor: `rgba(0, 100, 255, ${0.06 + v * 0.8})`,
            color: v > 0.55 ? "#fff" : "#0050D6",
          }}
        >
          {v.toFixed(2)}
        </span>
      ))}
    </>
  );
}
