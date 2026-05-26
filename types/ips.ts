/**
 * @file types/ips.ts
 *
 * ┌─────────────────────────────────────────────────────────────────┐
 * │  모듈 간 데이터 계약서 (Data Contract)                           │
 * │  ⚠️  이 파일을 변경할 때는 반드시 팀 합의가 필요합니다.           │
 * │                                                                 │
 * │  PB 상담 발화 → LLM 분석 → RRTTLLU 구조화 JSON                  │
 * │  modules/ips, modules/portfolio, modules/dashboard 가           │
 * │  공통으로 참조하는 핵심 스키마입니다.                             │
 * └─────────────────────────────────────────────────────────────────┘
 */

// ────────────────────────────────────────────────
// 1. 제네릭 래퍼 타입
// ────────────────────────────────────────────────

/**
 * RRTTLLU 각 요소를 감싸는 제네릭 래퍼.
 * 값(value) 외에 추출 품질 지표(confidence, conflict)와
 * 출처 발화(sourceText)를 함께 보관한다.
 *
 * @template T - 실제 값의 타입
 */
export interface IPSField<T> {
  /** 추출된 실제 값. 발화에서 파악 불가 시 null */
  value: T;

  /**
   * LLM 추출 신뢰도 (0 ~ 1).
   * 높을수록 발화 근거가 명확함.
   *
   * // TODO: 현재 산출 로직 미구현 — 임시로 0.85 고정.
   *           추후 LLM logprob 기반 신뢰도 계산으로 교체 예정.
   * @default 0.85
   */
  confidence: number;

  /**
   * 정량·정성 진술 모순 플래그.
   * 예) "안정적으로" 발화했으나 목표 수익률이 30% 이상일 때 true.
   *
   * // TODO: 현재 모순 감지 로직 미구현 — 자리만 마련.
   *           채택 여부는 팀 회의 후 결정.
   * @default false
   */
  conflict: boolean;

  /**
   * 이 값을 추출한 원본 발화 일부.
   * LLM 응답에서 근거 발화를 함께 반환할 때 사용.
   * 제공이 어려운 경우 생략 가능.
   */
  sourceText?: string;
}

// ────────────────────────────────────────────────
// 2. RRTTLLU 7요소 메인 인터페이스
// ────────────────────────────────────────────────

/**
 * IPS (Investment Policy Statement) 프로파일.
 * PB 상담 발화로부터 LLM이 추출한 RRTTLLU 7요소를 담는다.
 *
 * @example
 * const profile: IPSProfile = {
 *   return_target:         { value: 8.0,          confidence: 0.85, conflict: false },
 *   risk_tolerance:        { value: 'moderate',   confidence: 0.85, conflict: false },
 *   time_horizon_months:   { value: 36,           confidence: 0.85, conflict: false },
 *   tax_situation:         { value: '금융종합과세 대상', confidence: 0.85, conflict: false },
 *   liquidity_needs:       { value: [{ amount_krw: 50_000_000, due_date: '2025-12' }], confidence: 0.85, conflict: false },
 *   legal_constraints:     { value: null,         confidence: 0.85, conflict: false },
 *   unique_circumstances:  { value: '자녀 유학 예정', confidence: 0.85, conflict: false },
 * };
 */
export interface IPSProfile {
  /**
   * [R] Return — 목표 수익률 (%).
   * 예) 8.0 → 연 8% 수익 목표.
   * 발화에서 수치 미확인 시 null.
   */
  return_target: IPSField<number | null>;

  /**
   * [R] Risk — 위험 성향.
   * - 'conservative' : 안정형 (원금 보전 최우선)
   * - 'moderate'     : 중립형
   * - 'aggressive'   : 공격형 (고수익 추구)
   * - null           : 발화에서 판단 불가
   */
  risk_tolerance: IPSField<'conservative' | 'moderate' | 'aggressive' | null>;

  /**
   * [T] Time — 투자 기간 (개월 단위).
   * 예) 36 → 3년.
   * 발화에서 기간 미확인 시 null.
   */
  time_horizon_months: IPSField<number | null>;

  /**
   * [T] Tax — 세금 요인 메모.
   * 금융종합과세, 비과세 한도, 해외 소득 등 자유 텍스트.
   * 관련 발화 없으면 null.
   */
  tax_situation: IPSField<string | null>;

  /**
   * [L] Liquidity — 유동성 필요 스케줄.
   * 특정 시점까지 필요한 금액 목록.
   * - amount_krw : 필요 금액 (원화)
   * - due_date   : 필요 시점 (YYYY-MM 형식 권장)
   * 유동성 이슈가 없거나 발화 없으면 null.
   */
  liquidity_needs: IPSField<
    { amount_krw: number; due_date: string }[] | null
  >;

  /**
   * [L] Legal — 법적·규제 제약.
   * 임원 주식 의무 보유, 공직자 투자 제한 등 자유 텍스트.
   * 관련 발화 없으면 null.
   */
  legal_constraints: IPSField<string | null>;

  /**
   * [U] Unique — 고객 고유 상황.
   * 가족 이슈, 건강, 이민 계획 등 다른 항목에 분류되지 않는 특이 사항.
   * 관련 발화 없으면 null.
   */
  unique_circumstances: IPSField<string | null>;
}

// ────────────────────────────────────────────────
// 3. 페르소나 메타데이터
// ────────────────────────────────────────────────

/**
 * 대시보드에서 고객(페르소나)을 식별·표시하기 위한 메타데이터.
 * IPSProfile 과 함께 사용되며 별도 테이블(예: Supabase personas)에 저장.
 */
export interface PersonaMeta {
  /** 고객 고유 ID (Supabase UUID 또는 내부 식별자) */
  id: string;

  /** 고객 이름 또는 익명화된 레이블 (예: "홍길동", "VIP-042") */
  name: string;

  /**
   * 한 줄 상황 요약.
   * 대시보드 목록 카드에 표시되는 짧은 설명.
   * 예) "은퇴 3년 전, 자녀 유학 자금 필요"
   */
  summary: string;
}
