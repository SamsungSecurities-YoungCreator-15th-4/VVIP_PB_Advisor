"use client";

import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { TAX_EFFECT, PORTFOLIOS } from "@/lib/mockData";
import { toDisplayAllocation, DISPLAY_GROUP_COLORS } from "@/lib/assetMapping";
import { useDashboardStore } from "@/lib/store";
import type { AccountSlot } from "@/lib/types";

// 출처: 조세특례제한법 §91의18(ISA), 소득세법 §59의3(연금·IRP)
const REFERENCE_MAN: Record<string, number> = {
  isa: 2000,
  pension: 900,
};

const CHART_MAX = 2000;

const ACCOUNT_META: Record<string, { name: string }> = {
  isa: { name: "ISA" },
  pension: { name: "연금저축 + IRP" },
};

function buildData(accounts: typeof TAX_EFFECT.accounts) {
  return accounts
    .filter((a) => a.name !== "일반계좌")
    .map((a) => {
      const key = a.name === "ISA" ? "isa" : "pension";
      const ref = REFERENCE_MAN[key];
      const used = a.used !== null ? a.used : Math.round(ref * 0.45);
      return { name: ACCOUNT_META[key].name, used, reference: ref };
    });
}

function buildFromSlots(slots: AccountSlot[]) {
  return slots
    .filter((s) => s.key !== "general")
    .map((s) => {
      const key = s.key;
      const meta = ACCOUNT_META[key] ?? { name: key };
      const ref = REFERENCE_MAN[key] ?? s.limitManwon ?? 1000;
      const used =
        s.usedManwon !== null ? s.usedManwon : Math.round(ref * 0.45);
      return { name: meta.name, used, reference: ref };
    });
}

const xFmt = (v: number) =>
  v === 0 ? "0" : v >= 1000 ? `${v / 1000}천만` : `${v}만`;

/** ② 절세 계좌 배치 활용도 — 포트폴리오 구성 세그먼트 바 + ISA / 연금저축+IRP 바 차트 */
export default function AccountAllocation({
  accounts,
}: {
  accounts?: AccountSlot[];
}) {
  const { selectedPortfolioId } = useDashboardStore();
  const portfolio =
    PORTFOLIOS.find((p) => p.id === selectedPortfolioId) ?? PORTFOLIOS[1];
  const allocation = toDisplayAllocation(portfolio.weights).filter(
    ({ weight }) => weight > 0,
  );

  const data =
    accounts && accounts.length > 0
      ? buildFromSlots(accounts)
      : buildData(TAX_EFFECT.accounts);

  return (
    <div className="flex h-full flex-col">
      <p className="mb-2 flex items-center gap-1.5 text-[13px] font-extrabold">
        계좌 배치 활용도
      </p>

      {/* 전체 계좌 세그먼트 바 — YAxis width(72px) 기준 정렬, 2px 여백 */}
      <div className="mb-1 flex items-center">
        <span className="w-[72px] shrink-0 text-right text-[12px] font-extrabold text-[#4E5968]">
          전체 계좌
        </span>
        <div className="ml-[2px] mr-[16px] flex h-[10px] flex-1 overflow-hidden rounded-md">
          {allocation.map(({ group, weight }) => (
            <div
              key={group}
              style={{
                width: `${weight}%`,
                backgroundColor: DISPLAY_GROUP_COLORS[group],
              }}
            />
          ))}
        </div>
      </div>

      {/* 세그먼트 범례 */}
      <div className="mb-3 ml-[74px] mr-[16px] flex flex-wrap gap-x-2 gap-y-0.5">
        {allocation.map(({ group, weight }) => (
          <span
            key={group}
            className="flex items-center gap-1 text-[11px] font-semibold text-muted-foreground"
          >
            <span
              className="inline-block size-1.5 rounded-[2px]"
              style={{ backgroundColor: DISPLAY_GROUP_COLORS[group] }}
            />
            {group} {weight}%
          </span>
        ))}
      </div>

      {/* ISA / 연금저축+IRP 바 차트 */}
      <div className="h-32">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 4, right: 16, bottom: 4, left: 2 }}
            barCategoryGap={28}
            barGap={3}
          >
            <XAxis
              type="number"
              domain={[0, CHART_MAX]}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 11, fill: "#B0B8C1", fontWeight: 600 }}
              tickFormatter={xFmt}
              ticks={[0, 500, 1000, 1500, 2000]}
            />
            <YAxis
              type="category"
              dataKey="name"
              width={72}
              tickLine={false}
              axisLine={false}
              tick={{ dx: 0, fontSize: 12, fontWeight: 800, fill: "#4E5968" }}
            />
            <Tooltip
              cursor={{ fill: "#EAF1FF" }}
              content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null;
                return (
                  <div
                    style={{
                      background: "#fff",
                      border: "1px solid #e5e7eb",
                      borderRadius: 8,
                      padding: "8px 12px",
                      fontSize: 13,
                    }}
                  >
                    <p style={{ fontWeight: 700, marginBottom: 4 }}>{label}</p>
                    {payload.map((entry) => (
                      <p
                        key={String(entry.dataKey)}
                        style={{
                          color:
                            entry.dataKey === "reference"
                              ? "#4E5968"
                              : String(entry.color),
                        }}
                      >
                        {entry.dataKey === "reference" ? "기준값" : "사용액"} :{" "}
                        {Number(entry.value ?? 0).toLocaleString()}만원
                      </p>
                    ))}
                  </div>
                );
              }}
            />
            <Bar
              dataKey="reference"
              name="기준값"
              fill="#D1D5DB"
              radius={4}
              barSize={14}
              isAnimationActive={false}
            />
            <Bar
              dataKey="used"
              name="사용액"
              radius={4}
              barSize={14}
              isAnimationActive={false}
            >
              {data.map((_, i) => (
                <Cell key={i} fill={i === 0 ? "#0064FF" : "#3D8BFF"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-auto flex gap-3">
        <LegendDot color="#0064FF" label="ISA 사용액" />
        <LegendDot color="#3D8BFF" label="연금 사용액" />
        <LegendDot color="#D1D5DB" label="기준값" />
      </div>
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5 text-[12px] font-bold text-muted-foreground">
      <span
        className="size-2 rounded-[3px]"
        style={{ backgroundColor: color }}
      />
      {label}
    </span>
  );
}
