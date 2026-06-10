-- =====================================================================
-- VVIP_PB_Advisor  Supabase 초기 스키마 (v0.1)
-- 작성: 백엔드·DB 리드 최중현
-- 실행 위치: Supabase Dashboard → SQL Editor → 전체 붙여넣기 → Run
-- 원칙
--   1) 변동성 큰 데이터는 jsonb 로 둔다 (MVP 단계 스키마 안정성)
--   2) 임베딩 차원은 모델 미정 → vector(1536) 로 잡되 모델명/차원 메타 동봉
--   3) 모든 PK 는 uuid (gen_random_uuid())
-- =====================================================================

-- 0. 확장(extension) ---------------------------------------------------
create extension if not exists "pgcrypto";   -- gen_random_uuid()
create extension if not exists "vector";      -- pgvector (RAG 임베딩)

-- =====================================================================
-- 축 A. RAG (문서 검색)
-- =====================================================================

-- 원문 단위. 투운사/AFPK/절세해설/삼성증권 하우스뷰 등
create table if not exists document (
  id          uuid primary key default gen_random_uuid(),
  title       text not null,
  source_type text not null,          -- 'house_view' | 'afpk' | 'tax_law' | 'internal' ...
  source_url  text,
  meta        jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now()
);

-- 청크 단위. 임베딩은 여기에 저장
create table if not exists document_chunk (
  id              uuid primary key default gen_random_uuid(),
  document_id     uuid not null references document(id) on delete cascade,
  chunk_index     int  not null,
  content         text not null,
  -- 임베딩: 차원 미정이므로 1536 으로 선고정. 모델 확정 시 ALTER 또는 신컬럼.
  embedding       vector(1536),
  embedding_model text,               -- 'text-embedding-3-small' 등 추적용
  embedding_dim   int,                -- 실제 사용 차원(섞임 방지 검증용)
  token_count     int,
  created_at      timestamptz not null default now(),
  unique (document_id, chunk_index)
);

-- 벡터 유사도 인덱스 (코사인). 데이터가 쌓인 뒤 만드는 게 정석이나,
-- MVP 규모(소량)에서는 미리 만들어도 무방.
create index if not exists idx_document_chunk_embedding
  on document_chunk
  using hnsw (embedding vector_cosine_ops);

-- =====================================================================
-- 축 B. 절세 (규칙표 + 페르소나)  ※ 다른 테이블의 FK 아님 = 참조용 시드
-- =====================================================================

-- 하드코딩 규칙표. 2모듈: 마찰비용 차감 / 절세 자산배치
create table if not exists tax_rule (
  id          uuid primary key default gen_random_uuid(),
  module      text not null,          -- 'friction_cost' | 'tax_efficient_location'
  rule_key    text not null,          -- 'overseas_stock_transfer_tax' 등
  description text,
  params      jsonb not null default '{}'::jsonb,  -- 세율/한도/조건 등 유연 보관
  priority    int  not null default 100,
  is_active   boolean not null default true,
  created_at  timestamptz not null default now(),
  unique (module, rule_key)
);

-- 페르소나 3명: 이사조 / 김성삼 / 박기업
create table if not exists persona (
  id        uuid primary key default gen_random_uuid(),
  name      text not null unique,
  tax_tags  text[] not null default '{}', -- {'해외주식양도세','거래비용'} 등
  profile   jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- =====================================================================
-- 축 C. 상담 → IPS → 포폴 → 제안서(PDF)
-- =====================================================================

create table if not exists client (
  id         uuid primary key default gen_random_uuid(),
  name       text not null,
  created_by uuid,                    -- PB(추후 auth.users 연동 시 FK)
  meta       jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists consultation (
  id         uuid primary key default gen_random_uuid(),
  client_id  uuid not null references client(id) on delete cascade,
  raw_note   text not null,           -- 상담노트 원문(붙여넣기)
  created_at timestamptz not null default now()
);

-- IPS RRTTLLU 7요소. 졸작 연계 confidence/conflict 구조 선반영
create table if not exists ips_profile (
  id                  uuid primary key default gen_random_uuid(),
  consultation_id     uuid not null unique references consultation(id) on delete cascade,
  -- RRTTLLU 7요소 + 필드별 confidence/conflict/sourceText 를 jsonb 로
  rrttllu             jsonb not null default '{}'::jsonb,
  confidence_per_field jsonb not null default '{}'::jsonb,  -- 구조만 선반영
  conflict_flags      jsonb not null default '{}'::jsonb,   -- 정량·정성 모순 검출
  created_at          timestamptz not null default now()
);

create table if not exists portfolio_option (
  id              uuid primary key default gen_random_uuid(),
  consultation_id uuid not null references consultation(id) on delete cascade,
  label           text not null,      -- '옵션 A' | '옵션 B'
  allocation      jsonb not null default '{}'::jsonb,  -- 자산군별 비중
  pre_tax_return  numeric,
  after_tax_return numeric,
  stress_result   jsonb not null default '{}'::jsonb,  -- 시나리오 스트레스 테스트
  created_at      timestamptz not null default now()
);

create table if not exists proposal (
  id                  uuid primary key default gen_random_uuid(),
  portfolio_option_id uuid not null references portfolio_option(id) on delete cascade,
  pdf_url             text,           -- Supabase Storage 경로
  meta                jsonb not null default '{}'::jsonb,
  generated_at        timestamptz not null default now()
);

-- =====================================================================
-- RAG 검색 함수 (코사인 유사도 top-k). 백엔드에서 rpc 로 호출
-- =====================================================================
create or replace function match_document_chunks (
  query_embedding vector(1536),
  match_count int default 5
)
returns table (
  id uuid,
  document_id uuid,
  content text,
  similarity float
)
language sql stable
as $$
  select
    dc.id,
    dc.document_id,
    dc.content,
    1 - (dc.embedding <=> query_embedding) as similarity
  from document_chunk dc
  where dc.embedding is not null
  order by dc.embedding <=> query_embedding
  limit match_count;
$$;

-- =====================================================================
-- RLS (Row Level Security) 뼈대
--   주의: 아래는 "활성화만" 해두고 정책은 인증 붙일 때 추가.
--   service_role 키(백엔드)는 RLS 우회하므로 MVP 백엔드 접근엔 지장 없음.
-- =====================================================================
alter table client            enable row level security;
alter table consultation      enable row level security;
alter table ips_profile       enable row level security;
alter table portfolio_option  enable row level security;
alter table proposal          enable row level security;
-- document / document_chunk / tax_rule / persona 는 공용 참조성이라
-- 읽기 정책을 느슨하게 갈 수 있음 → 인증 설계 확정 후 결정.

-- =====================================================================
-- 시드(seed) 자리 — 절세 규칙·페르소나는 별도 seed.sql 에서 채운다.
--   예) insert into persona (name, tax_tags, profile) values (...);
-- =====================================================================
