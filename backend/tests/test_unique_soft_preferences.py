# ruff: noqa: E501
from __future__ import annotations

import pytest

from app.portfolio import unique_semantic
from app.portfolio.generation import (
    build_portfolio_b_fallback_rank_tuple,
    build_portfolio_b_rank_tuple,
    build_selection_rank_tuple,
)


def _weights(**overrides):
    result = {asset: 0.0 for asset in unique_semantic.ASSET_TICKERS}
    result.update(overrides)
    return result


def _metrics(**overrides):
    result = {
        "after_tax_return": 0.08,
        "expected_return": 0.09,
        "sharpe_ratio": 1.0,
        "historical_var_95_daily_loss": 0.02,
        "risk_contribution_max_share": 0.30,
        "volatility": 0.10,
        "mdd": -0.15,
    }
    result.update(overrides)
    return result


def test_interest_and_cash_phrases_are_soft_preferences():
    text = "미국 배당주에 관심이 있고 비상자금은 어느 정도 남겨두고 싶습니다."
    result = unique_semantic._validate_llm_payload(
        text,
        {
            "constraints": [],
            "soft_preferences": [
                {
                    "subject_type": "asset",
                    "subject": "overseas_dividend",
                    "direction": "prefer",
                    "evidence": "미국 배당주에 관심이 있고",
                },
                {
                    "subject_type": "group",
                    "subject": "cash_like",
                    "direction": "prefer",
                    "evidence": "비상자금은 어느 정도 남겨두고 싶습니다",
                },
            ],
            "liquidity": {},
            "accounts": {},
            "advisory_only": [],
            "unmatched_segments": [],
        },
    )
    assert [item["subject"] for item in result["soft_preferences"]] == [
        "overseas_dividend",
        "cash_like",
    ]


def test_more_specific_asset_wins_over_overlapping_group():
    text = "해외주식 중 미국 배당주를 선호합니다."
    result = unique_semantic._validate_llm_payload(
        text,
        {
            "constraints": [],
            "soft_preferences": [
                {
                    "subject_type": "group",
                    "subject": "overseas_equity",
                    "direction": "prefer",
                    "evidence": text,
                },
                {
                    "subject_type": "asset",
                    "subject": "overseas_dividend",
                    "direction": "prefer",
                    "evidence": text,
                },
            ],
            "liquidity": {},
            "accounts": {},
            "advisory_only": [],
            "unmatched_segments": [],
        },
    )
    assert [item["subject"] for item in result["soft_preferences"]] == [
        "overseas_dividend"
    ]
    assert any(
        item["reason"] == "less_specific_group_duplicate"
        for item in result["discarded_claims"]
    )


def test_tax_concern_alone_is_not_asset_avoidance():
    text = "해외주식 양도세 부담이 걱정됩니다."
    result = unique_semantic._validate_llm_payload(
        text,
        {
            "constraints": [],
            "soft_preferences": [
                {
                    "subject_type": "group",
                    "subject": "overseas_equity",
                    "direction": "avoid",
                    "evidence": text,
                }
            ],
            "liquidity": {},
            "accounts": {},
            "advisory_only": [],
            "unmatched_segments": [],
        },
    )
    assert result["soft_preferences"] == []
    assert any(
        item["reason"] == "tax_context_not_asset_preference"
        for item in result["discarded_claims"]
    )


def test_explicit_increase_is_not_duplicated_as_soft_preference():
    text = "미국 배당주 비중을 늘리고 싶습니다."
    result = unique_semantic._validate_llm_payload(
        text,
        {
            "constraints": [],
            "soft_preferences": [
                {
                    "subject_type": "asset",
                    "subject": "overseas_dividend",
                    "direction": "prefer",
                    "evidence": text,
                }
            ],
            "liquidity": {},
            "accounts": {},
            "advisory_only": [],
            "unmatched_segments": [],
        },
    )
    assert result["soft_preferences"] == []


def test_soft_preference_subset_is_removed_when_matching_hard_constraint():
    text = "미국 배당주를 선호해서 비중을 늘리고 싶습니다."
    result = unique_semantic._validate_llm_payload(
        text,
        {
            "constraints": [
                {
                    "subject_type": "asset",
                    "subject": "overseas_dividend",
                    "operator": "increase",
                    "value_pct": None,
                    "precision_digits": None,
                    "evidence": text,
                }
            ],
            "soft_preferences": [
                {
                    "subject_type": "asset",
                    "subject": "overseas_dividend",
                    "direction": "prefer",
                    "evidence": "미국 배당주를 선호해서",
                }
            ],
            "liquidity": {},
            "accounts": {},
            "advisory_only": [],
            "unmatched_segments": [],
        },
    )

    assert len(result["constraints"]) == 1
    assert result["soft_preferences"] == []
    assert any(
        item["reason"] == "duplicate_of_hard_constraint"
        for item in result["discarded_claims"]
    )


@pytest.mark.parametrize(
    "unique_profile",
    [
        None,
        [],
        "invalid-profile",
        {"soft_preferences": "not-a-list"},
        {"soft_preferences": [None, "invalid-item"]},
    ],
)
def test_alignment_handles_invalid_unique_profile_shape(unique_profile):
    result = unique_semantic.calculate_soft_preference_alignment(
        candidate_weights=_weights(cash=1.0),
        unique_profile=unique_profile,
    )

    assert result["score"] == 0.0
    assert result["preference_count"] == 0
    assert result["details"] == []


def test_alignment_uses_actual_weights_and_equal_preference_weights():
    profile = {
        "soft_preferences": [
            {"subject_type": "asset", "subject": "overseas_dividend", "direction": "prefer"},
            {"subject_type": "asset", "subject": "low_coupon_bond", "direction": "prefer"},
        ]
    }
    result = unique_semantic.calculate_soft_preference_alignment(
        candidate_weights=_weights(overseas_dividend=0.20, low_coupon_bond=0.10, cash=0.70),
        unique_profile=profile,
    )
    assert result["score"] == pytest.approx(0.15)


def test_a_soft_preference_only_breaks_same_display_value_ties():
    preferred = build_selection_rank_tuple(_metrics(after_tax_return=0.0801), 0.90)
    less_preferred = build_selection_rank_tuple(_metrics(after_tax_return=0.0802), 0.10)
    clearly_higher = build_selection_rank_tuple(_metrics(after_tax_return=0.0811), 0.0)
    assert preferred > less_preferred
    assert clearly_higher > preferred


def test_b_soft_preference_only_breaks_same_1bp_band_ties():
    preferred = build_portfolio_b_rank_tuple(_metrics(risk_contribution_max_share=0.30001), 0.90)
    less_preferred = build_portfolio_b_rank_tuple(_metrics(risk_contribution_max_share=0.30002), 0.10)
    clearly_lower = build_portfolio_b_rank_tuple(_metrics(risk_contribution_max_share=0.29980), 0.0)
    assert preferred < less_preferred
    assert clearly_lower < preferred


def test_b_fallback_keeps_target_shortfall_priority():
    preferred = build_portfolio_b_fallback_rank_tuple(_metrics(after_tax_return=0.0791), 0.08, 0.90)
    less_preferred = build_portfolio_b_fallback_rank_tuple(_metrics(after_tax_return=0.0792), 0.08, 0.10)
    clearly_smaller = build_portfolio_b_fallback_rank_tuple(_metrics(after_tax_return=0.0796), 0.08, 0.0)
    assert preferred < less_preferred
    assert clearly_smaller < preferred
