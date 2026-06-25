"""PR #143 리뷰 반영 회귀 테스트."""

from unittest.mock import patch

from app.portfolio import unique_semantic
from app.portfolio.adapters import extract_flat_ips_payload
from app.portfolio.tax_parser import (
    apply_tax_profile_to_ips_payload,
    build_tax_routes,
)


def test_calculate_path_does_not_call_tax_llm_by_default():
    with patch(
        "app.portfolio.tax_llm_fallback.enrich_tax_profile_with_llm",
        side_effect=AssertionError("calculate 기본 경로에서 LLM을 호출하면 안 됩니다."),
    ) as mocked:
        result = apply_tax_profile_to_ips_payload(
            {},
            "세금 관련 추가 검토가 필요합니다.",
        )

    mocked.assert_not_called()
    assert "tax_profile" in result


def test_tax_llm_can_be_explicitly_enabled():
    def fake_enrich(profile):
        enriched = dict(profile)
        enriched["facts"] = dict(profile.get("facts") or {})
        enriched["facts"]["external_financial_income_krw"] = 10_000_000.0
        return enriched

    with patch(
        "app.portfolio.tax_llm_fallback.enrich_tax_profile_with_llm",
        side_effect=fake_enrich,
    ) as mocked:
        result = apply_tax_profile_to_ips_payload(
            {},
            "외부 금융소득은 1천만원입니다.",
            allow_llm_fallback=True,
        )

    mocked.assert_called_once()
    assert result["tax_profile"]["facts"]["external_financial_income_krw"] == 10_000_000.0


def test_public_tax_route_builder():
    routes = build_tax_routes(
        [
            {
                "topic": "gift_tax",
                "route": "transfer.gift",
                "status": "current",
                "support_level": "calculation",
                "recommendation_effect": "liquidity_constraint",
                "required_facts": ["transfer_amount_krw"],
            }
        ],
        {"transfer_amount_krw": 100_000_000.0},
    )

    assert routes[0]["can_calculate"] is True
    assert routes[0]["missing_inputs"] == []


def test_nested_rrttllu_mapping_is_preserved_exactly():
    rrttllu = {
        "Return": "연 7%",
        "Risk": "균형형",
        "Time": "10년",
        "Tax": "금융소득 3천만원",
        "Liquidity": "중간",
        "Legal": "가업승계 관련 전문가 검토",
        "Unique": "3년 후 주택자금 5억원",
    }
    payload = {
        "ips_json": {
            "Goal": "장기 자산 증식",
            "Asset": 50,
            "RRTTLLU": rrttllu,
        }
    }

    flat = extract_flat_ips_payload(payload)

    assert flat["Goal"] == "장기 자산 증식"
    assert flat["Asset"] == 50
    for key, value in rrttllu.items():
        assert flat[key] == value


def test_tax_enrichment_does_not_overwrite_other_rrttllu_fields():
    original = {
        "liquidity_need": "high",
        "legal_text": "가업승계 관련 전문가 검토",
        "unique_raw": "3년 후 주택자금 5억원",
    }

    result = apply_tax_profile_to_ips_payload(
        original,
        "금융소득 3천만원",
    )

    assert result["liquidity_need"] == original["liquidity_need"]
    assert result["legal_text"] == original["legal_text"]
    assert result["unique_raw"] == original["unique_raw"]


def test_current_weights_normalization_is_cached():
    unique_semantic._normalize_weight_items.cache_clear()
    weights = {"domestic_equity": 0.5, "cash": 0.5}

    first = unique_semantic._normalize_current_weight_map(
        {**weights, "request_id": "first-request"}
    )
    second = unique_semantic._normalize_current_weight_map(
        {**weights, "request_id": "second-request"}
    )
    cache_info = unique_semantic._normalize_weight_items.cache_info()

    assert first == second
    assert cache_info.hits >= 1


def test_current_weights_normalization_rejects_non_dict_input():
    assert unique_semantic._normalize_current_weight_map(["not", "a", "dict"]) is None


def test_portfolio_logic_does_not_import_removed_money_unit_constant():
    import ast
    from pathlib import Path

    source_path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "portfolio"
        / "portfolio_logic.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))

    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "adapters"
        for alias in node.names
    }

    assert "KOREAN_MONEY_UNITS" not in imported_names


def test_adapters_explicitly_disable_tax_llm_on_calculate_paths():
    import ast
    from pathlib import Path

    source_path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "portfolio"
        / "adapters.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))

    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Name):
            function_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            function_name = node.func.attr
        else:
            continue

        if function_name == "apply_tax_profile_to_ips_payload":
            calls.append(node)

    assert len(calls) >= 2

    for call in calls:
        keyword = next(
            (
                item
                for item in call.keywords
                if item.arg == "allow_llm_fallback"
            ),
            None,
        )
        assert keyword is not None
        assert isinstance(keyword.value, ast.Constant)
        assert keyword.value.value is False


def test_adapters_use_conditional_non_blocking_tax_llm_mode():
    import ast
    from pathlib import Path

    source_path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "portfolio"
        / "adapters.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))

    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            function_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            function_name = node.func.attr
        else:
            continue
        if function_name == "apply_tax_profile_to_ips_payload":
            calls.append(node)

    assert len(calls) >= 2
    for call in calls:
        keywords = {item.arg: item.value for item in call.keywords if item.arg}
        assert isinstance(keywords["allow_llm_fallback"], ast.Constant)
        assert keywords["allow_llm_fallback"].value is False
        assert isinstance(keywords["llm_fallback_mode"], ast.Constant)
        assert keywords["llm_fallback_mode"].value == "conditional_non_blocking"


def test_tax_non_blocking_skips_llm_when_parser_is_sufficient(monkeypatch):
    from app.portfolio import tax_llm_fallback

    monkeypatch.setattr(
        tax_llm_fallback,
        "_should_call_fallback",
        lambda profile: False,
    )
    monkeypatch.setattr(
        tax_llm_fallback,
        "enrich_tax_profile_with_llm",
        lambda profile: (_ for _ in ()).throw(
            AssertionError("충분한 parser 결과에는 LLM을 호출하면 안 됩니다.")
        ),
    )

    profile = {
        "raw_text": "금융소득 3천만원",
        "facts": {"external_financial_income_krw": 30_000_000.0},
    }
    result = tax_llm_fallback.enrich_tax_profile_with_llm_non_blocking(profile)
    assert result == profile


def test_tax_non_blocking_runs_llm_only_for_incomplete_profile(monkeypatch):
    from app.portfolio import tax_llm_fallback

    tax_llm_fallback._TAX_LLM_BACKGROUND_FUTURES.clear()
    tax_llm_fallback._TAX_LLM_BACKGROUND_RESULTS.clear()
    monkeypatch.setattr(
        tax_llm_fallback,
        "_should_call_fallback",
        lambda profile: True,
    )

    calls = []

    def fake_enrich(profile):
        calls.append(profile["raw_text"])
        result = dict(profile)
        result["facts"] = {
            **(profile.get("facts") or {}),
            "external_financial_income_krw": 30_000_000.0,
        }
        result["llm_fallback"] = {"status": "live"}
        return result

    monkeypatch.setattr(
        tax_llm_fallback,
        "enrich_tax_profile_with_llm",
        fake_enrich,
    )
    monkeypatch.setenv("PORTFOLIO_TAX_LLM_MAX_WAIT_SECONDS", "1")

    profile = {
        "raw_text": "다른 곳에서 이자도 받았는데 정확한 분류가 필요합니다.",
        "facts": {},
        "unmatched_segments": [
            "다른 곳에서 이자도 받았는데 정확한 분류가 필요합니다."
        ],
    }
    result = tax_llm_fallback.enrich_tax_profile_with_llm_non_blocking(profile)

    assert calls == [profile["raw_text"]]
    assert result["facts"]["external_financial_income_krw"] == 30_000_000.0

