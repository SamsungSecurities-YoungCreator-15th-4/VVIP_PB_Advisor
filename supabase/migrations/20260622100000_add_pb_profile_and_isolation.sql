-- =====================================================================
-- VVIP_PB_Advisor DB 마이그레이션
-- PB 프로파일 테이블 생성 + client 테이블 pb_id 연결 + RLS 정책
--
-- 목적: "PB가 로그인하면 본인이 담당하는 고객만 볼 수 있다" (DB 보안 챕터 핵심 증거)
--   1) pb_profile — auth.users 와 연결되는 PB 정보(이름, pb_code)
--   2) client.pb_id — 담당 PB 외래키 (auth.users 참조)
--   3) RLS 정책 — client / consultation / ips_snapshot 접근을 pb_id 기준 격리
--
-- 멱등성: IF NOT EXISTS / IF EXISTS 사용해 재실행 안전.
-- 주의: 백엔드는 service_role 키 사용 → RLS 우회 → 백엔드 접근에 지장 없음.
--       RLS 는 직접 DB 접근(anon/authenticated role) 방어용 1차 방어선이다.
--       백엔드에서 pb_id 명시 필터링이 2차 방어선.
-- =====================================================================

-- ───────────────────────────────────────────────
-- 1. PB 프로파일 테이블
-- ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pb_profile (
  id         uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  name       text NOT NULL,
  pb_code    text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(pb_code)
);

ALTER TABLE pb_profile ENABLE ROW LEVEL SECURITY;

-- PB는 자기 프로파일만 읽기
CREATE POLICY pb_profile_select_own ON pb_profile
  FOR SELECT USING (id = auth.uid());

-- ───────────────────────────────────────────────
-- 2. client 테이블에 pb_id 컬럼 추가
--    기존 created_by(미사용 잔류 컬럼)는 건드리지 않고 신규 컬럼으로 분리.
-- ───────────────────────────────────────────────
ALTER TABLE client
  ADD COLUMN IF NOT EXISTS pb_id uuid REFERENCES auth.users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_client_pb_id ON client(pb_id);

-- ───────────────────────────────────────────────
-- 3. client RLS 정책 (pb_id = auth.uid())
-- ───────────────────────────────────────────────

-- SELECT: 담당 PB만 고객 조회
CREATE POLICY client_select_own ON client
  FOR SELECT USING (pb_id = auth.uid());

-- INSERT: 자신이 담당 PB인 고객만 등록
CREATE POLICY client_insert_own ON client
  FOR INSERT WITH CHECK (pb_id = auth.uid());

-- UPDATE: 담당 PB만 고객 정보 수정
CREATE POLICY client_update_own ON client
  FOR UPDATE
  USING    (pb_id = auth.uid())
  WITH CHECK (pb_id = auth.uid());

-- ───────────────────────────────────────────────
-- 4. consultation RLS 정책 (client.pb_id 조인)
-- ───────────────────────────────────────────────

CREATE POLICY consultation_select_own ON consultation
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM client
      WHERE client.id = consultation.client_id
        AND client.pb_id = auth.uid()
    )
  );

CREATE POLICY consultation_insert_own ON consultation
  FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM client
      WHERE client.id = consultation.client_id
        AND client.pb_id = auth.uid()
    )
  );

-- ───────────────────────────────────────────────
-- 5. ips_snapshot RLS 정책 (client.pb_id 조인)
-- ───────────────────────────────────────────────

CREATE POLICY ips_snapshot_select_own ON ips_snapshot
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM client
      WHERE client.id = ips_snapshot.client_id
        AND client.pb_id = auth.uid()
    )
  );

CREATE POLICY ips_snapshot_insert_own ON ips_snapshot
  FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM client
      WHERE client.id = ips_snapshot.client_id
        AND client.pb_id = auth.uid()
    )
  );

-- ───────────────────────────────────────────────
-- 6. portfolio_option / proposal
--    consultation → client 을 2단계 조인. 현재 백엔드에서 직접 INSERT하지 않으므로
--    SELECT 정책만 추가한다(INSERT는 향후 기능 확장 시 추가).
-- ───────────────────────────────────────────────

CREATE POLICY portfolio_option_select_own ON portfolio_option
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM consultation
      JOIN client ON client.id = consultation.client_id
      WHERE consultation.id = portfolio_option.consultation_id
        AND client.pb_id = auth.uid()
    )
  );

CREATE POLICY proposal_select_own ON proposal
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM portfolio_option
      JOIN consultation ON consultation.id = portfolio_option.consultation_id
      JOIN client ON client.id = consultation.client_id
      WHERE portfolio_option.id = proposal.portfolio_option_id
        AND client.pb_id = auth.uid()
    )
  );
