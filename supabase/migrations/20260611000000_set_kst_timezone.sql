-- =====================================================================
-- VVIP_PB_Advisor DB 마이그레이션 0005
-- timestamptz created_at/generated_at 조회 표시 기준을 한국 시간으로 맞춘다.
-- PostgreSQL은 timestamptz 값을 절대시각으로 보관하므로 기존 데이터의
-- 실제 시각은 변경하지 않고, DB/API 세션의 표시 타임존만 Asia/Seoul로 고정한다.
-- =====================================================================

alter database postgres set timezone to 'Asia/Seoul';

do $$
declare
  role_name text;
begin
  foreach role_name in array array[
    'anon',
    'authenticated',
    'service_role',
    'authenticator'
  ]
  loop
    if exists (
      select 1
      from pg_roles
      where rolname = role_name
    ) then
      execute format(
        'alter role %I set timezone to %L',
        role_name,
        'Asia/Seoul'
      );
    end if;
  end loop;
end $$;

set timezone to 'Asia/Seoul';
