"""GET /clients/{id}/previous-dashboard 의 회차 선택 로직 회귀 테스트.

배경:
    '지난 상담 불러오기'에서 특정 회차를 골라도 대시보드는 고객의 '최신' 스냅샷만
    복원돼, 옛 회차를 눌러도 화면이 그대로였다(=IPS만 바뀌는 것처럼 보임).
    수정으로 consultation_id 를 지정하면 그 회차의 스냅샷을 반환하도록 했다.

원칙(AGENTS.md): Supabase 없이 순수 선택 로직(_pick_first_dashboard_snapshot)의
불변식만 고정한다.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.routers.clients import (  # noqa: E402
    FIRST_DASHBOARD_SNAPSHOT_KEY,
    _pick_first_dashboard_snapshot,
)


def _row(consultation_id: str, *, has_snapshot: bool = True):
    snap = {"consultation_id": consultation_id, "dashboard_result": {"k": consultation_id}}
    raw = {FIRST_DASHBOARD_SNAPSHOT_KEY: snap} if has_snapshot else {}
    return {"consultation_id": consultation_id, "raw_ips_json": raw}


# created_at 내림차순으로 정렬돼 들어온다고 가정(최신이 앞).
ROWS = [_row("c3"), _row("c2"), _row("c1")]


class PickFirstDashboardSnapshotTest(unittest.TestCase):
    def test_latest_when_no_consultation_id(self):
        snap = _pick_first_dashboard_snapshot(
            ROWS, consultation_id=None, current_consultation_id=None
        )
        self.assertEqual(snap["consultation_id"], "c3")  # 가장 최신

    def test_specific_consultation_returns_that_one(self):
        snap = _pick_first_dashboard_snapshot(
            ROWS, consultation_id="c1", current_consultation_id=None
        )
        self.assertEqual(snap["consultation_id"], "c1")  # 최신이 아니라 선택한 회차

    def test_specific_consultation_without_snapshot_returns_none(self):
        rows = [_row("c3"), _row("c2", has_snapshot=False), _row("c1")]
        snap = _pick_first_dashboard_snapshot(
            rows, consultation_id="c2", current_consultation_id=None
        )
        self.assertIsNone(snap)  # 그 회차에 저장된 분석이 없으면 폴백 금지(None)

    def test_current_consultation_excluded_for_latest(self):
        snap = _pick_first_dashboard_snapshot(
            ROWS, consultation_id=None, current_consultation_id="c3"
        )
        self.assertEqual(snap["consultation_id"], "c2")  # 현재 회차 c3 제외 → 직전

    def test_consultation_id_takes_precedence_over_current_exclusion(self):
        # 특정 회차 조회는 current 제외 규칙과 무관하게 그 회차를 본다.
        snap = _pick_first_dashboard_snapshot(
            ROWS, consultation_id="c3", current_consultation_id="c3"
        )
        self.assertEqual(snap["consultation_id"], "c3")

    def test_empty_rows_returns_none(self):
        self.assertIsNone(
            _pick_first_dashboard_snapshot(
                [], consultation_id=None, current_consultation_id=None
            )
        )
        self.assertIsNone(
            _pick_first_dashboard_snapshot(
                None, consultation_id=None, current_consultation_id=None
            )
        )


if __name__ == "__main__":
    unittest.main()
