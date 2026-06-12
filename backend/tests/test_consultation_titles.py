import unittest
from datetime import datetime

from app.routers.consultations import _build_stt_titles


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


if __name__ == "__main__":
    unittest.main()
