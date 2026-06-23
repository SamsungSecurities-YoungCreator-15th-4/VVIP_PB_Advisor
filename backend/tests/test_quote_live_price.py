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
    def __init__(self, last_price, closes):
        self._last = last_price
        self._closes = closes

    @property
    def fast_info(self):
        return {"last_price": self._last} if self._last is not None else {}

    def history(self, period="5d", interval="1d"):
        return pd.DataFrame({"Close": self._closes})


def _run(last, closes):
    yc.yf.Ticker = lambda symbol: _FakeTicker(last, closes)  # type: ignore
    return yc._fetch_quote_sync("^KS11")


def test_history_lagging_uses_live_price():
    # 스크린샷 케이스: 실시간 8203.84, history 일봉은 전일(9114.55)에 머묾
    q = _run(8203.84, [9000.0, 9052.42, 9114.55])
    assert abs(q.price - 8203.84) < 1e-6              # 현재가 = 실시간
    assert abs(q.change - (-910.71)) < 0.01           # 전일(9114.55) 대비
    assert abs(q.changePct - (-9.99)) < 0.05          # -9.99%
    print(f"✅ 일봉 지연 시 실시간가 사용: {q.price} ({q.changePct:.2f}%)")


def test_history_caught_up_uses_prev_close():
    # history가 당일까지 반영됨(마지막=현재가) → 전일은 그 직전 종가
    q = _run(8203.84, [9114.55, 8203.84])
    assert abs(q.price - 8203.84) < 1e-6
    assert abs(q.change - (-910.71)) < 0.01           # prev = iloc[-2] = 9114.55
    print(f"✅ history 최신 반영 시 직전 종가로 변화 계산: {q.changePct:.2f}%")


def test_fast_info_unavailable_falls_back_to_history():
    # 실시간가 없으면 history 마지막 종가로 폴백(기존 동작)
    q = _run(None, [9052.0, 9114.55])
    assert abs(q.price - 9114.55) < 1e-6
    assert abs(q.change - (9114.55 - 9052.0)) < 0.01
    print(f"✅ fast_info 실패 → history 폴백: {q.price}")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\n전체 통과 ✅")
