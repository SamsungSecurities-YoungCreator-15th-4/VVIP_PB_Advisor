"""market API 수동 검증 스크립트 — 서버(uvicorn) 기동 후 실행.

사용법: python3 scripts/verify_market_api.py
표준 라이브러리만 사용하므로 venv 없이 아무 파이썬으로 실행 가능.
"""
import json
import sys
import urllib.request

BASE = "http://localhost:8000"

HARDCODED = {"kospi": 8160.59, "sp500": 7383.74, "treasuryYield": 4.536, "krwUsd": 1545.29}


def get(path: str):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=30) as res:
        return json.loads(res.read())


def fmt(v, nd=4):
    return "N/A" if v is None else round(v, nd)


def main() -> int:
    failures = []

    # ① 거시지표
    print("=" * 60)
    print("① /api/macro-indicators — 6가지 지표")
    print("=" * 60)
    macro = get("/api/macro-indicators")
    for key in ["baseRate", "treasuryYield", "krwUsd", "cpi", "kospi", "sp500"]:
        item = macro[key]
        if item.get("isStatic"):
            status = "정적(발표 기준) — 정상"
        elif item.get("isFallback"):
            status = "!! 지연 시세 (실시간 조회 실패, 마지막 성공값)"
        elif key in HARDCODED and item["price"] == HARDCODED[key]:
            status = "!! 하드코딩 fallback 값과 동일 — 라이브 조회 실패 의심"
            failures.append(f"{key}: 하드코딩 값")
        else:
            status = "라이브 OK"
        print(f"  {key:14s} {item['price']:>10.2f}  {status}")

    # ② 포트폴리오 지표
    print()
    print("=" * 60)
    print("② /api/portfolios — 채권 3분류 티커 + 전체 지표")
    print("=" * 60)
    for p in get("/api/portfolios"):
        m = p["metrics"]
        n_bt = len(m["backtestData"])
        print(
            f"  {p['id']:10s} 수익률 {fmt(m['expectedReturn'])} | 변동성 {fmt(m['volatility'])}"
            f" | 샤프 {fmt(m['sharpeRatio'], 2)} | 소르티노 {fmt(m['sortinoRatio'], 2)}"
            f" | MDD {fmt(m['maxDrawdown'])} | 백테스트 {n_bt}점"
        )
        if m["sortinoRatio"] is None or m["maxDrawdown"] is None or n_bt == 0:
            failures.append(f"{p['id']}: 실측 시계열 없음 (티커 조회 실패 의심)")

    # ③-1 충격 0 항등성
    print()
    print("=" * 60)
    print("③-1 /api/stressed-portfolios (충격 0) — base == stressed 항등성")
    print("=" * 60)
    keys = ["expectedReturn", "volatility", "sharpeRatio", "sortinoRatio", "maxDrawdown"]
    for p in get("/api/stressed-portfolios?base_rate_delta_bp=0&krw_usd_delta=0"):
        same = all(
            abs((p["base"][k] or 0) - (p["stressed"][k] or 0)) < 1e-9 for k in keys
        )
        print(f"  {p['id']:10s} {'항등성 OK' if same else '불일치 — 버그!'}")
        if not same:
            failures.append(f"{p['id']}: 충격 0 항등성 불일치")

    # ③-2 금리 +100bp 방향성
    print()
    print("=" * 60)
    print("③-2 /api/stressed-portfolios (금리 +100bp) — 5개 지표 전부 변화")
    print("=" * 60)
    for p in get("/api/stressed-portfolios?base_rate_delta_bp=100"):
        b, s = p["base"], p["stressed"]
        print(
            f"  {p['id']:10s} 수익률 {fmt(b['expectedReturn'])} → {fmt(s['expectedReturn'])}"
            f" | 변동성 {fmt(b['volatility'])} → {fmt(s['volatility'])}"
            f" | 샤프 {fmt(b['sharpeRatio'], 2)} → {fmt(s['sharpeRatio'], 2)}"
            f" | 소르티노 {fmt(b['sortinoRatio'], 2)} → {fmt(s['sortinoRatio'], 2)}"
            f" | MDD {fmt(b['maxDrawdown'])} → {fmt(s['maxDrawdown'])}"
        )
        checks = [
            ("수익률 하락", s["expectedReturn"] < b["expectedReturn"]),
            ("변동성 상승", s["volatility"] > b["volatility"]),
        ]
        if b["maxDrawdown"] is not None and s["maxDrawdown"] is not None:
            checks.append(("MDD 악화", s["maxDrawdown"] >= b["maxDrawdown"]))
        for name, ok in checks:
            if not ok:
                failures.append(f"{p['id']}: {name} 방향성 불일치")

    # ④ 과거 위기 P&L
    print()
    print("=" * 60)
    print("④ /api/historical-crises — 과거 위기 재현 예상 손실률(P&L)")
    print("=" * 60)
    for c in get("/api/historical-crises"):
        line = " | ".join(
            f"{pid} {r*100:+.1f}%" for pid, r in sorted(c["results"].items())
        )
        print(f"  {c['nameKr']} ({c['period']})")
        print(f"    {line}")
        if not c["results"]:
            failures.append(f"{c['id']}: results 비어 있음")
    # 2008·2020은 전 포트폴리오 손실이어야 정상 (방향성 sanity check)
    for c in get("/api/historical-crises"):
        if c["id"] in ("gfc_2008", "covid_2020"):
            for pid, r in c["results"].items():
                if r >= 0:
                    failures.append(f"{c['id']}/{pid}: 위기인데 P&L 양수 — 가중치/수익률 확인 필요")

    # 결과 요약
    print()
    print("=" * 60)
    if failures:
        print(f"검증 실패 {len(failures)}건:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("전체 검증 통과 ✓")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except urllib.error.URLError:
        print("서버에 연결할 수 없습니다 — uvicorn이 켜져 있는지 확인하세요.")
        sys.exit(1)
