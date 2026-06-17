-- =====================================================================
-- VVIP_PB_Advisor DB 마이그레이션 0007
-- STT 상담 저장과 상담 기반 IPS snapshot 저장을 단일 Postgres 함수로 묶는다.
-- Supabase RPC 호출 1회가 하나의 DB 트랜잭션으로 실행되므로 보상 삭제 없이도
-- consultation / ips_snapshot 원자성을 보장한다.
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
  v_created_at timestamptz;
begin
  insert into consultation (
    client_id,
    raw_note,
    transcript_title,
    ips_title,
    transcript_json,
    ips_json
  )
  values (
    p_client_id,
    p_raw_note,
    p_transcript_title,
    p_ips_title,
    coalesce(p_transcript_json, '[]'::jsonb),
    coalesce(p_ips_json, '{}'::jsonb)
  )
  returning id, consultation.created_at
  into v_consultation_id, v_created_at;

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
    raw_ips_json
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
    coalesce(p_raw_ips_json, '{}'::jsonb)
  )
  returning id
  into v_snapshot_id;

  return query
  select
    v_consultation_id,
    p_client_id,
    p_transcript_title,
    p_ips_title,
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
