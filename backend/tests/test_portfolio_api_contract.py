from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.portfolio_api import PortfolioCalculationRequest


def valid_payload() -> dict:
    return {
        "api_version": "portfolio-api-v1",
        "client_id": "client-1",
        "consultation_id": "consultation-1",
        "ips": {
            "total_asset_krw": 5_000_000_000,
            "target_after_tax_return_rate": 0.06,
            "risk_profile": "balanced",
            "investment_horizon_years": 10,
            "tax_sensitivity": "high",
            "liquidity_need": "mid",
            "unique": {
                "raw_text": "내년 전세자금 3억 필요. 미국 배당주 선호.",
                "need_amount_krw": 300_000_000,
                "reserve_asset": "cash",
            },
        },
        "current_portfolio": [
            {"asset_class": "domestic_equity", "weight_rate": 0.30},
            {"asset_class": "overseas_dividend", "weight_rate": 0.30},
            {"asset_class": "general_bond", "weight_rate": 0.30},
            {"asset_class": "cash", "weight_rate": 0.10},
        ],
        "scenario": {
            "base_interest_rate": 0.035,
            "base_fx_rate_krw_per_usd": 1400,
            "stress_interest_rate_shock_rate": 0.01,
            "stress_fx_shock_rate": 0.10,
        },
    }


def test_public_request_accepts_only_one_shape() -> None:
    request = PortfolioCalculationRequest.model_validate(valid_payload())
    assert request.ips.total_asset_krw == 5_000_000_000
    assert request.ips.target_after_tax_return_rate == 0.06


@pytest.mark.parametrize(
    "extra_field",
    ["ips_json", "selected_benchmark", "target_after_tax_return"],
)
def test_legacy_or_ambiguous_fields_are_rejected(extra_field: str) -> None:
    payload = valid_payload()
    payload[extra_field] = {}
    with pytest.raises(ValidationError):
        PortfolioCalculationRequest.model_validate(payload)


def test_rate_unit_is_decimal_only() -> None:
    payload = valid_payload()
    payload["ips"]["target_after_tax_return_rate"] = 6
    with pytest.raises(ValidationError):
        PortfolioCalculationRequest.model_validate(payload)


def test_weight_unit_is_decimal_only() -> None:
    payload = valid_payload()
    payload["current_portfolio"][0]["weight_rate"] = 30
    with pytest.raises(ValidationError):
        PortfolioCalculationRequest.model_validate(payload)


def test_weights_must_sum_to_one() -> None:
    payload = valid_payload()
    payload["current_portfolio"][0]["weight_rate"] = 0.20
    with pytest.raises(ValidationError):
        PortfolioCalculationRequest.model_validate(payload)


def test_duplicate_assets_are_rejected() -> None:
    payload = valid_payload()
    payload["current_portfolio"][1]["asset_class"] = "domestic_equity"
    with pytest.raises(ValidationError):
        PortfolioCalculationRequest.model_validate(payload)


def test_unique_need_cannot_exceed_total_asset() -> None:
    payload = valid_payload()
    payload["ips"]["unique"]["need_amount_krw"] = 6_000_000_000
    with pytest.raises(ValidationError):
        PortfolioCalculationRequest.model_validate(payload)
