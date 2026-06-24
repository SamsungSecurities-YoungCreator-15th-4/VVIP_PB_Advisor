"""_fetch_quote_sync 시세 추출 검증 — fast_info 실시간가 우선, history 폴백.

Yahoo 접속 없이 가짜 티커로 로직만 검증한다.
실행: cd backend && python tests/test_quote_live_price.py
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.market import yfinance_client as yc  # noqa: E402


class _FakeTicker:
    def __init__(self, last_price, closes, prev_close=None):
        self._last = last_price
        self._closes = closes
        self._prev = prev_close

    @property
    def fast_info(self):
        info = {}
        if self._last is not None:
            info["last_price"] = self._last
        if self._prev is not None:
            info["previous_close"] = self._prev
        return info

    def history(self, period="5d", interval="1d"):
        return pd.DataFrame({"Close": self._closes})


def _run(last, closes, prev_close=None):
    yc.yf.Ticker = lambda symbol: _FakeTicker(last, closes, prev_close)  # type: ignore
    return yc._fetch_quote_sync("^KS11")


def test_prev_close_from_fast_info_is_preferred():
    # fast_info에 previous_close가 있으면 그걸 전일로 사용(가장 정확)
    q = _run(8203.84, [9000.0, 9052.42, 9114.55], prev_close=9114.55)
    assert abs(q.price - 8203.84) < 1e-6
    assert abs(q.change - (-910.71)) < 0.01
    assert abs(q.changePct - (-9.99)) < 0.05
    print(f"✅ previous_close 우선 사용: {q.changePct:.2f}%")


def test_after_hours_diff_does_not_zero_out_change():
    # Gemini 리뷰 케이스: history가 최신(8203.84)인데 실시간가가 장후 미세차(8204.10).
    # previous_close(9114.55)를 쓰므로 변화율이 0%로 뭉개지지 않아야 한다.
    q = _run(8204.10, [9114.55, 8203.84], prev_close=9114.55)
    assert abs(q.price - 8204.10) < 1e-6
    assert q.changePct < -9.0          # 전일 대비 약 -10%, 0% 아님
    print(f"✅ 장후 미세차에도 전일 기준 유지: {q.changePct:.2f}% (0% 뭉갬 방지)")


def test_history_lagging_fallback_when_no_prev_close():
    # previous_close 없음 → history 지연 폴백: 마지막 종가(9114.55)를 전일로
    q = _run(8203.84, [9000.0, 9052.42, 9114.55])
    assert abs(q.price - 8203.84) < 1e-6
    assert abs(q.change - (-910.71)) < 0.01
    assert abs(q.changePct - (-9.99)) < 0.05
    print(f"✅ prev_close 폴백(일봉 지연): {q.changePct:.2f}%")


def test_history_caught_up_fallback_when_no_prev_close():
    # previous_close 없음 + history 최신(마지막=현재가) → 직전 종가를 전일로
    q = _run(8203.84, [9114.55, 8203.84])
    assert abs(q.price - 8203.84) < 1e-6
    assert abs(q.change - (-910.71)) < 0.01           # prev = iloc[-2] = 9114.55
    print(f"✅ prev_close 폴백(history 최신): {q.changePct:.2f}%")


def test_fast_info_unavailable_falls_back_to_history():
    # 실시간가·전일종가 모두 없으면 history 마지막 종가로 폴백(기존 동작)
    q = _run(None, [9052.0, 9114.55])
    assert abs(q.price - 9114.55) < 1e-6
    assert abs(q.change - (9114.55 - 9052.0)) < 0.01
    print(f"✅ fast_info 실패 → history 폴백: {q.price}")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\n전체 통과 ✅")
