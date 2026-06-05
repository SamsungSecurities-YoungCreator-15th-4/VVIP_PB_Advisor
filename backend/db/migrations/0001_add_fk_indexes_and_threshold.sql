-- =====================================================================
-- VVIP_PB_Advisor DB 마이그레이션 0001
-- baseline(schema.sql v0.1) 이후 변경분. Supabase SQL Editor에서 실행.
-- 코드리뷰(Gemini) 반영: FK 인덱스 3건 + RAG 검색 함수 임계값 파라미터.
-- 제외: document_chunk.document_id 인덱스
--       → unique(document_id, chunk_index) 인덱스가 선행 컬럼으로 이미 커버.
-- 보류(팀 합의 필요): numeric 정밀도, ips_profile 구조 통합.
-- =====================================================================

-- 1) FK 컬럼 인덱스 (CASCADE 삭제·조인 성능)
create index if not exists idx_consultation_client_id
  on consultation(client_id);
create index if not exists idx_portfolio_option_consultation_id
  on portfolio_option(consultation_id);
create index if not exists idx_proposal_portfolio_option_id
  on proposal(portfolio_option_id);

-- 2) RAG 검색 함수에 유사도 임계값 추가 (기본 0.0 = 하위호환)
--    HNSW 인덱스 성능을 위해 먼저 Top-K(match_count)를 인덱스로 빠르게 뽑은 뒤,
--    바깥 쿼리에서 similarity_threshold 미만을 필터링한다.
--    (WHERE에서 임계값을 먼저 걸면 결과가 부족할 때 인덱스/테이블 풀스캔 위험)
create or replace function match_document_chunks (
  query_embedding vector(1536),
  match_count int default 5,
  similarity_threshold float default 0.0
)
returns table (
  id uuid,
  document_id uuid,
  content text,
  similarity float
)
language sql stable
as $$
  select *
  from (
    select
      dc.id,
      dc.document_id,
      dc.content,
      1 - (dc.embedding <=> query_embedding) as similarity
    from document_chunk dc
    where dc.embedding is not null
    order by dc.embedding <=> query_embedding
    limit match_count
  ) sub
  where sub.similarity > similarity_threshold;
$$;
