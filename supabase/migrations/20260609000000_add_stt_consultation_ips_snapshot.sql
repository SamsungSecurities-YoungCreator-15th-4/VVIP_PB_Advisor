-- =====================================================================
-- VVIP_PB_Advisor DB 마이그레이션 0002
-- STT 상담 업로드 결과와 IPS 스냅샷 저장 구조 추가.
-- 기존 client / consultation 테이블을 재사용해 고객·상담 개념 중복을 피한다.
-- =====================================================================

-- 고객명 기반 조회와 3명 페르소나 시드의 중복 방지.
create unique index if not exists ux_client_name
  on client(name);

-- STT 상담 내역 저장용 컬럼.
alter table consultation
  add column if not exists audio_filename text,
  add column if not exists transcript_json jsonb not null default '[]'::jsonb,
  add column if not exists ips_json jsonb not null default '{}'::jsonb;

-- 최초 IPS와 상담 후 IPS를 같은 구조로 보관하는 계산용 스냅샷.
create table if not exists ips_snapshot (
  id                  uuid primary key default gen_random_uuid(),
  client_id           uuid not null references client(id) on delete cascade,
  consultation_id     uuid references consultation(id) on delete cascade,
  source_type         text not null check (source_type in ('initial', 'consultation')),
  goal                text,
  asset               numeric,
  "return"            numeric,
  risk                text check (risk in ('안정형', '균형형', '공격형') or risk is null),
  "time"              numeric,
  tax                 text,
  liquidity           text check (liquidity in ('낮음', '중간', '높음') or liquidity is null),
  legal               text,
  "unique"            text,
  raw_ips_json        jsonb not null default '{}'::jsonb,
  created_at          timestamptz not null default now(),
  check (
    (source_type = 'initial' and consultation_id is null)
    or (source_type = 'consultation' and consultation_id is not null)
  )
);

create index if not exists idx_ips_snapshot_client_id
  on ips_snapshot(client_id);

create index if not exists idx_ips_snapshot_consultation_id
  on ips_snapshot(consultation_id);

create index if not exists idx_ips_snapshot_created_at
  on ips_snapshot(created_at desc);

create unique index if not exists ux_ips_snapshot_initial_client_id
  on ips_snapshot(client_id)
  where source_type = 'initial';

create unique index if not exists ux_ips_snapshot_consultation_id
  on ips_snapshot(consultation_id)
  where source_type = 'consultation';

alter table ips_snapshot enable row level security;

insert into client (name, meta)
values
  ('김성삼', '{"persona": true}'::jsonb),
  ('이사조', '{"persona": true}'::jsonb),
  ('박기업', '{"persona": true}'::jsonb)
on conflict (name) do update
set meta = client.meta || excluded.meta;

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
select
  c.id,
  null,
  'initial',
  seed.goal,
  seed.asset,
  seed."return",
  seed.risk,
  seed."time",
  seed.tax,
  seed.liquidity,
  seed.legal,
  seed."unique",
  jsonb_build_object(
    'Goal', seed.goal,
    'Asset', seed.asset,
    'Return', seed."return",
    'Risk', seed.risk,
    'Time', seed."time",
    'Tax', seed.tax,
    'Liquidity', seed.liquidity,
    'Legal', seed.legal,
    'Unique', seed."unique"
  )
from (
  values
    (
      '김성삼',
      '전세자금 마련 및 장기 증여 계획',
      18::numeric,
      8::numeric,
      '균형형',
      10::numeric,
      '증여세, 금융소득세, 종합과세, 양도세',
      '중간',
      '증여세법, 자금 출처 조사 대비',
      '전세 자금 3억, 미국 배당주 장기채 선호'
    ),
    (
      '이사조',
      '창업 대금 마련을 위한 자산 다각화',
      30::numeric,
      25::numeric,
      '공격형',
      1::numeric,
      '해외주식 양도세, 거래비용, 수수료',
      '낮음',
      '해외주식 대주주 요건 및 신고 의무 준수',
      'AI 섹터 선호, 단기 트레이딩 성향 강함'
    ),
    (
      '박기업',
      '기업 승계 및 상속 준비',
      750::numeric,
      3::numeric,
      '안정형',
      10::numeric,
      '종합소득세, 부동산, 양도세, 증여세',
      '높음',
      '기업 상속 공제 요건',
      '법인 단기 운전자금 20억원 유동성 필요'
    )
) as seed(
  name,
  goal,
  asset,
  "return",
  risk,
  "time",
  tax,
  liquidity,
  legal,
  "unique"
)
join client c on c.name = seed.name
on conflict (client_id) where source_type = 'initial' do update
set
  goal = excluded.goal,
  asset = excluded.asset,
  "return" = excluded."return",
  risk = excluded.risk,
  "time" = excluded."time",
  tax = excluded.tax,
  liquidity = excluded.liquidity,
  legal = excluded.legal,
  "unique" = excluded."unique",
  raw_ips_json = excluded.raw_ips_json;
