-- =====================================================================
-- VVIP_PB_Advisor DB 마이그레이션 0008
-- STT 상담 제목을 고객별·KST 날짜별 순번으로 저장한다.
-- 예: 260611_김성삼_상담 스크립트(1), 260611_김성삼_ips(1)
-- =====================================================================

create or replace function public.create_stt_consultation_with_snapshot(
  p_client_id uuid,
  p_raw_note text,
  p_transcript_title text,
  p_ips_title text,
  p_transcript_json jsonb,
  p_ips_json jsonb,
  p_goal text,
  p_asset numeric,
  p_return numeric,
  p_risk text,
  p_time numeric,
  p_tax text,
  p_liquidity text,
  p_legal text,
  p_unique text,
  p_raw_ips_json jsonb
)
returns table (
  consultation_id uuid,
  customer_id uuid,
  transcript_title text,
  ips_title text,
  transcript_json jsonb,
  ips_json jsonb,
  ips_snapshot_id uuid,
  created_at timestamptz
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_consultation_id uuid;
  v_snapshot_id uuid;
  v_created_at timestamptz := now();
  v_customer_name text;
  v_day_start timestamptz;
  v_day_end timestamptz;
  v_sequence integer;
  v_title_prefix text;
  v_transcript_title text;
  v_ips_title text;
begin
  select name
  into v_customer_name
  from client
  where id = p_client_id
  for update;

  if v_customer_name is null then
    raise exception 'client not found: %', p_client_id;
  end if;

  v_day_start := date_trunc('day', v_created_at at time zone 'Asia/Seoul')
    at time zone 'Asia/Seoul';
  v_day_end := v_day_start + interval '1 day';

  select count(*) + 1
  into v_sequence
  from consultation
  where client_id = p_client_id
    and created_at >= v_day_start
    and created_at < v_day_end;

  v_title_prefix := to_char(v_created_at at time zone 'Asia/Seoul', 'YYMMDD')
    || '_' || v_customer_name;
  v_transcript_title := v_title_prefix || '_상담 스크립트(' || v_sequence || ')';
  v_ips_title := v_title_prefix || '_ips(' || v_sequence || ')';

  insert into consultation (
    client_id,
    raw_note,
    transcript_title,
    ips_title,
    transcript_json,
    ips_json,
    created_at
  )
  values (
    p_client_id,
    p_raw_note,
    v_transcript_title,
    v_ips_title,
    coalesce(p_transcript_json, '[]'::jsonb),
    coalesce(p_ips_json, '{}'::jsonb),
    v_created_at
  )
  returning id
  into v_consultation_id;

  insert into ips_snapshot (
    client_id,
    consultation_id,
    source_type,
    goal,
    asset,
    "return",
    risk,
    "time",
    tax,
    liquidity,
    legal,
    "unique",
    raw_ips_json,
    created_at
  )
  values (
    p_client_id,
    v_consultation_id,
    'consultation',
    p_goal,
    p_asset,
    p_return,
    p_risk,
    p_time,
    p_tax,
    p_liquidity,
    p_legal,
    p_unique,
    coalesce(p_raw_ips_json, '{}'::jsonb),
    v_created_at
  )
  returning id
  into v_snapshot_id;

  return query
  select
    v_consultation_id,
    p_client_id,
    v_transcript_title,
    v_ips_title,
    coalesce(p_transcript_json, '[]'::jsonb),
    coalesce(p_ips_json, '{}'::jsonb),
    v_snapshot_id,
    v_created_at;
end;
$$;

revoke all on function public.create_stt_consultation_with_snapshot(
  uuid,
  text,
  text,
  text,
  jsonb,
  jsonb,
  text,
  numeric,
  numeric,
  text,
  numeric,
  text,
  text,
  text,
  text,
  jsonb
) from public;

grant execute on function public.create_stt_consultation_with_snapshot(
  uuid,
  text,
  text,
  text,
  jsonb,
  jsonb,
  text,
  numeric,
  numeric,
  text,
  numeric,
  text,
  text,
  text,
  text,
  jsonb
) to service_role;
