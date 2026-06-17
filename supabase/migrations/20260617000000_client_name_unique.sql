-- =====================================================================
-- VVIP_PB_Advisor DB 마이그레이션
-- 고객 추가 기능: STT 가 고객명으로 client 를 조회(Option A)하므로, 동명이인이 생기면
-- 어떤 client_id 를 FK 로 쓸지 모호해진다. client.name 을 고유키로 잡아 모호성을 차단한다.
-- (애플리케이션(POST /clients)도 중복 이름을 409 로 선차단하지만, 이 제약이 최종 가드)
--
-- 주의: 적용 전 기존 데이터에 동명이인이 없어야 한다(현재 페르소나 3명은 모두 고유).
--   확인: select name, count(*) from client group by name having count(*) > 1;
-- =====================================================================

alter table client add constraint client_name_key unique (name);
