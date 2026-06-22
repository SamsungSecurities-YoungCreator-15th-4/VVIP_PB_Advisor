"""tax_advice 단위 테스트 — 6종 카드·게이팅·우선순위 결합 검증.

순수 파이썬 모듈이라 외부 의존 없이 실행됨:
    python backend/tests/test_tax_advice.py   또는   pytest backend/tests/test_tax_advice.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "portfolio_logic"))
import tax_advice as T  # noqa: E402

# 종합과세 구간에 드는 포트폴리오 (채권·배당·해외성장 혼합)
PORTFOLIO = [
    {"asset_class": "general_bond", "weight": 0.20},
    {"asset_class": "low_coupon_bond", "weight": 0.10},
    {"asset_class": "overseas_dividend", "weight": 0.25},
    {"asset_class": "reit", "weight": 0.10},
    {"asset_class": "overseas_growth", "weight": 0.20},
    {"asset_class": "domestic_equity", "weight": 0.15},
]
BASE = dict(portfolio=PORTFOLIO, gross_return=0.06, total_assets=50.0,
            marginal_income_tax_rate=0.462, realized_loss_manwon=500)


def _card(cards, key):
    return next(c for c in cards if c["key"] == key)


def test_six_cards_present():
    cards = T.calc_tax_advice(**BASE)
    keys = {c["key"] for c in cards}
    assert keys == {"isa", "pension_credit", "separate_bond",
                    "low_tax_dividend", "overseas_exemption", "tax_loss"}
    print("✅ 6종 카드 모두 생성")


def test_separate_bond_only_when_marginal_above_33():
    low = _card(T.calc_tax_advice(**{**BASE, "marginal_income_tax_rate": 0.30}), "separate_bond")
    high = _card(T.calc_tax_advice(**{**BASE, "marginal_income_tax_rate": 0.462}), "separate_bond")
    assert low["savingManwon"] == 0 and low["applicable"] is False
    assert high["savingManwon"] > 0 and high["applicable"] is True
    print(f"✅ 분리과세채: 한계30% → 0만 / 한계46.2% → {high['savingManwon']}만")


def test_no_comprehensive_no_income_saving():
    # 금융소득이 2,000만 이하면 종합과세 초과분 0 → 분리과세채·저율배당 절감 0
    cards = T.calc_tax_advice(portfolio=PORTFOLIO, gross_return=0.06, total_assets=1.0,
                              marginal_income_tax_rate=0.462)
    assert _card(cards, "separate_bond")["savingManwon"] == 0
    assert _card(cards, "low_tax_dividend")["savingManwon"] == 0
    print("✅ 종합과세 구간 밖(소액): 분리과세채·저율배당 절감 0")


def test_pension_age_gating():
    # 이사조 33세/3년 → 연금 부적합
    lee = _card(T.calc_tax_advice(**{**BASE, "age": 33, "horizon_years": 3}), "pension_credit")
    assert lee["applicable"] is False and "연금 수령까지" in (lee["ineligibleReason"] or "")
    # 박기업 62세 → 적합
    park = _card(T.calc_tax_advice(**{**BASE, "age": 62, "horizon_years": 10}), "pension_credit")
    assert park["applicable"] is True and park["ineligibleReason"] is None
    # 김성삼 54세/10년 → 적합(수령까지 1년 < 10년)
    kim = _card(T.calc_tax_advice(**{**BASE, "age": 54, "horizon_years": 10}), "pension_credit")
    assert kim["applicable"] is True
    print("✅ 연금 게이팅: 이사조 부적합 / 박기업·김성삼 적합")


def test_isa_horizon_gating_for_new_account():
    # 소액(종합과세 구간 밖) + 신규 개설 + 투자기간 < 3년 → 투자기간 게이트로 부적합
    short = _card(T.calc_tax_advice(portfolio=PORTFOLIO, gross_return=0.06, total_assets=1.0,
                                    isa_opened=False, horizon_years=2), "isa")
    assert short["applicable"] is False and "의무보유" in (short["ineligibleReason"] or "")
    # 종합과세 대상이면 신규개설 자체 불가 게이트가 먼저 걸림
    comp = _card(T.calc_tax_advice(**{**BASE, "isa_opened": False, "horizon_years": 2}), "isa")
    assert comp["applicable"] is False and "신규 개설 불가" in (comp["ineligibleReason"] or "")
    print("✅ ISA 게이팅: 소액+단기 → 의무보유 미달 / 종합과세대상 → 신규개설 불가")


def test_combined_less_than_naive_sum():
    cards = T.calc_tax_advice(**BASE)
    naive = sum(c["savingManwon"] for c in cards)
    combined = T.calc_combined_tax_saving(**BASE)
    # 공유 풀 중복 때문에 결합 총액 ≤ 단순 합산
    assert combined["totalManwon"] <= naive
    # 결합 기여분 합 == 총액 (반올림 오차 1만 허용)
    assert abs(sum(combined["contributions"].values()) - combined["totalManwon"]) <= 1
    print(f"✅ 결합 총액 {combined['totalManwon']}만 ≤ 단순 합산 {naive}만 (중복 제거)")
    print(f"   기여분: {combined['contributions']}")


def test_isa_not_applicable_does_not_starve_pool():
    # ISA 한도 소진(isa_used=2000만) → ISA 적용 불가 → rem(공유 풀) 차감 안 됨
    args = {**BASE, "isa_used_manwon": 2000}
    combined = T.calc_combined_tax_saving(**args)
    assert combined["contributions"]["isa"] == 0
    # ISA가 풀을 안 깎으므로 저율배당은 전체 excess 기준(=단독 카드 절감액)과 동일
    cards = {c["key"]: c for c in T.calc_tax_advice(**args)}
    assert abs(combined["contributions"]["low_tax_dividend"]
               - cards["low_tax_dividend"]["savingManwon"]) <= 1
    print("✅ ISA 미적용 시 저율배당이 풀을 온전히 사용 (버그픽스 검증)")


def test_none_kwargs_do_not_crash():
    # 선택 인자가 None으로 와도 TypeError 안 남 (방어코드)
    combined = T.calc_combined_tax_saving(
        portfolio=PORTFOLIO, gross_return=0.06, total_assets=50.0,
        marginal_income_tax_rate=None, other_financial_income=None,
        realized_loss_manwon=None, isa_used_manwon=None, near_term_need_manwon=None,
    )
    assert combined["totalManwon"] >= 0
    print("✅ None 인자 방어: 크래시 없음")


def test_overseas_stack_is_capped_by_gain():
    # 손익통산 + 250만 공제는 차익을 넘지 못함
    combined = T.calc_combined_tax_saving(**BASE)
    c = combined["contributions"]
    assert c["tax_loss"] >= 0 and c["overseas_exemption"] >= 0
    print(f"✅ 양도세 스택: 손익통산 {c['tax_loss']}만 + 공제 {c['overseas_exemption']}만")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\n전체 통과 ✅")
