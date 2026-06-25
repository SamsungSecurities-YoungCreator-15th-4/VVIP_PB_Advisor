# ruff: noqa: E501
"""portfolio_logic.py 분할: tax_accounts 모듈."""


import numpy as np
import pandas as pd
from typing import Any, Dict, Optional, Tuple

from .assets import ASSET_INCOME_YIELD_ASSUMPTIONS, ASSET_NAMES_KR, ASSET_TICKERS, INCOME_TAXABLE_ASSETS, IRP_PRIORITY_ASSETS, ISA_PRIORITY_ASSETS, OVERSEAS_STOCK_CAPITAL_GAIN_ASSETS
from .constants import DEFAULT_WITHHOLDING_TAX_RATE, FINANCIAL_INCOME_COMPREHENSIVE_TAX_THRESHOLD, IRP_PENSION_COMBINED_TAX_CREDIT_LIMIT, ISA_ANNUAL_CONTRIBUTION_LIMIT, ISA_GENERAL_TAX_FREE_LIMIT, ISA_LOW_TAX_RATE, ISA_MANDATORY_HOLDING_YEARS, ISA_SEOGMIN_TAX_FREE_LIMIT, ISA_TOTAL_CONTRIBUTION_LIMIT, OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE, OVERSEAS_STOCK_GAIN_DEDUCTION, PENSION_RECEIVE_AGE, TAX_RULE_EFFECTIVE_DATE, TAX_RULE_TABLE, TAX_RULE_TABLE_VERSION
from .models import PortfolioRequest
from .utils import normalize_weights, safe_float, safe_round

# ============================================================
# 7. 세금 / 계좌
# ============================================================


def get_common_tax_rules() -> Dict[str, Any]:
    return {
        "version": TAX_RULE_TABLE_VERSION,
        "effective_date": TAX_RULE_EFFECTIVE_DATE,
        "rules": TAX_RULE_TABLE,
    }


def estimate_income_profit_for_asset(
    asset: str,
    weight: float,
    expected_return: float,
    total_asset: float,
) -> float:
    if asset not in INCOME_TAXABLE_ASSETS:
        return 0.0

    positive_return = max(safe_float(expected_return), 0.0)
    income_yield = ASSET_INCOME_YIELD_ASSUMPTIONS.get(asset, positive_return)
    income_return = min(positive_return, max(income_yield, 0.0))
    return float(max(weight, 0.0) * total_asset * income_return)


def estimate_overseas_capital_gain_profit_for_asset(
    asset: str,
    weight: float,
    expected_return: float,
    total_asset: float,
) -> float:
    if asset not in OVERSEAS_STOCK_CAPITAL_GAIN_ASSETS:
        return 0.0

    total_positive_profit = max(weight, 0.0) * total_asset * max(safe_float(expected_return), 0.0)
    income_profit = estimate_income_profit_for_asset(
        asset=asset,
        weight=weight,
        expected_return=expected_return,
        total_asset=total_asset,
    )
    return float(max(total_positive_profit - income_profit, 0.0))


def estimate_taxable_financial_income(
    weights: Dict[str, float],
    expected_returns: pd.Series,
    total_asset: float,
) -> float:
    estimated_income = 0.0
    weights = normalize_weights(weights)

    for asset in INCOME_TAXABLE_ASSETS:
        if asset in expected_returns.index:
            estimated_income += estimate_income_profit_for_asset(
                asset=asset,
                weight=weights.get(asset, 0.0),
                expected_return=float(expected_returns[asset]),
                total_asset=total_asset,
            )

    return float(estimated_income)


def resolve_external_financial_income_krw(request: PortfolioRequest) -> float:
    """현재 포트폴리오 외 연 이자·배당 금융소득을 원 단위로 정규화한다.

    프론트 화면은 만원 입력을 사용하므로 명시형 필드를 함께 지원한다.
    여러 필드가 동시에 오면 단위가 명확한 krw → manwon → 기존 필드 순으로 사용한다.
    """
    explicit_krw = getattr(request, "external_financial_income_krw", None)
    if explicit_krw is not None:
        return max(safe_float(explicit_krw), 0.0)

    explicit_manwon = getattr(request, "external_financial_income_manwon", None)
    if explicit_manwon is not None:
        return max(safe_float(explicit_manwon), 0.0) * 10_000

    return max(safe_float(getattr(request, "other_financial_income", 0.0)), 0.0)


def calculate_financial_income_comprehensive_tax_status(
    portfolio_financial_income: float,
    external_financial_income: float = 0.0,
    marginal_income_tax_rate: float = 0.24,
) -> Dict[str, Any]:
    """금융소득종합과세 임계선 화면과 세후 계산에 쓰는 단일 상태값.

    - portfolio_financial_income: 추천 포트폴리오에서 예상되는 연 이자·배당(원)
    - external_financial_income: 예금·기존 계좌 등 현재 포트폴리오 외 금융소득(원)
    - 총 금융소득이 2,000만원을 초과하는지 판단한다.
    - 포트폴리오 세후수익률에는 외부소득 자체의 세금을 떠넘기지 않도록
      '외부소득만 있을 때 대비 포트폴리오로 증가한 추가세액'을 별도 산출한다.
    """
    portfolio_income = max(safe_float(portfolio_financial_income), 0.0)
    external_income = max(safe_float(external_financial_income), 0.0)
    total_income = portfolio_income + external_income
    threshold = FINANCIAL_INCOME_COMPREHENSIVE_TAX_THRESHOLD
    excess = max(total_income - threshold, 0.0)
    external_only_excess = max(external_income - threshold, 0.0)

    marginal_rate = min(max(safe_float(marginal_income_tax_rate), 0.0), 0.495)
    additional_rate = max(marginal_rate - DEFAULT_WITHHOLDING_TAX_RATE, 0.0)
    total_additional_tax = excess * additional_rate
    external_baseline_tax = external_only_excess * additional_rate
    portfolio_incremental_tax = max(total_additional_tax - external_baseline_tax, 0.0)

    def to_manwon(value: float) -> int:
        return int(round(value / 10_000))

    return {
        # 기존 키는 총 금융소득 의미로 유지해 기존 프론트와 하위호환한다.
        "taxable_financial_income": safe_round(total_income, 0),
        "portfolio_financial_income": safe_round(portfolio_income, 0),
        "external_financial_income": safe_round(external_income, 0),
        "total_financial_income": safe_round(total_income, 0),
        "threshold": threshold,
        "excess_over_threshold": safe_round(excess, 0),
        "is_over_threshold": total_income > threshold,
        "withholding_tax_rate": DEFAULT_WITHHOLDING_TAX_RATE,
        "marginal_income_tax_rate": safe_round(marginal_rate, 6),
        "additional_tax_rate": safe_round(additional_rate, 6),
        "estimated_additional_tax_total": safe_round(total_additional_tax, 0),
        "estimated_additional_tax_external_baseline": safe_round(
            external_baseline_tax, 0
        ),
        "estimated_additional_tax_attributable_to_portfolio": safe_round(
            portfolio_incremental_tax, 0
        ),
        "rule_key": "financial_income_tax_threshold",
        "basis": (
            "현재 포트폴리오 외 금융소득과 포트폴리오 예상 이자·배당을 합산해 "
            "금융소득종합과세 2,000만원 기준을 점검합니다. 실제 세액은 다른 종합소득과 "
            "공제사항을 포함해 확인해야 합니다."
        ),
        # TaxGauge가 별도 환산 로직 없이 바로 사용할 수 있는 표시 계약.
        "gauge": {
            "external_financial_income_manwon": to_manwon(external_income),
            "portfolio_financial_income_manwon": to_manwon(portfolio_income),
            "total_financial_income_manwon": to_manwon(total_income),
            "threshold_manwon": to_manwon(threshold),
            "excess_over_threshold_manwon": to_manwon(excess),
            "estimated_additional_tax_manwon": to_manwon(total_additional_tax),
            "is_over_threshold": total_income > threshold,
            "withholding_rate_pct": safe_round(
                DEFAULT_WITHHOLDING_TAX_RATE * 100, 1
            ),
            "marginal_rate_pct": safe_round(marginal_rate * 100, 1),
            "additional_rate_pct": safe_round(additional_rate * 100, 1),
            "separate_rate_label": f"{DEFAULT_WITHHOLDING_TAX_RATE * 100:.1f}%",
            "comprehensive_rate_label": f"예상 {marginal_rate * 100:.1f}%",
            "rate_note": (
                "49.5%는 최고세율이며, 화면에는 고객 입력 한계세율을 표시합니다."
            ),
        },
    }


def estimate_overseas_stock_capital_gains_tax(
    weights: Dict[str, float],
    expected_returns: pd.Series,
    total_asset: float,
    realized_gain_rate: float,
    realized_gain_krw: Optional[float] = None,
    realized_loss_krw: float = 0.0,
) -> Dict[str, Any]:
    gross_realized_gain = 0.0
    weights = normalize_weights(weights)

    for asset in OVERSEAS_STOCK_CAPITAL_GAIN_ASSETS:
        if asset in expected_returns.index:
            asset_capital_gain = estimate_overseas_capital_gain_profit_for_asset(
                asset=asset,
                weight=weights.get(asset, 0.0),
                expected_return=float(expected_returns[asset]),
                total_asset=total_asset,
            )
            gross_realized_gain += asset_capital_gain * realized_gain_rate

    if realized_gain_krw is not None:
        gross_realized_gain = max(safe_float(realized_gain_krw), 0.0)

    realized_loss = max(safe_float(realized_loss_krw), 0.0)
    net_realized_gain = max(gross_realized_gain - realized_loss, 0.0)
    taxable_gain = max(net_realized_gain - OVERSEAS_STOCK_GAIN_DEDUCTION, 0.0)
    estimated_tax = taxable_gain * OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE

    return {
        "gross_realized_gain": safe_round(gross_realized_gain, 0),
        "realized_loss_offset": safe_round(realized_loss, 0),
        "net_realized_gain": safe_round(net_realized_gain, 0),
        "basic_deduction": OVERSEAS_STOCK_GAIN_DEDUCTION,
        "taxable_gain": safe_round(taxable_gain, 0),
        "tax_rate": OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE,
        "estimated_tax": safe_round(estimated_tax, 0),
        "rule_keys": ["overseas_stock_transfer_tax"],
        "basis": (
            "해외상장 주식/ETF의 가격차익 부분에 기본공제 250만 원과 "
            "기본세율 22%를 적용한 간이 추정. 배당·이자성 수익과 "
            "가격차익은 중복 과세하지 않도록 분리 추정."
        ),
    }


def calculate_isa_status(request: PortfolioRequest) -> Dict[str, Any]:
    can_open_new = not request.isa_recent_3yr_comprehensive_taxed
    account_year_count = max(int(np.floor(request.isa_account_age_years)) + 1, 1)

    if request.isa_account_exists:
        earned_capacity = min(
            ISA_ANNUAL_CONTRIBUTION_LIMIT * account_year_count,
            ISA_TOTAL_CONTRIBUTION_LIMIT,
        )
        account_usable = request.isa_existing_account_usable
    else:
        earned_capacity = ISA_ANNUAL_CONTRIBUTION_LIMIT
        account_usable = can_open_new

    calculated_capacity = max(
        earned_capacity - request.isa_cumulative_contribution,
        0.0,
    )
    manual_capacity = request.isa_remaining_capacity
    if request.isa_remaining_capacity_override is not None:
        manual_capacity = request.isa_remaining_capacity_override

    remaining_capacity = min(calculated_capacity, manual_capacity)
    isa_usable = request.isa_enabled and account_usable and remaining_capacity > 0

    calculated_years_until_liquid = max(
        ISA_MANDATORY_HOLDING_YEARS - request.isa_account_age_years,
        0.0,
    )
    years_until_liquid = min(
        request.isa_years_until_liquid,
        calculated_years_until_liquid,
    )

    if not isa_usable:
        remaining_capacity = 0.0

    if isa_usable and request.isa_account_exists:
        reason = "existing_isa_account_usable"
    elif isa_usable:
        reason = "new_isa_opening_allowed"
    elif not request.isa_enabled:
        reason = "isa_disabled_by_input"
    elif not account_usable:
        reason = "isa_account_or_eligibility_not_usable"
    else:
        reason = "isa_remaining_capacity_zero"

    return {
        "enabled": request.isa_enabled,
        "usable": isa_usable,
        "type": request.isa_type,
        "account_exists": request.isa_account_exists,
        "account_age_years": safe_round(request.isa_account_age_years, 2),
        "can_open_new": can_open_new,
        "existing_account_usable": request.isa_existing_account_usable,
        "recent_3yr_comprehensive_taxed": (
            request.isa_recent_3yr_comprehensive_taxed
        ),
        "annual_contribution_limit": ISA_ANNUAL_CONTRIBUTION_LIMIT,
        "total_contribution_limit": ISA_TOTAL_CONTRIBUTION_LIMIT,
        "earned_capacity": safe_round(earned_capacity, 0),
        "cumulative_contribution": safe_round(
            request.isa_cumulative_contribution, 0
        ),
        "calculated_remaining_capacity": safe_round(calculated_capacity, 0),
        "remaining_capacity_input": safe_round(request.isa_remaining_capacity, 0),
        "remaining_capacity_override": safe_round(
            request.isa_remaining_capacity_override, 0
        )
        if request.isa_remaining_capacity_override is not None
        else None,
        "remaining_capacity": safe_round(remaining_capacity, 0),
        "years_until_liquid": safe_round(years_until_liquid, 2),
        "reason": reason,
    }


def calculate_irp_status(
    request: PortfolioRequest,
) -> Dict[str, Any]:
    calculated_capacity = max(
        IRP_PENSION_COMBINED_TAX_CREDIT_LIMIT
        - request.irp_current_year_contribution,
        0.0,
    )
    manual_capacity = (
        request.irp_remaining_tax_credit_capacity
    )
    if (
        request
        .irp_remaining_tax_credit_capacity_override
        is not None
    ):
        manual_capacity = (
            request
            .irp_remaining_tax_credit_capacity_override
        )

    remaining_capacity = min(
        calculated_capacity,
        manual_capacity,
    )
    age_input_available = (
        request.age is not None
    )

    derived_years_until_access: (
        Optional[float]
    ) = None
    if age_input_available:
        derived_years_until_access = float(
            max(
                PENSION_RECEIVE_AGE
                - request.age,
                0,
            )
        )

    effective_years_until_access = max(
        safe_float(
            request.irp_years_until_access
        ),
        safe_float(
            derived_years_until_access
        ),
    )
    horizon_suitable = bool(
        age_input_available
        and (
            request.age
            >= PENSION_RECEIVE_AGE
            or (
                request
                .investment_horizon_years
                >= effective_years_until_access
            )
        )
    )
    manual_review_required = bool(
        request.irp_enabled
        and request.irp_eligible
        and not age_input_available
    )
    irp_usable = bool(
        request.irp_enabled
        and request.irp_eligible
        and age_input_available
        and horizon_suitable
        and remaining_capacity > 0
    )

    if not irp_usable:
        remaining_capacity = 0.0

    if irp_usable:
        reason = (
            "irp_tax_credit_capacity_available"
        )
    elif not request.irp_enabled:
        reason = "irp_disabled_by_input"
    elif not request.irp_eligible:
        reason = "irp_not_eligible"
    elif not age_input_available:
        reason = (
            "age_missing_manual_review_required"
        )
    elif not horizon_suitable:
        reason = (
            "investment_horizon_shorter_"
            "than_pension_access"
        )
    else:
        reason = (
            "irp_remaining_capacity_zero"
        )

    return {
        "enabled": request.irp_enabled,
        "eligible": request.irp_eligible,
        "usable": irp_usable,
        "age": request.age,
        "age_input_available": (
            age_input_available
        ),
        "manual_review_required": (
            manual_review_required
        ),
        "pension_receive_age": (
            PENSION_RECEIVE_AGE
        ),
        "horizon_suitable": (
            horizon_suitable
        ),
        "investment_horizon_years": (
            request.investment_horizon_years
        ),
        "account_exists": (
            request.irp_account_exists
        ),
        "account_age_years": safe_round(
            request.irp_account_age_years,
            2,
        ),
        "cumulative_contribution": safe_round(
            request.irp_cumulative_contribution,
            0,
        ),
        "annual_tax_credit_limit": (
            IRP_PENSION_COMBINED_TAX_CREDIT_LIMIT
        ),
        "current_year_contribution": (
            safe_round(
                request
                .irp_current_year_contribution,
                0,
            )
        ),
        "calculated_remaining_capacity": (
            safe_round(
                calculated_capacity,
                0,
            )
        ),
        "remaining_tax_credit_capacity_input": (
            safe_round(
                request
                .irp_remaining_tax_credit_capacity,
                0,
            )
        ),
        "remaining_capacity_override": (
            safe_round(
                request
                .irp_remaining_tax_credit_capacity_override,
                0,
            )
            if (
                request
                .irp_remaining_tax_credit_capacity_override
                is not None
            )
            else None
        ),
        "remaining_tax_credit_capacity": (
            safe_round(
                remaining_capacity,
                0,
            )
        ),
        "tax_credit_rate": (
            request.irp_tax_credit_rate
        ),
        "years_until_access_input": (
            safe_round(
                request.irp_years_until_access,
                2,
            )
        ),
        "years_until_access_derived_from_age": (
            safe_round(
                derived_years_until_access,
                2,
            )
            if (
                derived_years_until_access
                is not None
            )
            else None
        ),
        "years_until_access": safe_round(
            effective_years_until_access,
            2,
        ),
        "reason": reason,
    }


def allocate_account_buckets(
    weights: Dict[str, float],
    total_asset: float,
    request: PortfolioRequest,
) -> Dict[str, Any]:
    weights = normalize_weights(weights)
    remaining_amounts = {
        asset: weights.get(asset, 0.0) * total_asset for asset in ASSET_TICKERS.keys()
    }

    isa_status = calculate_isa_status(request)
    irp_status = calculate_irp_status(request)

    isa_alloc = {asset: 0.0 for asset in ASSET_TICKERS.keys()}
    irp_alloc = {asset: 0.0 for asset in ASSET_TICKERS.keys()}
    taxable_alloc = {asset: 0.0 for asset in ASSET_TICKERS.keys()}

    # 일반과세계좌의 명확한 역할 1: 단기 필요자금은 lock-up 계좌보다 먼저 확보한다.
    liquidity_reserve_target = min(max(request.unique_need_amount, 0.0), total_asset)
    liquidity_reserve_remaining = liquidity_reserve_target
    reserve_priority = ["cash", "general_bond", "low_coupon_bond", "separate_tax_bond"]
    for asset in reserve_priority:
        amount = min(remaining_amounts.get(asset, 0.0), liquidity_reserve_remaining)
        if amount > 0:
            taxable_alloc[asset] += amount
            remaining_amounts[asset] -= amount
            liquidity_reserve_remaining -= amount
        if liquidity_reserve_remaining <= 0:
            break

    if isa_status["usable"]:
        remaining_isa_capacity = isa_status["remaining_capacity"]
        for asset in ISA_PRIORITY_ASSETS:
            amount = min(remaining_amounts.get(asset, 0.0), remaining_isa_capacity)
            if amount > 0:
                isa_alloc[asset] += amount
                remaining_amounts[asset] -= amount
                remaining_isa_capacity -= amount
            if remaining_isa_capacity <= 0:
                break

    if irp_status["usable"]:
        remaining_irp_capacity = irp_status["remaining_tax_credit_capacity"]
        for asset in IRP_PRIORITY_ASSETS:
            amount = min(remaining_amounts.get(asset, 0.0), remaining_irp_capacity)
            if amount > 0:
                irp_alloc[asset] += amount
                remaining_amounts[asset] -= amount
                remaining_irp_capacity -= amount
            if remaining_irp_capacity <= 0:
                break

    # 일반과세계좌의 역할 2: 세제계좌 한도·적격성 적용 후 나머지 투자자산을 계속 운용한다.
    for asset, amount in remaining_amounts.items():
        taxable_alloc[asset] += max(amount, 0.0)

    isa_total = sum(isa_alloc.values())
    irp_total = sum(irp_alloc.values())
    taxable_total = sum(taxable_alloc.values())
    liquidity_reserve_allocated = max(
        liquidity_reserve_target - liquidity_reserve_remaining, 0.0
    )

    isa_locked_amount = isa_total if isa_status["years_until_liquid"] > 0 else 0.0
    irp_tax_credit = min(
        irp_total,
        irp_status["remaining_tax_credit_capacity"],
    ) * request.irp_tax_credit_rate

    isa_tax_free_limit = (
        ISA_GENERAL_TAX_FREE_LIMIT
        if request.isa_type == "general"
        else ISA_SEOGMIN_TAX_FREE_LIMIT
    )

    return {
        "isa": {
            **isa_status,
            "allocated_amount": safe_round(isa_total, 0),
            "used_capacity": safe_round(isa_total, 0),
            "utilization_ratio": safe_round(
                isa_total / isa_status["remaining_capacity"], 6
            )
            if isa_status["remaining_capacity"] > 0
            else 0.0,
            "locked_amount_for_liquidity": safe_round(isa_locked_amount, 0),
            "tax_free_limit": isa_tax_free_limit,
            "low_tax_rate_after_tax_free_limit": ISA_LOW_TAX_RATE,
            "rule_keys": ["isa_tax_exemption"],
            "allocations": {
                asset: {
                    "label": ASSET_NAMES_KR[asset],
                    "amount": safe_round(amount, 0),
                    "weight_in_total_asset": safe_round(amount / total_asset, 6),
                }
                for asset, amount in isa_alloc.items()
                if amount > 0
            },
        },
        "irp": {
            **irp_status,
            "allocated_amount": safe_round(irp_total, 0),
            "used_capacity": safe_round(irp_total, 0),
            "utilization_ratio": safe_round(
                irp_total / irp_status["remaining_tax_credit_capacity"], 6
            )
            if irp_status["remaining_tax_credit_capacity"] > 0
            else 0.0,
            "estimated_tax_credit": safe_round(irp_tax_credit, 0),
            "rule_keys": ["pension_account_tax_credit"],
            "allocations": {
                asset: {
                    "label": ASSET_NAMES_KR[asset],
                    "amount": safe_round(amount, 0),
                    "weight_in_total_asset": safe_round(amount / total_asset, 6),
                }
                for asset, amount in irp_alloc.items()
                if amount > 0
            },
        },
        "taxable_account": {
            "account_role": "taxable_investment_and_liquidity",
            "display_name": "일반과세 자산 운용",
            "allocated_amount": safe_round(taxable_total, 0),
            "liquidity_reserve_target": safe_round(liquidity_reserve_target, 0),
            "liquidity_reserve_allocated": safe_round(liquidity_reserve_allocated, 0),
            "liquidity_reserve_shortfall": safe_round(liquidity_reserve_remaining, 0),
            "liquidity_reserve_basis": "cash_like_assets_only",
            "liquidity_reserve_assets": reserve_priority,
            "liquidity_reserve_fully_funded": (
                liquidity_reserve_remaining <= 1e-6
            ),
            "allocations": {
                asset: {
                    "label": ASSET_NAMES_KR[asset],
                    "amount": safe_round(amount, 0),
                    "weight_in_total_asset": safe_round(amount / total_asset, 6),
                }
                for asset, amount in taxable_alloc.items()
                if amount > 0
            },
        },
    }


def estimate_tax_saving_effect(
    weights: Dict[str, float],
    expected_returns: pd.Series,
    total_asset: float,
    request: PortfolioRequest,
    account_buckets: Dict[str, Any],
) -> Dict[str, Any]:
    weights = normalize_weights(weights)
    taxable_income_before = estimate_taxable_financial_income(
        weights, expected_returns, total_asset
    )

    irp_tax_credit = account_buckets["irp"]["estimated_tax_credit"]

    income_shifted_to_isa = 0.0
    for asset, info in account_buckets["isa"]["allocations"].items():
        if asset not in expected_returns.index:
            continue
        asset_amount = safe_float(info["amount"])
        asset_weight = asset_amount / total_asset if total_asset > 0 else 0.0
        income_shifted_to_isa += estimate_income_profit_for_asset(
            asset=asset,
            weight=asset_weight,
            expected_return=float(expected_returns[asset]),
            total_asset=total_asset,
        )

    isa_tax_free_limit = (
        ISA_GENERAL_TAX_FREE_LIMIT if request.isa_type == "general" else ISA_SEOGMIN_TAX_FREE_LIMIT
    )
    isa_tax_free_income = min(income_shifted_to_isa, isa_tax_free_limit)
    isa_low_tax_income = max(income_shifted_to_isa - isa_tax_free_limit, 0.0)

    isa_tax_saving = isa_tax_free_income * DEFAULT_WITHHOLDING_TAX_RATE + isa_low_tax_income * max(
        DEFAULT_WITHHOLDING_TAX_RATE - ISA_LOW_TAX_RATE, 0.0
    )

    estimated_total_tax_saving = isa_tax_saving + irp_tax_credit

    return {
        "taxable_financial_income_before_account_allocation": safe_round(
            taxable_income_before, 0
        ),
        "estimated_income_shifted_to_isa": safe_round(income_shifted_to_isa, 0),
        "isa_tax_free_income_used": safe_round(isa_tax_free_income, 0),
        "isa_low_tax_income_used": safe_round(isa_low_tax_income, 0),
        "estimated_isa_tax_saving": safe_round(isa_tax_saving, 0),
        "estimated_irp_tax_credit": safe_round(irp_tax_credit, 0),
        "estimated_total_tax_saving": safe_round(estimated_total_tax_saving, 0),
        "note": "절세제안은 제외하고, 세후수익률 반영을 위한 간이 절세효과만 계산.",
    }



def calculate_six_strategy_tax_model(
    weights: Dict[str, float],
    expected_returns: pd.Series,
    total_asset: float,
    request: PortfolioRequest,
    account_buckets: Optional[
        Dict[str, Any]
    ] = None,
    include_standalone: bool = True,
) -> Dict[str, Any]:
    try:
        from .tax_advice import (
            calc_combined_tax_saving,
            calc_tax_advice,
        )
    except ImportError:
        from tax_advice import (
            calc_combined_tax_saving,
            calc_tax_advice,
        )

    normalized = normalize_weights(weights)
    portfolio = [
        {
            "asset_class": asset,
            "weight": safe_float(weight),
        }
        for asset, weight
        in normalized.items()
        if safe_float(weight) > 1e-12
    ]
    expected_return = sum(
        normalized.get(asset, 0.0)
        * safe_float(
            expected_returns.get(asset)
        )
        for asset in normalized
        if asset in expected_returns.index
    )
    expected_by_asset = {
        asset: safe_float(
            expected_returns.get(asset)
        )
        for asset in normalized
        if asset in expected_returns.index
    }

    if account_buckets is None:
        account_buckets = (
            allocate_account_buckets(
                normalized,
                total_asset,
                request,
            )
        )
    isa_status = account_buckets["isa"]
    irp_status = account_buckets["irp"]

    kwargs = {
        "isa_used_manwon": (
            request
            .isa_current_year_contribution
            / 10_000
        ),
        "pension_used_manwon": (
            request
            .irp_current_year_contribution
            / 10_000
        ),
        "realized_loss_manwon": (
            request.overseas_realized_loss
            / 10_000
        ),
        "other_financial_income": (
            resolve_external_financial_income_krw(
                request
            )
            / 1e8
        ),
        "marginal_income_tax_rate": (
            request
            .marginal_income_tax_rate
        ),
        "age": request.age,
        "horizon_years": (
            request
            .investment_horizon_years
        ),
        "near_term_need_manwon": (
            request.unique_need_amount
            / 10_000
        ),
        "near_term_need_years": (
            request.unique_profile.get(
                "liquidity_need_years"
            )
        ),
        "isa_opened": (
            request.isa_account_exists
        ),
        "isa_type": request.isa_type,
        "isa_can_open_new": (
            isa_status.get(
                "can_open_new",
                True,
            )
        ),
        "isa_usable": (
            isa_status.get("usable")
        ),
        "isa_years_until_liquid": (
            isa_status.get(
                "years_until_liquid"
            )
        ),
        "pension_usable": (
            irp_status.get("usable")
        ),
        "pension_tax_liability_sufficient": (
            request
            .pension_tax_liability_sufficient
        ),
        "pension_tax_credit_rate": (
            request.irp_tax_credit_rate
        ),
        "expected_returns_by_asset": (
            expected_by_asset or None
        ),
    }

    if include_standalone:
        standalone = calc_tax_advice(
            portfolio,
            expected_return,
            total_asset / 1e8,
            **kwargs,
        )
        combined = (
            calc_combined_tax_saving(
                portfolio,
                expected_return,
                total_asset / 1e8,
                standalone_cards=standalone,
                **kwargs,
            )
        )
    else:
        standalone = []
        combined = (
            calc_combined_tax_saving(
                portfolio,
                expected_return,
                total_asset / 1e8,
                calculate_standalone_cards=False,
                **kwargs,
            )
        )

    return {
        "model_version": (
            "six_strategy_combined_v1"
        ),
        "standalone": standalone,
        "combined": combined,
    }


def calculate_after_tax_return(
    weights: Dict[str, float],
    expected_returns: pd.Series,
    total_asset: float,
    request: PortfolioRequest,
    include_details: bool = True,
) -> Tuple[float, Dict[str, Any]]:
    weights = normalize_weights(weights)
    gross_profit = 0.0
    withholding_tax = 0.0

    for asset, weight in weights.items():
        if asset not in expected_returns.index:
            continue

        asset_expected_return = safe_float(
            expected_returns[asset]
        )
        asset_profit = (
            weight
            * total_asset
            * asset_expected_return
        )
        gross_profit += asset_profit

        income_profit = (
            estimate_income_profit_for_asset(
                asset=asset,
                weight=weight,
                expected_return=(
                    asset_expected_return
                ),
                total_asset=total_asset,
            )
        )
        if income_profit > 0:
            withholding_tax += (
                income_profit
                * DEFAULT_WITHHOLDING_TAX_RATE
            )

    portfolio_financial_income = (
        estimate_taxable_financial_income(
            weights,
            expected_returns,
            total_asset,
        )
    )
    external_financial_income = (
        resolve_external_financial_income_krw(
            request
        )
    )
    comprehensive_tax_status = (
        calculate_financial_income_comprehensive_tax_status(
            portfolio_financial_income=(
                portfolio_financial_income
            ),
            external_financial_income=(
                external_financial_income
            ),
            marginal_income_tax_rate=(
                request
                .marginal_income_tax_rate
            ),
        )
    )

    overseas_tax = (
        estimate_overseas_stock_capital_gains_tax(
            weights=weights,
            expected_returns=expected_returns,
            total_asset=total_asset,
            realized_gain_rate=(
                request
                .overseas_stock_realized_gain_rate
            ),
            realized_gain_krw=(
                request
                .overseas_realized_gain_krw
            ),
            realized_loss_krw=(
                request.overseas_realized_loss
            ),
        )
    )

    account_buckets = (
        allocate_account_buckets(
            weights,
            total_asset,
            request,
        )
    )

    if include_details:
        legacy_tax_saving_effect = (
            estimate_tax_saving_effect(
                weights=weights,
                expected_returns=(
                    expected_returns
                ),
                total_asset=total_asset,
                request=request,
                account_buckets=(
                    account_buckets
                ),
            )
        )
        legacy_account_only_tax_saving = (
            safe_float(
                legacy_tax_saving_effect.get(
                    "estimated_total_tax_saving"
                )
            )
        )
    else:
        legacy_tax_saving_effect = {}
        legacy_account_only_tax_saving = (
            0.0
        )

    six_strategy_tax_model = (
        calculate_six_strategy_tax_model(
            weights=weights,
            expected_returns=(
                expected_returns
            ),
            total_asset=total_asset,
            request=request,
            account_buckets=(
                account_buckets
            ),
            include_standalone=(
                include_details
            ),
        )
    )
    calculated_six_strategy_saving = (
        safe_float(
            six_strategy_tax_model
            .get("combined", {})
            .get("totalWon")
        )
    )

    additional_comprehensive_tax = (
        safe_float(
            comprehensive_tax_status[
                "estimated_additional_tax_"
                "attributable_to_portfolio"
            ]
        )
    )

    total_tax_before_saving = (
        withholding_tax
        + overseas_tax["estimated_tax"]
        + additional_comprehensive_tax
    )
    modeled_tax_reduction = min(
        calculated_six_strategy_saving,
        max(
            total_tax_before_saving,
            0.0,
        ),
    )
    total_tax_after_saving = max(
        total_tax_before_saving
        - modeled_tax_reduction,
        0.0,
    )

    after_tax_profit = (
        gross_profit
        - total_tax_after_saving
    )
    after_tax_return = (
        after_tax_profit / total_asset
        if total_asset > 0
        else 0.0
    )

    if not include_details:
        return (
            float(after_tax_return),
            {
                "gross_profit": safe_round(
                    gross_profit,
                    0,
                ),
                "financial_income_"
                "comprehensive_tax": (
                    comprehensive_tax_status
                ),
                "account_buckets": (
                    account_buckets
                ),
                "total_tax_after_saving": (
                    safe_round(
                        total_tax_after_saving,
                        0,
                    )
                ),
                "after_tax_profit": (
                    safe_round(
                        after_tax_profit,
                        0,
                    )
                ),
                "after_tax_return": (
                    safe_round(
                        after_tax_return,
                        6,
                    )
                ),
            },
        )

    tax_saving_effect = {
        **legacy_tax_saving_effect,
        "selection_model": (
            "six_strategy_combined_v1"
        ),
        "legacy_account_only_tax_saving": (
            safe_round(
                legacy_account_only_tax_saving,
                0,
            )
        ),
        "estimated_total_tax_saving": (
            safe_round(
                modeled_tax_reduction,
                0,
            )
        ),
        "calculated_six_strategy_saving": (
            safe_round(
                calculated_six_strategy_saving,
                0,
            )
        ),
        "modeled_tax_reduction": (
            safe_round(
                modeled_tax_reduction,
                0,
            )
        ),
        "unapplied_credit_or_saving": (
            safe_round(
                max(
                    calculated_six_strategy_saving
                    - modeled_tax_reduction,
                    0.0,
                ),
                0,
            )
        ),
    }

    tax_breakdown = {
        "gross_profit": safe_round(
            gross_profit,
            0,
        ),
        "withholding_tax_estimate": (
            safe_round(
                withholding_tax,
                0,
            )
        ),
        "financial_income_"
        "comprehensive_tax": (
            comprehensive_tax_status
        ),
        "additional_comprehensive_"
        "tax_estimate": (
            safe_round(
                additional_comprehensive_tax,
                0,
            )
        ),
        "additional_comprehensive_"
        "tax_total_estimate": (
            comprehensive_tax_status[
                "estimated_additional_"
                "tax_total"
            ]
        ),
        "additional_comprehensive_"
        "tax_external_baseline": (
            comprehensive_tax_status[
                "estimated_additional_tax_"
                "external_baseline"
            ]
        ),
        "overseas_stock_"
        "capital_gains_tax": overseas_tax,
        "account_buckets": (
            account_buckets
        ),
        "tax_saving_effect": (
            tax_saving_effect
        ),
        "six_strategy_tax_model": (
            six_strategy_tax_model
        ),
        "total_tax_before_saving": (
            safe_round(
                total_tax_before_saving,
                0,
            )
        ),
        "total_tax_after_saving": (
            safe_round(
                total_tax_after_saving,
                0,
            )
        ),
        "after_tax_profit": safe_round(
            after_tax_profit,
            0,
        ),
        "after_tax_return": safe_round(
            after_tax_return,
            6,
        ),
        "tax_disclaimer": (
            "세금 계산은 프로젝트용 간이 "
            "추정입니다. 실제 세액은 전체 "
            "소득, 실현손익, 공제 및 상품별 "
            "요건에 따라 달라집니다."
        ),
    }

    return (
        float(after_tax_return),
        tax_breakdown,
    )

