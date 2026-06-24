"""위기 시나리오 프리셋(2008/2022 러우) 단위 테스트.

실행: cd backend && python -m pytest tests/test_stress_scenarios.py
      또는 cd backend && python tests/test_stress_scenarios.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.portfolio.portfolio_logic import (  # noqa: E402
    ASSET_TICKERS,
    CRISIS_SCENARIO_SHOCKS,
    resolve_scenario_shocks,
)


def test_two_scenarios_exist():
    assert set(CRISIS_SCENARIO_SHOCKS) == {"crisis_2008", "crisis_ru_war"}
    print("✅ 위기 시나리오 2종 (2008·러우)")


def test_all_asset_keys_covered():
    for sc, vec in CRISIS_SCENARIO_SHOCKS.items():
        missing = set(ASSET_TICKERS) - set(vec)
        assert not missing, f"{sc} 누락 자산: {missing}"
    print("✅ 모든 자산군 12종 충격값 정의됨")


def test_2008_is_deflationary():
    # 디플레형: 주식·리츠·원자재↓, 채권·금·달러↑
    s = CRISIS_SCENARIO_SHOCKS["crisis_2008"]
    assert s["domestic_equity"] < 0 and s["overseas_blue_chip"] < 0
    assert s["reit"] < 0 and s["commodity"] < 0
    assert s["general_bond"] > 0 and s["gold"] > 0 and s["dollar"] > 0
    print("✅ 2008 = 디플레형(주식·리츠·원자재↓, 채권·금·달러↑)")


def test_2022_is_inflationary():
    # 인플레/원자재 쇼크형: 원자재↑, 채권↓(금리↑), 성장주 직격
    s = CRISIS_SCENARIO_SHOCKS["crisis_ru_war"]
    assert s["commodity"] > 0
    assert s["general_bond"] < 0 and s["separate_tax_bond"] < 0
    assert s["overseas_growth"] < 0
    print("✅ 2022 = 인플레형(원자재↑, 채권↓, 성장주 직격)")


def test_2008_vs_2022_bond_direction_opposite():
    # 핵심 대비: 채권 방향이 반대 (2008 강세 vs 2022 약세)
    assert CRISIS_SCENARIO_SHOCKS["crisis_2008"]["general_bond"] > 0
    assert CRISIS_SCENARIO_SHOCKS["crisis_ru_war"]["general_bond"] < 0
    print("✅ 채권 방향 반대(2008 +, 2022 −) — 두 위기 성격 구분")


def test_resolve_filters_to_held_assets():
    out = resolve_scenario_shocks("crisis_2008", ["domestic_equity", "gold"])
    assert set(out) == {"domestic_equity", "gold"}
    assert out["domestic_equity"] == -0.40
    print("✅ 보유 자산만 충격 반환")


def test_resolve_drops_zero_shocks():
    out = resolve_scenario_shocks("crisis_2008", ["cash", "domestic_equity"])
    assert "cash" not in out  # cash 충격 0 → 제외
    print("✅ 충격 0(현금) 제외")


def test_unknown_scenario_raises():
    try:
        resolve_scenario_shocks("nope", ["domestic_equity"])
        assert False, "알 수 없는 시나리오인데 예외 안 남"
    except ValueError:
        print("✅ 미지원 시나리오 → ValueError")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\n전체 통과 ✅")
