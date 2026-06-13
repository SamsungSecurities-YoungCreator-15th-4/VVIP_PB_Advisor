-- =====================================================================
-- VVIP_PB_Advisor DB 마이그레이션 0003
-- STT 상담 결과를 음성 파일명이 아닌 결과 JSON 명칭으로 저장한다.
-- 음성 파일은 백엔드 처리 후 저장하지 않는다.
-- =====================================================================

alter table consultation
  add column if not exists transcript_title text,
  add column if not exists ips_title text;

update consultation co
set
  transcript_title = coalesce(
    nullif(co.transcript_title, ''),
    to_char(co.created_at at time zone 'Asia/Seoul', 'YYMMDD') || '_' || c.name || '_상담 스크립트'
  ),
  ips_title = coalesce(
    nullif(co.ips_title, ''),
    to_char(co.created_at at time zone 'Asia/Seoul', 'YYMMDD') || '_' || c.name || '_ips'
  )
from client c
where co.client_id = c.id
  and (
    co.transcript_title is null
    or co.transcript_title = ''
    or co.ips_title is null
    or co.ips_title = ''
  );

alter table consultation
  alter column transcript_title set not null,
  alter column ips_title set not null,
  drop column if exists audio_filename;

create index if not exists idx_consultation_client_created_at
  on consultation(client_id, created_at desc);
