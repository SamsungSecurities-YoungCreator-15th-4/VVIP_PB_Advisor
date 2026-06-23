"use client";

import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { TAX_EFFECT } from "@/lib/mockData";
import type { AccountSlot } from "@/lib/types";

// 기준값(한도) — ISA·연금은 세법 한도, 일반계좌는 UI 시안 기준값 (만원)
// 출처: 조세특례제한법 §91의18(ISA), 소득세법 §59의3(연금·IRP)
const REFERENCE_MAN: Record<string, number> = {
  isa: 2000,
  pension: 900,
  general: 3000,
};

const CHART_MAX = 4000; // X축 최대 (만원)

const ACCOUNT_META: Record<
  string,
  { name: string; tag: string; caption: string }
> = {
  isa: {
    name: "ISA",
    tag: "비과세·분리과세",
    caption: "납입 한도 100% 활용 · 비과세 200만 + 초과분 9.9% 분리과세",
  },
  pension: {
    name: "연금저축 + IRP",
    tag: "세액공제",
    caption: "세액공제 한도 소진 · 공제율 16.5%",
  },
  general: {
    name: "일반계좌",
    tag: "분리과세 ETF",
    caption: "국내·해외 ETF 중심으로 금융소득종합과세 구간 회피",
  },
};

function buildData(accounts: typeof TAX_EFFECT.accounts) {
  return accounts.map((a) => {
    const key =
      a.name === "ISA"
        ? "isa"
        : a.name === "연금저축 + IRP"
          ? "pension"
          : "general";
    const meta = ACCOUNT_META[key];
    const ref = REFERENCE_MAN[key];
    const used =
      a.used !== null ? a.used : Math.round(ref * 0.45); // 일반계좌 더미 45%
    return { name: meta.name, tag: meta.tag, caption: meta.caption, used, reference: ref };
  });
}

function buildFromSlots(slots: AccountSlot[]) {
  return slots.map((s) => {
    const key = s.key;
    const meta = ACCOUNT_META[key] ?? { name: key, tag: "", caption: "" };
    const ref = REFERENCE_MAN[key] ?? s.limitManwon ?? 1000;
    const used = s.usedManwon !== null ? s.usedManwon : Math.round(ref * 0.45);
    return { name: meta.name, tag: meta.tag, caption: meta.caption, used, reference: ref };
  });
}

const xFmt = (v: number) =>
  v === 0 ? "0" : v >= 1000 ? `${v / 1000}천만` : `${v}만`;

/** ② 절세 계좌 배치 활용도 — ISA / 연금저축+IRP / 일반계좌 다중 바 차트 */
export default function AccountAllocation({ accounts }: { accounts?: AccountSlot[] }) {
  const data =
    accounts && accounts.length > 0
      ? buildFromSlots(accounts)
      : buildData(TAX_EFFECT.accounts);

  return (
    <div>
      <p className="mb-2 flex items-center gap-1.5 text-[12px] font-extrabold">
        <span className="flex size-4 items-center justify-center rounded-full bg-brand/10 text-[10px] text-brand-dark">
          2
        </span>
        절세 계좌 배치 활용도
      </p>

      <div className="h-36">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 0, right: 16, bottom: 0, left: 0 }}
            barCategoryGap="28%"
            barGap={3}
          >
            <XAxis
              type="number"
              domain={[0, CHART_MAX]}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 10, fill: "#B0B8C1", fontWeight: 600 }}
              tickFormatter={xFmt}
              ticks={[0, 1000, 2000, 3000, 4000]}
            />
            <YAxis
              type="category"
              dataKey="name"
              width={72}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 11, fontWeight: 800, fill: "#4E5968" }}
            />
            <Tooltip
              cursor={{ fill: "#EAF1FF" }}
              content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null;
                return (
                  <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: "8px 12px", fontSize: 12 }}>
                    <p style={{ fontWeight: 700, marginBottom: 4 }}>{label}</p>
                    {payload.map((entry) => (
                      <p key={String(entry.dataKey)} style={{ color: entry.dataKey === "reference" ? "#4E5968" : String(entry.color) }}>
                        {entry.dataKey === "reference" ? "기준값" : "사용액"} : {Number(entry.value ?? 0).toLocaleString()}만원
                      </p>
                    ))}
                  </div>
                );
              }}
            />
            {/* 기준값 — 회색 */}
            <Bar dataKey="reference" name="기준값" fill="#D1D5DB" radius={4} barSize={10} isAnimationActive={false} />
            {/* 사용액 — 브랜드 블루 */}
            <Bar dataKey="used" name="사용액" fill="#0064FF" radius={4} barSize={10} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 범례 */}
      <div className="mb-2 flex gap-3">
        <LegendDot color="#0064FF" label="사용액" />
        <LegendDot color="#D1D5DB" label="기준값" />
      </div>

    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5 text-[11px] font-bold text-muted-foreground">
      <span className="size-2 rounded-[3px]" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}
