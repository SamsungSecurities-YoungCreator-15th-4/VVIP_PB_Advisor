/**
 * PB용 PDF 템플릿 — A4 세로(794×1123px) 5페이지.
 * 구조: 표지 → 시장현황&IPS → 포트폴리오 비교 → 절세 최적화 → AI 인사이트
 */

import {
  PORTFOLIOS,
  TAX_EFFECT,
  TAX_ADVICE,
  INSIGHT,
  MACRO_INDICATORS,
  BASE_TIME,
} from "@/lib/mockData";
import { useDashboardStore } from "@/lib/store";

// ── 상수 ────────────────────────────────────────────────────────
const W = 794;
const H = 1123;
const BRAND = "#0050D6";
const BRAND_DARK = "#003FA8";
const BRAND_LIGHT = "#EAF1FF";
const BRAND_MID = "#C9DBFF";
const UP = "#F04452";
const TEXT = "#111827";
const MUTED = "#6B7280";
const BORDER = "#E5E7EB";
const BG_ALT = "#FAFAFA";

/** 현재 대시보드에서 선택된 고객(없으면 첫 고객)을 store 에서 읽는다. */
function useSelectedCustomer() {
  const customers = useDashboardStore((s) => s.customers);
  const selectedCustomerId = useDashboardStore((s) => s.selectedCustomerId);
  return customers.find((c) => c.id === selectedCustomerId) ?? customers[0];
}

// 절세 계좌 배치 — 기준값(한도) 및 차트 최대값
// 출처: 조세특례제한법 §91의18(ISA), 소득세법 §59의3(연금·IRP)
const ACCOUNT_CHART_MAX = 2000;
const ACCOUNT_PDF = [
  {
    key: "isa",
    name: "ISA",
    refManwon: 2000,
    caption: "납입 한도 100% 활용 · 비과세 200만 + 초과분 9.9% 분리과세",
  },
  {
    key: "pension",
    name: "연금저축 + IRP",
    refManwon: 900,
    caption: "세액공제 한도 소진 · 공제율 16.5% → 환급 148만",
  },
  {
    key: "general",
    name: "일반계좌",
    refManwon: 3000,
    caption: "국내·해외 ETF 중심으로 금융소득종합과세 구간 회피",
  },
];

const ASSET_GROUPS = [
  { label: "국내주식", color: "#003FA8" },
  { label: "해외배당주", color: "#0050D6" },
  { label: "해외성장주", color: "#2C7BFF" },
  { label: "일반채권", color: "#4B8FF5" },
  { label: "저쿠폰채", color: "#6FA8FF" },
  { label: "분리과세", color: "#93BEFF" },
];
const WEIGHTS = {
  current: [25, 18, 12, 22, 12, 11],
  a: [20, 22, 12, 18, 14, 14],
  b: [28, 26, 22, 12, 8, 4],
};


// 스트레스 테스트 시나리오 — 포트폴리오 A 기준 운용자산 18억원 시뮬레이션 추정치
const SCENARIO_ROWS = [
  {
    name: "현재",
    rate: "3.50%",
    fx: "1,220원",
    pnl: "+9,900만원",
    pnlColor: UP,
    action: "변화 없음",
  },
  {
    name: "금리 변동",
    rate: "4.75%",
    fx: "1,420원",
    pnl: "-",
    pnlColor: MUTED,
    action: "채권 비중 축소 권장",
  },
  {
    name: "환율 변동",
    rate: "현행",
    fx: "1,420원",
    pnl: "환헤지 상향",
    pnlColor: BRAND,
    action: "해외 비중 상향 효과",
  },
  {
    name: "금융위기",
    rate: "0.25%",
    fx: "1,570원",
    pnl: "-3,200만원",
    pnlColor: UP,
    action: "주식·하이일드 비중 축소",
  },
  {
    name: "러우전쟁",
    rate: "4.25%",
    fx: "1,440원",
    pnl: "-1,100만원",
    pnlColor: UP,
    action: "에너지·원자재 분산 검토",
  },
];

// 거시지표 한국어 레이블 (ClientPdfTemplate 동일)
const MACRO_DESC: Record<string, string> = {
  기준금리: "미국 기준금리",
  "미 10Y": "미국 장기금리",
  "원/달러": "원/달러 환율",
  KOSPI: "국내 주식 (KOSPI)",
  "S&P500": "미국 주식 (S&P500)",
  CPI: "미국 CPI",
};

// ── 날짜 유틸 ────────────────────────────────────────────────────
function getToday() {
  const d = new Date();
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, "0")}.${String(d.getDate()).padStart(2, "0")}`;
}

// ── 공통 컴포넌트 ────────────────────────────────────────────────
function PageFooter({ page, total }: { page: number; total: number }) {
  return (
    <div
      style={{
        position: "absolute",
        bottom: 24,
        left: 40,
        right: 40,
        borderTop: `1px solid ${BORDER}`,
        paddingTop: 8,
      }}
    >
      <div
        style={{
          position: "relative",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span style={{ fontSize: 10, color: MUTED }}>
          VVIP PB Advisor · 내부 기밀 자료
        </span>
        <span
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            textAlign: "center",
            fontSize: 10,
            color: MUTED,
          }}
        >
          Page {page} / {total}
        </span>
        <span style={{ fontSize: 10, color: MUTED }}>
          {getToday()} {BASE_TIME}
        </span>
      </div>
    </div>
  );
}

function SectionBar() {
  return (
    <div
      style={{
        width: 4,
        height: 18,
        background: BRAND,
        borderRadius: 2,
        marginRight: 10,
        flexShrink: 0,
      }}
    />
  );
}

function PageHeader({
  pageNum,
  title,
  subtitle,
}: {
  pageNum: string;
  title: string;
  subtitle: string;
}) {
  const customer = useSelectedCustomer();
  return (
    <div
      style={{
        background: `linear-gradient(90deg, ${BRAND_DARK} 0%, ${BRAND} 100%)`,
        padding: "19px 40px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}
    >
      <div>
        <div style={{ fontSize: 18, fontWeight: 800, color: "white" }}>
          {pageNum} {title}
        </div>
        <div
          style={{
            fontSize: 13,
            color: "rgba(255,255,255,0.75)",
            marginTop: 2,
          }}
        >
          {subtitle}
        </div>
      </div>
      <div style={{ textAlign: "right" }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: "white" }}>
          {customer.name}
        </div>
        <div style={{ fontSize: 12, color: "rgba(255,255,255,0.7)" }}>
          {customer.pbCode}
        </div>
      </div>
    </div>
  );
}

function AssetBar({
  label,
  pct,
  color,
}: {
  label: string;
  pct: number;
  color: string;
}) {
  return (
    <div
      style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 5 }}
    >
      <span style={{ width: 48, fontSize: 11, color: MUTED, flexShrink: 0 }}>
        {label}
      </span>
      <div
        style={{
          flex: 1,
          height: 7,
          background: "#F3F4F6",
          borderRadius: 4,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background: color,
            borderRadius: 4,
          }}
        />
      </div>
      <span
        style={{
          width: 26,
          fontSize: 11,
          fontWeight: 700,
          textAlign: "right" as const,
          color,
        }}
      >
        {pct}%
      </span>
    </div>
  );
}

// ── 페이지 1: 표지 ───────────────────────────────────────────────
function CoverPage() {
  const customer = useSelectedCustomer();
  const today = getToday();
  const selectedPortfolioId = useDashboardStore((s) => s.selectedPortfolioId);
  const storePortfolios = useDashboardStore((s) => s.portfolios);
  const selectedPortfolioName =
    (storePortfolios.length > 0 ? storePortfolios : PORTFOLIOS).find(
      (p) => p.id === selectedPortfolioId,
    )?.name ?? "포트폴리오 A";
  return (
    <div
      data-pdf-page=""
      style={{
        width: W,
        height: H,
        fontFamily: "Pretendard, Apple SD Gothic Neo, sans-serif",
        background: "white",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 420,
          background:
            "linear-gradient(135deg, #003FA8 0%, #0050D6 55%, #2C7BFF 100%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          top: 340,
          left: -60,
          right: -60,
          height: 120,
          background: "white",
          borderRadius: "50% 50% 0 0 / 60px 60px 0 0",
        }}
      />
      <div style={{ position: "relative", padding: "44px 52px 0" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 50,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/logo.png"
              alt=""
              style={{ width: 36, height: 36, borderRadius: 9, objectFit: "cover" }}
            />
            <div>
              <div
                style={{
                  fontSize: 16,
                  fontWeight: 800,
                  color: "white",
                  letterSpacing: 0.5,
                }}
              >
                S.upervisor
              </div>
              <div
                style={{
                  fontSize: 10,
                  color: "rgba(255,255,255,0.7)",
                  marginTop: 1,
                }}
              >
                VVIP PB ADVISOR
              </div>
            </div>
          </div>
          <span
            style={{
              background: "rgba(255,255,255,0.15)",
              border: "1px solid rgba(255,255,255,0.25)",
              color: "rgba(255,255,255,0.92)",
              fontSize: 11,
              fontWeight: 700,
              padding: "5px 13px",
              borderRadius: 20,
              whiteSpace: "nowrap" as const,
            }}
          >
            PB 내부용
          </span>
        </div>
        <div
          style={{
            fontSize: 44,
            fontWeight: 900,
            color: "white",
            lineHeight: 1.2,
            marginBottom: 20,
            marginTop: 60,
          }}
        >
          포트폴리오
          <br />
          분석 <span style={{ color: BRAND_MID }}>리포트</span>
        </div>
        <div
          style={{
            fontSize: 14,
            color: "rgba(255,255,255,0.65)",
            fontWeight: 400,
          }}
        >
          PB 상담 보조 자료
        </div>
      </div>

      <div style={{ position: "relative", padding: "72px 52px 0" }}>
        <div
          style={{
            background: BRAND_LIGHT,
            border: `1px solid ${BRAND_MID}`,
            borderRadius: 14,
            padding: "24px 28px",
            marginBottom: 60,
            marginTop: 56,
          }}
        >
          <div
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: BRAND,
              letterSpacing: 1.5,
              marginBottom: 10,
            }}
          >
            CLIENT
          </div>
          <div
            style={{
              fontSize: 28,
              fontWeight: 700,
              color: TEXT,
              marginBottom: 6,
            }}
          >
            {customer.name} 고객
          </div>
          <div style={{ fontSize: 12, color: MUTED, fontWeight: 500 }}>
            {customer.pbCode} · {customer.grade} 등급 · {customer.aumLabel}
          </div>
        </div>
        <div style={{ display: "flex" }}>
          {[
            { label: "보고서 일자", value: today },
            { label: "기준 시각", value: `${BASE_TIME} 기준` },
            { label: "선택 포트폴리오", value: selectedPortfolioName },
            {
              label: "예상 연간 절세",
              value: `+${TAX_EFFECT.annualSavingManwon.toLocaleString()}만원/년`,
            },
          ].map((item, i) => (
            <div
              key={item.label}
              style={{
                flex: 1,
                paddingLeft: i > 0 ? 20 : 0,
                borderLeft: i > 0 ? `1px solid ${BORDER}` : "none",
                marginLeft: i > 0 ? 20 : 0,
              }}
            >
              <div
                style={{
                  fontSize: 10,
                  color: MUTED,
                  letterSpacing: 0.8,
                  marginBottom: 5,
                }}
              >
                {item.label}
              </div>
              <div style={{ fontSize: 15, fontWeight: 800, color: TEXT }}>
                {item.value}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          bottom: 36,
          left: 52,
          right: 52,
          background: "#F9FAFB",
          border: `1px solid ${BORDER}`,
          borderRadius: 10,
          padding: "14px 18px",
        }}
      >
        <p style={{ fontSize: 13, color: MUTED, lineHeight: 1.7, margin: 0 }}>
          본 자료는 PB 상담 보조를 위한 내부 기밀 자료입니다. 본 보고서의 분석
          내용, 포트폴리오 제안 및 시뮬레이션 결과는 시장 데이터와 AI 분석을
          기반으로 작성되었으며, 최종 투자 판단은 고객의 투자 목적·위험
          성향·세무·법률 상황을 종합적으로 고려하여 결정되어야 합니다. 무단
          배포를 금합니다.
        </p>
      </div>
    </div>
  );
}

// ── 페이지 2: 시장 현황 & IPS ────────────────────────────────────
function MarketIpsPage() {
  const customer = useSelectedCustomer();
  const ips = useDashboardStore((s) => s.ips);
  const IPS_ROWS = [
    {
      key: "GOAL",
      korean: "투자 목적",
      tag: "복합",
      tagColor: "#6B7280",
      detail: (ips.goal ?? "") + " (3년 내 자금 활용 가능성 포함)",
    },
    {
      key: "ASSET",
      korean: "운용 자산",
      tag: customer.aumLabel,
      tagColor: "#F59E0B",
      detail: "총 운용 가능 자산 기준. 기존 자산 구성 변경 검토 중",
    },
    {
      key: "RETURN",
      korean: "목표 수익률",
      tag: `${ips.returnPct}%`,
      tagColor: "#10B981",
      detail: `연 ${ips.returnPct}% 목표 (세후 기준). 변동성 최소화 조건 병행`,
    },
    {
      key: "RISK",
      korean: "위험 성향",
      tag: ips.risk,
      tagColor: "#F59E0B",
      detail: "안정형~공격형 스펙트럼 중 균형형. MDD -15% 이내 선호",
    },
    {
      key: "TIME",
      korean: "투자 기간",
      tag: `${ips.timeYears}년`,
      tagColor: BRAND,
      detail: "장기 운용 기준. 단, 유동성 필요 시 분리 운용 필요",
    },
    {
      key: "TAX",
      korean: "세금",
      tag: "종합과세",
      tagColor: UP,
      detail: (ips.tax ?? "") + " 절세전략 필요",
    },
    {
      key: "LIQUID",
      korean: "유동성",
      tag: ips.liquidity,
      tagColor: "#F59E0B",
      detail: "낮음~높음 중 중간. 비상자금 3억 별도 보유 권장",
    },
    {
      key: "LEGAL",
      korean: "법적 제약",
      tag: "검토필요",
      tagColor: UP,
      detail: (ips.legal ?? "") + ". 사전 증여 전략 수립 권장",
    },
    {
      key: "UNIQUE",
      korean: "특수 사항",
      tag: "복합",
      tagColor: "#6B7280",
      detail: ips.unique,
    },
  ];
  return (
    <div
      data-pdf-page=""
      style={{
        width: W,
        height: H,
        fontFamily: "Pretendard, Apple SD Gothic Neo, sans-serif",
        background: "white",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <PageHeader
        pageNum="①"
        title="시장 현황 &amp; 고객 IPS 요약"
        subtitle="Market Overview &amp; Investment Policy Statement"
      />

      <div style={{ padding: "28px 40px 80px", wordBreak: "keep-all" }}>
        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 28 }}
        >
          <SectionBar />
          <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>
            주요 시장 지표
          </div>
        </div>

        <div
          style={{
            display: "flex",
            border: `1px solid ${BORDER}`,
            borderRadius: 10,
            overflow: "hidden",
            marginBottom: 48,
          }}
        >
          {MACRO_INDICATORS.map((m, idx) => {
            const isUp = m.direction === "up";
            return (
              <div
                key={m.label}
                style={{
                  flex: 1,
                  padding: "12px 10px",
                  borderRight:
                    idx < MACRO_INDICATORS.length - 1
                      ? `1px solid ${BORDER}`
                      : "none",
                  background: "white",
                }}
              >
                <div
                  style={{
                    fontSize: 10,
                    color: MUTED,
                    fontWeight: 600,
                    marginBottom: 5,
                  }}
                >
                  {MACRO_DESC[m.label] ?? m.label}
                </div>
                <div
                  style={{
                    fontSize: 17,
                    fontWeight: 900,
                    color: TEXT,
                    lineHeight: 1.1,
                    marginBottom: 5,
                  }}
                >
                  {m.value}
                </div>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: isUp ? UP : BRAND,
                  }}
                >
                  {isUp ? "▲" : "▼"} {m.change}
                </div>
              </div>
            );
          })}
        </div>

        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 28 }}
        >
          <SectionBar />
          <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>
            고객 IPS 요약
          </div>
        </div>

        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            tableLayout: "fixed",
          }}
        >
          <colgroup>
            <col style={{ width: 140 }} />
            <col />
          </colgroup>
          <thead>
            <tr style={{ background: BRAND }}>
              <th
                style={{
                  padding: "9px 12px",
                  textAlign: "left",
                  fontSize: 11,
                  fontWeight: 700,
                  color: "white",
                }}
              >
                항목
              </th>
              <th
                style={{
                  padding: "9px 12px",
                  textAlign: "left",
                  fontSize: 11,
                  fontWeight: 700,
                  color: "white",
                }}
              >
                세부 내용
              </th>
            </tr>
          </thead>
          <tbody>
            {IPS_ROWS.map((row, i) => (
              <tr
                key={row.key}
                style={{
                  borderBottom: `1px solid ${BORDER}`,
                  background: i % 2 === 0 ? "white" : BG_ALT,
                }}
              >
                <td style={{ padding: "9px 12px" }}>
                  <div style={{ fontSize: 12, fontWeight: 800, color: TEXT }}>
                    {row.key}
                  </div>
                  <div style={{ fontSize: 11, color: MUTED }}>{row.korean}</div>
                </td>
                <td
                  style={{
                    padding: "9px 12px",
                    fontSize: 11,
                    color: TEXT,
                    lineHeight: 1.55,
                  }}
                >
                  {row.detail}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <PageFooter page={2} total={6} />
    </div>
  );
}

// ── 페이지 3: 포트폴리오 비교 ────────────────────────────────────
function PortfolioPage() {
  const storePortfolios = useDashboardStore((s) => s.portfolios);
  const displayPortfolios = storePortfolios.length > 0 ? storePortfolios : PORTFOLIOS;
  const current = displayPortfolios.find((p) => p.id === "current") ?? PORTFOLIOS.find((p) => p.id === "current")!;
  const portA = displayPortfolios.find((p) => p.id === "a") ?? PORTFOLIOS.find((p) => p.id === "a")!;
  const portB = displayPortfolios.find((p) => p.id === "b") ?? PORTFOLIOS.find((p) => p.id === "b")!;
  const cols = [
    {
      p: current,
      weights: WEIGHTS.current,
      label: "현재 포트폴리오",
      badge: "",
      badgeColor: "#6B7280",
      headerColor: "#6B7280",
      selected: false,
    },
    {
      p: portA,
      weights: WEIGHTS.a,
      label: "포트폴리오 A",
      badge: "수익추구형",
      badgeColor: BRAND,
      headerColor: BRAND,
      selected: true,
    },
    {
      p: portB,
      weights: WEIGHTS.b,
      label: "포트폴리오 B",
      badge: "안정추구형",
      badgeColor: "#2C7BFF",
      headerColor: "#2C7BFF",
      selected: false,
    },
  ];

  const perfRows = [
    {
      label: "기대수익률 (연)",
      vals: [
        `${current.metrics.expectedReturnPct}%`,
        `${portA.metrics.expectedReturnPct}%`,
        `${portB.metrics.expectedReturnPct}%`,
      ],
    },
    {
      label: "변동성 (표준편차)",
      vals: [
        `${current.metrics.volatilityPct}%`,
        `${portA.metrics.volatilityPct}%`,
        `${portB.metrics.volatilityPct}%`,
      ],
    },
    {
      label: "샤프 지수",
      vals: [
        `${current.metrics.sharpe}`,
        `${portA.metrics.sharpe}`,
        `${portB.metrics.sharpe}`,
      ],
    },
    {
      label: "소르티노 지수",
      vals: [
        `${current.metrics.sortino}`,
        `${portA.metrics.sortino}`,
        `${portB.metrics.sortino}`,
      ],
    },
    {
      label: "최대낙폭 (MDD)",
      vals: [
        `▼${current.metrics.mddPct}%\n(${current.metrics.mddAmountLabel})`,
        `▼${portA.metrics.mddPct}%\n(${portA.metrics.mddAmountLabel})`,
        `▼${portB.metrics.mddPct}%\n(${portB.metrics.mddAmountLabel})`,
      ],
    },
    {
      label: "세후 수익률",
      vals: [
        `${current.metrics.afterTaxReturnPct}%\n(${current.metrics.afterTaxAmountLabel})`,
        `${portA.metrics.afterTaxReturnPct}%\n(${portA.metrics.afterTaxAmountLabel})`,
        `${portB.metrics.afterTaxReturnPct}%\n(${portB.metrics.afterTaxAmountLabel})`,
      ],
    },
  ];

  return (
    <div
      data-pdf-page=""
      style={{
        width: W,
        height: H,
        fontFamily: "Pretendard, Apple SD Gothic Neo, sans-serif",
        background: "white",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <PageHeader
        pageNum="②"
        title="포트폴리오 비교 분석"
        subtitle="자산별 성과 지표 및 Stress Test 결과"
      />

      <div style={{ padding: "28px 40px 80px", wordBreak: "keep-all" }}>
        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 28 }}
        >
          <SectionBar />
          <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>
            자산 배분 비교
          </div>
        </div>

        <div style={{ display: "flex", gap: 12, marginBottom: 40 }}>
          {cols.map(({ p, weights, label, badge, badgeColor, selected }) => (
            <div
              key={p.id}
              style={{
                flex: 1,
                border: selected ? `2px solid ${BRAND}` : `1px solid ${BORDER}`,
                borderRadius: 10,
                padding: "13px 14px",
                background: "white",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: 11,
                }}
              >
                <span style={{ fontSize: 12, fontWeight: 800, color: TEXT }}>
                  {label}
                </span>
                {badge && (
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      color: badgeColor,
                      background: `${badgeColor}18`,
                      padding: "2px 8px",
                      borderRadius: 10,
                    }}
                  >
                    {badge}
                  </span>
                )}
              </div>
              {ASSET_GROUPS.map((g, i) => (
                <AssetBar
                  key={g.label}
                  label={g.label}
                  pct={weights[i]}
                  color={g.color}
                />
              ))}
            </div>
          ))}
        </div>

        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 28 }}
        >
          <SectionBar />
          <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>
            성과 지표 비교
          </div>
        </div>

        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            tableLayout: "fixed",
            marginBottom: 40,
          }}
        >
          <colgroup>
            <col style={{ width: 150 }} />
            <col />
            <col />
            <col />
          </colgroup>
          <thead>
            <tr style={{ background: BG_ALT }}>
              <th
                style={{
                  padding: "8px 10px",
                  textAlign: "left",
                  fontSize: 11,
                  fontWeight: 700,
                  color: MUTED,
                  borderBottom: `2px solid ${BORDER}`,
                }}
              >
                지표
              </th>
              {cols.map((c) => (
                <th
                  key={c.p.id}
                  style={{
                    padding: "8px 10px",
                    textAlign: "center",
                    fontSize: 11,
                    fontWeight: 700,
                    color: c.headerColor,
                    borderBottom: `2px solid ${c.headerColor}`,
                  }}
                >
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {perfRows.map((row, i) => (
              <tr
                key={row.label}
                style={{
                  borderBottom: `1px solid ${BORDER}`,
                  background: i % 2 === 0 ? "white" : BG_ALT,
                }}
              >
                <td style={{ padding: "8px 10px", fontSize: 11, color: TEXT }}>
                  {row.label}
                </td>
                {row.vals.map((v, j) => (
                  <td
                    key={j}
                    style={{
                      padding: "8px 10px",
                      textAlign: "center",
                      fontSize: 11,
                      fontWeight: j === 0 ? 500 : 700,
                      color: cols[j].headerColor,
                      whiteSpace: "pre-line" as const,
                      lineHeight: 1.4,
                      background: cols[j].selected ? `${BRAND}0D` : "inherit",
                    }}
                  >
                    {v}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>

        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 28 }}
        >
          <SectionBar />
          <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>
            Stress Test
          </div>
        </div>

        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            tableLayout: "fixed",
          }}
        >
          <colgroup>
            <col style={{ width: 160 }} />
            <col style={{ width: 70 }} />
            <col style={{ width: 80 }} />
            <col style={{ width: 130 }} />
            <col />
          </colgroup>
          <thead>
            <tr style={{ background: BG_ALT }}>
              {[
                "시나리오",
                "금리",
                "환율",
                "예상 평가손익",
                "포트폴리오 A 영향",
              ].map((h) => (
                <th
                  key={h}
                  style={{
                    padding: "7px 10px",
                    textAlign: "left",
                    fontSize: 11,
                    fontWeight: 700,
                    color: TEXT,
                    borderBottom: `1.5px solid #D1D5DB`,
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {SCENARIO_ROWS.map((row, i) => (
              <tr
                key={row.name}
                style={{
                  borderBottom: `1px solid #D1D5DB`,
                  background: i % 2 === 0 ? "white" : BG_ALT,
                }}
              >
                <td
                  style={{
                    padding: "8px 10px",
                    fontSize: 11,
                    fontWeight: 700,
                    color: TEXT,
                  }}
                >
                  {row.name}
                </td>
                <td style={{ padding: "8px 10px", fontSize: 11, color: TEXT }}>
                  {row.rate}
                </td>
                <td style={{ padding: "8px 10px", fontSize: 11, color: TEXT }}>
                  {row.fx}
                </td>
                <td
                  style={{
                    padding: "8px 10px",
                    fontSize: 11,
                    fontWeight: 700,
                    color: row.pnlColor,
                  }}
                >
                  {row.pnl}
                </td>
                <td style={{ padding: "8px 10px", fontSize: 11, color: TEXT }}>
                  {row.action}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <PageFooter page={3} total={6} />
    </div>
  );
}

// ── 페이지 4: 절세 최적화 전략 ──────────────────────────────────
function TaxPage() {
  const customer = useSelectedCustomer();
  // 계좌별 사용액 계산 (AccountAllocation 동일 로직)
  const accountRows = ACCOUNT_PDF.filter((acct) => acct.key !== "general").map(
    (acct) => {
      const accData = TAX_EFFECT.accounts.find((a) => a.name === acct.name);
      const used =
        accData?.used != null
          ? accData.used
          : Math.round(acct.refManwon * 0.45);
      return { ...acct, used };
    },
  );

  return (
    <div
      data-pdf-page=""
      style={{
        width: W,
        height: H,
        fontFamily: "Pretendard, Apple SD Gothic Neo, sans-serif",
        background: "white",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <PageHeader
        pageNum="③"
        title="절세 최적화 전략"
        subtitle="세금 효과 시뮬레이터"
      />

      <div style={{ padding: "20px 40px 80px", wordBreak: "keep-all" }}>
        {/* 연간 절세 효과 하이라이트 */}
        <div
          style={{
            background: `linear-gradient(135deg, ${BRAND_DARK} 0%, ${BRAND} 60%, #2C7BFF 100%)`,
            borderRadius: 12,
            padding: "16px 24px",
            marginBottom: 20,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div
              style={{
                color: "rgba(255,255,255,0.7)",
                fontSize: 11,
                fontWeight: 600,
                marginBottom: 4,
              }}
            >
              연간 절세 효과 (포트폴리오 A 기준 · {customer.aumLabel})
            </div>
            <div
              style={{
                color: "white",
                fontSize: 34,
                fontWeight: 900,
                lineHeight: 1,
              }}
            >
              + {TAX_EFFECT.annualSavingManwon.toLocaleString()}만원
            </div>
          </div>
          <div style={{ textAlign: "right", maxWidth: 260 }}>
            <div
              style={{
                color: "rgba(255,255,255,0.65)",
                fontSize: 11,
                lineHeight: 1.7,
              }}
            >
              {TAX_EFFECT.subNote}
            </div>
          </div>
        </div>

        {/* 섹션 1: 절세 전략 비교 */}
        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 12 }}
        >
          <SectionBar />
          <div style={{ fontSize: 13, fontWeight: 800, color: TEXT }}>
            절세 전략 비교 ({TAX_EFFECT.flow.pretaxLabel})
          </div>
        </div>

        <div style={{ display: "flex", gap: 12, marginBottom: 20 }}>
          {/* 세금 효과 비교 테이블 */}
          <div
            style={{
              flex: 1.1,
              border: `1px solid ${BORDER}`,
              borderRadius: 10,
              overflow: "hidden",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <div
              style={{
                background: BG_ALT,
                padding: "6px 12px",
                fontSize: 11,
                fontWeight: 800,
                color: TEXT,
                borderBottom: `1px solid ${BORDER}`,
              }}
            >
              세금 효과 비교
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${BORDER}` }}>
                  {["구분", "세후 수익", "절세액", "비고"].map((h) => (
                    <th
                      key={h}
                      style={{
                        padding: "5px 8px",
                        fontSize: 10,
                        fontWeight: 700,
                        color: MUTED,
                        textAlign: "center",
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {TAX_EFFECT.flow.rows.map((row, i) => (
                  <tr
                    key={row.label}
                    style={{
                      borderBottom: `1px solid ${BORDER}`,
                      background: "white",
                    }}
                  >
                    <td
                      style={{
                        padding: "7px 8px",
                        fontSize: 11,
                        fontWeight: 700,
                        color: TEXT,
                      }}
                    >
                      {row.label}
                    </td>
                    <td
                      style={{
                        padding: "7px 8px",
                        fontSize: 10,
                        textAlign: "center",
                        color: TEXT,
                      }}
                    >
                      세후 {row.afterTaxManwon.toLocaleString()}만원
                    </td>
                    <td
                      style={{
                        padding: "7px 8px",
                        fontSize: 10,
                        textAlign: "center",
                        fontWeight: 700,
                        color: UP,
                      }}
                    >
                      {row.taxManwon.toLocaleString()}만
                    </td>
                    <td
                      style={{
                        padding: "7px 8px",
                        fontSize: 10,
                        textAlign: "center",
                        color: MUTED,
                      }}
                    >
                      {i === 0 ? "기준" : "ISA+IRP"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div
              style={{
                padding: "7px 12px",
                background: BG_ALT,
                borderTop: `1px solid ${BORDER}`,
                marginTop: "auto",
              }}
            >
              <div style={{ fontSize: 10, color: MUTED, lineHeight: 1.7 }}>
                ✓ 세후 수익률 {TAX_EFFECT.afterTaxReturn.from} →{" "}
                {TAX_EFFECT.afterTaxReturn.to} (
                {TAX_EFFECT.afterTaxReturn.delta})<br />✓ 실효세 절감{" "}
                {TAX_EFFECT.effectiveTax.from} → {TAX_EFFECT.effectiveTax.to} (
                {TAX_EFFECT.effectiveTax.delta})
              </div>
            </div>
          </div>

          {/* 절세 계좌 배치 최적화 — 대시보드 동일 레이아웃 */}
          <div
            style={{
              flex: 1,
              border: `1px solid ${BORDER}`,
              borderRadius: 10,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                background: BG_ALT,
                padding: "6px 12px",
                fontSize: 11,
                fontWeight: 800,
                color: TEXT,
                borderBottom: `1px solid ${BORDER}`,
              }}
            >
              절세 계좌 배치 최적화
            </div>
            <div style={{ padding: "12px 14px 10px" }}>
              {/* 전체 계좌 세그먼트 바 */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  marginBottom: 4,
                }}
              >
                <span
                  style={{
                    width: 68,
                    flexShrink: 0,
                    textAlign: "right" as const,
                    paddingRight: 8,
                    fontSize: 10,
                    fontWeight: 800,
                    color: "#4E5968",
                  }}
                >
                  전체 계좌
                </span>
                <div
                  style={{
                    flex: 1,
                    height: 10,
                    display: "flex",
                    overflow: "hidden",
                    borderRadius: 4,
                    marginRight: 47,
                  }}
                >
                  {ASSET_GROUPS.map((g, i) => (
                    <div
                      key={g.label}
                      style={{
                        width: `${WEIGHTS.a[i]}%`,
                        height: "100%",
                        background: g.color,
                      }}
                    />
                  ))}
                </div>
              </div>
              {/* 세그먼트 범례 */}
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap" as const,
                  gap: "2px 6px",
                  marginLeft: 68,
                  marginBottom: 10,
                }}
              >
                {ASSET_GROUPS.map((g, i) => (
                  <span
                    key={g.label}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 3,
                      fontSize: 9,
                      color: MUTED,
                      fontWeight: 600,
                    }}
                  >
                    <span
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: 1,
                        background: g.color,
                        display: "inline-block",
                        flexShrink: 0,
                      }}
                    />
                    {g.label} {WEIGHTS.a[i]}%
                  </span>
                ))}
              </div>
              {/* Y축 + 바 영역 */}
              <div style={{ display: "flex", gap: 0 }}>
                {/* Y축 레이블 */}
                <div style={{ width: 68, flexShrink: 0 }}>
                  {accountRows.map((acct, idx) => (
                    <div
                      key={acct.name}
                      style={{
                        height: 30,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "flex-end",
                        paddingRight: 8,
                        marginBottom: idx < accountRows.length - 1 ? 14 : 0,
                        fontSize: 10,
                        fontWeight: 800,
                        color: "#4E5968",
                        textAlign: "right" as const,
                        lineHeight: 1.2,
                      }}
                    >
                      {acct.name}
                    </div>
                  ))}
                </div>
                {/* 바 영역 */}
                <div style={{ flex: 1 }}>
                  {accountRows.map((acct, idx) => {
                    const refPct = (acct.refManwon / ACCOUNT_CHART_MAX) * 100;
                    const usedPct = (acct.used / ACCOUNT_CHART_MAX) * 100;
                    const usedColor = idx === 0 ? "#0064FF" : "#3D8BFF";
                    return (
                      <div
                        key={acct.name}
                        style={{
                          marginBottom: idx < accountRows.length - 1 ? 14 : 0,
                        }}
                      >
                        {/* 기준값 바 (회색, 위) + 값 */}
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 5,
                            marginBottom: 4,
                          }}
                        >
                          <div
                            style={{
                              flex: 1,
                              height: 13,
                              background: "#F3F4F6",
                              borderRadius: 4,
                              overflow: "hidden",
                            }}
                          >
                            <div
                              style={{
                                width: `${refPct}%`,
                                height: "100%",
                                background: "#D1D5DB",
                                borderRadius: 4,
                              }}
                            />
                          </div>
                          <span
                            style={{
                              width: 42,
                              fontSize: 9,
                              fontWeight: 600,
                              color: MUTED,
                              textAlign: "right" as const,
                              flexShrink: 0,
                            }}
                          >
                            {acct.refManwon.toLocaleString()}만
                          </span>
                        </div>
                        {/* 사용액 바 (파란색, 아래) + 값 */}
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 5,
                          }}
                        >
                          <div
                            style={{
                              flex: 1,
                              height: 13,
                              background: "#F3F4F6",
                              borderRadius: 4,
                              overflow: "hidden",
                            }}
                          >
                            <div
                              style={{
                                width: `${usedPct}%`,
                                height: "100%",
                                background: usedColor,
                                borderRadius: 4,
                              }}
                            />
                          </div>
                          <span
                            style={{
                              width: 42,
                              fontSize: 9,
                              fontWeight: 800,
                              color: usedColor,
                              textAlign: "right" as const,
                              flexShrink: 0,
                            }}
                          >
                            {acct.used.toLocaleString()}만
                          </span>
                        </div>
                      </div>
                    );
                  })}
                  {/* X축 틱 */}
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      marginTop: 6,
                    }}
                  >
                    {["0", "500만", "1천만", "1500만", "2천만"].map((t) => (
                      <span
                        key={t}
                        style={{
                          fontSize: 8.5,
                          color: "#B0B8C1",
                          fontWeight: 600,
                        }}
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
              {/* 범례 (하단) */}
              <div style={{ display: "flex", gap: 14, marginTop: 10 }}>
                {[
                  { color: "#0064FF", label: "ISA 사용액" },
                  { color: "#3D8BFF", label: "연금 사용액" },
                  { color: "#D1D5DB", label: "기준값" },
                ].map((l) => (
                  <div
                    key={l.label}
                    style={{ display: "flex", alignItems: "center", gap: 5 }}
                  >
                    <div
                      style={{
                        width: 10,
                        height: 10,
                        background: l.color,
                        borderRadius: 2,
                      }}
                    />
                    <span
                      style={{ fontSize: 9.5, color: MUTED, fontWeight: 700 }}
                    >
                      {l.label}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* 섹션 2: 절세 제안 6개 카드 (전략 요약만 — 상품은 하단 표 참조) */}
        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 12 }}
        >
          <SectionBar />
          <div style={{ fontSize: 13, fontWeight: 800, color: TEXT }}>
            절세 제안
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 10,
            marginBottom: 10,
          }}
        >
          {TAX_ADVICE.cards.map((card) => (
            <div
              key={card.title}
              style={{
                border: `1px solid ${BORDER}`,
                borderRadius: 10,
                padding: "12px 14px",
                background: "white",
              }}
            >
              {/* 헤더: 제목만 */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  marginBottom: 8,
                }}
              >
                <span style={{ fontSize: 12, fontWeight: 800, color: TEXT }}>
                  {card.title}
                </span>
              </div>
              {/* 본문 */}
              <p
                style={{
                  fontSize: 11,
                  color: MUTED,
                  lineHeight: 1.65,
                  margin: "0 0 6px 0",
                }}
              >
                {card.body}
              </p>
              {/* 태그 */}
              <div style={{ fontSize: 10, color: "#9CA3AF", marginBottom: 5 }}>
                {card.tag}
              </div>
              {/* 절세액 — 태그 아래 */}
              {card.saving && (
                <span style={{ fontSize: 13, fontWeight: 900, color: UP }}>
                  {card.saving}
                </span>
              )}
            </div>
          ))}
        </div>

        {/* 총 절세 효과 요약 바 */}
        <div
          style={{
            background: BRAND_LIGHT,
            border: `1px solid ${BRAND_MID}`,
            borderRadius: 7,
            padding: "7px 14px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span style={{ fontSize: 10, fontWeight: 700, color: BRAND_DARK }}>
            {TAX_ADVICE.totalLabel}
          </span>
          <span style={{ fontSize: 11, fontWeight: 900, color: BRAND_DARK }}>
            {TAX_ADVICE.totalSaving}
          </span>
        </div>
      </div>

      <PageFooter page={4} total={6} />
    </div>
  );
}

// ── 페이지 5: 절세 제안 추천 상품 ──────────────────────────────
function TaxProductsPage() {
  return (
    <div
      data-pdf-page=""
      style={{
        width: W,
        height: H,
        fontFamily: "Pretendard, Apple SD Gothic Neo, sans-serif",
        background: "white",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <PageHeader
        pageNum="③-2"
        title="전략별 추천 상품"
        subtitle="삼성증권 상품 연계 목록"
      />

      <div style={{ padding: "28px 40px 80px", wordBreak: "keep-all" }}>
        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 16 }}
        >
          <SectionBar />
          <div style={{ fontSize: 15, fontWeight: 800, color: TEXT }}>
            전략별 추천 상품 목록
          </div>
        </div>

        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            tableLayout: "fixed",
          }}
        >
          <colgroup>
            <col style={{ width: 176 }} />
            <col />
          </colgroup>
          <thead>
            <tr style={{ background: BRAND }}>
              <th
                style={{
                  padding: "10px 14px",
                  textAlign: "left",
                  fontSize: 13,
                  fontWeight: 700,
                  color: "white",
                }}
              >
                전략
              </th>
              <th
                style={{
                  padding: "10px 14px",
                  textAlign: "left",
                  fontSize: 13,
                  fontWeight: 700,
                  color: "white",
                }}
              >
                추천 상품 목록
              </th>
            </tr>
          </thead>
          <tbody>
            {TAX_ADVICE.cards.map((card, i) => (
              <tr
                key={card.title}
                style={{
                  borderBottom: `1px solid ${BORDER}`,
                  background: i % 2 === 0 ? "white" : BG_ALT,
                }}
              >
                <td
                  style={{
                    padding: "13px 14px",
                    verticalAlign: "top" as const,
                  }}
                >
                  <div
                    style={{ display: "flex", alignItems: "center", gap: 8 }}
                  >
                    <span
                      style={{ fontSize: 13, fontWeight: 800, color: TEXT }}
                    >
                      {card.title}
                    </span>
                  </div>
                </td>
                <td
                  style={{
                    padding: "13px 14px",
                    fontSize: 12,
                    color: TEXT,
                    lineHeight: 1.85,
                    whiteSpace: "pre-line" as const,
                  }}
                >
                  {card.products.map((p) => p.name).join("\n")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <PageFooter page={5} total={6} />
    </div>
  );
}

// ── 페이지 6: AI 인사이트 ────────────────────────────────────────
function AiPage() {
  const insightResult = useDashboardStore((s) => s.insightResult);
  const answer = insightResult?.data?.answer ?? INSIGHT.defaultAnswer;
  const citationSources = insightResult?.data?.citations ?? INSIGHT.sources;
  return (
    <div
      data-pdf-page=""
      style={{
        width: W,
        height: H,
        fontFamily: "Pretendard, Apple SD Gothic Neo, sans-serif",
        background: "white",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <PageHeader
        pageNum="④"
        title="AI 인사이트"
        subtitle="RAG 기반 포트폴리오 분석 · 시장 환경 대응 제안"
      />

      <div style={{ padding: "28px 40px 80px", wordBreak: "keep-all" }}>
        {/* AI 인사이트 */}
        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 20 }}
        >
          <SectionBar />
          <div style={{ fontSize: 15, fontWeight: 800, color: TEXT }}>
            AI 인사이트
          </div>
        </div>

        <div
          style={{
            border: `1px solid ${BORDER}`,
            borderRadius: 10,
            padding: "16px 20px",
            background: BG_ALT,
            marginBottom: 36,
          }}
        >
          <div
            style={{
              display: "flex",
              gap: 8,
              marginBottom: 12,
              alignItems: "flex-start",
            }}
          >
            <span
              style={{
                fontSize: 14,
                fontWeight: 900,
                color: BRAND,
                flexShrink: 0,
                lineHeight: 1.5,
              }}
            >
              Q.
            </span>
            <span
              style={{
                fontSize: 12,
                color: TEXT,
                fontWeight: 600,
                lineHeight: 1.65,
                paddingTop: 1,
              }}
            >
              {INSIGHT.query}
            </span>
          </div>
          <div
            style={{
              borderTop: `1px solid ${BORDER}`,
              paddingTop: 12,
              display: "flex",
              gap: 8,
              alignItems: "flex-start",
            }}
          >
            <span
              style={{
                fontSize: 14,
                fontWeight: 900,
                color: TEXT,
                flexShrink: 0,
                lineHeight: 1.5,
              }}
            >
              A.
            </span>
            <span
              style={{
                fontSize: 12,
                color: "#374151",
                lineHeight: 1.75,
                paddingTop: 1,
              }}
            >
              {answer}
            </span>
          </div>
        </div>

        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 16 }}
        >
          <SectionBar />
          <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>
            출처 / 인용 목록
          </div>
        </div>

        <table style={{ width: "100%", borderCollapse: "collapse" as const }}>
          <thead>
            <tr style={{ background: BG_ALT }}>
              <th
                style={{
                  padding: "7px 12px",
                  textAlign: "left" as const,
                  fontSize: 11,
                  fontWeight: 700,
                  color: MUTED,
                  borderBottom: `1px solid ${BORDER}`,
                }}
              >
                파일명
              </th>
              <th
                style={{
                  padding: "7px 12px",
                  textAlign: "left" as const,
                  fontSize: 11,
                  fontWeight: 700,
                  color: MUTED,
                  borderBottom: `1px solid ${BORDER}`,
                  width: 110,
                }}
              >
                발행일자
              </th>
            </tr>
          </thead>
          <tbody>
            {citationSources.map((src, i) => (
              <tr
                key={src.title}
                style={{
                  borderBottom: `1px solid ${BORDER}`,
                  background: i % 2 === 0 ? "white" : BG_ALT,
                }}
              >
                <td
                  style={{
                    padding: "8px 12px",
                    fontSize: 11,
                    color: TEXT,
                    fontWeight: 600,
                  }}
                >
                  {src.title}
                </td>
                <td style={{ padding: "8px 12px", fontSize: 11, color: MUTED }}>
                  {src.date}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <PageFooter page={6} total={6} />
    </div>
  );
}

// ── 메인 ────────────────────────────────────────────────────────
export default function PbPdfTemplate() {
  return (
    <div>
      <CoverPage />
      <MarketIpsPage />
      <PortfolioPage />
      <TaxPage />
      <TaxProductsPage />
      <AiPage />
    </div>
  );
}
