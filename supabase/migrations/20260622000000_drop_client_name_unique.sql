-- =====================================================================
-- VVIP_PB_Advisor DB 마이그레이션
-- client.name UNIQUE 제약 완전 제거
--
-- 배경:
--   VVIP 동명이인을 허용해야 하므로 name 컬럼의 UNIQUE 제약을 전부 제거한다.
--   고유성은 PK(id uuid)가 이미 보장하고 있으므로 별도 작업 불필요.
--
-- 제거 대상:
--   ① client_name_key  — ALTER TABLE ADD CONSTRAINT 으로 추가된 UNIQUE constraint
--                         (20260617142445_client_name_unique.sql 에서 추가)
--   ② ux_client_name   — CREATE UNIQUE INDEX 로 추가된 unique index
--                         (20260609000000_add_stt_consultation_ips_snapshot.sql 에서 추가)
--
-- 멱등성: IF EXISTS 를 사용해 재실행 시 안전(no-op).
-- =====================================================================

-- ① UNIQUE constraint 제거 (ALTER TABLE ... DROP CONSTRAINT)
ALTER TABLE client DROP CONSTRAINT IF EXISTS client_name_key;

-- ② UNIQUE index 제거 (DROP INDEX) 및 일반 인덱스 추가
--    name 기반 조회(SELECT ... WHERE name = ?)는 계속 사용되므로
--    Full Table Scan 방지를 위해 non-unique index 로 교체한다.
DROP INDEX IF EXISTS ux_client_name;
CREATE INDEX IF NOT EXISTS idx_client_name ON client(name);
