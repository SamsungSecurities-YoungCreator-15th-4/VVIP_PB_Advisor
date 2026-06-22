-- =====================================================================
-- VVIP_PB_Advisor DB 마이그레이션 0010
-- DART 재무 조회 1단계: 회사명 → corp_code(8자리 고유번호) 매핑 캐시.
-- 시세가 아니라 "식별자" 캐싱이라 RAG 임베딩 금지 원칙과 무관하다.
-- 적재는 일회성 스크립트(scripts/ingest_corp_code.py)가 로컬에서 수행하고,
-- Render 런타임은 조회만 한다(corpCode.xml 전체 적재는 메모리 부담 → 런타임 적재 금지).
-- 상장사만 적재한다(stock_code 존재 행) — 비상장 ~9만 건은 재무 조회 대상이 아님.
-- 실행 위치: Supabase Dashboard → SQL Editor → 붙여넣기 → Run.
-- =====================================================================

create table if not exists dart_corp_code (
  corp_code             text primary key,   -- DART 8자리 고유번호 (예: '00126380')
  corp_name             text not null,      -- 원본 정식 법인명 (예: '삼성전자(주)')
  corp_name_normalized  text not null,      -- 조회용 정규화명 ((주)·주식회사·공백 제거)
  stock_code            text,               -- 종목코드 (상장사만, 예: '005930')
  modify_date           text                -- DART 제공 최종 갱신일 (예: '20260101')
);

-- 정규화명 기반 정확일치 조회용. 동명 정규화가 있을 수 있어 unique 가 아닌 일반 인덱스.
create index if not exists idx_dart_corp_code_name_normalized
  on dart_corp_code(corp_name_normalized);

-- 종목코드 보조 조회용("005930" 등으로 직접 찾는 경로).
create index if not exists idx_dart_corp_code_stock_code
  on dart_corp_code(stock_code);

-- RLS: 프로젝트 컨벤션(모든 테이블 RLS on + 정책 0개 = service_role 전용)에 맞춘다.
-- 적재·조회 모두 백엔드가 service_role 키로 수행(RLS 우회)하므로 anon/authenticated
-- 정책은 두지 않는다(공개 법인 메타지만 불필요한 노출면을 만들지 않음 = 최소권한).
-- (원격에는 Supabase 가 public 테이블 생성 시 RLS 를 자동 활성화하나, 파일만으로
--  재생성할 때도 동일하도록 여기서 명시한다. enable 은 멱등이라 재적용 무해.)
alter table dart_corp_code enable row level security;
