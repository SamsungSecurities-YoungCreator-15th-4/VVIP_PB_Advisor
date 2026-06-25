from __future__ import annotations

import numpy as np
import pandas as pd

from app.portfolio.constants import (
    ISA_GENERAL_TAX_FREE_LIMIT,
    ISA_SEOGMIN_TAX_FREE_LIMIT,
)
from app.portfolio.generation import (
    calculate_portfolio_return_correlation,
)
from app.portfolio.metrics import (
    build_monte_carlo_scenario_context,
    calculate_monte_carlo_metric_ranges,
    calculate_risk_contribution,
)
from app.portfolio.prices import (
    _download_close_prices_with_individual_retry,
    _supplement_missing_assets_from_snapshot,
)
from app.portfolio.tax_advice import (
    _resolve_isa_tax_free_limit,
)
from app.portfolio.unique_semantic import (
    enrich_unique_profile,
)


def test_risk_contribution_concentration_is_renormalized() -> None:
    assets = [
        "domestic_equity",
        "general_bond",
    ]
    weights = np.array(
        [0.1, 0.9],
        dtype=float,
    )
    covariance = pd.DataFrame(
        [
            [1.0, -0.2],
            [-0.2, 0.05],
        ],
        index=assets,
        columns=assets,
    )

    result = calculate_risk_contribution(
        assets,
        weights,
        covariance,
    )

    assert (
        result["by_asset"][
            "domestic_equity"
        ]
        < 0
    )
    assert (
        result["by_asset"][
            "general_bond"
        ]
        > 1
    )
    assert (
        0.0
        <= result["max_share"]
        <= 1.0
    )
    assert 0.0 <= result["hhi"] <= 1.0
    assert (
        result[
            "concentration_share_sum"
        ]
        == 1.0
    )


def test_undefined_portfolio_correlation_returns_zero() -> None:
    returns = pd.DataFrame(
        {
            "cash": [
                0.0,
                0.0,
                0.0,
                0.0,
            ],
        }
    )
    correlation = (
        calculate_portfolio_return_correlation(
            {"cash": 1.0},
            {"cash": 1.0},
            returns,
        )
    )
    assert correlation == 0.0


def test_isa_type_uses_common_limits() -> None:
    assert (
        _resolve_isa_tax_free_limit(
            "general"
        )
        == ISA_GENERAL_TAX_FREE_LIMIT
    )
    assert (
        _resolve_isa_tax_free_limit(
            "seogmin"
        )
        == ISA_SEOGMIN_TAX_FREE_LIMIT
    )


def test_existing_soft_preferences_are_preserved(
    monkeypatch,
) -> None:
    existing = {
        "subject_type": "asset",
        "subject": "gold",
        "direction": "avoid",
        "evidence": (
            "금 투자는 부담스럽다"
        ),
    }
    incoming = {
        "subject_type": "asset",
        "subject": (
            "overseas_dividend"
        ),
        "direction": "prefer",
        "evidence": (
            "미국 배당주에 관심이 있다"
        ),
    }

    monkeypatch.setattr(
        "app.portfolio.unique_semantic."
        "parse_unique_semantic",
        lambda _value: {
            "status": "live",
            "version": "test",
            "constraints": [],
            "soft_preferences": [
                incoming
            ],
            "liquidity": {},
            "accounts": {
                "isa": {},
                "irp": {},
            },
            "advisory_only": [],
            "unmatched_segments": [],
            "discarded_claims": [],
        },
    )

    result = enrich_unique_profile(
        {
            "soft_preferences": [
                existing
            ]
        },
        "test",
    )
    assert (
        result["soft_preferences"]
        == [
            existing,
            incoming,
        ]
    )


def test_bulk_missing_asset_is_retried_individually(
    monkeypatch,
) -> None:
    index = pd.date_range(
        "2025-01-01",
        periods=3,
        freq="D",
    )
    bulk = pd.DataFrame(
        [
            [1.0],
            [1.1],
            [1.2],
        ],
        index=index,
        columns=pd.MultiIndex.from_tuples(
            [
                (
                    "Close",
                    "AAA",
                )
            ]
        ),
    )
    individual = pd.DataFrame(
        {
            "Close": [
                2.0,
                2.1,
                2.2,
            ]
        },
        index=index,
    )

    def fake_download(
        tickers,
        **_kwargs,
    ):
        if isinstance(tickers, list):
            return bulk
        assert tickers == "BBB"
        return individual

    monkeypatch.setattr(
        "app.portfolio.prices."
        "yf.download",
        fake_download,
    )

    (
        prices,
        attempted,
        recovered,
        missing,
    ) = (
        _download_close_prices_with_individual_retry(
            {
                "asset_a": "AAA",
                "asset_b": "BBB",
            },
            "1y",
        )
    )

    assert list(prices.columns) == [
        "asset_a",
        "asset_b",
    ]
    assert attempted == ["asset_b"]
    assert recovered == ["asset_b"]
    assert missing == []


def test_snapshot_supplements_only_missing_asset() -> None:
    index = pd.date_range(
        "2025-01-01",
        periods=3,
        freq="D",
    )
    live = pd.DataFrame(
        {
            "asset_a": [
                1.0,
                1.1,
                1.2,
            ]
        },
        index=index,
    )
    snapshot = pd.DataFrame(
        {
            "asset_b": [
                2.0,
                2.1,
                2.2,
            ]
        },
        index=index,
    )

    (
        combined,
        supplemented,
        remaining,
    ) = (
        _supplement_missing_assets_from_snapshot(
            live,
            ["asset_b"],
            snapshot,
        )
    )

    assert set(combined.columns) == {
        "asset_a",
        "asset_b",
    }
    assert supplemented == ["asset_b"]
    assert remaining == []


def test_shared_monte_carlo_context_matches_direct_path() -> None:
    rng = np.random.default_rng(7)
    index = pd.date_range(
        "2025-01-01",
        periods=100,
        freq="B",
    )
    returns = pd.DataFrame(
        {
            "domestic_equity": (
                rng.normal(
                    0.0003,
                    0.01,
                    len(index),
                )
            ),
            "general_bond": (
                rng.normal(
                    0.0001,
                    0.003,
                    len(index),
                )
            ),
        },
        index=index,
    )
    expected = pd.Series(
        {
            "domestic_equity": 0.07,
            "general_bond": 0.03,
        }
    )
    weights = {
        "domestic_equity": 0.6,
        "general_bond": 0.4,
    }
    tax_breakdown = {
        "gross_profit": 10_000_000,
        "total_tax_after_saving": (
            1_000_000
        ),
    }

    context = (
        build_monte_carlo_scenario_context(
            returns,
            expected,
            investment_horizon_years=1,
            random_seed=42,
            num_simulations=100,
        )
    )
    reused = (
        calculate_monte_carlo_metric_ranges(
            weights,
            returns,
            expected,
            total_asset=(
                1_000_000_000
            ),
            investment_horizon_years=1,
            tax_breakdown=tax_breakdown,
            random_seed=42,
            num_simulations=100,
            scenario_context=context,
        )
    )
    direct = (
        calculate_monte_carlo_metric_ranges(
            weights,
            returns,
            expected,
            total_asset=(
                1_000_000_000
            ),
            investment_horizon_years=1,
            tax_breakdown=tax_breakdown,
            random_seed=42,
            num_simulations=100,
        )
    )

    assert (
        reused["scenario_basis_id"]
        == direct["scenario_basis_id"]
    )
    assert (
        reused["after_tax_return"]
        == direct["after_tax_return"]
    )
    assert reused["mdd"] == direct["mdd"]
