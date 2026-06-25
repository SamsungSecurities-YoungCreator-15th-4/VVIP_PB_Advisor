# ruff: noqa: E501

from __future__ import annotations

from app.portfolio import legal_semantic


def _categories(text: str):
    return {
        item["category"]
        for item in legal_semantic.parse_legal_semantic(text)["issues"]
    }


def test_three_persona_legal_phrases_are_covered_without_llm(monkeypatch):
    monkeypatch.setattr(
        legal_semantic,
        "_call_legal_llm",
        lambda text: (_ for _ in ()).throw(AssertionError("LLM should not be called")),
    )

    assert "business_succession" in _categories("기업 상속 공제 요건")
    assert "overseas_stock_reporting" in _categories("해외주식 대주주 요건 및 신고 의무 준수")
    assert "gift_fund_source" in _categories("증여세법·자금출처조사 대비")


def test_legal_llm_is_advisory_only_and_uses_evidence(monkeypatch):
    monkeypatch.setattr(legal_semantic, "env_enabled", lambda name, default=True: True)
    monkeypatch.setattr(
        legal_semantic,
        "_call_legal_llm",
        lambda text: (
            {
                "issues": [
                    {
                        "category": "contractual_restriction",
                        "evidence": "담보 약정 때문에 처분이 제한됩니다",
                    },
                    {
                        "category": "corporate_governance",
                        "evidence": "원문에 없는 지분 제한",
                    },
                ],
                "unmatched_segments": [],
            },
            "test-fingerprint",
        ),
    )

    profile = legal_semantic.parse_legal_semantic("담보 약정 때문에 처분이 제한됩니다")

    assert [item["category"] for item in profile["issues"]] == ["contractual_restriction"]
    assert all(item["policy"] == "advisory_only_no_portfolio_effect" for item in profile["issues"])
    assert profile["discarded_claims"][0]["reason"] == "evidence_not_found"
    assert "semantic_constraints" not in profile
    assert "weights" not in profile


def test_legal_llm_failure_keeps_calculation_safe(monkeypatch):
    monkeypatch.setattr(legal_semantic, "env_enabled", lambda name, default=True: True)
    monkeypatch.setattr(
        legal_semantic,
        "_call_legal_llm",
        lambda text: (_ for _ in ()).throw(RuntimeError("azure unavailable")),
    )

    profile = legal_semantic.parse_legal_semantic("별도 인허가 검토가 필요한 것 같습니다")

    assert profile["llm_audit"]["status"] == "failed"
    assert profile["issues"] == []
    assert profile["unmatched_segments"] == ["별도 인허가 검토가 필요한 것 같습니다"]
