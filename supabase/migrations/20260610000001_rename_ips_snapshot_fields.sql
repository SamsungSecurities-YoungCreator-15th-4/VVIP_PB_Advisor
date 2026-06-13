-- =====================================================================
-- VVIP_PB_Advisor DB 마이그레이션 0004
-- ips_snapshot의 Goal/Asset/RRTTLLU 컬럼명을 단순 IPS 항목명으로 정리한다.
-- asset은 STT/IPS JSON과 같은 억 원 단위 숫자로 저장한다.
-- =====================================================================

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'ips_snapshot'
      and column_name = 'asset_krw'
  ) and not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'ips_snapshot'
      and column_name = 'asset'
  ) then
    alter table ips_snapshot rename column asset_krw to asset;
    update ips_snapshot
    set asset = asset / 100000000
    where asset is not null;
  end if;

  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'ips_snapshot'
      and column_name = 'target_return_pct'
  ) and not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'ips_snapshot'
      and column_name = 'return'
  ) then
    alter table ips_snapshot rename column target_return_pct to "return";
  end if;

  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'ips_snapshot'
      and column_name = 'risk_profile'
  ) and not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'ips_snapshot'
      and column_name = 'risk'
  ) then
    alter table ips_snapshot rename column risk_profile to risk;
  end if;

  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'ips_snapshot'
      and column_name = 'time_horizon_years'
  ) and not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'ips_snapshot'
      and column_name = 'time'
  ) then
    alter table ips_snapshot rename column time_horizon_years to "time";
  end if;

  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'ips_snapshot'
      and column_name = 'tax_notes'
  ) and not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'ips_snapshot'
      and column_name = 'tax'
  ) then
    alter table ips_snapshot rename column tax_notes to tax;
  end if;

  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'ips_snapshot'
      and column_name = 'liquidity_need'
  ) and not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'ips_snapshot'
      and column_name = 'liquidity'
  ) then
    alter table ips_snapshot rename column liquidity_need to liquidity;
  end if;

  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'ips_snapshot'
      and column_name = 'legal_notes'
  ) and not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'ips_snapshot'
      and column_name = 'legal'
  ) then
    alter table ips_snapshot rename column legal_notes to legal;
  end if;

  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'ips_snapshot'
      and column_name = 'unique_needs'
  ) and not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'ips_snapshot'
      and column_name = 'unique'
  ) then
    alter table ips_snapshot rename column unique_needs to "unique";
  end if;
end $$;
