-- =====================================================================
-- VVIP_PB_Advisor DB 마이그레이션 0006
-- 상담 목록/상세 API 분리에 맞춰 제목 기반 상세 조회를 빠르게 한다.
-- 프론트는 목록에서 consultation_id를 함께 받지만, transcript_title 기반 조회도 지원한다.
-- =====================================================================

create index if not exists idx_consultation_client_transcript_title
  on consultation(client_id, transcript_title);
