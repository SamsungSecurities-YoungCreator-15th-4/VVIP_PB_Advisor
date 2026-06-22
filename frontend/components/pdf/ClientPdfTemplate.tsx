/**
 * 고객용 PDF 템플릿 — A4 세로(794×1123px) 고정, 5페이지.
 * 구조: 표지 → 시장&IPS → 포트폴리오 비교&지표 → 절세&계좌 → 분산투자&상관관계
 */

import {
  MACRO_INDICATORS,
  CUSTOMERS,
  PORTFOLIOS,
  TAX_EFFECT,
  IPS_DEFAULT,
  CORRELATION_MATRIX,
} from "@/lib/mockData";
import { DISPLAY_GROUPS } from "@/lib/assetMapping";

const C = CUSTOMERS[0];
const portCurrent = PORTFOLIOS.find((p) => p.id === "current")!;
const portA = PORTFOLIOS.find((p) => p.id === "a")!;

const BRAND = "#0050D6";
const BRAND_DARK = "#1A4BAF";
const BRAND_LIGHT = "#EFF4FF";
const BRAND_MID = "#DBEAFE";
const UP = "#F04452";
const TEXT = "#111827";
const MUTED = "#6B7280";
const BORDER = "#E5E7EB";

const getTodayShort = () =>
  new Date()
    .toLocaleDateString("ko-KR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    })
    .replace(/\. /g, ".")
    .replace(/\.$/, "");

// ── 공통 헬퍼 ──────────────────────────────────────────────────

function PageFooter({ page, total }: { page: number; total: number }) {
  return (
    <div
      style={{
        position: "absolute",
        bottom: 24,
        left: 40,
        right: 40,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        borderTop: `1px solid ${BORDER}`,
        paddingTop: 8,
      }}
    >
      <span style={{ fontSize: 10, color: MUTED }}>
        VVIP PB Advisor · 고객 안내 자료
      </span>
      <span style={{ fontSize: 10, color: MUTED }}>
        Page {page} / {total}
      </span>
      <span style={{ fontSize: 10, color: MUTED }}>{getTodayShort()}</span>
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

// ── Page 1: 표지 ────────────────────────────────────────────────

function CoverPage() {
  return (
    <div
      data-pdf-page=""
      style={{
        width: 794,
        height: 1123,
        fontFamily: "Pretendard, Apple SD Gothic Neo, sans-serif",
        background: "white",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* 상단 그라디언트 배너 */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 420,
          background:
            "linear-gradient(135deg, #1A4BAF 0%, #0050D6 55%, #2C7BFF 100%)",
        }}
      />

      {/* 물결 곡선 장식 */}
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

      {/* 배너 내용 */}
      <div style={{ position: "relative", padding: "44px 52px 0" }}>
        {/* 로고 영역 */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            marginBottom: 32,
          }}
        >
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 9,
              background: "rgba(255,255,255,0.2)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 18,
              fontWeight: 900,
              color: "white",
            }}
          >
            S
          </div>
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

        {/* 부제 */}
        <div
          style={{
            fontSize: 13,
            color: "rgba(255,255,255,0.85)",
            marginBottom: 60,
            fontWeight: 500,
          }}
        >
          고객님의 소중한 자산을 위한 맞춤형 포트폴리오 분석 보고서입니다.
        </div>

        {/* 메인 타이틀 */}
        <div
          style={{
            fontSize: 44,
            fontWeight: 900,
            color: "white",
            lineHeight: 1.2,
            marginBottom: 8,
          }}
        >
          투자 포트폴리오
          <br />
          분석 보고서
        </div>
        <div
          style={{
            fontSize: 14,
            color: "rgba(255,255,255,0.65)",
            fontWeight: 400,
          }}
        >
          My Portfolio Analysis &amp; Tax Optimization Report
        </div>
      </div>

      {/* 흰색 영역 콘텐츠 */}
      <div style={{ position: "relative", padding: "60px 52px 0" }}>
        {/* 구분선 */}
        <div
          style={{
            width: 40,
            height: 3,
            background: BRAND,
            borderRadius: 2,
            marginBottom: 28,
          }}
        />

        {/* 고객 카드 */}
        <div
          style={{
            background: BRAND_LIGHT,
            border: `1px solid ${BRAND_MID}`,
            borderRadius: 14,
            padding: "24px 28px",
            marginBottom: 32,
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
            PREPARED FOR
          </div>
          <div
            style={{
              fontSize: 34,
              fontWeight: 700,
              color: TEXT,
              marginBottom: 6,
            }}
          >
            {C.name} 고객님
          </div>
          <div style={{ fontSize: 12, color: MUTED, fontWeight: 500 }}>
            {C.grade} 등급 · {C.aumLabel} · {C.pbCode}
          </div>
        </div>

        {/* 요약 스탯 행 */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr",
            gap: 16,
            marginBottom: 0,
          }}
        >
          {[
            { label: "보고서 일자", value: getTodayShort(), color: TEXT },
            { label: "선택 포트폴리오", value: "포트폴리오 A", color: BRAND },
            {
              label: "예상 연간 절세",
              value: `+${TAX_EFFECT.annualSavingManwon}만원`,
              color: UP,
            },
          ].map((s) => (
            <div key={s.label}>
              <div style={{ fontSize: 11, color: MUTED, marginBottom: 4 }}>
                {s.label}
              </div>
              <div style={{ fontSize: 18, fontWeight: 800, color: s.color }}>
                {s.value}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 면책 고지 — 페이지 하단 절대 위치 */}
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
        <p style={{ fontSize: 10, color: MUTED, lineHeight: 1.7, margin: 0 }}>
          본 보고서는 상담 내용, 고객 IPS, 시장 데이터 및 AI 분석 결과를
          바탕으로 고객의 투자 목적과 제약조건을 정리하고, 이에 적합한
          포트폴리오 방향을 제안하기 위해 작성되었습니다. 본 자료는 PB 상담을
          보조하기 위한 참고자료이며, 최종 투자 판단은 고객의 투자 목적, 위험
          선호도, 세무·법률 상황을 종합적으로 고려하여 결정되어야 합니다.
        </p>
      </div>
    </div>
  );
}

// ── Page 2: 시장 환경 & IPS ─────────────────────────────────────

// 거시지표 한국어 설명
const MACRO_DESC: Record<
  string,
  { name: string; dir: string; explain: string }
> = {
  기준금리: {
    name: "기준금리",
    dir: "인하",
    explain: "금리가 내리면 채권 가격은 올라가는 경향이 있어요",
  },
  "미 10Y": {
    name: "미국 장기금리",
    dir: "하락",
    explain: "미국 채권 금리. 해외 투자 수익에 영향을 줍니다",
  },
  "원/달러": {
    name: "원/달러 환율",
    dir: "상승",
    explain: "환율 상승 시 해외 자산 원화 환산 가치가 높아져요",
  },
  KOSPI: {
    name: "국내 주식 (KOSPI)",
    dir: "상승",
    explain: "국내 대형주 호름. 국내 주식 비중에 영향을 줍니다",
  },
  "S&P500": {
    name: "미국 주식 (S&P500)",
    dir: "상승",
    explain: "미국 대표 지수. 해외성장주·배당주 투자의 핵심 지표입니다",
  },
};

// CPI는 고객용에서 제외 (MACRO_INDICATORS는 6개이나 표시는 5개)
const CLIENT_MACROS = MACRO_INDICATORS.filter((m) => m.label !== "CPI");

function MarketIpsPage() {
  const IPS_ITEMS = [
    {
      tag: "Goal",
      label: "투자 목적",
      value: "자녀 전세자금\n+ 장기 증여",
      sub: "3년 내 자금 활용 가능성 고려한 운용 계획",
    },
    {
      tag: "Asset",
      label: "운용 자산",
      value: IPS_DEFAULT.assetLabel,
      sub: "전체 운용 가능 자산 기준. 비상자금 3억원은 별도",
    },
    {
      tag: "R",
      label: "목표 수익률",
      value: `연 ${IPS_DEFAULT.returnPct}%\n(세후 기준)`,
      sub: "변동성 최소화하면서 세후 8%를 목표",
    },
    {
      tag: "R",
      label: "위험 성향",
      value: IPS_DEFAULT.risk,
      sub: "급격한 손실(MDD -15% 이내)을 허용하지 않는 안정적 운용 선호",
    },
    {
      tag: "T",
      label: "투자 기간",
      value: `${IPS_DEFAULT.timeYears}년`,
      sub: "장기 운용 기준이나 유동성 필요 시 단기 자금은 별도 운용",
    },
    {
      tag: "T",
      label: "세금 상황",
      value: "종합과세\n대상",
      sub: IPS_DEFAULT.tax,
    },
    {
      tag: "L",
      label: "유동성 필요",
      value: IPS_DEFAULT.liquidity,
      sub: "비상자금 3억원 외 3년 내 자금 활용 가능성 고려",
    },
    {
      tag: "L",
      label: "법적 제약",
      value: "증여세법\n대비",
      sub: IPS_DEFAULT.legal,
    },
    {
      tag: "U",
      label: "특별 사항",
      value: "배당주·장기채\n선호",
      sub: IPS_DEFAULT.unique,
    },
  ];

  return (
    <div
      data-pdf-page=""
      style={{
        width: 794,
        height: 1123,
        fontFamily: "Pretendard, Apple SD Gothic Neo, sans-serif",
        background: "white",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* 페이지 헤더 바 */}
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
            ① 지금의 시장 환경과 나의 투자 목표
          </div>
          <div
            style={{
              fontSize: 13,
              color: "rgba(255,255,255,0.75)",
              marginTop: 2,
            }}
          >
            시장 현황 쉽게 이해하기 · 내 투자 방향 확인하기
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: "white" }}>
            {C.name} 고객님
          </div>
          <div style={{ fontSize: 12, color: "rgba(255,255,255,0.7)" }}>
            {getTodayShort()} 기준
          </div>
        </div>
      </div>

      <div style={{ padding: "28px 40px 80px", wordBreak: "keep-all" }}>
        {/* 섹션 1: 시장 현황 */}
        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 28 }}
        >
          <SectionBar />
          <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>
            지금 시장은 어떤 상황인가요?
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(5, 1fr)",
            gap: 10,
            marginBottom: 48,
          }}
        >
          {CLIENT_MACROS.map((m) => {
            const desc = MACRO_DESC[m.label];
            return (
              <div
                key={m.label}
                style={{
                  background: BRAND_LIGHT,
                  borderRadius: 10,
                  padding: "14px 12px",
                  border: `1px solid ${BRAND_MID}`,
                }}
              >
                <div
                  style={{
                    fontSize: 10,
                    color: MUTED,
                    fontWeight: 600,
                    marginBottom: 6,
                  }}
                >
                  {desc?.name ?? m.label}
                </div>
                <div
                  style={{
                    fontSize: 20,
                    fontWeight: 900,
                    color: TEXT,
                    marginBottom: 4,
                  }}
                >
                  {m.value}
                </div>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: m.direction === "up" ? UP : BRAND,
                    marginBottom: 6,
                  }}
                >
                  {m.direction === "up" ? "▲" : "▼"} {m.change}
                  {m.label === "원/달러" ? "원 " : "%p "}
                  {desc?.dir}
                </div>
                <div style={{ fontSize: 10, color: MUTED, lineHeight: 1.4 }}>
                  {desc?.explain}
                </div>
              </div>
            );
          })}
        </div>

        {/* 섹션 2: IPS */}
        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 28 }}
        >
          <SectionBar />
          <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>
            나의 투자 목표 요약 (IPS)
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 8,
            marginBottom: 20,
          }}
        >
          {IPS_ITEMS.map((item) => (
            <div
              key={item.label}
              style={{
                background: "white",
                border: `1px solid ${BORDER}`,
                borderRadius: 10,
                padding: "12px 14px",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  marginBottom: 6,
                }}
              >
                <span
                  style={{
                    fontSize: 9,
                    fontWeight: 800,
                    background: BRAND,
                    color: "white",
                    borderRadius: 4,
                    padding: "1px 5px",
                    letterSpacing: 0.5,
                  }}
                >
                  {item.tag}
                </span>
                <span style={{ fontSize: 11, color: MUTED, fontWeight: 600 }}>
                  {item.label}
                </span>
              </div>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 900,
                  color: TEXT,
                  lineHeight: 1.3,
                  marginBottom: 6,
                  whiteSpace: "pre-line",
                  wordBreak: "keep-all",
                }}
              >
                {item.value}
              </div>
              <div
                style={{
                  fontSize: 9,
                  color: MUTED,
                  lineHeight: 1.4,
                  wordBreak: "keep-all",
                }}
              >
                {item.sub}
              </div>
            </div>
          ))}
        </div>

        {/* 전략 방향 박스 */}
        <div
          style={{
            background: `linear-gradient(135deg, ${BRAND_LIGHT} 0%, #F0F9FF 100%)`,
            border: `1.5px solid ${BRAND_MID}`,
            borderRadius: 12,
            padding: "18px 22px",
          }}
        >
          <div
            style={{
              fontSize: 12,
              fontWeight: 800,
              color: BRAND,
              marginBottom: 10,
            }}
          >
            고객님의 상황을 고려한 핵심 전략 방향
          </div>
          <p style={{ fontSize: 12, color: TEXT, lineHeight: 1.7, margin: 0 }}>
            고객님은 <strong>금융소득 종합과세 대상</strong>이시므로, 절세
            계좌(ISA, 연금저축, IRP)를 적극 활용하는 것이 중요합니다. 또한 자녀
            전세자금 3억원은 별도로 유동성이 높은 상품으로 운용하고, 나머지는
            장기 포트폴리오로 구성하는 <strong>&lsquo;투 트랙&rsquo;</strong> 전략을
            권장합니다.
          </p>
        </div>
      </div>

      <PageFooter page={2} total={5} />
    </div>
  );
}

// ── Page 3: 포트폴리오 비교 & 지표 설명 ───────────────────────────

const ASSET_LABELS_A = [
  "국내주식 20%",
  "해외배당주 22%",
  "해외성장주 12%",
  "일반채권 18%",
  "저쿠폰채 14%",
  "분리과세 ETF 14%",
];

const METRIC_CARDS = [
  {
    num: "①",
    title: "기대수익률",
    en: "Expected Return",
    body: "1년 동안 예상되는 평균 수익의 비율입니다. 높을수록 더 많은 이익을 기대할 수 있습니다.",
    example: "6.4%라면 1억원 투자 시 연 640만원 기대",
  },
  {
    num: "②",
    title: "변동성 (표준편차)",
    en: "Volatility / Std. Dev.",
    body: "수익률이 평균에서 얼마나 흔들리는지를 나타냅니다. 낮을수록 안정적인 투자입니다.",
    example: "12.5%라면 평균 수익에서 ±12.5% 오내릴 수 있음",
  },
  {
    num: "③",
    title: "샤프 지수",
    en: "Sharpe Ratio",
    body: "위험 한 단위당 얼마나 수익을 얻는지 나타냅니다. 높을수록 효율적인 포트폴리오입니다.",
    example: "0.61은 0.43보다 좋음 — 같은 위험으로 더 많이 버는 구조",
  },
  {
    num: "④",
    title: "소르티노 지수",
    en: "Sortino Ratio",
    body: "하락 위험(손실이 나는 변동)만을 기준으로 한 효율성 지표입니다. 높을수록 손실 방어력이 좋습니다.",
    example: "샤프와 달리 하락만 위험으로 봄 — 손실 방어력 측정",
  },
  {
    num: "⑤",
    title: "최대낙폭 (MDD)",
    en: "Maximum Drawdown",
    body: "투자 기간 중 고점 대비 가장 많이 떨어진 최대 손실 폭입니다. 낮을수록 안전합니다.",
    example: "-11.2%라면 18억원 중 최대 약 2,000만원 손실 가능성",
  },
  {
    num: "⑥",
    title: "세후 수익률",
    en: "After-Tax Return",
    body: "세금을 납부한 후 실제 고객님 손에 남는 수익률입니다. 종합과세 고려 시 이 수치가 핵심입니다.",
    example: "5.5% = 세금 납부 후 실수령 수익률 (절세 효과 포함)",
  },
];

function PortfolioPage() {
  const cur = portCurrent.metrics;
  const a = portA.metrics;

  return (
    <div
      data-pdf-page=""
      style={{
        width: 794,
        height: 1123,
        fontFamily: "Pretendard, Apple SD Gothic Neo, sans-serif",
        background: "white",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* 페이지 헤더 바 */}
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
            ② 포트폴리오 비교 &amp; 주요 지표 쉽게 이해하기
          </div>
          <div
            style={{
              fontSize: 13,
              color: "rgba(255,255,255,0.75)",
              marginTop: 2,
            }}
          >
            현재 vs 고객 선택 포트폴리오 · 6가지 핵심 지표 설명
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: "white" }}>
            {C.name} 고객님
          </div>
          <div style={{ fontSize: 12, color: "rgba(255,255,255,0.7)" }}>
            {getTodayShort()} 기준
          </div>
        </div>
      </div>

      <div style={{ padding: "24px 40px 80px", wordBreak: "keep-all" }}>
        {/* 섹션 1: 성과 비교 */}
        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 28 }}
        >
          <SectionBar />
          <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>
            포트폴리오별 성과 한눈에 보기 (5년 분석 기준)
          </div>
        </div>

        {/* 현재 포트폴리오 */}
        <div
          style={{
            border: `1px solid ${BORDER}`,
            borderRadius: 10,
            padding: "16px 20px",
            marginBottom: 14,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 12,
            }}
          >
            <div style={{ fontSize: 13, fontWeight: 800, color: TEXT }}>
              현재 포트폴리오
            </div>
            <div style={{ fontSize: 10, color: MUTED }}>현재 구성 기준</div>
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(6, 1fr)",
              gap: 8,
            }}
          >
            {[
              {
                label: "기대수익률",
                value: `연 ${cur.expectedReturnPct}%`,
                color: TEXT,
                sub: null,
                subColor: MUTED,
              },
              {
                label: "샤프지수",
                value: `${cur.sharpe}`,
                color: TEXT,
                sub: null,
                subColor: MUTED,
              },
              {
                label: "소르티노",
                value: `${cur.sortino}`,
                color: TEXT,
                sub: null,
                subColor: MUTED,
              },
              {
                label: "세후수익률",
                value: `▲${cur.afterTaxReturnPct}%`,
                color: UP,
                sub: cur.afterTaxAmountLabel,
                subColor: UP,
              },
              {
                label: "변동성",
                value: `${cur.volatilityPct}%`,
                color: TEXT,
                sub: cur.volatilityAmountLabel,
                subColor: MUTED,
              },
              {
                label: "MDD",
                value: `▼${cur.mddPct}%`,
                color: BRAND,
                sub: cur.mddAmountLabel,
                subColor: BRAND,
              },
            ].map((s) => (
              <div key={s.label} style={{ textAlign: "center" }}>
                <div style={{ fontSize: 10, color: MUTED, marginBottom: 4 }}>
                  {s.label}
                </div>
                <div style={{ fontSize: 15, fontWeight: 900, color: s.color }}>
                  {s.value}
                </div>
                {s.sub && (
                  <div
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      color: s.subColor,
                      marginTop: 2,
                    }}
                  >
                    {s.sub}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* 포트폴리오 A */}
        <div
          style={{
            border: `1.5px solid ${BRAND}`,
            borderRadius: 10,
            padding: "16px 20px",
            background: BRAND_LIGHT,
            marginBottom: 20,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 12,
            }}
          >
            <div style={{ fontSize: 13, fontWeight: 800, color: BRAND }}>
              포트폴리오 A
            </div>
            <div
              style={{
                background: "#F3F4F6",
                color: MUTED,
                fontSize: 10,
                fontWeight: 700,
                borderRadius: 6,
                padding: "3px 8px",
                border: `1px solid ${BORDER}`,
              }}
            >
              고객님 선택
            </div>
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(6, 1fr)",
              gap: 8,
              marginBottom: 10,
            }}
          >
            {[
              {
                label: "기대수익률",
                value: `연 ${a.expectedReturnPct}%`,
                color: TEXT,
                sub: null,
                subColor: MUTED,
              },
              {
                label: "샤프지수",
                value: `${a.sharpe} ↑`,
                color: TEXT,
                sub: null,
                subColor: MUTED,
              },
              {
                label: "소르티노",
                value: `${a.sortino}`,
                color: TEXT,
                sub: null,
                subColor: MUTED,
              },
              {
                label: "세후수익률",
                value: `▲${a.afterTaxReturnPct}%`,
                color: UP,
                sub: a.afterTaxAmountLabel,
                subColor: UP,
              },
              {
                label: "변동성",
                value: `${a.volatilityPct}%`,
                color: TEXT,
                sub: a.volatilityAmountLabel,
                subColor: MUTED,
              },
              {
                label: "MDD",
                value: `▼${a.mddPct}%`,
                color: BRAND,
                sub: a.mddAmountLabel,
                subColor: BRAND,
              },
            ].map((s) => (
              <div key={s.label} style={{ textAlign: "center" }}>
                <div style={{ fontSize: 10, color: MUTED, marginBottom: 4 }}>
                  {s.label}
                </div>
                <div style={{ fontSize: 15, fontWeight: 900, color: s.color }}>
                  {s.value}
                </div>
                {s.sub && (
                  <div
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      color: s.subColor,
                      marginTop: 2,
                    }}
                  >
                    {s.sub}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* 자산 배분 태그 */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              flexWrap: "wrap",
            }}
          >
            <span style={{ fontSize: 10, fontWeight: 700, color: MUTED }}>
              자산 배분 구성
            </span>
            {ASSET_LABELS_A.map((t) => (
              <span
                key={t}
                style={{
                  fontSize: 10,
                  background: "white",
                  border: `1px solid ${BRAND_MID}`,
                  color: BRAND,
                  borderRadius: 5,
                  padding: "2px 7px",
                  fontWeight: 600,
                }}
              >
                {t}
              </span>
            ))}
          </div>
        </div>

        {/* 개선 인사이트 한 줄 */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "8px 14px",
            marginBottom: 48,
            background: "#F9FAFB",
            borderLeft: `3px solid ${BRAND}`,
            borderRadius: "0 6px 6px 0",
          }}
        >
          <span style={{ fontSize: 11, color: MUTED }}>
            포트폴리오 A 선택 시 현재 대비 연간 세후수익
          </span>
          <span style={{ fontSize: 13, fontWeight: 800, color: BRAND }}>
            +2,700만원 개선
          </span>
          <span style={{ fontSize: 10, color: MUTED }}>예상됩니다.</span>
        </div>

        {/* 섹션 2: 지표 설명 */}
        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 28 }}
        >
          <SectionBar />
          <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>
            핵심 투자 지표 6가지 — 쉽게 이해하기
          </div>
        </div>

        <div
          style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}
        >
          {METRIC_CARDS.map((c) => (
            <div
              key={c.num}
              style={{
                border: `1px solid ${BORDER}`,
                borderRadius: 10,
                padding: "14px 16px",
                background: "white",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  marginBottom: 6,
                }}
              >
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 800,
                    color: BRAND,
                    background: BRAND_LIGHT,
                    borderRadius: 5,
                    padding: "2px 6px",
                  }}
                >
                  {c.num}
                </span>
                <span style={{ fontSize: 13, fontWeight: 800, color: TEXT }}>
                  {c.title}
                </span>
              </div>
              <div style={{ fontSize: 10, color: MUTED, marginBottom: 6 }}>
                {c.en}
              </div>
              <p
                style={{
                  fontSize: 11,
                  color: TEXT,
                  lineHeight: 1.6,
                  margin: "0 0 8px",
                }}
              >
                {c.body}
              </p>
              <div
                style={{
                  fontSize: 10,
                  color: BRAND,
                  background: BRAND_LIGHT,
                  borderRadius: 6,
                  padding: "5px 9px",
                }}
              >
                {c.example}
              </div>
            </div>
          ))}
        </div>
      </div>

      <PageFooter page={3} total={5} />
    </div>
  );
}

// ── Page 4: 절세 전략 & 계좌 배치 ─────────────────────────────────

function TaxPage() {
  const accs = TAX_EFFECT.accounts;

  return (
    <div
      data-pdf-page=""
      style={{
        width: 794,
        height: 1123,
        fontFamily: "Pretendard, Apple SD Gothic Neo, sans-serif",
        background: "white",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* 페이지 헤더 바 */}
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
            ③ 절세 전략 &amp; 분산투자 — 계좌 배치 활용
          </div>
          <div
            style={{
              fontSize: 13,
              color: "rgba(255,255,255,0.75)",
              marginTop: 2,
            }}
          >
            세금 아끼는 방법 · 위험 분산을 위한 계좌 전략
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: "white" }}>
            {C.name} 고객님
          </div>
          <div style={{ fontSize: 12, color: "rgba(255,255,255,0.7)" }}>
            {getTodayShort()} 기준
          </div>
        </div>
      </div>

      <div style={{ padding: "24px 40px 80px", wordBreak: "keep-all" }}>
        {/* 절세 하이라이트 박스 */}
        <div
          style={{
            background: `linear-gradient(135deg, ${BRAND_DARK} 0%, ${BRAND} 60%, #2C7BFF 100%)`,
            borderRadius: 14,
            padding: "24px 28px",
            marginBottom: 40,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div
              style={{
                fontSize: 12,
                color: "rgba(255,255,255,0.8)",
                marginBottom: 6,
              }}
            >
              연간 절세 효과 (포트폴리오 A · {C.aumLabel} 기준)
            </div>
            <div
              style={{
                fontSize: 44,
                fontWeight: 900,
                color: "white",
                lineHeight: 1,
              }}
            >
              + {TAX_EFFECT.annualSavingManwon}만원
            </div>
            <div
              style={{
                fontSize: 11,
                color: "rgba(255,255,255,0.7)",
                marginTop: 6,
              }}
            >
              {TAX_EFFECT.subNote}
            </div>
          </div>
          <div
            style={{
              background: "rgba(255,255,255,0.15)",
              borderRadius: 12,
              padding: "16px 20px",
              textAlign: "right",
            }}
          >
            <div
              style={{
                fontSize: 10,
                color: "rgba(255,255,255,0.75)",
                marginBottom: 6,
              }}
            >
              실효 세금 절감
            </div>
            <div style={{ fontSize: 18, fontWeight: 800, color: "white" }}>
              {TAX_EFFECT.effectiveTax.from}만
            </div>
            <div
              style={{
                fontSize: 12,
                color: "rgba(255,255,255,0.6)",
                margin: "4px 0",
              }}
            >
              ↓
            </div>
            <div style={{ fontSize: 20, fontWeight: 900, color: "white" }}>
              {TAX_EFFECT.effectiveTax.to}
            </div>
            <div
              style={{
                fontSize: 11,
                color: "rgba(255,255,255,0.75)",
                marginTop: 4,
              }}
            >
              {TAX_EFFECT.effectiveTax.delta} 절감
            </div>
          </div>
        </div>

        {/* 절세 전략 4가지 카드 */}
        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 28 }}
        >
          <SectionBar />
          <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>
            맞춤 절세 전략 4가지
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 10,
            marginBottom: 40,
          }}
        >
          {[
            {
              icon: "I",
              title: "ISA 계좌 활용",
              saving: "+210만원",
              body: "배당주 4,000만원을 ISA로 이전 — 비과세 한도 적용 후 초과분 분리과세 9.9%.",
            },
            {
              icon: "채",
              title: "분리과세 채권",
              saving: "+180만원",
              body: "저쿠폰·장기채로 이자소득을 분리과세(14%) 전환해 종합과세 합산에서 제외.",
            },
            {
              icon: "배",
              title: "저율과세 배당주",
              saving: "+90만원",
              body: "고배당 종목을 저율과세 ETF·우선주로 조정해 배당소득세 부담 완화.",
            },
            {
              icon: "L",
              title: "Tax-loss Harvesting",
              saving: "+396만원",
              body: "평가손실 1,800만원 확정 → 해외주식 양도차익과 상계해 양도세(22%) 절감.",
            },
          ].map((c) => (
            <div
              key={c.title}
              style={{
                border: `1px solid ${BORDER}`,
                borderRadius: 10,
                padding: "14px 16px",
                background: "#F8FAFF",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: 8,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div
                    style={{
                      width: 24,
                      height: 24,
                      borderRadius: "50%",
                      background: BRAND_LIGHT,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 11,
                      fontWeight: 800,
                      color: BRAND,
                    }}
                  >
                    {c.icon}
                  </div>
                  <span style={{ fontSize: 13, fontWeight: 800, color: TEXT }}>
                    {c.title}
                  </span>
                </div>
                <span style={{ fontSize: 13, fontWeight: 800, color: UP }}>
                  {c.saving}
                </span>
              </div>
              <p
                style={{
                  fontSize: 11,
                  color: MUTED,
                  lineHeight: 1.6,
                  margin: 0,
                }}
              >
                {c.body}
              </p>
            </div>
          ))}
        </div>

        {/* 절세 계좌 배치 */}
        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 28 }}
        >
          <SectionBar />
          <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>
            절세 계좌 배치 활용도
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {accs.map((acc) => {
            const pct =
              acc.used !== null && acc.limit !== null
                ? (acc.used / acc.limit) * 100
                : 45;
            // 대시보드 AccountAllocation 색상과 동일
            const barGradient =
              acc.name === "일반계좌"
                ? "linear-gradient(to right, #B8D4FF, #7AABFF)"
                : "linear-gradient(to right, #5C9CFF, #0064FF)";
            return (
              <div key={acc.name}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginBottom: 6,
                  }}
                >
                  <div
                    style={{ display: "flex", alignItems: "center", gap: 8 }}
                  >
                    <span
                      style={{ fontSize: 14, fontWeight: 800, color: TEXT }}
                    >
                      {acc.name}
                    </span>
                    <span
                      style={{
                        fontSize: 10,
                        background: BRAND_LIGHT,
                        color: BRAND,
                        borderRadius: 4,
                        padding: "2px 6px",
                        fontWeight: 700,
                      }}
                    >
                      {acc.tag}
                    </span>
                  </div>
                  <span style={{ fontSize: 12, fontWeight: 700, color: TEXT }}>
                    {acc.used !== null && acc.limit !== null
                      ? `${acc.used.toLocaleString()} / ${acc.limit.toLocaleString()}만`
                      : "잔여 자산 배치"}
                  </span>
                </div>
                {/* 진행 바 */}
                <div
                  style={{
                    height: 10,
                    background: "#E5E7EB",
                    borderRadius: 5,
                    marginBottom: 6,
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      height: "100%",
                      width: `${pct}%`,
                      background: barGradient,
                      borderRadius: 5,
                    }}
                  />
                </div>
                <div style={{ fontSize: 11, color: MUTED }}>{acc.caption}</div>
              </div>
            );
          })}
        </div>
      </div>

      <PageFooter page={4} total={5} />
    </div>
  );
}

// ── Page 5: 분산투자 & 상관관계 ────────────────────────────────────

// 대시보드 CorrelationHeatmap과 동일한 데이터·색상 공식
// 색상: rgba(0,100,255, 0.06 + v * 0.8) — CorrelationHeatmap.tsx 동일
const GROUP_ABBR: Record<string, string> = {
  국내주식: "국내주식",
  해외배당주: "해외배당",
  해외성장주: "해외성장",
  일반채권: "일반채권",
  저쿠폰채: "저쿠폰채",
  분리과세: "분리과세",
};

function heatBg(v: number): string {
  return `rgba(0, 100, 255, ${(0.06 + v * 0.8).toFixed(2)})`;
}

function heatTextColor(v: number): string {
  return v > 0.55 ? "#fff" : "#0050D6";
}

const ASSET_CARDS = [
  {
    title: "저쿠폰 장기채",
    corr: "주식과 상관계수: −0.3 ~ −0.5",
    body: "금리가 내릴 때 가격이 크게 오르는 채권입니다. 주식 시장 하락 시 포트폴리오를 안정시키는 역할을 합니다.",
    note: "포트폴리오 A에 14% 배분 — 주식 급락 시 완충 역할",
  },
  {
    title: "해외 배당주",
    corr: "국내주식과 상관계수: 0.4~0.6",
    body: "미국 등 해외 고배당 주식은 국내 주식과 완전히 같이 움직이지 않아 분산 효과가 있습니다. 환율 상승 시 추가 이익도 기대할 수 있습니다.",
    note: "포트폴리오 A에 22% 배분 — 환율 상승 시 추가 수익 기대",
  },
  {
    title: "분리과세 채권 ETF",
    corr: "주식과 상관계수: 0.1~0.2",
    body: "세금 면에서 유리하게 설계된 채권 ETF입니다. 주식과 거의 독립적으로 움직여 안정적인 수익을 제공하면서 세금도 줄여줍니다.",
    note: "ISA 계좌에 담아 비과세/분리과세 혜택 동시 누림",
  },
  {
    title: "리츠 (부동산 ETF)",
    corr: "주식과 상관계수: 0.5~0.7",
    body: "부동산에 간접 투자하는 방법으로, 정기적인 배당 수익을 기대할 수 있습니다. 실물 부동산보다 유동성이 높아 필요 시 빠르게 현금화됩니다.",
    note: "향후 추가 검토 자산 — 증여 전략과 연계 가능",
  },
];

function DiversificationPage() {
  return (
    <div
      data-pdf-page=""
      style={{
        width: 794,
        height: 1123,
        fontFamily: "Pretendard, Apple SD Gothic Neo, sans-serif",
        background: "white",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* 페이지 헤더 바 */}
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
            분산투자 효과 — 상관관계가 낮은 대체자산이란?
          </div>
          <div
            style={{
              fontSize: 13,
              color: "rgba(255,255,255,0.75)",
              marginTop: 2,
            }}
          >
            왜 여러 자산을 함께 보유해야 하는지 이해하기
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: "white" }}>
            {C.name} 고객님
          </div>
          <div style={{ fontSize: 12, color: "rgba(255,255,255,0.7)" }}>
            {getTodayShort()} 기준
          </div>
        </div>
      </div>

      <div style={{ padding: "24px 40px 80px", wordBreak: "keep-all" }}>
        {/* 상관관계 설명 박스 */}
        <div
          style={{
            background: BRAND_LIGHT,
            border: `1px solid ${BRAND_MID}`,
            borderRadius: 10,
            padding: "14px 18px",
            marginBottom: 22,
          }}
        >
          <div
            style={{
              fontSize: 13,
              fontWeight: 800,
              color: BRAND,
              marginBottom: 6,
            }}
          >
            상관관계(Correlation)란?
          </div>
          <p style={{ fontSize: 12, color: TEXT, lineHeight: 1.7, margin: 0 }}>
            두 자산이 함께 움직이는 정도를 나타냅니다. −1에 가까울수록 반대로
            움직이고, +1에 가까울수록 같이 움직입니다. 주식과{" "}
            <strong>상관관계가 낮거나 음(−)인 자산을 함께 보유하면</strong>,
            주식이 하락할 때 손실을 줄여주는 효과가 있습니다.
          </p>
        </div>

        {/* 상관관계 매트릭스 — 대시보드 CorrelationHeatmap과 동일한 데이터·색상 */}
        <div style={{ marginBottom: 40 }}>
          <div
            style={{
              fontSize: 12,
              fontWeight: 800,
              color: TEXT,
              marginBottom: 10,
            }}
          >
            자산별 상관관계 히트맵
          </div>

          {/* 히트맵 테이블 */}
          <table style={{ borderCollapse: "separate", borderSpacing: 2 }}>
            <thead>
              <tr>
                <th style={{ width: 76, padding: 0 }} />
                {DISPLAY_GROUPS.map((g) => (
                  <th
                    key={g}
                    style={{
                      width: 96,
                      paddingBottom: 4,
                      fontSize: 10,
                      fontWeight: 600,
                      color: MUTED,
                      textAlign: "center",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {GROUP_ABBR[g]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {CORRELATION_MATRIX.map((row, ri) => (
                <tr key={ri}>
                  <td
                    style={{
                      fontSize: 10,
                      fontWeight: 600,
                      color: MUTED,
                      paddingRight: 8,
                      textAlign: "right",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {GROUP_ABBR[DISPLAY_GROUPS[ri]]}
                  </td>
                  {row.map((v, ci) => (
                    <td
                      key={ci}
                      style={{
                        width: 96,
                        height: 40,
                        background: heatBg(v),
                        textAlign: "center",
                        fontSize: 11,
                        fontWeight: 700,
                        color: heatTextColor(v),
                        borderRadius: 3,
                      }}
                    >
                      {v.toFixed(2)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>

          {/* 범례 — 그라디언트 바 */}
          <div
            style={{ marginTop: 12, width: 96 * 6 + 76, paddingLeft: 76 + 8 }}
          >
            <div
              style={{
                height: 12,
                borderRadius: 6,
                background:
                  "linear-gradient(to right, rgba(0,100,255,0.06), rgba(0,100,255,0.26), rgba(0,100,255,0.46), rgba(0,100,255,0.66), rgba(0,100,255,0.86))",
                marginBottom: 4,
              }}
            />
            {/* 눈금 라벨 */}
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              {[
                { v: 0.0, label: "0.0\n매우 낮음" },
                { v: 0.25, label: "0.25\n낮음" },
                { v: 0.5, label: "0.50\n중간" },
                { v: 0.75, label: "0.75\n높음" },
                { v: 1.0, label: "1.0\n매우 높음" },
              ].map(({ v, label }) => (
                <div key={v} style={{ textAlign: "center" }}>
                  {label.split("\n").map((line, i) => (
                    <div
                      key={i}
                      style={{
                        fontSize: 9,
                        color: i === 0 ? TEXT : MUTED,
                        fontWeight: i === 0 ? 700 : 500,
                        lineHeight: 1.4,
                      }}
                    >
                      {line}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 대체자산 4종 카드 */}
        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 28 }}
        >
          <SectionBar />
          <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>
            분산 효과가 있는 대체자산 4종
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 12,
            marginBottom: 24,
          }}
        >
          {ASSET_CARDS.map((c) => (
            <div
              key={c.title}
              style={{
                border: `1px solid ${BORDER}`,
                borderRadius: 10,
                padding: "14px 16px",
                background: "white",
              }}
            >
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 800,
                  color: TEXT,
                  marginBottom: 4,
                }}
              >
                {c.title}
              </div>
              <div
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  color: BRAND,
                  background: BRAND_LIGHT,
                  borderRadius: 4,
                  padding: "2px 7px",
                  display: "inline-block",
                  marginBottom: 8,
                }}
              >
                {c.corr}
              </div>
              <p
                style={{
                  fontSize: 11,
                  color: TEXT,
                  lineHeight: 1.6,
                  margin: "0 0 8px",
                }}
              >
                {c.body}
              </p>
              <div
                style={{
                  fontSize: 10,
                  color: MUTED,
                  borderTop: `1px solid ${BORDER}`,
                  paddingTop: 6,
                }}
              >
                ◆ {c.note}
              </div>
            </div>
          ))}
        </div>
      </div>

      <PageFooter page={5} total={5} />
    </div>
  );
}

// ── 최종 export ─────────────────────────────────────────────────

export default function ClientPdfTemplate() {
  return (
    <>
      <CoverPage />
      <MarketIpsPage />
      <PortfolioPage />
      <TaxPage />
      <DiversificationPage />
    </>
  );
}
