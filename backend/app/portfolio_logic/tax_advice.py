"""절세 제안 6종 카드 + 나이·투자기간 게이팅 + 우선순위 결합 총액.

market.tax_optimizer(검증 완료)를 계산엔진(portfolio_logic) 쪽으로 이식한 모듈.
순수 파이썬(외부 의존 없음)이라 단독 테스트가 쉽고, portfolio_logic이 import해 쓴다.

세법 상수 출처:
  소득세법 §14③(금융소득종합과세 2,000만), §129(원천징수 15.4%·장기채 분리과세 33%),
  §59의3(연금계좌 세액공제 한도 900만·고소득 13.2%), §118의2(해외주식 양도 250만 공제·22%),
  조특법 §91의18(ISA 한도 2,000만·비과세 200만·초과 9.9%·의무보유 3년)
※ 법정 상수라 값이 고정. portfolio_logic의 동명 상수와 일치해야 한다.

검증: docs/절세-시뮬레이터-검증정리.md
      (verify_tax_strategies / verify_tax_overlap / verify_persona_gating)
"""
from __future__ import annotations

from typing import Optional

# ── 세법 상수 ────────────────────────────────────────────────────────────────
WITHHOLDING_TAX_RATE = 0.154          # 이자·배당 원천징수(지방세 포함)
COMPREHENSIVE_TAX_THRESHOLD = 20_000_000  # 금융소득종합과세 기준 2,000만
DEFAULT_MARGINAL_INCOME_TAX_RATE = 0.385  # 한계세율 기본 가정(호출 시 덮어씀)
ISA_ANNUAL_LIMIT_WON = 20_000_000     # ISA 연 납입한도
ISA_TAX_FREE_LIMIT_WON = 2_000_000    # ISA 일반형 비과세 한도 200만
ISA_EXCESS_TAX_RATE = 0.099           # ISA 비과세 초과분 분리과세 9.9%
ISA_MANDATORY_HOLDING_YEARS = 3       # ISA 의무보유기간
PENSION_TAX_CREDIT_LIMIT_WON = 9_000_000  # 연금계좌 세액공제 한도(연)
PENSION_TAX_CREDIT_RATE = 0.132       # 세액공제율(고소득 13.2% 가정)
PENSION_RECEIVE_AGE = 55              # 연금 수령 가능 연령
LONG_BOND_SEPARATE_TAX_RATE = 0.33    # 장기채권 분리과세(30%+지방세)
OVERSEAS_STOCK_GAIN_DEDUCTION = 2_500_000  # 해외주식 양도 기본공제 250만
OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE = 0.22  # 해외주식 양도세율 22%

# 자산군 분류 (portfolio_logic 키와 일치)
ASSET_INCOME_YIELD_ASSUMPTIONS = {
    "cash": 0.025,
    "general_bond": 0.030,
    "low_coupon_bond": 0.015,
    "separate_tax_bond": 0.025,
    "overseas_dividend": 0.035,
    "reit": 0.040,
}
INCOME_TAXABLE_ASSETS = set(ASSET_INCOME_YIELD_ASSUMPTIONS)
OVERSEAS_STOCK_CAPITAL_GAIN_ASSETS = {
    "overseas_blue_chip", "overseas_growth", "overseas_dividend", "reit",
}
_BOND_INCOME_ASSETS = {"general_bond", "low_coupon_bond"}   # 분리과세 전환 대상 채권
_DIVIDEND_INCOME_ASSETS = {"overseas_dividend", "reit"}     # 고배당성 자산


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────
def _won_to_manwon(won: float) -> int:
    return int(round(won / 10_000))


def _income_won_by_asset(
    portfolio: list[dict], gross_return: float, total_won: float
) -> dict[str, float]:
    """자산군별 연간 이자·배당성 금융소득(원) = weight × 총자산 × min(수익률, income yield)."""
    out: dict[str, float] = {}
    if gross_return <= 0 or total_won <= 0:
        return out
    for a in portfolio:
        cls = a["asset_class"]
        if cls in INCOME_TAXABLE_ASSETS:
            y = ASSET_INCOME_YIELD_ASSUMPTIONS[cls]
            out[cls] = out.get(cls, 0.0) + a["weight"] * total_won * min(gross_return, max(y, 0.0))
    return out


def _overseas_capital_gain_won(
    portfolio: list[dict], gross_return: float, total_won: float
) -> float:
    """해외상장 주식·ETF 연간 가격차익(원) = 총이익 − 이자·배당분."""
    if gross_return <= 0 or total_won <= 0:
        return 0.0
    gain = 0.0
    for a in portfolio:
        cls = a["asset_class"]
        if cls in OVERSEAS_STOCK_CAPITAL_GAIN_ASSETS:
            total_profit = a["weight"] * total_won * gross_return
            income_part = 0.0
            if cls in INCOME_TAXABLE_ASSETS:
                y = ASSET_INCOME_YIELD_ASSUMPTIONS[cls]
                income_part = a["weight"] * total_won * min(gross_return, max(y, 0.0))
            gain += max(total_profit - income_part, 0.0)
    return gain


# ── 6종 카드 (단독 절감액 + 게이팅) ──────────────────────────────────────────
def calc_tax_advice(
    portfolio: list[dict],            # [{"asset_class": str, "weight": float}, ...]
    gross_return: float,              # 포트폴리오 연 기대수익률(소수)
    total_assets: float,              # 억 원
    *,
    isa_used_manwon: float = 0.0,
    pension_used_manwon: float = 0.0,
    realized_loss_manwon: float = 0.0,
    other_financial_income: float = 0.0,   # 억 원
    marginal_income_tax_rate: float = DEFAULT_MARGINAL_INCOME_TAX_RATE,
    age: Optional[int] = None,
    horizon_years: Optional[float] = None,
    near_term_need_manwon: float = 0.0,
    near_term_need_years: Optional[float] = None,
    isa_opened: bool = True,
) -> list[dict]:
    """절세 6종의 '단독' 절감액(만원) + 적합성 게이팅.

    각 항목: {key, savingManwon, applicable, transferableManwon, ineligibleReason}.
    주의: 각 카드는 '단독 적용 시' 절감액이라 단순 합산하면 과대평가됨
          (공유 풀 중복). 합산 표시는 calc_combined_tax_saving 사용.
    """
    total_won = max(total_assets, 0.0) * 1e8
    other_income_won = max(other_financial_income, 0.0) * 1e8
    income_by_asset = _income_won_by_asset(portfolio, gross_return, total_won)

    total_financial_income_won = sum(income_by_asset.values()) + other_income_won
    excess_won = max(total_financial_income_won - COMPREHENSIVE_TAX_THRESHOLD, 0.0)
    extra_rate = max(marginal_income_tax_rate - WITHHOLDING_TAX_RATE, 0.0)
    is_comprehensive = excess_won > 0
    investable_won = max(total_won - max(near_term_need_manwon, 0.0) * 10_000, 0.0)

    cards: list[dict] = []

    # ① ISA 계좌 활용
    isa_headroom_won = max(ISA_ANNUAL_LIMIT_WON - isa_used_manwon * 10_000, 0.0)
    income_asset_value_won = sum(
        a["weight"] * total_won for a in portfolio if a["asset_class"] in INCOME_TAXABLE_ASSETS
    )
    transferable_won = min(isa_headroom_won, income_asset_value_won, investable_won)
    isa_saving_won, isa_applicable, isa_reason = 0.0, False, None
    if not isa_opened and is_comprehensive:
        isa_reason = "직전 금융소득종합과세 대상(추정) → ISA 신규 개설 불가"
    elif (not isa_opened and horizon_years is not None
          and horizon_years < ISA_MANDATORY_HOLDING_YEARS):
        isa_reason = (
            f"투자기간 {horizon_years:g}년 < ISA 의무보유기간 "
            f"{ISA_MANDATORY_HOLDING_YEARS}년"
        )
    if isa_reason is None and transferable_won > 0 and income_asset_value_won > 0:
        avg_income_rate = sum(income_by_asset.values()) / income_asset_value_won
        moved_income_won = transferable_won * avg_income_rate
        comp_portion_won = min(moved_income_won, excess_won)
        tax_outside_won = moved_income_won * WITHHOLDING_TAX_RATE + comp_portion_won * extra_rate
        tax_isa_won = max(moved_income_won - ISA_TAX_FREE_LIMIT_WON, 0.0) * ISA_EXCESS_TAX_RATE
        isa_saving_won = max(tax_outside_won - tax_isa_won, 0.0)
        isa_applicable = isa_saving_won > 0
    cards.append({
        "key": "isa",
        "savingManwon": _won_to_manwon(isa_saving_won) if isa_applicable else 0,
        "applicable": isa_applicable,
        "transferableManwon": _won_to_manwon(transferable_won) if isa_applicable else 0,
        "ineligibleReason": isa_reason,
    })

    # ② 연금계좌 세액공제 (만 55세 수령요건 게이팅)
    pension_headroom_won = max(
        PENSION_TAX_CREDIT_LIMIT_WON - max(pension_used_manwon, 0.0) * 10_000, 0.0
    )
    pension_saving_won = min(pension_headroom_won, investable_won) * PENSION_TAX_CREDIT_RATE
    pension_reason = None
    if age is not None and age < PENSION_RECEIVE_AGE:
        years_to_receive = PENSION_RECEIVE_AGE - age
        if horizon_years is not None and horizon_years < years_to_receive:
            pension_reason = f"투자기간 {horizon_years:g}년 < 연금 수령까지 {years_to_receive:g}년"
    pension_applicable = pension_reason is None and pension_saving_won > 0
    cards.append({
        "key": "pension_credit",
        "savingManwon": _won_to_manwon(pension_saving_won) if pension_applicable else 0,
        "applicable": pension_applicable,
        "transferableManwon": (
            _won_to_manwon(min(pension_headroom_won, investable_won))
            if pension_applicable else 0
        ),
        "ineligibleReason": pension_reason,
    })

    # ③ 분리과세 채권 (한계세율 > 33%일 때만)
    bond_income_won = sum(income_by_asset.get(c, 0.0) for c in _BOND_INCOME_ASSETS)
    bond_eligible_won = min(bond_income_won, excess_won)
    bond_saving_won = bond_eligible_won * max(
        marginal_income_tax_rate - LONG_BOND_SEPARATE_TAX_RATE, 0.0
    )
    cards.append({
        "key": "separate_bond", "savingManwon": _won_to_manwon(bond_saving_won),
        "applicable": bond_saving_won > 0, "transferableManwon": 0, "ineligibleReason": None,
    })

    # ④ 저율과세 배당주 (종합과세 추가분 회피, 보수적)
    dividend_income_won = sum(income_by_asset.get(c, 0.0) for c in _DIVIDEND_INCOME_ASSETS)
    dividend_eligible_won = min(dividend_income_won, excess_won)
    dividend_saving_won = dividend_eligible_won * extra_rate
    cards.append({
        "key": "low_tax_dividend", "savingManwon": _won_to_manwon(dividend_saving_won),
        "applicable": dividend_saving_won > 0, "transferableManwon": 0, "ineligibleReason": None,
    })

    overseas_gain_won = _overseas_capital_gain_won(portfolio, gross_return, total_won)

    # ⑤ 해외주식 양도 250만 기본공제
    exemption_realizable_won = min(overseas_gain_won, OVERSEAS_STOCK_GAIN_DEDUCTION)
    exemption_saving_won = exemption_realizable_won * OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE
    cards.append({
        "key": "overseas_exemption", "savingManwon": _won_to_manwon(exemption_saving_won),
        "applicable": exemption_saving_won > 0, "transferableManwon": 0, "ineligibleReason": None,
    })

    # ⑥ Tax-loss Harvesting
    realized_loss_won = max(realized_loss_manwon, 0.0) * 10_000
    offset_won = min(realized_loss_won, overseas_gain_won)
    harvest_saving_won = offset_won * OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE
    cards.append({
        "key": "tax_loss", "savingManwon": _won_to_manwon(harvest_saving_won),
        "applicable": harvest_saving_won > 0, "transferableManwon": 0, "ineligibleReason": None,
    })

    return cards


# ── 우선순위 결합 총액 (중복 제거, 정직한 합계) ──────────────────────────────
def calc_combined_tax_saving(
    portfolio: list[dict],
    gross_return: float,
    total_assets: float,
    **kwargs,
) -> dict:
    """공유 풀(종합과세 초과분·해외 양도차익)을 한 번씩만 깎아 '결합 총 절감액'을 산출.

    우선순위 = 1원당 절감 효율 순:
      종합과세 초과분 풀: ISA → 저율배당 → 분리과세채 (효율 高→低)
      해외 양도차익     : 손익통산 + 250만 공제는 양도세 공식상 함께 차감(스택)
      연금              : 독립
    반환: {totalManwon, contributions: {key: manwon}, ineligible: {key: reason}}
    각 contributions 합 == totalManwon (단순 합산과 달리 과대평가 없음).
    """
    marginal = kwargs.get("marginal_income_tax_rate", DEFAULT_MARGINAL_INCOME_TAX_RATE)
    extra_rate = max(marginal - WITHHOLDING_TAX_RATE, 0.0)
    total_won = max(total_assets, 0.0) * 1e8
    other_income_won = max(kwargs.get("other_financial_income", 0.0), 0.0) * 1e8

    # 적합성(게이팅)은 단독 카드와 동일 판정 재사용
    cards = {c["key"]: c for c in calc_tax_advice(portfolio, gross_return, total_assets, **kwargs)}

    income_by_asset = _income_won_by_asset(portfolio, gross_return, total_won)
    excess = max(
        sum(income_by_asset.values()) + other_income_won - COMPREHENSIVE_TAX_THRESHOLD, 0.0
    )

    contrib: dict[str, float] = {}
    ineligible: dict[str, str] = {}

    # --- 종합과세 초과분 풀: ISA → 저율배당 → 분리과세채 ---
    rem = excess
    # 1) ISA: 단독 카드가 이미 적합/절감 판정 → 그 절감액을 인정하되, 소진한 excess 차감
    isa = cards["isa"]
    if isa["ineligibleReason"]:
        ineligible["isa"] = isa["ineligibleReason"]
        contrib["isa"] = 0.0
    else:
        contrib["isa"] = isa["savingManwon"] * 10_000
        # ISA가 종합과세 구간에서 소진한 income(=이전 income 중 excess 부분) 만큼 차감
        income_asset_value = sum(
            a["weight"] * total_won for a in portfolio if a["asset_class"] in INCOME_TAXABLE_ASSETS
        )
        if income_asset_value > 0:
            avg_rate = sum(income_by_asset.values()) / income_asset_value
            isa_headroom = max(
                ISA_ANNUAL_LIMIT_WON - kwargs.get("isa_used_manwon", 0.0) * 10_000, 0.0
            )
            investable = max(
                total_won - max(kwargs.get("near_term_need_manwon", 0.0), 0.0) * 10_000, 0.0
            )
            transferable = min(isa_headroom, income_asset_value, investable)
            rem = max(rem - min(transferable * avg_rate, rem), 0.0)

    # 2) 저율배당: 남은 excess 한도 내
    div_income = sum(income_by_asset.get(c, 0.0) for c in _DIVIDEND_INCOME_ASSETS)
    div_elig = min(div_income, rem)
    contrib["low_tax_dividend"] = div_elig * extra_rate
    rem = max(rem - div_elig, 0.0)

    # 3) 분리과세채: 남은 excess 한도 내
    bond_income = sum(income_by_asset.get(c, 0.0) for c in _BOND_INCOME_ASSETS)
    bond_elig = min(bond_income, rem)
    contrib["separate_bond"] = bond_elig * max(marginal - LONG_BOND_SEPARATE_TAX_RATE, 0.0)
    rem = max(rem - bond_elig, 0.0)

    # --- 해외 양도차익: 손익통산 + 250만 공제 스택 ---
    gain = _overseas_capital_gain_won(portfolio, gross_return, total_won)
    loss = max(kwargs.get("realized_loss_manwon", 0.0), 0.0) * 10_000
    offset = min(loss, gain)
    contrib["tax_loss"] = offset * OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE
    remaining_gain = gain - offset
    realizable = min(remaining_gain, OVERSEAS_STOCK_GAIN_DEDUCTION)
    contrib["overseas_exemption"] = realizable * OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE

    # --- 연금: 독립 ---
    pen = cards["pension_credit"]
    if pen["ineligibleReason"]:
        ineligible["pension_credit"] = pen["ineligibleReason"]
        contrib["pension_credit"] = 0.0
    else:
        contrib["pension_credit"] = pen["savingManwon"] * 10_000

    total = sum(contrib.values())
    return {
        "totalManwon": _won_to_manwon(total),
        "contributions": {k: _won_to_manwon(v) for k, v in contrib.items()},
        "ineligible": ineligible,
    }
