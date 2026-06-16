/**
 * PB용 PDF 템플릿 — A4 세로(794×1123px) 4페이지.
 * 각 페이지에 data-pdf-page 속성을 부여하고,
 * PdfExportButton에서 페이지별로 캡처해 4페이지 PDF를 생성한다.
 */

import {
  CUSTOMERS,
  PORTFOLIOS,
  TAX_EFFECT,
  INSIGHT,
  MACRO_INDICATORS,
  BASE_TIME,
  IPS_DEFAULT,
} from "@/lib/mockData";

// ── 상수 ────────────────────────────────────────────────────────
const W = 794;
const H = 1123;
const BRAND = "#0050D6";
const BRAND_DARK = "#1A4BAF";
const BRAND_LIGHT = "#EFF4FF";
const UP = "#F04452";
const TEXT = "#111827";
const MUTED = "#6B7280";
const BORDER = "#E5E7EB";
const BG_ALT = "#FAFAFA";

const customer = CUSTOMERS[0];
const current = PORTFOLIOS.find((p) => p.id === "current")!;
const portA = PORTFOLIOS.find((p) => p.id === "a")!;
const portB = PORTFOLIOS.find((p) => p.id === "b")!;

// 6분류 자산군 (mockData 시안 기준)
const ASSET_GROUPS = [
  { label: "국내주식", color: BRAND },
  { label: "해외배당주", color: "#2C7BFF" },
  { label: "해외성장주", color: "#60A5FA" },
  { label: "일반채권", color: "#F59E0B" },
  { label: "저쿠폰채", color: "#FCD34D" },
  { label: "분리과세", color: "#34D399" },
];
const WEIGHTS = {
  current: [25, 18, 12, 22, 12, 11],
  a: [20, 22, 12, 18, 14, 14],
  b: [28, 26, 22, 12, 8, 4],
};

const IPS_ROWS = [
  { key: "GOAL", korean: "투자 목적", tag: "복합", tagColor: "#6B7280", detail: IPS_DEFAULT.goal + " (3년 내 자금 활용 가능성 포함)" },
  { key: "ASSET", korean: "운용 자산", tag: IPS_DEFAULT.assetLabel, tagColor: "#F59E0B", detail: "총 운용 가능 자산 기준. 기존 자산 구성 변경 검토 중" },
  { key: "RETURN", korean: "목표 수익률", tag: `${IPS_DEFAULT.returnPct}%`, tagColor: "#10B981", detail: `연 ${IPS_DEFAULT.returnPct}% 목표 (세후 기준). 변동성 최소화 조건 병행` },
  { key: "RISK", korean: "위험 성향", tag: IPS_DEFAULT.risk, tagColor: "#F59E0B", detail: "안정형~공격형 스펙트럼 중 균형형. MDD -15% 이내 선호" },
  { key: "TIME", korean: "투자 기간", tag: `${IPS_DEFAULT.timeYears}년`, tagColor: BRAND, detail: "장기 운용 기준. 단, 유동성 필요 시 분리 운용 필요" },
  { key: "TAX", korean: "세금", tag: "종합과세", tagColor: UP, detail: IPS_DEFAULT.tax + " 절세전략 필요" },
  { key: "LIQUID", korean: "유동성", tag: IPS_DEFAULT.liquidity, tagColor: "#F59E0B", detail: "낮음~높음 중 중간. 비상자금 3억 별도 보유 권장" },
  { key: "LEGAL", korean: "법적 제약", tag: "검토필요", tagColor: UP, detail: IPS_DEFAULT.legal + ". 사전 증여 전략 수립 권장" },
  { key: "UNIQUE", korean: "특수 사항", tag: "복합", tagColor: "#6B7280", detail: IPS_DEFAULT.unique },
];

const SCENARIO_ROWS = [
  { name: "기준 시나리오", rate: "3.50%", fx: "1,220원", pnl: "+9,900만원", pnlColor: UP, action: "변화 없음" },
  { name: "금리 상승 시나리오", rate: "4.75%", fx: "1,420원", pnl: "▲ 0만원", pnlColor: MUTED, action: "채권 비중 축소 권장" },
  { name: "환율 상승 헤지", rate: "현행", fx: "1,420원", pnl: "환헤지 비중 상향", pnlColor: BRAND, action: "해외 비중 상향 효과" },
];

// ── 날짜 유틸 ────────────────────────────────────────────────────
function getToday() {
  const d = new Date();
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, "0")}.${String(d.getDate()).padStart(2, "0")}`;
}

// ── 공통 컴포넌트 ────────────────────────────────────────────────
function PageHeaderBar({ circled, title, sub }: { circled: string; title: string; sub: string }) {
  return (
    <div style={{ background: `linear-gradient(90deg, ${BRAND_DARK} 0%, ${BRAND} 100%)`, height: 62, padding: "0 36px", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
      <div>
        <div style={{ color: "white", fontSize: 14, fontWeight: 800, lineHeight: 1.3 }}>
          {circled} {title}
        </div>
        <div style={{ color: "rgba(255,255,255,0.6)", fontSize: 11 }}>{sub}</div>
      </div>
      <div style={{ textAlign: "right" }}>
        <div style={{ color: "white", fontSize: 12, fontWeight: 700 }}>{customer.name} · {customer.grade}</div>
        <div style={{ color: "rgba(255,255,255,0.6)", fontSize: 11 }}>{customer.pbCode} · {getToday()}</div>
      </div>
    </div>
  );
}

function PageFooter({ page, total }: { page: number; total: number }) {
  return (
    <div style={{ height: 34, borderTop: `1px solid ${BORDER}`, background: BG_ALT, display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 36px", flexShrink: 0 }}>
      <span style={{ fontSize: 11, color: "#9CA3AF" }}>VVIP PB Advisor · 내부 기밀 자료</span>
      <span style={{ fontSize: 11, color: "#9CA3AF" }}>Page {page} / {total}</span>
      <span style={{ fontSize: 11, color: "#9CA3AF" }}>{getToday()} {BASE_TIME}</span>
    </div>
  );
}

function SectionLabel({ title }: { title: string }) {
  return (
    <div style={{ borderLeft: `3px solid ${BRAND}`, paddingLeft: 10, marginBottom: 10, marginTop: 2 }}>
      <span style={{ fontSize: 13, fontWeight: 800, color: TEXT }}>{title}</span>
    </div>
  );
}

function AssetBar({ label, pct, color }: { label: string; pct: number; color: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 5 }}>
      <span style={{ width: 48, fontSize: 11, color: MUTED, flexShrink: 0 }}>{label}</span>
      <div style={{ flex: 1, height: 7, background: "#F3F4F6", borderRadius: 4, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 4 }} />
      </div>
      <span style={{ width: 26, fontSize: 11, fontWeight: 700, textAlign: "right", color }}>{pct}%</span>
    </div>
  );
}

// ── 페이지 1: 표지 ───────────────────────────────────────────────
function CoverPage() {
  const today = getToday();
  return (
    <div
      data-pdf-page=""
      style={{ width: W, height: H, background: "white", fontFamily: "Pretendard, sans-serif", display: "flex", flexDirection: "column", overflow: "hidden" }}
    >
      {/* 상단 그라데이션 배너 */}
      <div style={{ background: `linear-gradient(135deg, ${BRAND_DARK} 0%, ${BRAND} 65%, #2C7BFF 100%)`, padding: "30px 40px 36px", flexShrink: 0 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 70 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 34, height: 34, background: "rgba(255,255,255,0.2)", borderRadius: 9, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 17, fontWeight: 900, color: "white" }}>S</div>
            <span style={{ color: "white", fontSize: 16, fontWeight: 800, letterSpacing: 0.5 }}>S.upervisor</span>
          </div>
          <span style={{ background: "rgba(255,255,255,0.15)", border: "1px solid rgba(255,255,255,0.25)", color: "rgba(255,255,255,0.92)", fontSize: 11, fontWeight: 700, padding: "5px 13px", borderRadius: 20 }}>
            PB 내부용 · CONFIDENTIAL
          </span>
        </div>
        <div style={{ color: "rgba(255,255,255,0.55)", fontSize: 11, fontWeight: 600, letterSpacing: 2.5 }}>
          VVIP PB ADVISOR · PORTFOLIO ADVISORY
        </div>
      </div>

      {/* 타이틀 영역 */}
      <div style={{ padding: "44px 40px 0", flex: 1, display: "flex", flexDirection: "column" }}>
        <h1 style={{ fontSize: 44, fontWeight: 900, color: TEXT, lineHeight: 1.15, margin: 0, marginBottom: 10 }}>
          포트폴리오<br />
          분석 <span style={{ color: BRAND }}>리포트</span>
        </h1>
        <p style={{ fontSize: 13, color: MUTED, margin: "10px 0 0 0" }}>
          PB 상담 보조 자료 · Portfolio Analysis Report
        </p>

        <div style={{ width: 52, height: 3, background: BRAND, borderRadius: 2, margin: "28px 0 36px" }} />

        {/* 고객 카드 */}
        <div style={{ background: BRAND_LIGHT, borderRadius: 16, padding: "22px 28px", border: `1px solid ${BRAND}25` }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: BRAND, letterSpacing: 2.5, marginBottom: 10 }}>CLIENT</div>
          <div style={{ fontSize: 28, fontWeight: 900, color: TEXT, marginBottom: 8 }}>{customer.name} 고객</div>
          <div style={{ fontSize: 12, color: MUTED }}>
            {customer.pbCode} · {customer.grade} 등급 · {customer.aumLabel}
          </div>
        </div>

        <div style={{ flex: 1 }} />
      </div>

      {/* 하단 통계 바 */}
      <div style={{ background: BG_ALT, borderTop: `1px solid ${BORDER}`, padding: "18px 40px", display: "flex", justifyContent: "space-around", flexShrink: 0 }}>
        {[
          { label: "REPORT DATE", value: today },
          { label: "BASE TIME", value: `${BASE_TIME} 기준` },
          { label: "RECOMMENDED", value: "포트폴리오 A" },
          { label: "TAX SAVING", value: `+${TAX_EFFECT.annualSavingManwon.toLocaleString()}만원/년` },
        ].map((item) => (
          <div key={item.label} style={{ textAlign: "center" }}>
            <div style={{ fontSize: 11, color: "#9CA3AF", fontWeight: 600, letterSpacing: 1.2, marginBottom: 6 }}>{item.label}</div>
            <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>{item.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── 페이지 2: 시장 현황 & IPS ────────────────────────────────────
function MarketIpsPage() {
  return (
    <div
      data-pdf-page=""
      style={{ width: W, height: H, background: "white", fontFamily: "Pretendard, sans-serif", display: "flex", flexDirection: "column", overflow: "hidden" }}
    >
      <PageHeaderBar circled="①" title="시장 현황 & 고객 IPS 요약" sub="Market Overview & Investment Policy Statement" />

      <div style={{ flex: 1, padding: "20px 36px 16px", display: "flex", flexDirection: "column", gap: 18, overflow: "hidden" }}>
        {/* 주요 시장 지표 */}
        <div>
          <SectionLabel title={`주요 시장 지표 (기준 ${BASE_TIME})`} />
          <div style={{ display: "flex", gap: 8 }}>
            {MACRO_INDICATORS.map((m) => (
              <div key={m.label} style={{ flex: 1, background: BRAND_LIGHT, borderRadius: 10, padding: "11px 13px" }}>
                <div style={{ fontSize: 11, color: MUTED, marginBottom: 5 }}>{m.label}</div>
                <div style={{ fontSize: 17, fontWeight: 900, color: TEXT, lineHeight: 1.1 }}>{m.value}</div>
                <div style={{ fontSize: 11, fontWeight: 700, marginTop: 4, color: m.direction === "up" ? UP : BRAND }}>
                  {m.direction === "up" ? "▲" : "▼"} {m.change}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* IPS 표 */}
        <div>
          <SectionLabel title="고객 IPS (투자정책서) 요약" />
          <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
            <colgroup>
              <col style={{ width: 140 }} />
              <col style={{ width: 90 }} />
              <col />
            </colgroup>
            <thead>
              <tr style={{ background: BRAND }}>
                <th style={{ padding: "9px 12px", textAlign: "left", fontSize: 11, fontWeight: 700, color: "white" }}>항목 (Category)</th>
                <th style={{ padding: "9px 12px", textAlign: "left", fontSize: 11, fontWeight: 700, color: "white" }}>분류</th>
                <th style={{ padding: "9px 12px", textAlign: "left", fontSize: 11, fontWeight: 700, color: "white" }}>세부 내용</th>
              </tr>
            </thead>
            <tbody>
              {IPS_ROWS.map((row, i) => (
                <tr key={row.key} style={{ borderBottom: `1px solid ${BORDER}`, background: i % 2 === 0 ? "white" : BG_ALT }}>
                  <td style={{ padding: "9px 12px" }}>
                    <div style={{ fontSize: 12, fontWeight: 800, color: TEXT }}>{row.key}</div>
                    <div style={{ fontSize: 11, color: MUTED }}>{row.korean}</div>
                  </td>
                  <td style={{ padding: "9px 12px" }}>
                    <span style={{ background: `${row.tagColor}18`, color: row.tagColor, fontSize: 11, fontWeight: 700, padding: "3px 9px", borderRadius: 12, whiteSpace: "nowrap" as const }}>
                      {row.tag}
                    </span>
                  </td>
                  <td style={{ padding: "9px 12px", fontSize: 11, color: MUTED, lineHeight: 1.55 }}>{row.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <PageFooter page={2} total={4} />
    </div>
  );
}

// ── 페이지 3: 포트폴리오 비교 ────────────────────────────────────
function PortfolioPage() {
  const cols = [
    { p: current, weights: WEIGHTS.current, label: "현재 포트폴리오", badge: "현재", badgeColor: "#6B7280", headerColor: "#6B7280" },
    { p: portA, weights: WEIGHTS.a, label: "포트폴리오 A", badge: "BEST", badgeColor: BRAND, headerColor: BRAND },
    { p: portB, weights: WEIGHTS.b, label: "포트폴리오 B", badge: "추천", badgeColor: "#2C7BFF", headerColor: "#2C7BFF" },
  ];

  const perfRows = [
    { label: "기대수익률 (연)", vals: [`${current.metrics.expectedReturnPct}%`, `${portA.metrics.expectedReturnPct}%`, `${portB.metrics.expectedReturnPct}%`] },
    { label: "변동성 (표준편차)", vals: [`${current.metrics.volatilityPct}%`, `${portA.metrics.volatilityPct}%`, `${portB.metrics.volatilityPct}%`] },
    { label: "샤프 지수", vals: [`${current.metrics.sharpe}`, `${portA.metrics.sharpe}`, `${portB.metrics.sharpe}`] },
    { label: "소르티노 지수", vals: [`${current.metrics.sortino}`, `${portA.metrics.sortino}`, `${portB.metrics.sortino}`] },
    { label: "최대낙폭 (MDD)", vals: [`▼${current.metrics.mddPct}%\n(${current.metrics.mddAmountLabel})`, `▼${portA.metrics.mddPct}%\n(${portA.metrics.mddAmountLabel})`, `▼${portB.metrics.mddPct}%\n(${portB.metrics.mddAmountLabel})`] },
    { label: "세후 수익률", vals: [`${current.metrics.afterTaxReturnPct}%\n(${current.metrics.afterTaxAmountLabel})`, `${portA.metrics.afterTaxReturnPct}%\n(${portA.metrics.afterTaxAmountLabel})`, `${portB.metrics.afterTaxReturnPct}%\n(${portB.metrics.afterTaxAmountLabel})`] },
  ];

  return (
    <div
      data-pdf-page=""
      style={{ width: W, height: H, background: "white", fontFamily: "Pretendard, sans-serif", display: "flex", flexDirection: "column", overflow: "hidden" }}
    >
      <PageHeaderBar circled="②" title="포트폴리오 비교 분석 (현재 vs A vs B)" sub="5년 백테스트 기준 · 절세 최적화 포함" />

      <div style={{ flex: 1, padding: "18px 36px 14px", display: "flex", flexDirection: "column", gap: 16, overflow: "hidden" }}>
        {/* 자산 배분 비교 */}
        <div>
          <SectionLabel title="자산 배분 비교" />
          <div style={{ display: "flex", gap: 12 }}>
            {cols.map(({ p, weights, label, badge, badgeColor }) => (
              <div key={p.id} style={{ flex: 1, border: `1px solid ${BORDER}`, borderRadius: 10, padding: "13px 14px", background: "white" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 11 }}>
                  <span style={{ fontSize: 12, fontWeight: 800, color: TEXT }}>{label}</span>
                  <span style={{ fontSize: 11, fontWeight: 700, color: badgeColor, background: `${badgeColor}18`, padding: "2px 8px", borderRadius: 10 }}>{badge}</span>
                </div>
                {ASSET_GROUPS.map((g, i) => (
                  <AssetBar key={g.label} label={g.label} pct={weights[i]} color={g.color} />
                ))}
              </div>
            ))}
          </div>
        </div>

        {/* 성과 지표 비교 */}
        <div>
          <SectionLabel title="성과 지표 비교 (5년 백테스트 기준)" />
          <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
            <colgroup>
              <col style={{ width: 150 }} />
              <col /><col /><col />
            </colgroup>
            <thead>
              <tr style={{ background: BG_ALT }}>
                <th style={{ padding: "8px 10px", textAlign: "left", fontSize: 11, fontWeight: 700, color: MUTED, borderBottom: `2px solid ${BORDER}` }}>지표</th>
                {cols.map((c) => (
                  <th key={c.p.id} style={{ padding: "8px 10px", textAlign: "center", fontSize: 11, fontWeight: 700, color: c.headerColor, borderBottom: `2px solid ${c.headerColor}` }}>
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {perfRows.map((row, i) => (
                <tr key={row.label} style={{ borderBottom: `1px solid ${BORDER}`, background: i % 2 === 0 ? "white" : BG_ALT }}>
                  <td style={{ padding: "8px 10px", fontSize: 11, color: TEXT }}>{row.label}</td>
                  {row.vals.map((v, j) => (
                    <td key={j} style={{ padding: "8px 10px", textAlign: "center", fontSize: 11, fontWeight: j === 0 ? 500 : 700, color: cols[j].headerColor, whiteSpace: "pre-line" as const, lineHeight: 1.4 }}>{v}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* 시나리오 분석 */}
        <div>
          <SectionLabel title="시나리오 분석 (금리 4.75%, 환율 1,420원)" />
          <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
            <colgroup>
              <col style={{ width: 160 }} />
              <col style={{ width: 70 }} />
              <col style={{ width: 80 }} />
              <col style={{ width: 130 }} />
              <col />
            </colgroup>
            <thead>
              <tr style={{ background: BG_ALT }}>
                {["시나리오", "금리", "환율", "예상 평가손익", "포트폴리오 A 영향"].map((h) => (
                  <th key={h} style={{ padding: "7px 10px", textAlign: "left", fontSize: 11, fontWeight: 700, color: MUTED, borderBottom: `1px solid ${BORDER}` }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {SCENARIO_ROWS.map((row, i) => (
                <tr key={row.name} style={{ borderBottom: `1px solid ${BORDER}`, background: i % 2 === 0 ? "white" : BG_ALT }}>
                  <td style={{ padding: "8px 10px", fontSize: 11, fontWeight: 700, color: TEXT }}>{row.name}</td>
                  <td style={{ padding: "8px 10px", fontSize: 11, color: MUTED }}>{row.rate}</td>
                  <td style={{ padding: "8px 10px", fontSize: 11, color: MUTED }}>{row.fx}</td>
                  <td style={{ padding: "8px 10px", fontSize: 11, fontWeight: 700, color: row.pnlColor }}>{row.pnl}</td>
                  <td style={{ padding: "8px 10px", fontSize: 11, color: MUTED }}>{row.action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <PageFooter page={3} total={4} />
    </div>
  );
}

// ── 페이지 4: 절세 & AI 인사이트 ─────────────────────────────────
function TaxAiPage() {
  const aiParas = INSIGHT.defaultAnswer.split("\n\n");

  return (
    <div
      data-pdf-page=""
      style={{ width: W, height: H, background: "white", fontFamily: "Pretendard, sans-serif", display: "flex", flexDirection: "column", overflow: "hidden" }}
    >
      <PageHeaderBar circled="③" title="절세 최적화 전략 & AI 인사이트" sub="세금 효과 시뮬레이터 · 절세 계좌 배치도 · AI 분석" />

      <div style={{ flex: 1, padding: "18px 36px 14px", display: "flex", flexDirection: "column", gap: 16, overflow: "hidden" }}>
        {/* 연간 절세 효과 하이라이트 */}
        <div style={{ background: `linear-gradient(135deg, ${BRAND_DARK} 0%, ${BRAND} 100%)`, borderRadius: 13, padding: "18px 24px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <div style={{ color: "rgba(255,255,255,0.7)", fontSize: 12, fontWeight: 600, marginBottom: 5 }}>
              연간 절세 효과 (포트폴리오 A 기준 · 18억원)
            </div>
            <div style={{ color: "white", fontSize: 30, fontWeight: 900, lineHeight: 1 }}>
              + {TAX_EFFECT.annualSavingManwon.toLocaleString()}만원
            </div>
          </div>
          <div style={{ textAlign: "right", maxWidth: 300 }}>
            <div style={{ color: "rgba(255,255,255,0.65)", fontSize: 11, lineHeight: 1.7 }}>{TAX_EFFECT.subNote}</div>
          </div>
        </div>

        {/* 절세 전략 비교 + 계좌 배치 */}
        <div>
          <SectionLabel title={`절세 전략 비교 (${TAX_EFFECT.flow.pretaxLabel})`} />
          <div style={{ display: "flex", gap: 14 }}>
            {/* 세금 효과 비교 테이블 */}
            <div style={{ flex: 1.1, border: `1px solid ${BORDER}`, borderRadius: 10, overflow: "hidden" }}>
              <div style={{ background: BG_ALT, padding: "8px 12px", fontSize: 12, fontWeight: 800, color: TEXT, borderBottom: `1px solid ${BORDER}` }}>세금 효과 비교</div>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: `1px solid ${BORDER}` }}>
                    {["구분", "세후 수익", "절세액", "비고"].map((h) => (
                      <th key={h} style={{ padding: "7px 10px", fontSize: 11, fontWeight: 700, color: MUTED, textAlign: "center" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {TAX_EFFECT.flow.rows.map((row, i) => (
                    <tr key={row.label} style={{ borderBottom: `1px solid ${BORDER}`, background: i === 1 ? BRAND_LIGHT : "white" }}>
                      <td style={{ padding: "9px 10px", fontSize: 12, fontWeight: 700, color: i === 1 ? BRAND : TEXT }}>{row.label}</td>
                      <td style={{ padding: "9px 10px", fontSize: 11, textAlign: "center", color: TEXT }}>세후 {row.afterTax.toLocaleString()}만원</td>
                      <td style={{ padding: "9px 10px", fontSize: 11, textAlign: "center", fontWeight: 700, color: UP }}>{row.tax.toLocaleString()}만</td>
                      <td style={{ padding: "9px 10px", fontSize: 11, textAlign: "center", color: MUTED }}>{i === 0 ? "기준" : "ISA+IRP"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ padding: "9px 12px", background: BG_ALT, borderTop: `1px solid ${BORDER}` }}>
                <div style={{ fontSize: 11, color: MUTED, lineHeight: 1.7 }}>
                  ✓ 세후 수익률 {TAX_EFFECT.afterTaxReturn.from} → {TAX_EFFECT.afterTaxReturn.to} ({TAX_EFFECT.afterTaxReturn.delta})<br />
                  ✓ 실효세 절감 {TAX_EFFECT.effectiveTax.from} → {TAX_EFFECT.effectiveTax.to} ({TAX_EFFECT.effectiveTax.delta})
                </div>
              </div>
            </div>

            {/* 절세 계좌 배치 */}
            <div style={{ flex: 1, border: `1px solid ${BORDER}`, borderRadius: 10, overflow: "hidden" }}>
              <div style={{ background: BG_ALT, padding: "8px 12px", fontSize: 12, fontWeight: 800, color: TEXT, borderBottom: `1px solid ${BORDER}` }}>절세 계좌 배치 최적화</div>
              <div style={{ padding: "12px 14px", display: "flex", flexDirection: "column", gap: 12 }}>
                {TAX_EFFECT.accounts.map((acc) => (
                  <div key={acc.name}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 3 }}>
                      <span style={{ fontSize: 12, fontWeight: 800, color: TEXT }}>{acc.name}</span>
                      {acc.used != null && (
                        <span style={{ fontSize: 11, fontWeight: 700, color: BRAND }}>{acc.used.toLocaleString()}만원</span>
                      )}
                    </div>
                    {acc.used != null && acc.limit != null && (
                      <div style={{ height: 5, background: "#F3F4F6", borderRadius: 3, overflow: "hidden", marginBottom: 4 }}>
                        <div style={{ width: `${(acc.used / acc.limit) * 100}%`, height: "100%", background: BRAND, borderRadius: 3 }} />
                      </div>
                    )}
                    <div style={{ fontSize: 11, color: MUTED, lineHeight: 1.6 }}>{acc.caption}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* AI 인사이트 */}
        <div>
          <SectionLabel title="AI 인사이트" />
          <div style={{ display: "flex", gap: 12 }}>
            {[
              { title: "금리 상승 대응 인사이트", body: aiParas[0]?.slice(0, 130) + "…" },
              { title: "포트폴리오 최적화 제안", body: aiParas[1]?.slice(0, 130) + "…" },
            ].map((card) => (
              <div key={card.title} style={{ flex: 1, border: `1px solid ${BRAND}30`, borderRadius: 10, padding: "12px 14px", background: BRAND_LIGHT }}>
                <div style={{ fontSize: 12, fontWeight: 800, color: BRAND, marginBottom: 7 }}>{card.title}</div>
                <div style={{ fontSize: 11, color: "#374151", lineHeight: 1.75 }}>{card.body}</div>
              </div>
            ))}
          </div>
        </div>

        {/* 출처 / 인용 목록 */}
        <div>
          <SectionLabel title="출처 / 인용 목록" />
          <div style={{ display: "flex", flexWrap: "wrap" as const, gap: 8 }}>
            {INSIGHT.sources.map((src) => (
              <div key={src.title} style={{ background: BG_ALT, border: `1px solid ${BORDER}`, borderRadius: 8, padding: "6px 13px", fontSize: 11, color: MUTED, display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ color: TEXT, fontWeight: 600 }}>{src.title}</span>
                <span style={{ color: "#D1D5DB" }}>·</span>
                <span>{src.date}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <PageFooter page={4} total={4} />
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
      <TaxAiPage />
    </div>
  );
}
