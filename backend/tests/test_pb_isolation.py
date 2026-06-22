"""PB 데이터 격리 단위 테스트.

핵심 시나리오: PB A로 로그인하면 PB A의 고객만 조회되고,
PB B의 고객은 전혀 보이지 않는다.

실행: pytest backend/tests/test_pb_isolation.py -v
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.routers.clients import _list_clients_for_pb
from app.routers.consultations import _get_client_by_id

PB_A = "aaaaaaaa-0000-0000-0000-000000000001"
PB_B = "bbbbbbbb-0000-0000-0000-000000000002"

CLIENT_A1 = {"id": "c1111111-0000-0000-0000-000000000001", "name": "김성삼", "pb_id": PB_A, "meta": {"aum_eokwon": 18.0, "persona": True}, "created_at": "2026-06-22T00:00:00+00:00"}
CLIENT_A2 = {"id": "c2222222-0000-0000-0000-000000000002", "name": "이사조", "pb_id": PB_A, "meta": {"aum_eokwon": 30.0, "persona": True}, "created_at": "2026-06-22T00:01:00+00:00"}
CLIENT_B1 = {"id": "c3333333-0000-0000-0000-000000000003", "name": "박기업", "pb_id": PB_B, "meta": {"aum_eokwon": 750.0, "persona": True}, "created_at": "2026-06-22T00:02:00+00:00"}

ALL_CLIENTS = [CLIENT_A1, CLIENT_A2, CLIENT_B1]


# ── 최소 mock — supabase-py 체인 빌더를 흉내냄 ─────────────────────────────

class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    """supabase.table(...).select(...).eq(...).limit(...).execute() 체인을 모사."""

    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._filters: list[tuple[str, object]] = []

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, field: str, value: object):
        self._filters.append((field, value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, _n: int):
        return self

    def execute(self) -> _FakeResult:
        filtered = self._rows
        for field, value in self._filters:
            filtered = [r for r in filtered if r.get(field) == value]
        return _FakeResult(filtered)


class _FakeSupabase:
    def __init__(self, table_data: dict[str, list[dict]]):
        self._data = table_data

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(self._data.get(name, []))


# ── 테스트 케이스 ────────────────────────────────────────────────────────────

class TestPbClientIsolation(unittest.TestCase):
    def setUp(self):
        self.supabase = _FakeSupabase({"client": ALL_CLIENTS})

    # 작업 2 검증 — 고객 목록 격리
    def test_pb_a_only_sees_own_clients(self):
        """PB A 는 자신의 고객(2명)만 조회되고 PB B 의 고객은 포함되지 않는다."""
        rows = _list_clients_for_pb(self.supabase, PB_A)
        ids = {r["id"] for r in rows}

        self.assertEqual(len(rows), 2)
        self.assertIn(CLIENT_A1["id"], ids)
        self.assertIn(CLIENT_A2["id"], ids)
        self.assertNotIn(CLIENT_B1["id"], ids, "PB B 고객이 PB A 조회에 노출됨!")

    def test_pb_b_only_sees_own_clients(self):
        """PB B 는 자신의 고객(1명)만 조회된다."""
        rows = _list_clients_for_pb(self.supabase, PB_B)
        ids = {r["id"] for r in rows}

        self.assertEqual(len(rows), 1)
        self.assertIn(CLIENT_B1["id"], ids)
        self.assertNotIn(CLIENT_A1["id"], ids)
        self.assertNotIn(CLIENT_A2["id"], ids)

    # 작업 3 검증 — consultations._get_client_by_id pb_id 2차 방어선
    def test_get_client_by_id_own_client_succeeds(self):
        """PB A 가 자신의 고객 ID 를 직접 조회하면 반환된다."""
        result = _get_client_by_id(self.supabase, CLIENT_A1["id"], pb_id=PB_A)
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], CLIENT_A1["id"])

    def test_get_client_by_id_other_pb_client_returns_none(self):
        """PB A 가 PB B 의 고객 ID 를 직접 조회하면 None 을 반환한다."""
        result = _get_client_by_id(self.supabase, CLIENT_B1["id"], pb_id=PB_A)
        self.assertIsNone(result, "PB A 가 PB B 의 고객을 직접 ID 로 조회할 수 없어야 합니다")

    def test_get_client_by_id_without_pb_filter_returns_row(self):
        """pb_id=None 이면 필터 없이 조회(WebSocket 경로 등 인증 미적용 구간 호환)."""
        result = _get_client_by_id(self.supabase, CLIENT_B1["id"])
        self.assertIsNotNone(result)

    def test_invalid_uuid_returns_none(self):
        """잘못된 UUID 형식은 DB 조회 없이 None 반환."""
        result = _get_client_by_id(self.supabase, "not-a-valid-uuid", pb_id=PB_A)
        self.assertIsNone(result)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestPbClientIsolation)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
