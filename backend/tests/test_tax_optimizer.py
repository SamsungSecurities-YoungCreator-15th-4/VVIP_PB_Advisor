"""절세 최적화 계산(tax_optimizer) 단위 테스트.

원칙(AGENTS.md): 세법 수식의 불변식·경계조건을 검증한다. 더미값이 아니라 출처 있는
상수(ISA 한도·분리과세율·양도세율 등)로부터 유도되는 관계를 확인한다.
"""
import pytest

from app.market.financial_calc import DEFAULT_WITHHOLDING_TAX_RATE
from app.market.schemas import AssetAllocation
from app.market.tax_optimizer import (
    ISA_ANNUAL_LIMIT_WON,
    OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE,
    PENSION_TAX_CREDIT_LIMIT_WON,
    calc_account_allocation,
    calc_tax_advice,
)


def _alloc(asset_class: str, weight: float) -> AssetAllocation:
    return AssetAllocation(
        ticker="X", name="X", nameKr="X", weight=weight, assetClass=asset_class, color="#000"
    )


# 종합과세 구간에 들어갈 만큼 이자·배당성 자산이 큰 포트폴리오(총 50억 기준)
PORTFOLIO = [
    _alloc("overseas_dividend", 0.25),  # 고배당
    _alloc("reit", 0.10),
    _alloc("general_bond", 0.20),  # 일반채
    _alloc("low_coupon_bond", 0.10),
    _alloc("overseas_growth", 0.20),  # 해외 성장주(양도차익)
    _alloc("domestic_equity", 0.15),
]


def _cards(**kwargs):
    defaults = dict(
        portfolio=PORTFOLIO,
        gross_return=0.06,
        total_assets=50.0,
        isa_used_manwon=0.0,
        realized_loss_manwon=0.0,
        other_financial_income=0.0,
        marginal_income_tax_rate=0.385,
    )
    defaults.update(kwargs)
    advice = calc_tax_advice(**defaults)
    return {c["key"]: c for c in advice}


def test_account_allocation_uses_statutory_limits():
    slots = {s["key"]: s for s in calc_account_allocation(2000, 600)}
    assert slots["isa"]["limitManwon"] == ISA_ANNUAL_LIMIT_WON // 10_000  # 2,000만
    assert slots["isa"]["usedManwon"] == 2000
    assert slots["pension"]["limitManwon"] == PENSION_TAX_CREDIT_LIMIT_WON // 10_000  # 900만
    assert slots["general"]["usedManwon"] is None and slots["general"]["limitManwon"] is None


def test_isa_proposal_hidden_when_limit_exhausted():
    # ISA 연 한도(2,000만)를 모두 소진 → 이전 가능액 0 → 제안 비노출
    cards = _cards(isa_used_manwon=2000)
    assert cards["isa"]["transferableManwon"] == 0
    assert cards["isa"]["applicable"] is False
    assert cards["isa"]["savingManwon"] == 0


def test_isa_proposal_active_with_headroom():
    cards = _cards(isa_used_manwon=0)
    assert cards["isa"]["transferableManwon"] > 0
    assert cards["isa"]["applicable"] is True
    assert cards["isa"]["savingManwon"] > 0


def test_isa_transferable_capped_by_annual_limit():
    # 이자·배당 자산 평가액이 한도보다 크므로 이전액은 연 한도(2,000만)로 캡된다.
    cards = _cards(isa_used_manwon=0)
    assert cards["isa"]["transferableManwon"] <= ISA_ANNUAL_LIMIT_WON // 10_000


def test_separate_bond_only_in_comprehensive_band():
    # 종합과세 구간 미진입(작은 자산 + 다른 소득 0) → 분리과세채 절감 없음
    small = _cards(total_assets=1.0)
    assert small["separate_bond"]["applicable"] is False
    # 다른 금융소득을 더해 종합과세 구간 진입 → 절감 발생
    big = _cards(other_financial_income=2.0)  # +2억 금융소득
    assert big["separate_bond"]["applicable"] is True
    assert big["separate_bond"]["savingManwon"] > 0


def test_low_tax_dividend_scales_with_marginal_rate():
    base = _cards(other_financial_income=2.0, marginal_income_tax_rate=0.385)
    higher = _cards(other_financial_income=2.0, marginal_income_tax_rate=0.495)
    # 한계세율이 높을수록 종합과세 추가과세 회피 효과(절감)가 커진다
    assert higher["low_tax_dividend"]["savingManwon"] > base["low_tax_dividend"]["savingManwon"]


def test_tax_loss_harvesting_offsets_overseas_gain():
    no_loss = _cards(realized_loss_manwon=0)
    assert no_loss["tax_loss"]["applicable"] is False
    with_loss = _cards(realized_loss_manwon=1800)
    assert with_loss["tax_loss"]["applicable"] is True
    # 절감액 ≈ min(손실, 해외양도차익) × 22% — 손실 한도 내에서는 22%를 넘지 않는다
    assert 0 < with_loss["tax_loss"]["savingManwon"] <= round(1800 * OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE)


def test_all_six_cards_present():
    cards = _cards()
    assert set(cards) == {
        "isa",
        "pension_credit",
        "separate_bond",
        "low_tax_dividend",
        "overseas_exemption",
        "tax_loss",
    }


def test_zero_return_yields_no_income_savings():
    cards = _cards(gross_return=0.0)
    for key in ("isa", "separate_bond", "low_tax_dividend"):
        assert cards[key]["savingManwon"] == 0


def test_pension_credit_blocked_when_horizon_below_receive_age():
    # 33세, 투자기간 3년 → 수령까지 22년 > 3년 → 부적합(사유 표시)
    young = _cards(age=33, horizon_years=3, pension_used_manwon=0)
    assert young["pension_credit"]["applicable"] is False
    assert young["pension_credit"]["ineligibleReason"] is not None
    assert young["pension_credit"]["savingManwon"] == 0


def test_pension_credit_active_for_older_customer():
    # 54세, 투자기간 10년 → 수령요건 충족 → 잔여 한도(900만)에 세액공제율 적용
    older = _cards(age=54, horizon_years=10, pension_used_manwon=0)
    assert older["pension_credit"]["applicable"] is True
    assert older["pension_credit"]["savingManwon"] > 0


def test_pension_credit_hidden_when_limit_exhausted():
    # 한도(900만) 소진 → 부적합이지만 사유 없음(비노출 대상)
    full = _cards(age=60, horizon_years=10, pension_used_manwon=900)
    assert full["pension_credit"]["applicable"] is False
    assert full["pension_credit"]["ineligibleReason"] is None
    assert full["pension_credit"]["savingManwon"] == 0


def test_isa_new_open_blocked_when_comprehensive():
    # 미개설 + 종합과세 구간(추정) → 신규 개설 불가(사유 표시)
    blocked = _cards(isa_opened=False, other_financial_income=2.0)
    assert blocked["isa"]["applicable"] is False
    assert blocked["isa"]["ineligibleReason"] is not None


def test_isa_new_open_allowed_when_not_comprehensive():
    # 미개설 + 종합과세 미진입(작은 자산) → 신규 개설 가능
    ok = _cards(isa_opened=False, total_assets=2.0, other_financial_income=0.0)
    assert ok["isa"]["ineligibleReason"] is None


def test_overseas_exemption_capped_at_deduction():
    cards = _cards()
    # 250만 공제 한도 × 22% = 55만이 절감 상한
    assert 0 < cards["overseas_exemption"]["savingManwon"] <= round(250 * 0.22)


def test_near_term_need_caps_isa_transfer():
    # 단기필요자금이 전체 자산을 덮으면 묶을 여유자금이 없어 이전 불가
    cards = _cards(isa_used_manwon=0, near_term_need_manwon=50.0 * 10000)
    assert cards["isa"]["transferableManwon"] == 0
