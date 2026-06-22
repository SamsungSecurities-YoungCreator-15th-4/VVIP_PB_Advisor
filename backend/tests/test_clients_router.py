import unittest

from app.routers.clients import _to_list_item


class ClientListItemTest(unittest.TestCase):
    def test_reads_meta_aum_and_persona_flag(self):
        item = _to_list_item(
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "name": "김성삼",
                "meta": {"aum_eokwon": 18, "persona": True},
                "created_at": "2026-06-22T08:00:00+00:00",
            }
        )

        self.assertEqual(item.client_id, "00000000-0000-0000-0000-000000000001")
        self.assertEqual(item.name, "김성삼")
        self.assertEqual(item.aum_eokwon, 18.0)
        self.assertIs(item.is_persona, True)
        self.assertEqual(item.created_at, "2026-06-22T17:00:00+09:00")

    def test_falls_back_when_meta_is_none(self):
        item = _to_list_item(
            {
                "id": "00000000-0000-0000-0000-000000000002",
                "name": "신규고객",
                "meta": None,
                "created_at": "2026-06-22T17:00:00+09:00",
            }
        )

        self.assertIsNone(item.aum_eokwon)
        self.assertIs(item.is_persona, False)

    def test_falls_back_when_required_display_fields_are_missing(self):
        item = _to_list_item({"meta": {"aum_eokwon": "bad"}})

        self.assertEqual(item.client_id, "")
        self.assertEqual(item.name, "Unknown")
        self.assertIsNone(item.aum_eokwon)
        self.assertEqual(item.created_at, "")


if __name__ == "__main__":
    unittest.main()
