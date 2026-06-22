import unittest
from datetime import datetime

from app.routers.consultations import (
    _build_stt_titles,
    _get_client_by_id,
    _parse_realtime_client_id,
    _to_kst_iso,
)


class FakeResult:
    def __init__(self, count=None, data=None):
        self.count = count
        self.data = data


class FakeQuery:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def select(self, *args, **kwargs):
        self.calls.append(("select", args, kwargs))
        return self

    def eq(self, *args):
        self.calls.append(("eq", args))
        return self

    def gte(self, *args):
        self.calls.append(("gte", args))
        return self

    def lt(self, *args):
        self.calls.append(("lt", args))
        return self

    def execute(self):
        return self.result


class FakeSupabase:
    def __init__(self, result):
        self.query = FakeQuery(result)
        self.table_name = None

    def table(self, name):
        self.table_name = name
        return self.query


class SttTitleTest(unittest.TestCase):
    def test_first_consultation_title_for_day(self):
        supabase = FakeSupabase(FakeResult(count=0))

        transcript_title, ips_title = _build_stt_titles(
            supabase=supabase,
            client_id="client-1",
            customer_name="김성삼",
            now=datetime.fromisoformat("2026-06-11T15:30:00+09:00"),
        )

        self.assertEqual(transcript_title, "260611_김성삼_상담 스크립트(1)")
        self.assertEqual(ips_title, "260611_김성삼_ips(1)")
        self.assertEqual(supabase.table_name, "consultation")

    def test_next_consultation_title_for_day(self):
        supabase = FakeSupabase(FakeResult(count=2))

        transcript_title, ips_title = _build_stt_titles(
            supabase=supabase,
            client_id="client-1",
            customer_name="김성삼",
            now=datetime.fromisoformat("2026-06-11T18:45:00+09:00"),
        )

        self.assertEqual(transcript_title, "260611_김성삼_상담 스크립트(3)")
        self.assertEqual(ips_title, "260611_김성삼_ips(3)")

    def test_falls_back_to_data_length_when_count_is_unavailable(self):
        supabase = FakeSupabase(FakeResult(data=[{"id": "1"}, {"id": "2"}]))

        _, ips_title = _build_stt_titles(
            supabase=supabase,
            client_id="client-1",
            customer_name="김성삼",
            now=datetime.fromisoformat("2026-06-11T18:45:00+09:00"),
        )

        self.assertEqual(ips_title, "260611_김성삼_ips(3)")

    def test_parses_postgres_timestamp_with_short_microseconds(self):
        created_at = _to_kst_iso("2026-06-21T22:34:39.04894+09:00")

        self.assertEqual(created_at, "2026-06-21T22:34:39.048940+09:00")

    def test_realtime_start_payload_requires_client_id(self):
        self.assertEqual(
            _parse_realtime_client_id({"client_id": " client-1 "}),
            "client-1",
        )

        with self.assertRaisesRegex(ValueError, "client_id"):
            _parse_realtime_client_id({"customer_name": "김성삼"})

    def test_get_client_by_id_rejects_invalid_uuid_before_query(self):
        supabase = FakeSupabase(FakeResult(data=[{"id": "client-1"}]))

        client = _get_client_by_id(supabase, "not-a-uuid")

        self.assertIsNone(client)
        self.assertIsNone(supabase.table_name)


if __name__ == "__main__":
    unittest.main()
