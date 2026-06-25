/**
 * 백엔드(FastAPI) 실제 요청/응답 스키마를 그대로 옮긴 TS 타입.
 * 출처: backend/app/routers/{rag,tax,consultations}.py · schemas/consultations.py
 * (필드명·타입·중첩을 백엔드 기준으로 맞춘다. 바꾸면 연동이 깨진다.)
 */

// ── RAG: POST /rag/insight ─────────────────────────────────────
export interface RagInsightRequest {
  consultation_id: string; // UUID
  query: string;
  context?: {
    risk_profile?: string | null;
    selected_portfolio?: string | null;
    dashboard?: Record<string, unknown> | null;
  };
}

export interface RagCitation {
  doc_id: string;
  source_type: string;
  title: string;
  published_date?: string | null; // ISO date
  chunk: string;
  similarity?: number | null;
}

export interface RagInsightResponse {
  answer: string;
  summary: string;
  citations: RagCitation[];
  as_of: string; // ISO datetime
}

// ── DART 재무: POST /dart/insight ──────────────────────────────
// 기업 재무제표(매출·영업이익 등)는 RAG 코퍼스에 없으므로 DART 전자공시에서
// 실시간 조회한다. 수치는 원문 그대로(접수번호로 감사추적), LLM 은 요약만 한다.
export interface DartInsightRequest {
  corp_name?: string | null;
  corp_code?: string | null;
  bsns_year?: number | null; // 미지정 시 최신 확정 사업보고서
}

export interface DartFinancialsPayload {
  revenue?: number | null;
  operating_income?: number | null;
  net_income?: number | null;
  total_assets?: number | null;
  total_liabilities?: number | null;
  total_equity?: number | null;
}

export interface DartSource {
  corp_code: string;
  bsns_year: number;
  reprt_code: string;
  rcept_no: string; // 공시 원문 접수번호(감사추적)
  fs_label: string; // 연결/별도
  currency: string;
  note: string;
}

export interface DartInsightResponse {
  query: string;
  resolve_status: string; // matched/disambiguated/excluded_delisted/manual_review/not_found
  resolve_reason: string;
  corp_code: string | null;
  corp_name: string | null;
  financials: DartFinancialsPayload | null;
  source: DartSource | null;
  summary: string;
  as_of: string; // ISO datetime
}

// ── 절세: POST /tax/insight ────────────────────────────────────
// tax_result 는 #30(build_tax_optimizer_payload) 출력 형태. extra 허용이라 부분 전송 가능.
export interface TaxHeadline {
  annual_tax_saving?: number | null;
  tax_amount_before?: number | null;
  tax_amount_after?: number | null;
  after_tax_return_before?: number | null; // 0.0432 = 4.32%
  after_tax_return_after?: number | null;
  after_tax_return_improvement_p?: number | null;
}

export interface TaxAccountCard {
  status_label?: string | null;
  description?: string | null;
  estimated_tax_saving?: number | null; // ISA
  estimated_tax_credit?: number | null; // IRP
  estimated_tax_after_strategy?: number | null; // 일반계좌
}

export interface TaxCalculationResult {
  portfolio_key?: string | null;
  portfolio_name?: string | null;
  total_asset?: number | null;
  headline?: TaxHeadline | null;
  account_cards?: Record<string, TaxAccountCard> | null;
  notes?: string[] | null;
}

export interface TaxInsightRequest {
  consultation_id: string; // UUID
  tax_result: TaxCalculationResult;
}

export interface TaxInsightResponse {
  summary: string;
  as_of: string; // ISO datetime
}

// ── STT: POST /consultations/stt (multipart) ───────────────────
// 백엔드는 customer_name 을 str 로 받아 DB(client.name)로 검증한다(없으면 404).
// /clients 로 신규 고객을 만들 수 있으므로 페르소나 3인으로 좁히지 않는다.
export type CustomerName = string;

export interface TranscriptItem {
  speaker_role: "PB" | "고객" | string;
  text: string;
  utterance_time: string; // "MM:SS"
}

/** flatten_ips_json 출력(RRTTLLU 9키 평탄화). 발화 미확인 값은 null 가능. */
export interface IpsJson {
  Goal: string | null;
  Asset: number | string | null;
  Return: number | string | null;
  Risk: string | null;
  Time: number | string | null;
  Tax: string | null;
  Liquidity: string | null;
  Legal: string | null;
  Unique: string | null;
}

export interface ConsultationResponse {
  consultation_id: string;
  customer_id: string;
  customer_name: CustomerName;
  consultation_date: string;
  transcript_title: string;
  ips_title: string;
  transcript_json: TranscriptItem[];
  ips_json: IpsJson;
  ips_snapshot_id: string | null;
  created_at: string; // ISO datetime (KST)
}

// ── 상담 내역 목록: GET /consultations?client_id= ──────────────
export interface ConsultationSummary {
  consultation_id: string;
  customer_id: string;
  customer_name: CustomerName;
  consultation_date: string;
  transcript_title: string;
  ips_title: string;
  created_at: string; // ISO datetime (KST)
}

export interface ConsultationListResponse {
  customer_name: CustomerName;
  consultations: ConsultationSummary[];
}

export interface InitialIpsResponse {
  ips_snapshot_id: string;
  customer_id: string;
  customer_name: CustomerName;
  source_type: "initial";
  ips_json: Record<string, unknown>;
  created_at: string;
}

// ── Clients: GET /clients · POST /clients ─────────────────────
export interface ClientListItem {
  client_id: string;
  name: string;
  aum_eokwon: number | null;
  is_persona: boolean;
  created_at: string;
}

export interface ClientListResponse {
  pb_id: string;
  clients: ClientListItem[];
}

export interface ClientCreateRequest {
  name: string;
  aum_eokwon: number;
}

export interface ClientCreateResponse {
  client_id: string;
  name: string;
  aum_eokwon: number;
  ips_snapshot_id: string;
  created_at: string;
}

// ── Dashboard Snapshot: POST /clients/{id}/dashboard-snapshot ─
export interface DashboardSnapshotSaveRequest {
  consultation_id: string;
  calculation_session_id: string;
  dashboard_result: Record<string, unknown>; // POST /portfolio/calculate 응답 전체
  stress_test_result?: Record<string, unknown>;
}

export interface DashboardSnapshotResponse {
  saved: boolean;
  client_id: string;
  consultation_id: string;
  calculation_session_id: string;
  dashboard_result: Record<string, unknown>;
  stress_test_result?: Record<string, unknown>;
  saved_at: string;
  message: string;
}

// ── Portfolio Calculate: POST /portfolio/calculate ─────────────
export interface STTIPSJson {
  Goal?: string | null;
  Asset: number | string;
  Return: number | string;
  Risk: string;
  Time: number | string;
  Tax: string;
  Liquidity: string;
  Legal?: string | null;
  Unique?: string | null;
}

export interface CurrentPortfolioItem {
  asset_class: string;
  weight: number; // 0–100
}

export interface ScenarioInput {
  base_interest_rate?: number | null;
  base_fx_rate_krw_per_usd?: number | null;
  stress_interest_rate_shock?: number;
  stress_fx_shock?: number;
  stress_affects_scoring?: boolean;
}

export interface PortfolioCalculateRequest {
  ips_json: STTIPSJson;
  client_id?: string | null;
  customer_id?: string | null;
  consultation_id?: string | null;
  current_portfolio?: CurrentPortfolioItem[] | null;
  benchmark_key?: "kospi" | "sp500" | "msci_acwi";
  period?: string;
  num_simulations?: number;
  expected_return_haircut?: number;
  random_seed?: number;
  scenario?: ScenarioInput | null;
  marginal_income_tax_rate?: number | null;
  external_financial_income_krw?: number | null;
  external_financial_income_manwon?: number | null;
  overseas_realized_loss?: number | null;
  overseas_realized_gain_krw?: number | null;
  isa_current_year_contribution?: number | null;
}

export interface AllocationItemResponse {
  asset_class: string;
  name: string;
  weight: number; // %
}

export interface BacktestPointResponse {
  date: string;
  value: number;
  base_index: number;
}

export interface BenchmarkMetadataResponse {
  benchmark_key?: string | null;
  ticker?: string | null;
  label?: string | null;
  currency?: string | null;
  applicable?: boolean | null;
  reason?: string | null;
  affects_portfolio_recommendation?: boolean | null;
}

export interface BenchmarkSeriesResponse {
  metadata: BenchmarkMetadataResponse;
  backtest: BacktestPointResponse[];
}

export interface BenchmarkCollectionResponse {
  kospi?: BenchmarkSeriesResponse | null;
  sp500?: BenchmarkSeriesResponse | null;
  msci_acwi?: BenchmarkSeriesResponse | null;
}

export interface BenchmarkComparisonResponse {
  beta?: number | null;
  metadata: BenchmarkMetadataResponse;
}

export interface BenchmarkComparisonsResponse {
  kospi?: BenchmarkComparisonResponse | null;
  sp500?: BenchmarkComparisonResponse | null;
  msci_acwi?: BenchmarkComparisonResponse | null;
}

export interface PortfolioMetricsResponse {
  expected_return: number; // %
  volatility: number; // %
  sharpe: number;
  sortino: number;
  mdd: number; // %
  beta?: number | null;
  beta_benchmark?: BenchmarkMetadataResponse | null;
  selected_benchmark_key?: string | null;
  benchmark_comparisons: BenchmarkComparisonsResponse;
  after_tax_return: number; // %
  [key: string]: unknown;
}

export interface PortfolioMetricsKRWResponse {
  basis: string;
  total_asset: number;
  expected_return: number;
  after_tax_return: number;
  mdd: number;
  volatility_band: number;
  note: string;
  [key: string]: unknown;
}

export interface VsCurrentKRWResponse {
  after_tax_return_delta: number;
  mdd_loss_improvement: number;
  basis: string;
  [key: string]: unknown;
}

export interface TaxWaterfallResponse {
  gross_return: number;
  dividend_interest_tax: number;
  capital_gains_tax: number;
  transaction_cost: number;
  fx_cost: number;
  after_tax: number;
  [key: string]: unknown;
}

export interface PortfolioTaxResponse {
  waterfall: TaxWaterfallResponse;
  saved_vs_current: number;
  summary: string;
  calculation_notes: string[];
  gauge?: StressTaxGauge | null;
  [key: string]: unknown;
}

export interface PortfolioItemResponse {
  kind: "current" | "A" | "B";
  rank?: number | null;
  label: string;
  badge?: string | null;
  allocation: AllocationItemResponse[];
  allocation_total: number;
  metrics: PortfolioMetricsResponse;
  metrics_krw: PortfolioMetricsKRWResponse;
  vs_current_krw: VsCurrentKRWResponse;
  backtest: BacktestPointResponse[];
  benchmark: BenchmarkSeriesResponse;
  benchmarks: BenchmarkCollectionResponse;
  tax: PortfolioTaxResponse;
  [key: string]: unknown;
}

export interface CorrelationAssetResponse {
  asset_class: string;
  name: string;
}

export interface CorrelationHeatmapResponse {
  assets: CorrelationAssetResponse[];
  matrix: number[][];
  value_type: "correlation";
}

export interface RejectionCountsResponse {
  suitability: number;
  liquidity: number;
  historical_var_95: number;
  risk_contribution: number;
  [key: string]: unknown;
}

export interface SearchSummaryResponse {
  generated_portfolios: number;
  guideline_pass_portfolios: number;
  suitable_portfolios: number;
  liquidity_pass_portfolios: number;
  risk_control_pass_portfolios: number;
  common_filter_pass_portfolios: number;
  filtered_out_portfolios: number;
  rejection_counts: RejectionCountsResponse;
  selection_method: string;
  portfolio_a_selection_mode: string;
  portfolio_b_selection_mode: string;
  portfolio_b_available: boolean;
  target_after_tax_return: number;
  eligible_assets: string[];
  excluded_by_horizon: string[];
  constraint_warnings: string[];
  [key: string]: unknown;
}

export interface ScenarioSummaryResponse {
  base_interest_rate: number;
  base_fx_rate_krw_per_usd: number;
  stressed_interest_rate: number;
  stressed_fx_rate_krw_per_usd: number;
  stress_interest_rate_shock: number;
  stress_fx_shock: number;
  stress_affects_scoring: boolean;
  rrttllu: Record<string, unknown>;
  unique_profile: Record<string, unknown>;
  [key: string]: unknown;
}

export interface DataSnapshotResponse {
  data_source?: string | null;
  period?: string | null;
  data_start?: string | null;
  data_end?: string | null;
  fallback_used?: boolean | null;
  fallback_reason?: string | null;
  backtest_data_snapshot: Record<string, unknown>;
  [key: string]: unknown;
}

export interface InputAdapterResponse {
  source: string;
  client_id?: string | null;
  consultation_id?: string | null;
  flat_ips_keys_used: string[];
  warnings: string[];
  [key: string]: unknown;
}

export interface MethodologyResponse {
  portfolio_generation: string;
  optimization_basis: string;
  risk_classification: string;
  selection_logic: string;
  duration_logic: string;
  suitability_filter: string;
  liquidity_metric: string;
  tax_logic: string;
  second_portfolio_logic: string;
  stress_test_logic: string;
  var_erc_logic: string;
  benchmark_beta_logic: string;
  corporate_context_logic: string;
  backtest_caution: string;
  [key: string]: unknown;
}

export interface PortfolioCalculateResponseContract {
  client_id?: string | null;
  consultation_id: string;
  calculation_session_id: string;
  as_of: string;
  risk_profile: string;
  risk_profile_label: string;
  portfolios: PortfolioItemResponse[];
  correlation_heatmap: CorrelationHeatmapResponse;
  search_summary: SearchSummaryResponse;
  scenario_summary: ScenarioSummaryResponse;
  data_snapshot: DataSnapshotResponse;
  input_adapter: InputAdapterResponse;
  methodology: MethodologyResponse;
  notes: string[];
}

// ── Portfolio Insight: POST /portfolio/insight ─────────────────
export interface PortfolioMetrics {
  expected_return?: number | null;
  volatility?: number | null;
  sharpe_ratio?: number | null;
  sortino_ratio?: number | null;
  mdd?: number | null;
  beta?: number | null;
  after_tax_return?: number | null;
  [key: string]: unknown;
}

export interface PortfolioSummary {
  api_key?: string | null;
  name?: string | null;
  metrics?: PortfolioMetrics | null;
  [key: string]: unknown;
}

export interface StressResult {
  [key: string]: unknown;
}

export interface TaxOptimizerResult {
  [key: string]: unknown;
}

export interface PortfolioInsightRequest {
  consultation_id?: string | null;
  benchmark_choice?: string | null;
  current?: PortfolioSummary | null;
  portfolio_a?: PortfolioSummary | null;
  portfolio_b?: PortfolioSummary | null;
  stress?: StressResult | null;
  tax_optimizer?: TaxOptimizerResult | null;
  [key: string]: unknown;
}

export interface PortfolioInsightResponse {
  summary: string;
  source: string; // "llm" | "fallback"
  as_of: string; // ISO datetime
}

// ── Stress Tax: base_tax / stressed_tax from POST /portfolio/stress-metrics ──
// 출처: 백엔드 stress-metrics 응답 스키마 (절세 최적화 시뮬레이터 연동 명세 v1)
export interface StressTaxHeadline {
  annual_tax_saving: number;                // 원
  tax_amount_before: number;                // 원
  tax_amount_after: number;                 // 원
  after_tax_return_before: number;          // 소수 (0.055 = 5.5%)
  after_tax_return_after: number;           // 소수
  after_tax_return_improvement_p: number;   // 소수 (%p)
  modeled_tax_reduction?: number | null;
  unapplied_credit_or_saving?: number | null;
  legacy_account_only_tax_saving?: number | null;
}

export interface StressTaxStrategyCard {
  key: string;                              // "isa"|"low_tax_dividend"|"separate_bond"|"tax_loss"|"overseas_exemption"|"pension_credit"
  title: string;
  calculation_order: number;
  priority_rank: number;
  applicable: boolean;
  standalone_saving: number;               // 원
  combined_contribution: number;           // 원
  combined_contribution_manwon: number;    // 만원
  transferable_amount?: number | null;
  rule_keys?: string[] | null;
  reason?: Record<string, unknown> | null;
}

export interface StressTaxStrategyCards {
  cards: StressTaxStrategyCard[];
  combined_total: number;                  // 원
  combined_total_manwon: number;           // 만원
  calculation_order?: string[] | null;
  display_order_basis?: string | null;
}

export interface StressTaxGauge {
  external_financial_income_manwon: number;
  portfolio_financial_income_manwon: number;
  total_financial_income_manwon: number;
  threshold_manwon: number;
  excess_over_threshold_manwon: number;
  estimated_additional_tax_manwon: number;
  is_over_threshold: boolean;
  withholding_rate_pct: number;
  marginal_rate_pct: number;
  additional_rate_pct: number;
  separate_rate_label: string;
  comprehensive_rate_label: string;
  rate_note?: string | null;
}

export interface StressTaxFlowEntry {
  after_tax_profit?: number | null;        // 원 (0이면 미제공)
  tax_amount?: number | null;              // 원
  tax_saving?: number | null;              // 원
}

export interface StressTaxFlow {
  general_tax_before_strategy?: StressTaxFlowEntry | null;
  after_tax_strategy?: StressTaxFlowEntry | null;
}

export interface StressTaxAccountCard {
  status_label?: string | null;
  description?: string | null;
  used_capacity?: number | null;        // 원
  remaining_capacity?: number | null;   // 원
  [key: string]: unknown;
}

export interface StressTaxAccountCards {
  isa?: StressTaxAccountCard | null;
  irp?: StressTaxAccountCard | null;
  taxable_account?: StressTaxAccountCard | null;
}

export interface StressTaxData {
  portfolio_key: string;                   // "base_tax" | "stressed_tax"
  portfolio_name: string;
  total_asset?: number | null;             // 억원 단위 (요청 portfolio.total_asset과 동일 스케일)
  headline: StressTaxHeadline;
  strategy_cards: StressTaxStrategyCards;
  financial_income_tax_gauge: StressTaxGauge;
  account_cards?: StressTaxAccountCards | null;
  tax_flow?: StressTaxFlow | null;
  notes?: string[] | null;
}

// ── Market: GET /api/macro-indicators · GET /api/market-data ──
export interface IndicatorData {
  price: number;
  change: number;
  changePct: number;
  isStatic?: boolean | null;
  isFallback?: boolean | null;
}

export interface MacroIndicators {
  baseRate: IndicatorData;
  treasuryYield: IndicatorData;
  krwUsd: IndicatorData;
  cpi: IndicatorData;
  kospi: IndicatorData;
  sp500: IndicatorData;
  fetchedAt: string;
}

export interface MarketDataPoint {
  ticker: string;
  prices: number[];
  dates: string[];
  annualReturn: number;
  annualVolatility: number;
}

