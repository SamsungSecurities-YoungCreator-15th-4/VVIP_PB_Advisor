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
