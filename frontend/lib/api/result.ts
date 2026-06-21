/**
 * 데이터 출처 상태 — 화면이 "지금 보는 값이 어디서 왔는지" 명시하기 위한 공통 타입.
 *
 * 우리 거버넌스: 폴백(mock) 값을 실데이터인 척 보여주지 않는다. 호출 결과는 항상
 * source 를 달고 돌려, UI 가 배지로 사용자에게 알리도록 한다.
 *  - "live"     : 백엔드 실데이터
 *  - "empty"    : 정상 응답이지만 결과 없음(예: RAG 404 — 관련 문서 없음)
 *  - "fallback" : 호출 실패(네트워크/타임아웃/5xx)로 mock 표시 중 ⚠️
 */
export type DataSource = "live" | "empty" | "fallback";

export interface ApiResult<T> {
  data: T;
  source: DataSource;
  /** 폴백·빈결과 사유(사용자 안내·디버깅용). live 일 땐 보통 비움. */
  note?: string;
}

export function live<T>(data: T): ApiResult<T> {
  return { data, source: "live" };
}

export function empty<T>(data: T, note?: string): ApiResult<T> {
  return { data, source: "empty", note };
}

export function fallback<T>(data: T, note?: string): ApiResult<T> {
  return { data, source: "fallback", note };
}
