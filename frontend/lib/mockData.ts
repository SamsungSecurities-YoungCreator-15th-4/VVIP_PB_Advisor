/**
 * 화면 골격용 더미 데이터 모음.
 *
 * ⚠️ 모든 수치는 HTML 시안·정본 디자인에서 그대로 옮긴 자리표시자다.
 *    실제 지표(샤프지수·MDD·세금 등)는 백엔드(yfinance + 세법 로직) 연동 후
 *    이 파일을 API 응답으로 대체한다. 임의 수치를 실데이터처럼 쓰지 말 것.
 */

import type { CalcUnitWeights } from "./assetMapping";

// ── 헤더: 거시지표 ──────────────────────────────────────────────
export interface MacroIndicator {
  label: string;
  value: string;
  change: string;
  direction: "up" | "down";
}

export const MACRO_INDICATORS: MacroIndicator[] = [
  { label: "미국 기준금리", value: "3.50%", change: "0.25", direction: "down" },
  { label: "미 10Y", value: "4.38%", change: "0.05", direction: "down" },
  { label: "원/달러", value: "1,220", change: "20", direction: "down" },
  { label: "미국 CPI", value: "3.2%", change: "0.25", direction: "down" },
  { label: "KOSPI", value: "2,790", change: "31", direction: "up" },
  { label: "S&P500", value: "5,640", change: "18", direction: "up" },
];

export const BASE_TIME = "17:20";

// ── 고객 ───────────────────────────────────────────────────────
export interface Customer {
  id: string;
  name: string;
  grade: "VVIP";
  pbCode: string;
  aumLabel: string; // 표시용
  aumEokwon: number; // 계산용 (억원)
  // 절세계좌 기납입액·세부담 입력값(만원/%) — 절세 제안 실계산용 고객 데이터.
  // 실서비스에서는 PB가 입력/연동(준호님 DB 반영 예정). 여기선 현실적 자리표시자.
  isaUsedManwon: number; // ISA 당해 기납입액 (법정 연 한도 2,000만)
  pensionUsedManwon: number; // 연금저축+IRP 당해 납입액 (세액공제 한도 900만)
  realizedLossManwon: number; // 확정 가능 평가손실 (Tax-loss harvesting용)
  marginalRatePct: number; // 한계세율(지방세 포함, %) — 종합과세 추가과세 비교용
  // 적합성(lock-up) 게이팅 입력 — 임시 수기 입력(추후 DB/IPS 연동).
  age: number; // 나이 — 연금 55세 수령요건 게이팅
  horizonYears: number; // 투자기간(년) — ISA 3년·연금 lock-up 게이팅 (IPS Time)
  nearTermNeedManwon: number; // 단기 필요자금(만원) — 묶이는 금액에서 제외 (IPS Unique)
  nearTermNeedYears: number | null; // 단기 필요자금 필요 시점(년)
  isaOpened: boolean; // ISA 기존 개설 여부(시나리오: 다들 옛날 개설=true)
  /** DB(client 테이블) UUID. 초기 mock 3명·미저장(데모) 고객은 없음. */
  clientId?: string;
  /** DB 저장 성공 여부. false = 데모(로컬에만 추가). undefined = mock 초기 고객. */
  persisted?: boolean;
}

export const CUSTOMERS: Customer[] = [
  {
    id: "cust-001",
    name: "김성삼",
    grade: "VVIP",
    pbCode: "PB-100482",
    aumLabel: "운용자산 18억원",
    aumEokwon: 18,
    isaUsedManwon: 2000, // ISA 연 한도 소진
    pensionUsedManwon: 900, // 연금계좌 세액공제 한도 소진
    realizedLossManwon: 1800,
    marginalRatePct: 38.5,
    age: 54,
    horizonYears: 10, // 장기 증여 준비
    nearTermNeedManwon: 30000, // 내년 가을 자녀 전세 3억
    nearTermNeedYears: 1,
    isaOpened: true,
  },
  {
    id: "cust-002",
    name: "이사조",
    grade: "VVIP",
    pbCode: "PB-100483",
    aumLabel: "운용자산 52억원",
    aumEokwon: 52,
    isaUsedManwon: 800, // ISA 여유 있음
    pensionUsedManwon: 600,
    realizedLossManwon: 3200,
    marginalRatePct: 49.5,
    age: 33,
    horizonYears: 3, // 변경: 1년 → 3년
    nearTermNeedManwon: 0, // 창업 대금(금액 미상) — 추후 입력
    nearTermNeedYears: null,
    isaOpened: true,
  },
  {
    id: "cust-003",
    name: "박기업",
    grade: "VVIP",
    pbCode: "PB-100484",
    aumLabel: "운용자산 31억원",
    aumEokwon: 31,
    isaUsedManwon: 0, // ISA 미납입
    pensionUsedManwon: 300,
    realizedLossManwon: 0,
    marginalRatePct: 38.5,
    age: 62,
    horizonYears: 10, // 초장기(10년 이상)
    nearTermNeedManwon: 0, // 법인 운전자금은 별도 관리
    nearTermNeedYears: null,
    isaOpened: true,
  },
];

// ── 지난 상담 기록 목록 (더미) ─────────────────────────────────
export interface PastConsultation {
  id: string;
  title: string;
}

export const PAST_CONSULTATIONS: PastConsultation[] = [
  { id: "pc-1", title: "20260628_김성삼_상담기록" },
  { id: "pc-2", title: "20260615_김성삼_상담기록" },
  { id: "pc-3", title: "20260601_김성삼_상담기록" },
  { id: "pc-4", title: "20260528_이사조_상담기록" },
  { id: "pc-5", title: "20260510_박기업_상담기록" },
];

// ── 상담 내역 ──────────────────────────────────────────────────
export interface ConsultMessage {
  speaker: "PB" | "고객";
  text: string;
  time: string;
}

export const CONSULT_DURATION = "02:14";

export const CONSULT_LOG: ConsultMessage[] = [
  {
    speaker: "PB",
    text: "최근 변동성 확대에 대한 고객님의 우려를 확인했습니다.",
    time: "00:07",
  },
  {
    speaker: "고객",
    text: "세후 수익률을 높이고 변동성을 줄이는 전략이 필요해요.",
    time: "00:12",
  },
  {
    speaker: "PB",
    text: "절세 전략과 대체자산을 활용한 분산을 제안드립니다.",
    time: "00:30",
  },
  {
    speaker: "고객",
    text: "ISA 계좌 활용은 이전에도 말씀드렸는데, 한도가 얼마죠?",
    time: "00:48",
  },
  {
    speaker: "PB",
    text: "연간 2,000만원 한도이며, 비과세 혜택과 분리과세 9.9%가 적용됩니다.",
    time: "00:55",
  },
  {
    speaker: "고객",
    text: "그럼 해외 배당주 비중은 좀 더 늘릴 수 있나요?",
    time: "01:10",
  },
  {
    speaker: "PB",
    text: "포트폴리오 A 기준 해외배당주를 22%까지 확대하면 세후 수익률이 5.5%로 개선됩니다.",
    time: "01:20",
  },
  {
    speaker: "고객",
    text: "좋네요. 증여 계획도 같이 검토해주실 수 있나요?",
    time: "01:45",
  },
  {
    speaker: "PB",
    text: "자녀 증여세 공제 한도(10년 5천만원)와 분할 증여 전략을 함께 안내드리겠습니다.",
    time: "01:58",
  },
];

// ── IPS 조율기 초기값 ──────────────────────────────────────────
export const IPS_DEFAULT = {
  goal: "자녀 전세자금 및 장기 증여 준비",
  assetLabel: "18억원",
  returnPct: 8,
  risk: "균형형" as "안정형" | "균형형" | "공격형",
  timeYears: 10,
  tax: "금융소득종합과세 · 양도세 · 증여세",
  liquidity: "중간" as "낮음" | "중간" | "높음",
  legal: "증여세법 · 자금출처조사 대비",
  unique: "전체 자금 3억 · 미국 배당주·장기채 선호",
};

// ── 포트폴리오 3종 (현재 / A 베스트 / B 추천) ──────────────────
export interface PortfolioMetrics {
  expectedReturnPct: number;
  volatilityPct: number;
  sharpe: number;
  sortino: number;
  volatilityAmountLabel: string;
  mddPct: number; // 양수로 보관, 표시 시 ▼ 접두
  mddAmountLabel: string;
  afterTaxReturnPct: number;
  afterTaxAmountLabel: string;
}

export interface Portfolio {
  id: "current" | "a" | "b";
  name: string;
  badge: "현재" | "베스트" | "추천";
  /** 11종 계산 단위 비중(%). 화면에는 assetMapping으로 6분류 합산해 표시 */
  weights: CalcUnitWeights;
  metrics: PortfolioMetrics;
}

// 11종 비중은 시안의 6분류 값(예: 현재 25/18/12/22/12/11)이 나오도록 가배분한 것.
// TODO(팀 확정 필요): 백엔드 11종 실데이터 연동 시 교체.
export const PORTFOLIOS: Portfolio[] = [
  {
    id: "current",
    name: "현재",
    badge: "현재",
    weights: {
      domesticEquity: 25,
      overseasDividendEquity: 18,
      overseasGrowthEquity: 9,
      emergingEquity: 3,
      domesticBond: 14,
      overseasBond: 8,
      lowCouponBond: 12,
      separateTaxBond: 5,
      reits: 3,
      gold: 2,
      infraFund: 1,
    },
    metrics: {
      expectedReturnPct: 4.8,
      volatilityPct: 11.2,
      volatilityAmountLabel: "±3,200만원",
      sharpe: 0.43,
      sortino: 0.3,
      mddPct: 14.6,
      mddAmountLabel: "-3,200만원",
      afterTaxReturnPct: 4.0,
      afterTaxAmountLabel: "+7,200만원",
    },
  },
  {
    id: "a",
    name: "포트폴리오 A",
    badge: "베스트",
    weights: {
      domesticEquity: 20,
      overseasDividendEquity: 22,
      overseasGrowthEquity: 9,
      emergingEquity: 3,
      domesticBond: 11,
      overseasBond: 7,
      lowCouponBond: 14,
      separateTaxBond: 6,
      reits: 4,
      gold: 2,
      infraFund: 2,
    },
    metrics: {
      expectedReturnPct: 6.4,
      volatilityPct: 12.5,
      volatilityAmountLabel: "±3,800만원",
      sharpe: 0.61,
      sortino: 0.48,
      mddPct: 11.2,
      mddAmountLabel: "-2,000만원",
      afterTaxReturnPct: 5.5,
      afterTaxAmountLabel: "+9,900만원",
    },
  },
  {
    id: "b",
    name: "포트폴리오 B",
    badge: "추천",
    weights: {
      domesticEquity: 28,
      overseasDividendEquity: 26,
      overseasGrowthEquity: 17,
      emergingEquity: 5,
      domesticBond: 8,
      overseasBond: 4,
      lowCouponBond: 8,
      separateTaxBond: 2,
      reits: 1,
      gold: 1,
      infraFund: 0,
    },
    metrics: {
      expectedReturnPct: 8.7,
      volatilityPct: 20.3,
      volatilityAmountLabel: "±6,100만원",
      sharpe: 0.43,
      sortino: 0.43,
      mddPct: 23.3,
      mddAmountLabel: "-4,200만원",
      afterTaxReturnPct: 7.2,
      afterTaxAmountLabel: "+1.29억원",
    },
  },
];

// ── 백테스트 (최근 5년, 100 기준 지수화 더미) ──────────────────
// 벤치마크(kospi·sp500·msciAcwi)는 실제 시장 흐름의 근사치 — 실 API 연동 전 UI 시안용.
export const BACKTEST_SERIES = [
  { year: "2021", current: 100, a: 100, b: 100, kospi: 100, sp500: 100, msciAcwi: 100 },
  { year: "2022", current: 96,  a: 103, b: 92,  kospi: 76,  sp500: 81,  msciAcwi: 80  },
  { year: "2023", current: 108, a: 116, b: 118, kospi: 90,  sp500: 104, msciAcwi: 100 },
  { year: "2024", current: 118, a: 131, b: 128, kospi: 97,  sp500: 134, msciAcwi: 123 },
  { year: "2025", current: 128, a: 150, b: 156, kospi: 101, sp500: 165, msciAcwi: 148 },
  { year: "2026", current: 140, a: 176, b: 200, kospi: 108, sp500: 190, msciAcwi: 168 },
];

// ── 상관관계 히트맵 (6분류 기준 더미 행렬, 대칭) ────────────────
// DISPLAY_GROUPS 순서와 동일한 6x6 행렬.
export const CORRELATION_MATRIX: number[][] = [
  [1.0, 0.62, 0.71, 0.18, 0.05, 0.12],
  [0.62, 1.0, 0.68, 0.22, 0.1, 0.15],
  [0.71, 0.68, 1.0, 0.14, 0.02, 0.09],
  [0.18, 0.22, 0.14, 1.0, 0.74, 0.4],
  [0.05, 0.1, 0.02, 0.74, 1.0, 0.35],
  [0.12, 0.15, 0.09, 0.4, 0.35, 1.0],
];

// ── 절세 최적화 시뮬레이터 ─────────────────────────────────────
export const TAX_EFFECT = {
  baseLabel: "기준 : 포트폴리오 A · 18억",
  annualSavingManwon: 1080,
  subNote:
    "일반과세 대비 · 세후 수익률 +0.6%p · 해외주식 양도세 22%·공제 250만 반영",
  afterTaxReturn: { from: "5.5%", to: "6.1%", delta: "+0.6%p" },
  effectiveTax: { from: "1,620", to: "540만", delta: "−1,080만" },
  // 세금 흐름 비교 (세전 기대수익 2.59억 기준, afterTaxManwon=만원)
  flow: {
    pretaxLabel: "세전 기대수익 2.59억 기준",
    rows: [
      { label: "기존 자산",      afterTaxManwon: 25100, taxManwon: 795 },
      { label: "포트폴리오 전환", afterTaxManwon: 25600, taxManwon: 363 },
      { label: "+ 절세 제안",   afterTaxManwon: 25900, taxManwon: 0   },
    ],
    totalLabel: "총 절세 효과 (전환 432만 + 제안 363만)",
    totalSavingManwon: 795,
  },
  // 절세 계좌 배치 활용도
  accounts: [
    {
      name: "ISA",
      tag: "비과세·분리과세",
      used: 2000,
      limit: 2000,
      caption: "납입 한도 100% 활용 · 비과세 200만 + 초과분 9.9% 분리과세",
    },
    {
      name: "연금저축 + IRP",
      tag: "세액공제",
      used: 900,
      limit: 900,
      caption: "세액공제 한도 소진 · 공제율 16.5% → 환급 148만",
    },
    {
      name: "일반계좌",
      tag: "분리과세 ETF",
      used: null,
      limit: null,
      caption: "국내·해외 ETF 중심으로 금융소득종합과세 구간 회피",
    },
  ],
};

// 종합과세 임계선 (금융소득종합과세 기준선 2,000만원 — 소득세법 §14③6)
export const TAX_THRESHOLD = {
  thresholdManwon: 2000,
  gaugeMaxManwon: 3000,
  otherIncomeDefault: 1650,
  otherIncomeMax: 2480,
  portfolioDividendManwon: 520, // 포트폴리오 A 예상 이자·배당 (더미)
  separateRateLabel: "15.4%",
  comprehensiveRateLabel: "최고 49.5%",
};

export const TAX_ADVICE = {
  cards: [
    {
      icon: "I",
      title: "ISA 계좌 활용",
      body: "배당주 4,000만원을 ISA로 이전 — 비과세 한도 적용 후 초과분 분리과세 9.9%.",
      tag: "비과세 자산 이전",
      saving: "+210만원",
    },
    {
      icon: "채",
      title: "분리과세 채권",
      body: "저쿠폰·장기채로 이자소득을 분리과세(14%) 전환해 종합과세 합산에서 제외.",
      tag: "분리과세 전환",
      saving: "+180만원",
    },
    {
      icon: "배",
      title: "저율과세 배당주",
      body: "고배당 종목을 저율과세 ETF·우선주로 조정해 배당소득세 부담 완화.",
      tag: "저율과세 편입",
      saving: "+90만원",
    },
    {
      icon: "L",
      title: "Tax-loss Harvesting",
      body: "평가손실 1,800만원 확정 → 해외주식 양도차익과 상계해 양도세(22%) 절감.",
      tag: "평가손실 확정",
      saving: "+396만원",
    },
  ],
  totalLabel: "알고리즘 제안 적용 시 예상 추가 절감",
  totalSaving: "+876만원",
};

// ── 시나리오 Test (스트레스 테스트) ─────────────────────────────
export const SCENARIO_BASE = {
  ratePct: 3.75, // 현재 기준금리 (시안 기준)
  rateMin: 0,
  rateMax: 6,
  rateStep: 0.25,
  fxKrw: 1530, // 현재 원/달러 (시안 기준)
  fxMin: 1000,
  fxMax: 2000,
  fxStep: 10,
};

// 시나리오 슬라이더 변화 → 예상 평가손익(억원) 더미 선형 민감도.
// 정본 시안의 표시값(금리 +1.00%p · 환율 -450원 → 현재 -1.0 / A -1.6 / B -3.2억)을
// 재현하도록 역산한 자리표시자다. 실제 민감도는 백엔드 시뮬레이션으로 대체.
export const SCENARIO_SENSITIVITY: Record<
  "current" | "a" | "b",
  { perRatePct: number; perFxKrw: number }
> = {
  current: { perRatePct: -0.4, perFxKrw: 0.6 / 450 },
  a: { perRatePct: -0.6, perFxKrw: 1.0 / 450 },
  b: { perRatePct: -1.2, perFxKrw: 2.0 / 450 },
};

// 기준 시나리오에서 이만큼 벗어나면 "큰 폭 변동" 경고를 띄운다 (UI 더미 기준)
export const SCENARIO_WARN = {
  rateDeltaPct: 0.75,
  fxDeltaKrw: 300,
  message:
    "매우 큰 폭의 변동을 가정한 시나리오입니다. 정밀한 수치보다는 전체적인 흐름을 보시는 용도로 적합합니다.",
};

// ── AI 인사이트 ────────────────────────────────────────────────
export const INSIGHT = {
  placeholder: "예: 금리 전망, 환율 리스크, 세액공제…",
  defaultAnswer:
    "현재 고객 포트폴리오는 국내주식 20%, 해외배당주 22% 비중으로 선진국 배당 자산에 상대적으로 집중되어 있습니다. 최근 미 연준의 금리 동결 기조 장기화 가능성을 고려할 때, 단기 채권 듀레이션을 1~2년 이내로 유지하면서 투자등급 회사채 비중을 소폭 확대하는 전략이 유효합니다.\n\n환율 측면에서는 원/달러 환율이 1,380~1,420원 구간에서 등락하는 현 상황에서, 해외자산 중 비헤지 비중이 44%에 달해 환손실 리스크가 잠재합니다. 달러 익스포저의 30% 수준까지 환헤지 전환을 단계적으로 검토하시기 바랍니다.\n\n세후 수익률 기준으로는 포트폴리오 A(세후 5.5%)가 현재 포트폴리오(세후 4.0%) 대비 약 1.5%p 우위에 있으며, ISA 계좌 편입과 연금저축 한도 추가 납입을 통해 절세 여력이 연간 최대 1,080만원 추가로 확보 가능합니다.\n\n리스크 관리 측면에서 MDD -11.2% 수준은 VVIP 고객 손실 허용 범위(통상 -15% 이내) 내에 있으나, 글로벌 경기 둔화 시나리오 하에서 해외성장주 비중(12%)이 변동성 확대의 주요 원인이 될 수 있습니다. 포트폴리오 B의 해외성장주 22% 비중 확대안은 고수익 추구 성향 고객에 한해 선별 제안을 권고합니다.",
  sources: [
    { title: "Young Creator 리서치 · 글로벌 전략", date: "2026.05.20" },
    { title: "yfinance Market Data API", date: "실시간" },
    { title: "Bloomberg Macro Outlook", date: "2026.05" },
    { title: "국세청 금융소득 종합과세 가이드", date: "2026" },
  ],
};
