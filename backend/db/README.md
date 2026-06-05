# DB Schema (Supabase)

이 디렉터리는 VVIP_PB_Advisor의 Supabase 데이터베이스 스키마를 **버전관리·팀 공유·설계도 보관** 목적으로 담는다.

## `schema.sql`

- Supabase 프로젝트의 **초기 스키마(v0.1) baseline**이다.
- 이미 Supabase 웹 SQL Editor에서 실행 완료되어 9개 테이블이 생성된 상태이며, 이 파일은 그 baseline을 레포에 보관하는 것이다.
- 3축 구조 · 9개 테이블:
  - **축 A — RAG(문서 검색)**: `document`, `document_chunk`
  - **축 B — 절세(규칙표 + 페르소나)**: `tax_rule`, `persona`
  - **축 C — 상담 → IPS → 포폴 → 제안서**: `client`, `consultation`, `ips_profile`, `portfolio_option`, `proposal`

### 실행 방법

1. Supabase Dashboard → **SQL Editor** 진입
2. `schema.sql` 내용을 전체 복사해 붙여넣기
3. **Run** 실행

> `create extension/table/index if not exists`, `create or replace function` 으로 작성되어 있어 재실행해도 안전(idempotent)하다.

## 임베딩 차원 안내

- 현재 임베딩 컬럼은 `vector(1536)` 으로 고정되어 있다 (OpenAI `text-embedding-3-small` 기준).
- 임베딩 모델이 확정/변경되면 `ALTER` 로 차원을 변경한다. `document_chunk.embedding_model` / `embedding_dim` 컬럼에 실제 사용 모델·차원을 기록해 혼용을 방지한다.

## 시드(seed)

- 절세 규칙(`tax_rule`)·페르소나(`persona`) 시드 데이터는 추후 별도 `seed.sql` 로 분리해 추가할 예정이다.
