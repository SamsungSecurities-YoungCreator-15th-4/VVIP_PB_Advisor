from __future__ import annotations

from app.schemas.portfolio_api import PortfolioCalculationRequest
from app.services.portfolio_api_service import to_legacy_analysis_request


def test_strict_request_converts_to_pr74_internal_model() -> None:
    public = PortfolioCalculationRequest.model_validate(
        {
            "ips": {
                "total_asset_krw": 3_000_000_000,
                "target_after_tax_return_rate": 0.055,
                "risk_profile": "balanced",
                "investment_horizon_years": 8,
                "tax_sensitivity": "high",
                "liquidity_need": "mid",
                "unique": {
                    "need_amount_krw": 200_000_000,
                    "reserve_asset": "cash",
                },
                "tax": {
                    "external_financial_income_krw": 30_000_000,
                },
            },
            "current_portfolio": [
                {"asset_class": "domestic_equity", "weight_rate": 0.4},
                {"asset_class": "general_bond", "weight_rate": 0.4},
                {"asset_class": "cash", "weight_rate": 0.2},
            ],
            "scenario": {
                "base_interest_rate": 0.035,
                "base_fx_rate_krw_per_usd": 1400,
                "stress_interest_rate_shock_rate": 0.01,
                "stress_fx_shock_rate": 0.1,
            },
        }
    )

    internal = to_legacy_analysis_request(public)
    assert internal.ips.total_asset == 3_000_000_000
    assert internal.ips.current_weights == {
        "domestic_equity": 0.4,
        "general_bond": 0.4,
        "cash": 0.2,
    }
    assert internal.ips.external_financial_income_krw == 30_000_000
    assert internal.scenario.stress_interest_rate_shock == 0.01
    assert internal.scenario.stress_fx_shock == 0.1
