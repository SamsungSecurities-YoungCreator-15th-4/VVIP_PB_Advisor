-- =====================================================================
-- seed.sql — 절세/마찰비용 규칙표 (tax_rule)
--
-- 원칙(차별점 = 재현성·감사추적성):
--   * 규칙 숫자는 LLM 추정이 아니라 국세청 등 명시 출처에 근거한다.
--   * 모든 행은 source 를 채운다(감사추적 필수, NOT NULL).
--   * 검증 미완료 항목은 임의 숫자를 넣지 않는다 → params {"note":"TODO"},
--     사유는 assumptions 에 ⚠️ 로 남기고 검증 후 채운다.
--
-- 스키마 매핑(기존 baseline tax_rule 재사용):
--   category  → module  ('friction_cost' | 'tax_efficient_location')
--   name_ko   → description
--   trigger   → (시드에 트리거 조건이 없어 미사용; 필요 시 params 에 보관)
--   audit 컬럼 source/source_law/effective_from/to/assumptions 는
--   20260611000000_tax_rule_audit_columns 마이그레이션에서 추가됨.
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
      'basic_deduction_krw', 2500000
    ),
    '국세청 2026 세금가이드 2권(양도소득 기본공제 250만원 확인) / 세율 재검증 TODO',
    null,
    '⚠️ 세율 0.22(20%+지방세 2%)는 검증 보강 대상 — 2권 양도세 조항 재확인 필요. 기본공제 250만원은 확인됨.'
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
    jsonb_build_object('note', 'TODO'),
    '검증 보강 TODO',
    null,
    '⚠️ 연금저축·IRP 세액공제율·한도 검증 보강 대상 — 검증 후 params 채움(임의값 금지).'
  ),
  (
    'tax_efficient_location',
    'capital_loss_offset',
    '손익통산',
    jsonb_build_object('note', 'TODO'),
    '검증 보강 TODO',
    null,
    '⚠️ 국외주식 양도손익 통산 메커니즘 검증 TODO — 검증 후 params 채움(임의값 금지).'
  )
-- effective_from/to 는 INSERT 에서 제공하지 않으므로(향후 수동/별도 관리)
-- DO UPDATE 에서 제외한다. 포함하면 재시드 시 기존 값이 NULL 로 덮어써진다.
on conflict (module, rule_key) do update set
  description    = excluded.description,
  params         = excluded.params,
  source         = excluded.source,
  source_law     = excluded.source_law,
  assumptions    = excluded.assumptions;
