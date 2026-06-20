-- =====================================================================
-- tax_rule 감사추적(audit-trail) 컬럼 보강
--   재현성·감사추적성이 차별점이므로, 규칙 숫자는 반드시 출처·시행일·가정과
--   함께 저장한다. baseline(20260605000000)의 tax_rule 에는 이 컬럼이 없어
--   "그것만" 추가하는 작은 마이그레이션이다.
--
-- 기존 컬럼은 유지한다(rename 없음):
--   id, module, rule_key, description, params, priority, is_active, created_at
--   unique(module, rule_key)
-- 추가 컬럼: source(필수), source_law, effective_from/to, assumptions
-- =====================================================================

alter table tax_rule
  add column if not exists source        text,   -- 출처 (감사추적: 필수)
  add column if not exists source_law    text,   -- 근거 법령(있을 때만)
  add column if not exists effective_from date,  -- 시행일(from)
  add column if not exists effective_to   date,  -- 종료일(to)
  add column if not exists assumptions    text;  -- 계산 가정·한계·검증상태

-- 모든 규칙은 출처가 있어야 한다(감사추적).
-- baseline 은 tax_rule 행을 INSERT 하지 않고, seed 는 migration 이후 실행되므로
-- reset/push 시점의 tax_rule 은 비어 있어 NOT NULL 적용이 안전하다.
-- (출처 없는 기존 행이 있으면 의도적으로 실패시켜 audit 위반을 드러낸다.)
alter table tax_rule
  alter column source set not null;

comment on column tax_rule.source        is '규칙 숫자의 출처(국세청 자료 등). 감사추적용 필수값.';
comment on column tax_rule.source_law    is '근거 법령 조문(예: 소득세법 §14).';
comment on column tax_rule.effective_from is '규칙 시행일.';
comment on column tax_rule.effective_to   is '규칙 종료일(현행이면 NULL).';
comment on column tax_rule.assumptions   is '계산 가정·한계·검증 상태(⚠️ TODO 포함).';
