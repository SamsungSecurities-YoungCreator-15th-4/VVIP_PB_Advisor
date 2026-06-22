import unittest

from app.routers.clients import _client_response_from_row


class ClientResponseTest(unittest.TestCase):
    def test_reads_meta_aum_and_persona_flag(self):
        response = _client_response_from_row(
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "name": "김성삼",
                "meta": {"aum_eokwon": 18, "persona": True},
                "created_at": "2026-06-22T08:00:00+00:00",
            }
        )

        self.assertEqual(response.client_id, "00000000-0000-0000-0000-000000000001")
        self.assertEqual(response.name, "김성삼")
        self.assertEqual(response.aum_eokwon, 18.0)
        self.assertIs(response.is_persona, True)
        self.assertEqual(response.created_at, "2026-06-22T17:00:00+09:00")

    def test_falls_back_when_meta_is_missing(self):
        response = _client_response_from_row(
            {
                "id": "00000000-0000-0000-0000-000000000002",
                "name": "신규고객",
                "meta": None,
                "created_at": "2026-06-22T17:00:00+09:00",
            }
        )

        self.assertEqual(response.aum_eokwon, 0.0)
        self.assertIs(response.is_persona, False)


if __name__ == "__main__":
    unittest.main()
