-- =====================================================================
-- VVIP_PB_Advisor DB 마이그레이션
-- 고객 추가 기능: STT 가 고객명으로 client 를 조회(Option A)하므로 동명이인이 생기면
-- client.name 의 고유성이 필요하다. 다만 이 고유성은 이미
-- 20260609000000_add_stt_consultation_ips_snapshot.sql 의 unique index
-- `ux_client_name` 가 강제하고 있다(고객명 조회·페르소나 시드 중복 방지).
--
-- 처음에는 이를 모르고 `client_name_key` UNIQUE 제약을 별도로 추가했으나,
-- 같은 (name) 컬럼에 unique index 가 2개(ux_client_name + client_name_key) 공존하는
-- 중복이라 정리한다. 권위 가드는 기존 `ux_client_name` 1개로 통일한다.
-- (애플리케이션 POST /clients 도 중복 이름을 409 로 선차단)
--
-- idempotent: 신규 DB 에서는 client_name_key 가 애초에 없으므로 no-op.
-- =====================================================================

alter table client drop constraint if exists client_name_key;
