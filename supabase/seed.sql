-- =====================================================================
-- seed.sql — 절세/마찰비용 규칙표 (tax_rule)
--
-- 원칙(차별점 = 재현성·감사추적성):
--   * 규칙 숫자는 LLM 추정이 아니라 국세청 등 명시 출처에 근거한다.
--   * 모든 행은 source 를 채운다(감사추적 필수, NOT NULL).
--   * 검증 미완료 항목은 임의 숫자를 넣지 않는다(값 미상이면 비워두고
--     사유를 assumptions 에 남긴 뒤 검증 후 채운다). 현재 전 행 검증 완료.
--
-- 스키마 매핑(기존 baseline tax_rule 재사용):
--   category  → module  ('friction_cost' | 'tax_efficient_location')
--   name_ko   → description
--   trigger   → (시드에 트리거 조건이 없어 미사용; 필요 시 params 에 보관)
--   audit 컬럼 source/source_law/effective_from/to/assumptions 는
--   20260611000002_tax_rule_audit_columns 마이그레이션에서 추가됨.
--
-- 주의: unique(module, rule_key). 재시드 안전을 위해 ON CONFLICT DO UPDATE.
-- =====================================================================

-- ── friction_cost (차감: 실현수익에서 빼야 할 마찰비용/세금) ──────────
insert into tax_rule (module, rule_key, description, params, source, source_law, assumptions)
values
  (
    'friction_cost',
    'financial_income_tax_threshold',
    '금융소득종합과세 임계(2천만원)',
    jsonb_build_object(
      'threshold_krw', 20000000,
      'rate_under',    0.154,
      'rate_over_max', 0.495,
      'calc',          '비교과세_큰값'
    ),
    '국세청 2026 세금절약가이드 1권',
    '소득세법 §14,§62',
    '2천만원 이하 15.4% 분리과세 효과 / 초과분 종합과세 누진 최고 49.5%(지방소득세 포함)'
  ),
  (
    'friction_cost',
    'bond_capital_gain_tax_free',
    '채권 자본차익 비과세',
    jsonb_build_object('rate', 0),
    '국세청 2026 세금가이드 1권',
    '소득세법',
    '개인의 채권 매매차익(자본차익)은 비과세. 표면이자(이자소득)는 별도 과세.'
  ),
  (
    'friction_cost',
    'overseas_stock_transfer_tax',
    '해외주식 양도소득세',
    jsonb_build_object(
      'rate',                0.22,
      'national_rate',       0.20,
      'local_rate',          0.02,
      'basic_deduction_krw', 2500000,
      'loss_offset_scope',   'overseas_equity_same_year'
    ),
    '국세청 2026 세금가이드 2권(기본공제 250만) + 유안타증권·토스뱅크 해외주식 양도세 안내(세율 22%)',
    '소득세법 양도소득(국외주식)',
    '국세 20%+지방세 2%=22%, 연 250만원 기본공제. 금투세 2024.12 폐지로 현행 유지(2026 기준). 같은 해 해외주식 양도손익끼리 통산 후 과세 — 일반 개인은 국내주식·해외파생과 통산 불가.'
  )
-- effective_from/to 는 INSERT 에서 제공하지 않으므로(향후 수동/별도 관리)
-- DO UPDATE 에서 제외한다. 포함하면 재시드 시 기존 값이 NULL 로 덮어써진다.
on conflict (module, rule_key) do update set
  description    = excluded.description,
  params         = excluded.params,
  source         = excluded.source,
  source_law     = excluded.source_law,
  assumptions    = excluded.assumptions;

-- ── tax_efficient_location (절감: 세 부담을 줄이는 절세 수단) ─────────────────────
insert into tax_rule (module, rule_key, description, params, source, source_law, assumptions)
values
  (
    'tax_efficient_location',
    'isa_tax_exemption',
    'ISA 비과세/분리과세',
    jsonb_build_object(
      'exempt_general_krw', 2000000,
      'exempt_low_krw',     4000000,
      'over_rate',          0.099,
      'lockup_years',       3
    ),
    '국세청 2026 세금가이드 1권',
    '조세특례제한법 §88의2',
    'ISA 의무가입 3년 → 유동성(L) 계산에 반영 필요. 일반형 200만원/서민형 400만원 비과세, 초과분 9.9% 분리과세.'
  ),
  (
    'tax_efficient_location',
    'low_coupon_bond',
    '저쿠폰채 절세전략',
    jsonb_build_object('mechanism', 'capital_gain_tax_free'),
    '삼성증권 저쿠폰 채권 전략 2.0(2025.02) / 국세청 1권',
    null,
    '저쿠폰채 절세효과 = 자본차익 비과세 활용(과세 이자 비중 최소화). 신청분리과세 30%는 2018 폐지. 금투세 2024.12 폐지 전제.'
  ),
  (
    'tax_efficient_location',
    'pension_account_tax_credit',
    '연금계좌 세액공제',
    jsonb_build_object(
      'limit_pension_krw',            6000000,
      'limit_total_krw',             9000000,
      'credit_rate_low_incl_local',  0.165,
      'credit_rate_high_incl_local', 0.132,
      'credit_rate_low_national',    0.15,
      'credit_rate_high_national',   0.12,
      'income_threshold_krw',        45000000,
      'salary_threshold_krw',        55000000,
      'isa_rollover_extra_rate',     0.10,
      'isa_rollover_extra_limit_krw', 3000000,
      'pension_receipt_rate_min',    0.033,
      'pension_receipt_rate_max',    0.055,
      'separate_tax_limit_krw',      15000000
    ),
    '국세청 2026 세금가이드 1권(근로자 세금)',
    '소득세법 §59의3',
    '연금저축 600만+IRP 합산 900만 한도. 공제율 국세 15%/12%(지방세 포함 16.5%/13.2%), 기준 종합소득 4,500만(총급여 5,500만) 이하 고율. 과세이연: 운용수익 비과세→수령 시 연금소득세 3~5%, 연 1,500만 이하 분리과세. ISA 만기 추가납입 10% 추가공제(300만 한도).'
  ),
  (
    'tax_efficient_location',
    'capital_loss_offset',
    '손익통산',
    jsonb_build_object(
      'scope',             'overseas_equity_same_year',
      'cross_domestic_equity', false,
      'cross_derivatives',     false
    ),
    '헬프미·토스뱅크·taxly 해외주식 양도세 안내(웹 교차검증)',
    '소득세법 양도소득 통산',
    '같은 해 해외주식 양도차익·차손 상계 가능. 일반 개인(대주주 아님)은 국내주식·해외파생상품과 통산 불가 → 해외주식 양도손익끼리만. Tax-loss Harvesting 근거.'
  )
-- effective_from/to 는 INSERT 에서 제공하지 않으므로(향후 수동/별도 관리)
-- DO UPDATE 에서 제외한다. 포함하면 재시드 시 기존 값이 NULL 로 덮어써진다.
on conflict (module, rule_key) do update set
  description    = excluded.description,
  params         = excluded.params,
  source         = excluded.source,
  source_law     = excluded.source_law,
  assumptions    = excluded.assumptions;
