/** 공유 상수. */

/**
 * STT 로 실 consultation_id 를 확보하기 전, RAG·tax 요청의 consultation_id(UUID 필수)
 * 자리표시자. 백엔드 라우터는 현재 consultation_id 존재검증이 TODO 라 nil UUID 로도
 * 동작한다(검증 추가되면 STT 결과의 실 id 를 반드시 사용해야 함).
 */
export const NIL_UUID = "00000000-0000-0000-0000-000000000000";
