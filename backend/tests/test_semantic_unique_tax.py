# ruff: noqa: E501

from __future__ import annotations

from app.portfolio import adapters, tax_llm_fallback, unique_semantic


def _weights(**overrides):
    result = {asset: 0.0 for asset in unique_semantic.ASSET_TICKERS}
    result.update(overrides)
    return result


def test_increase_and_decrease_are_relative_hard_filters_and_allow_equality():
    current = _weights(overseas_dividend=0.2, overseas_growth=0.3, cash=0.5)
    candidate_equal = dict(current)
    profile = {
        "semantic_constraints": [
            {
                "subject_type": "asset",
                "subject": "overseas_dividend",
                "operator": "increase",
                "value_ratio": None,
            },
            {
                "subject_type": "asset",
                "subject": "overseas_growth",
                "operator": "decrease",
                "value_ratio": None,
            },
        ]
    }

    passed, violations = unique_semantic.evaluate_unique_constraints(
        candidate_weights=candidate_equal,
        unique_profile=profile,
        current_weights=current,
    )

    assert passed is True
    assert violations == []


def test_direction_constraint_rejects_wrong_direction():
    current = _weights(overseas_dividend=0.2, cash=0.8)
    candidate = _weights(overseas_dividend=0.1, cash=0.9)
    profile = {
        "semantic_constraints": [
            {
                "subject_type": "asset",
                "subject": "overseas_dividend",
                "operator": "increase",
                "value_ratio": None,
            }
        ]
    }

    passed, violations = unique_semantic.evaluate_unique_constraints(
        candidate_weights=candidate,
        unique_profile=profile,
        current_weights=current,
    )

    assert passed is False
    assert violations[0]["subject"] == "overseas_dividend"


def test_target_uses_the_precision_explicitly_written_by_customer():
    profile = {
        "semantic_constraints": [
            {
                "subject_type": "asset",
                "subject": "overseas_dividend",
                "operator": "target",
                "value_ratio": 0.20,
                "precision_digits": 0,
            }
        ]
    }

    passed, _ = unique_semantic.evaluate_unique_constraints(
        candidate_weights=_weights(overseas_dividend=0.204, cash=0.796),
        unique_profile=profile,
        current_weights=None,
    )
    rejected, _ = unique_semantic.evaluate_unique_constraints(
        candidate_weights=_weights(overseas_dividend=0.216, cash=0.784),
        unique_profile=profile,
        current_weights=None,
    )

    assert passed is True  # 20.4% -> 고객이 쓴 정수 정밀도로 20%
    assert rejected is False  # 21.6% -> 22%


def test_exclusion_is_exact_zero_constraint():
    profile = {
        "semantic_constraints": [
            {
                "subject_type": "asset",
                "subject": "gold",
                "operator": "exclude",
                "value_ratio": 0.0,
            }
        ]
    }

    assert unique_semantic.get_excluded_assets(profile) == {"gold"}
    passed, _ = unique_semantic.evaluate_unique_constraints(
        candidate_weights=_weights(cash=1.0),
        unique_profile=profile,
        current_weights=None,
    )
    rejected, _ = unique_semantic.evaluate_unique_constraints(
        candidate_weights=_weights(gold=0.01, cash=0.99),
        unique_profile=profile,
        current_weights=None,
    )
    assert passed is True
    assert rejected is False


def test_group_direction_uses_sum_of_group_assets():
    current = _weights(domestic_equity=0.1, overseas_growth=0.2, cash=0.7)
    candidate = _weights(domestic_equity=0.15, overseas_growth=0.2, cash=0.65)
    profile = {
        "semantic_constraints": [
            {
                "subject_type": "group",
                "subject": "equity",
                "operator": "increase",
                "value_ratio": None,
            }
        ]
    }
    passed, _ = unique_semantic.evaluate_unique_constraints(
        candidate_weights=candidate,
        unique_profile=profile,
        current_weights=current,
    )
    assert passed is True


def test_unique_llm_only_supplements_missing_isa_irp_values(monkeypatch):
    deterministic = {
        "items": [],
        "liquidity_need_amount": 300_000_000,
        "liquidity_need_years": 1.0,
        "isa": {
            "detected": True,
            "account_exists": True,
            "start_year": 2022,
            "account_age_years": 4.0,
            "cumulative_contribution": 70_000_000,
        },
        "irp": {
            "detected": True,
            "account_exists": True,
            "start_year": 2019,
            "account_age_years": 7.0,
            "cumulative_contribution": 20_000_000,
            "current_year_contribution": 0.0,
        },
        "parser_note": "deterministic",
    }
    monkeypatch.setattr(
        unique_semantic,
        "parse_unique_semantic",
        lambda value: {
            "status": "live",
            "version": "test",
            "constraints": [],
            "liquidity": {"amount_krw": 900_000_000, "years_until_need": 5.0, "evidence": "e"},
            "accounts": {
                "isa": {
                    "account_exists": False,
                    "opened_year": 2020,
                    "cumulative_contribution_krw": 10_000_000,
                    "current_year_contribution_krw": 5_000_000,
                    "evidence": "e",
                },
                "irp": {
                    "account_exists": False,
                    "opened_year": 2020,
                    "cumulative_contribution_krw": 10_000_000,
                    "current_year_contribution_krw": 9_000_000,
                    "evidence": "e",
                },
            },
            "advisory_only": [],
            "unmatched_segments": [],
            "discarded_claims": [],
        },
    )

    enriched = unique_semantic.enrich_unique_profile(deterministic, "dummy")

    assert enriched["liquidity_need_amount"] == 300_000_000
    assert enriched["liquidity_need_years"] == 1.0
    assert enriched["isa"]["account_exists"] is True
    assert enriched["isa"]["start_year"] == 2022
    assert enriched["isa"]["cumulative_contribution"] == 70_000_000
    assert enriched["isa"]["current_year_contribution"] == 5_000_000
    assert enriched["irp"]["account_exists"] is True
    assert enriched["irp"]["start_year"] == 2019
    assert enriched["irp"]["current_year_contribution"] == 0.0


def test_tax_llm_never_overwrites_deterministic_fact(monkeypatch):
    profile = {
        "normalized_text": "금융소득 3천만원",
        "facts": {"external_financial_income_krw": 30_000_000},
        "routes": [{"missing_inputs": ["marginal_income_tax_rate"]}],
        "unmatched_text": [],
        "parser_note": "deterministic",
    }
    monkeypatch.setattr(
        tax_llm_fallback,
        "_parse_tax_fallback",
        lambda value: {
            "status": "live",
            "version": "test",
            "facts": {
                "external_financial_income_krw": 300_000_000,
                "marginal_income_tax_rate": 0.385,
            },
            "evidence": {},
            "discarded_claims": [],
            "unmatched_segments": [],
        },
    )

    enriched = tax_llm_fallback.enrich_tax_profile_with_llm(profile)

    assert enriched["facts"]["external_financial_income_krw"] == 30_000_000
    assert enriched["facts"]["marginal_income_tax_rate"] == 0.385
    assert enriched["llm_fallback"]["conflicts"][0]["selected"] == "deterministic"
    assert "semantic_constraints" not in enriched


def test_money_parser_supports_composite_korean_amounts():
    assert 150_000_000 in unique_semantic._parse_korean_money_candidates("1억 5천만원 필요")
    assert 30_000_000 in tax_llm_fallback._money_candidates("금융소득 3천만원")

def test_gold_alias_does_not_match_interest_rate_or_pension_words():
    assert unique_semantic._subject_is_supported_by_evidence(
        "asset",
        "gold",
        "금리가 낮아질 것 같아 장기채를 늘리고 싶다",
    ) is False
    assert unique_semantic._subject_is_supported_by_evidence(
        "asset",
        "gold",
        "연금 계좌는 유지하고 싶다",
    ) is False
    assert unique_semantic._subject_is_supported_by_evidence(
        "asset",
        "gold",
        "금을 조금 줄이고 싶다",
    ) is True


def test_new_unique_text_semantics_override_stale_profile(monkeypatch):
    stale_constraint = {
        "subject_type": "asset",
        "subject": "gold",
        "operator": "exclude",
        "value_ratio": 0.0,
    }
    fresh_constraint = {
        "subject_type": "asset",
        "subject": "overseas_dividend",
        "operator": "increase",
        "value_ratio": None,
        "evidence": "미국 배당주를 늘리고 싶다",
    }

    monkeypatch.setattr(
        unique_semantic,
        "parse_unique_semantic",
        lambda value: {
            "status": "live",
            "version": "test",
            "constraints": [fresh_constraint],
            "liquidity": {},
            "accounts": {"isa": {}, "irp": {}},
            "advisory_only": [],
            "unmatched_segments": [],
            "discarded_claims": [],
        },
    )

    result = adapters.apply_unique_profile_to_ips_payload(
        {
            "unique_need_amount": 0.0,
            "unique_asset": "cash",
            "unique_profile": {
                "semantic_constraints": [stale_constraint],
                "semantic_audit": {"status": "old"},
                "preserved_custom_field": "keep",
            },
        },
        "미국 배당주를 늘리고 싶다",
        [],
    )

    assert result["unique_profile"]["semantic_constraints"] == [fresh_constraint]
    assert result["unique_profile"]["semantic_audit"]["status"] == "live"
    assert result["unique_profile"]["preserved_custom_field"] == "keep"

