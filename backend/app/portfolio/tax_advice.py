"""Six tax-advice cards with suitability gates and overlap-safe combination.

This module keeps the public function names introduced by PR #70 while adding two
backward-compatible inputs used by the portfolio engine:

* ``expected_returns_by_asset``: avoids applying one portfolio-level return to
  every asset when per-asset expected returns are already available.
* explicit eligibility switches (ISA/pension): lets the portfolio request model
  remain the single source of truth for account eligibility.

Amounts returned to the UI are in 만원. Internal calculations stay in KRW and are
rounded only at the response boundary.
"""
from __future__ import annotations
import math
from typing import Any, Mapping, Optional

# 세율·한도·자산별 소득수익률 가정은 constants.py / assets.py를 단일 출처로 쓴다.
from .assets import (
    ASSET_INCOME_YIELD_ASSUMPTIONS,
    INCOME_TAXABLE_ASSETS as ASSET_INCOME_TAXABLE_ASSETS,
    OVERSEAS_STOCK_CAPITAL_GAIN_ASSETS as ASSET_OVERSEAS_STOCK_CAPITAL_GAIN_ASSETS,
)
from .constants import (
    DEFAULT_WITHHOLDING_TAX_RATE,
    FINANCIAL_INCOME_COMPREHENSIVE_TAX_THRESHOLD,
    IRP_PENSION_COMBINED_TAX_CREDIT_LIMIT,
    IRP_TAX_CREDIT_RATE_HIGH_INCOME,
    ISA_ANNUAL_CONTRIBUTION_LIMIT,
    ISA_GENERAL_TAX_FREE_LIMIT,
    ISA_LOW_TAX_RATE,
    ISA_MANDATORY_HOLDING_YEARS,
    ISA_SEOGMIN_TAX_FREE_LIMIT,
    OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE,
    OVERSEAS_STOCK_GAIN_DEDUCTION,
    PENSION_RECEIVE_AGE,
)

WITHHOLDING_TAX_RATE = (
    DEFAULT_WITHHOLDING_TAX_RATE
)
COMPREHENSIVE_TAX_THRESHOLD = (
    FINANCIAL_INCOME_COMPREHENSIVE_TAX_THRESHOLD
)
ISA_ANNUAL_LIMIT_WON = (
    ISA_ANNUAL_CONTRIBUTION_LIMIT
)
ISA_EXCESS_TAX_RATE = ISA_LOW_TAX_RATE
PENSION_TAX_CREDIT_LIMIT_WON = (
    IRP_PENSION_COMBINED_TAX_CREDIT_LIMIT
)
PENSION_TAX_CREDIT_RATE = (
    IRP_TAX_CREDIT_RATE_HIGH_INCOME
)

DEFAULT_MARGINAL_INCOME_TAX_RATE = 0.385
LONG_BOND_SEPARATE_TAX_RATE = 0.33

INCOME_TAXABLE_ASSETS = set(
    ASSET_INCOME_TAXABLE_ASSETS
)
# 종합과세 합산 대상 소득 자산 — separate_tax_bond는 33% 분리과세라 합산 제외
_COMPREHENSIVE_INCOME_ASSETS = INCOME_TAXABLE_ASSETS - {"separate_tax_bond"}
OVERSEAS_STOCK_CAPITAL_GAIN_ASSETS = set(
    ASSET_OVERSEAS_STOCK_CAPITAL_GAIN_ASSETS
)
_BOND_INCOME_ASSETS = {"general_bond", "low_coupon_bond"}
_DIVIDEND_INCOME_ASSETS = {"overseas_dividend", "reit"}

CALCULATION_ORDER = (
    "isa",
    "low_tax_dividend",
    "separate_bond",
    "tax_loss",
    "overseas_exemption",
    "pension_credit",
)


def _won_to_manwon(won: float) -> int:
    return int(round(float(won) / 10_000))


def _safe_nonnegative(value: Any) -> float:
    try:
        converted = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    if math.isnan(converted) or converted < 0:
        return 0.0
    return converted


def _asset_return(
    asset_class: str,
    gross_return: float,
    expected_returns_by_asset: Optional[Mapping[str, float]],
) -> float:
    if expected_returns_by_asset is None:
        return max(float(gross_return), 0.0)
    try:
        return max(float(expected_returns_by_asset.get(asset_class, gross_return)), 0.0)
    except (TypeError, ValueError, OverflowError):
        return max(float(gross_return), 0.0)


def _income_won_by_asset(
    portfolio: list[dict[str, Any]],
    gross_return: float,
    total_won: float,
    expected_returns_by_asset: Optional[Mapping[str, float]] = None,
) -> dict[str, float]:
    """Estimate annual interest/dividend-like income for comprehensive-tax-pool assets.

    separate_tax_bond is excluded: its interest is taxed at the 33% flat rate and
    is not included in the 2,000-man financial income threshold.
    """
    out: dict[str, float] = {}
    if total_won <= 0:
        return out
    for item in portfolio:
        asset_class = str(item.get("asset_class") or "")
        if asset_class not in _COMPREHENSIVE_INCOME_ASSETS:
            continue
        weight = _safe_nonnegative(item.get("weight"))
        expected_return = _asset_return(
            asset_class, gross_return, expected_returns_by_asset
        )
        income_yield = ASSET_INCOME_YIELD_ASSUMPTIONS[asset_class]
        income_return = min(expected_return, max(income_yield, 0.0))
        out[asset_class] = out.get(asset_class, 0.0) + (
            weight * total_won * income_return
        )
    return out


def _overseas_capital_gain_won(
    portfolio: list[dict[str, Any]],
    gross_return: float,
    total_won: float,
    expected_returns_by_asset: Optional[Mapping[str, float]] = None,
) -> float:
    """Estimate positive price gains for overseas-listed equity-like assets."""
    if total_won <= 0:
        return 0.0
    gain = 0.0
    for item in portfolio:
        asset_class = str(item.get("asset_class") or "")
        if asset_class not in OVERSEAS_STOCK_CAPITAL_GAIN_ASSETS:
            continue
        weight = _safe_nonnegative(item.get("weight"))
        expected_return = _asset_return(
            asset_class, gross_return, expected_returns_by_asset
        )
        total_profit = weight * total_won * expected_return
        income_part = 0.0
        if asset_class in INCOME_TAXABLE_ASSETS:
            income_yield = ASSET_INCOME_YIELD_ASSUMPTIONS[asset_class]
            income_part = weight * total_won * min(expected_return, income_yield)
        gain += max(total_profit - income_part, 0.0)
    return gain


def _base_context(
    portfolio: list[dict[str, Any]],
    gross_return: float,
    total_assets: float,
    *,
    other_financial_income: float,
    marginal_income_tax_rate: float,
    near_term_need_manwon: float,
    expected_returns_by_asset: Optional[Mapping[str, float]],
) -> dict[str, Any]:
    total_won = max(float(total_assets), 0.0) * 1e8
    other_income_won = max(float(other_financial_income), 0.0) * 1e8
    income_by_asset = _income_won_by_asset(
        portfolio,
        gross_return,
        total_won,
        expected_returns_by_asset,
    )
    total_financial_income = sum(income_by_asset.values()) + other_income_won
    excess = max(total_financial_income - COMPREHENSIVE_TAX_THRESHOLD, 0.0)
    marginal = max(float(marginal_income_tax_rate), 0.0)
    extra_rate = max(marginal - WITHHOLDING_TAX_RATE, 0.0)
    investable = max(total_won - max(float(near_term_need_manwon), 0.0) * 10_000, 0.0)
    return {
        "total_won": total_won,
        "income_by_asset": income_by_asset,
        "total_financial_income_won": total_financial_income,
        "excess_won": excess,
        "marginal": marginal,
        "extra_rate": extra_rate,
        "investable_won": investable,
    }


def _resolve_isa_tax_free_limit(
    isa_type: str,
) -> int:
    return (
        ISA_SEOGMIN_TAX_FREE_LIMIT
        if str(isa_type).lower()
        == "seogmin"
        else ISA_GENERAL_TAX_FREE_LIMIT
    )

def calc_tax_advice(
    portfolio: list[dict[str, Any]],
    gross_return: float,
    total_assets: float,
    *,
    isa_used_manwon: float = 0.0,
    pension_used_manwon: float = 0.0,
    realized_loss_manwon: float = 0.0,
    other_financial_income: float = 0.0,
    marginal_income_tax_rate: float = DEFAULT_MARGINAL_INCOME_TAX_RATE,
    age: Optional[int] = None,
    horizon_years: Optional[float] = None,
    near_term_need_manwon: float = 0.0,
    near_term_need_years: Optional[float] = None,
    isa_opened: bool = True,
    isa_type: str = "general",
    isa_can_open_new: Optional[bool] = None,
    isa_usable: Optional[bool] = None,
    isa_years_until_liquid: Optional[float] = None,
    pension_usable: Optional[bool] = None,
    pension_tax_liability_sufficient: bool = True,
    pension_tax_credit_rate: float = PENSION_TAX_CREDIT_RATE,
    expected_returns_by_asset: Optional[Mapping[str, float]] = None,
) -> list[dict[str, Any]]:
    """Return six standalone tax-saving cards with suitability gates.

    ``total_assets`` and ``other_financial_income`` use 억원 for PR #70
    compatibility. Contribution/need inputs use 만원, also matching PR #70.
    """
    if marginal_income_tax_rate is None:
        marginal_income_tax_rate = DEFAULT_MARGINAL_INCOME_TAX_RATE
    context = _base_context(
        portfolio,
        gross_return,
        total_assets,
        other_financial_income=other_financial_income or 0.0,
        marginal_income_tax_rate=marginal_income_tax_rate,
        near_term_need_manwon=near_term_need_manwon or 0.0,
        expected_returns_by_asset=expected_returns_by_asset,
    )
    total_won = context["total_won"]
    income_by_asset = context["income_by_asset"]
    excess_won = context["excess_won"]
    extra_rate = context["extra_rate"]
    investable_won = context["investable_won"]

    cards: list[dict[str, Any]] = []
    isa_tax_free_limit_won = (
        _resolve_isa_tax_free_limit(
            isa_type
        )
    )

    # 1) ISA
    isa_headroom_won = max(
        ISA_ANNUAL_LIMIT_WON - max(float(isa_used_manwon or 0.0), 0.0) * 10_000,
        0.0,
    )
    income_asset_value_won = sum(
        _safe_nonnegative(item.get("weight")) * total_won
        for item in portfolio
        if item.get("asset_class") in _COMPREHENSIVE_INCOME_ASSETS
    )
    transferable_won = min(isa_headroom_won, income_asset_value_won, investable_won)
    isa_reason: Optional[str] = None
    if isa_usable is False:
        isa_reason = "ISA 계좌 적격성·잔여한도 조건 미충족"
    elif not isa_opened and (
        isa_can_open_new is False
        or (isa_can_open_new is None and excess_won > 0)
    ):
        # isa_can_open_new=None은 PR #70의 레거시 호출 호환 경로다.
        # 실제 엔진 연동에서는 최근 3년 종합과세 이력으로 계산한 명시 값을 전달한다.
        isa_reason = "ISA 신규 개설 불가(적격성 조건 미충족)"
    else:
        remaining_lockup = (
            max(float(isa_years_until_liquid), 0.0)
            if isa_years_until_liquid is not None
            else (0.0 if isa_opened else float(ISA_MANDATORY_HOLDING_YEARS))
        )
        if (
            horizon_years is not None
            and remaining_lockup > 0
            and float(horizon_years) < remaining_lockup
        ):
            isa_reason = (
                f"투자기간 {float(horizon_years):g}년 < ISA 잔여 의무보유 "
                f"{remaining_lockup:g}년"
            )
    isa_saving_won = 0.0
    if isa_reason is None and transferable_won > 0 and income_asset_value_won > 0:
        avg_income_rate = sum(income_by_asset.values()) / income_asset_value_won
        moved_income_won = transferable_won * avg_income_rate
        comp_portion_won = min(moved_income_won, excess_won)
        tax_outside_won = (
            moved_income_won * WITHHOLDING_TAX_RATE
            + comp_portion_won * extra_rate
        )
        tax_isa_won = max(
            moved_income_won - isa_tax_free_limit_won, 0.0
        ) * ISA_EXCESS_TAX_RATE
        isa_saving_won = max(tax_outside_won - tax_isa_won, 0.0)
    cards.append(
        {
            "key": "isa",
            "savingManwon": _won_to_manwon(isa_saving_won),
            "savingWon": round(isa_saving_won),
            "applicable": isa_reason is None and isa_saving_won > 0,
            "transferableManwon": _won_to_manwon(transferable_won)
            if isa_reason is None
            else 0,
            "ineligibleReason": isa_reason,
            "isaType": str(isa_type).lower(),
            "taxFreeLimitWon": (
                isa_tax_free_limit_won
            ),
        }
    )

    # 2) Pension account credit
    pension_headroom_won = max(
        PENSION_TAX_CREDIT_LIMIT_WON
        - max(float(pension_used_manwon or 0.0), 0.0) * 10_000,
        0.0,
    )
    pension_reason: Optional[str] = None
    if pension_usable is False:
        pension_reason = "연금계좌 적격성·잔여 세액공제 한도 조건 미충족"
    elif not pension_tax_liability_sufficient:
        pension_reason = "산출세액이 세액공제액보다 작아 전액 공제 효과를 가정할 수 없음"
    elif age is not None and int(age) < PENSION_RECEIVE_AGE:
        years_to_receive = PENSION_RECEIVE_AGE - int(age)
        if horizon_years is not None and float(horizon_years) < years_to_receive:
            pension_reason = (
                f"투자기간 {float(horizon_years):g}년 < 연금 수령까지 "
                f"{years_to_receive:g}년"
            )
    pension_transferable = min(pension_headroom_won, investable_won)
    pension_saving_won = pension_transferable * max(
        float(pension_tax_credit_rate), 0.0
    )
    cards.append(
        {
            "key": "pension_credit",
            "savingManwon": _won_to_manwon(pension_saving_won)
            if pension_reason is None
            else 0,
            "savingWon": round(pension_saving_won)
            if pension_reason is None
            else 0,
            "applicable": pension_reason is None and pension_saving_won > 0,
            "transferableManwon": _won_to_manwon(pension_transferable)
            if pension_reason is None
            else 0,
            "ineligibleReason": pension_reason,
        }
    )

    # 3) Separate-tax bond model
    bond_income_won = sum(
        income_by_asset.get(asset_class, 0.0)
        for asset_class in _BOND_INCOME_ASSETS
    )
    bond_eligible_won = min(bond_income_won, excess_won)
    bond_saving_won = bond_eligible_won * max(
        context["marginal"] - LONG_BOND_SEPARATE_TAX_RATE, 0.0
    )
    bond_reason = None
    if context["marginal"] <= LONG_BOND_SEPARATE_TAX_RATE:
        bond_reason = "한계세율이 분리과세 가정세율 이하"
    elif excess_won <= 0:
        bond_reason = "금융소득종합과세 초과분 없음"
    elif bond_income_won <= 0:
        bond_reason = "대상 채권 이자소득 추정액 없음"
    cards.append(
        {
            "key": "separate_bond",
            "savingManwon": _won_to_manwon(bond_saving_won),
            "savingWon": round(bond_saving_won),
            "applicable": bond_saving_won > 0,
            "transferableManwon": 0,
            "ineligibleReason": bond_reason,
        }
    )

    # 4) Lower-tax dividend model used by the project
    dividend_income_won = sum(
        income_by_asset.get(asset_class, 0.0)
        for asset_class in _DIVIDEND_INCOME_ASSETS
    )
    dividend_eligible_won = min(dividend_income_won, excess_won)
    dividend_saving_won = dividend_eligible_won * extra_rate
    dividend_reason = None
    if excess_won <= 0:
        dividend_reason = "금융소득종합과세 초과분 없음"
    elif dividend_income_won <= 0:
        dividend_reason = "대상 배당성 자산 소득 추정액 없음"
    cards.append(
        {
            "key": "low_tax_dividend",
            "savingManwon": _won_to_manwon(dividend_saving_won),
            "savingWon": round(dividend_saving_won),
            "applicable": dividend_saving_won > 0,
            "transferableManwon": 0,
            "ineligibleReason": dividend_reason,
        }
    )

    overseas_gain_won = _overseas_capital_gain_won(
        portfolio,
        gross_return,
        total_won,
        expected_returns_by_asset,
    )

    # 5) Overseas-equity basic deduction
    exemption_realizable_won = min(
        overseas_gain_won, OVERSEAS_STOCK_GAIN_DEDUCTION
    )
    exemption_saving_won = (
        exemption_realizable_won * OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE
    )
    cards.append(
        {
            "key": "overseas_exemption",
            "savingManwon": _won_to_manwon(exemption_saving_won),
            "savingWon": round(exemption_saving_won),
            "applicable": exemption_saving_won > 0,
            "transferableManwon": 0,
            "ineligibleReason": None
            if exemption_saving_won > 0
            else "해외주식 가격차익 추정액 없음",
        }
    )

    # 6) Tax-loss harvesting
    realized_loss_won = max(float(realized_loss_manwon or 0.0), 0.0) * 10_000
    offset_won = min(realized_loss_won, overseas_gain_won)
    harvest_saving_won = offset_won * OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE
    cards.append(
        {
            "key": "tax_loss",
            "savingManwon": _won_to_manwon(harvest_saving_won),
            "savingWon": round(harvest_saving_won),
            "applicable": harvest_saving_won > 0,
            "transferableManwon": 0,
            "ineligibleReason": None
            if harvest_saving_won > 0
            else "실현 가능한 해외주식 손실 또는 상계 대상 차익 없음",
        }
    )

    return cards


def calc_combined_tax_saving(
    portfolio: list[dict[str, Any]],
    gross_return: float,
    total_assets: float,
    *,
    standalone_cards: Optional[
        list[dict[str, Any]]
    ] = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Combine six strategies without double-using shared tax bases.

    Calculation order maximizes savings per shared-pool KRW. UI display order can
    still be sorted by the resulting contribution amount.
    """
    marginal = kwargs.get("marginal_income_tax_rate")
    if marginal is None:
        marginal = DEFAULT_MARGINAL_INCOME_TAX_RATE
    expected_returns_by_asset = kwargs.get("expected_returns_by_asset")
    context = _base_context(
        portfolio,
        gross_return,
        total_assets,
        other_financial_income=kwargs.get("other_financial_income") or 0.0,
        marginal_income_tax_rate=marginal,
        near_term_need_manwon=kwargs.get("near_term_need_manwon") or 0.0,
        expected_returns_by_asset=expected_returns_by_asset,
    )
    card_list = (
        standalone_cards
        if standalone_cards is not None
        else calc_tax_advice(
            portfolio,
            gross_return,
            total_assets,
            **kwargs,
        )
    )
    cards = {
        card["key"]: card
        for card in card_list
    }
    income_by_asset = context["income_by_asset"]
    total_won = context["total_won"]
    rem = context["excess_won"]
    extra_rate = context["extra_rate"]
    marginal = context["marginal"]

    contrib: dict[str, float] = {}
    ineligible: dict[str, str] = {}
    exhausted: dict[str, str] = {}

    # Financial-income excess pool: ISA -> dividend -> separate-tax bond.
    isa = cards["isa"]
    if isa.get("ineligibleReason"):
        ineligible["isa"] = str(isa["ineligibleReason"])
        contrib["isa"] = 0.0
    elif not isa.get("applicable"):
        contrib["isa"] = 0.0
    else:
        contrib["isa"] = float(isa.get("savingWon", 0.0))
        income_asset_value = sum(
            _safe_nonnegative(item.get("weight")) * total_won
            for item in portfolio
            if item.get("asset_class") in _COMPREHENSIVE_INCOME_ASSETS
        )
        if income_asset_value > 0:
            avg_rate = sum(income_by_asset.values()) / income_asset_value
            isa_headroom = max(
                ISA_ANNUAL_LIMIT_WON
                - max(float(kwargs.get("isa_used_manwon") or 0.0), 0.0)
                * 10_000,
                0.0,
            )
            investable = context["investable_won"]
            transferable = min(isa_headroom, income_asset_value, investable)
            rem = max(rem - min(transferable * avg_rate, rem), 0.0)

    dividend_income = sum(
        income_by_asset.get(asset_class, 0.0)
        for asset_class in _DIVIDEND_INCOME_ASSETS
    )
    dividend_eligible = min(dividend_income, rem)
    contrib["low_tax_dividend"] = dividend_eligible * extra_rate
    rem = max(rem - dividend_eligible, 0.0)
    if (
        cards["low_tax_dividend"].get("applicable")
        and contrib["low_tax_dividend"] <= 0
    ):
        exhausted["low_tax_dividend"] = "상위 효율 전략 적용 후 공유 과세소득 풀 소진"

    bond_income = sum(
        income_by_asset.get(asset_class, 0.0)
        for asset_class in _BOND_INCOME_ASSETS
    )
    bond_eligible = min(bond_income, rem)
    contrib["separate_bond"] = bond_eligible * max(
        marginal - LONG_BOND_SEPARATE_TAX_RATE, 0.0
    )
    rem = max(rem - bond_eligible, 0.0)
    if cards["separate_bond"].get("applicable") and contrib["separate_bond"] <= 0:
        exhausted["separate_bond"] = "상위 효율 전략 적용 후 공유 과세소득 풀 소진"

    # Overseas gains: loss offset first, then basic deduction on remaining gain.
    gain = _overseas_capital_gain_won(
        portfolio,
        gross_return,
        total_won,
        expected_returns_by_asset,
    )
    loss = max(float(kwargs.get("realized_loss_manwon") or 0.0), 0.0) * 10_000
    offset = min(loss, gain)
    contrib["tax_loss"] = offset * OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE
    remaining_gain = max(gain - offset, 0.0)
    realizable_deduction = min(remaining_gain, OVERSEAS_STOCK_GAIN_DEDUCTION)
    contrib["overseas_exemption"] = (
        realizable_deduction * OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE
    )

    pension = cards["pension_credit"]
    if pension.get("ineligibleReason"):
        ineligible["pension_credit"] = str(pension["ineligibleReason"])
        contrib["pension_credit"] = 0.0
    else:
        contrib["pension_credit"] = float(pension.get("savingWon", 0.0))

    # Keep all six keys and deterministic ordering.
    ordered_contrib = {
        key: max(float(contrib.get(key, 0.0)), 0.0) for key in CALCULATION_ORDER
    }
    total = sum(ordered_contrib.values())
    return {
        "totalManwon": _won_to_manwon(total),
        "totalWon": round(total),
        "contributions": {
            key: _won_to_manwon(value) for key, value in ordered_contrib.items()
        },
        "contributionsWon": {
            key: round(value) for key, value in ordered_contrib.items()
        },
        "ineligible": ineligible,
        "exhausted": exhausted,
        "calculationOrder": list(CALCULATION_ORDER),
        "remainingFinancialIncomeExcessWon": round(rem),
    }
