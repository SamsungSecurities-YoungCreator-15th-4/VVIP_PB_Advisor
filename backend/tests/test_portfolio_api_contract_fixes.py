from app.portfolio.adapters import (
    parse_current_year_contribution,
    parse_stt_asset_to_krw,
)
from app.portfolio.api_contracts import PortfolioCalculateRequest
from app.portfolio.formatters import round_allocation_percentages
from app.portfolio.tax_parser import parse_tax_text


def test_stt_asset_numeric_is_eokwon():
    assert parse_stt_asset_to_krw(18) == 1_800_000_000
    assert parse_stt_asset_to_krw("18") == 1_800_000_000
    assert parse_stt_asset_to_krw("18억") == 1_800_000_000


def test_current_year_contribution_preserves_korean_unit():
    text = "IRP는 2016년에 가입했고 올해 900만 원 납입했습니다."
    assert parse_current_year_contribution(text, ["IRP"]) == 9_000_000


def test_allocation_rounding_is_two_decimals_and_exactly_100():
    rounded = round_allocation_percentages(
        [
            ("a", 0.333333),
            ("b", 0.333333),
            ("c", 0.333334),
        ]
    )
    assert rounded == {"a": 33.33, "b": 33.33, "c": 33.34}
    assert round(sum(rounded.values()), 2) == 100.00


def test_tax_parser_detects_persona_topics_without_sensitivity_score():
    profile = parse_tax_text(
        "최근 3개년 금융소득종합과세 이력은 없고, "
        "ISA는 2022년 가입해 올해 1,500만 원 납입했습니다. "
        "해외주식 양도세와 거래비용도 걱정됩니다."
    )
    topics = {item["topic"] for item in profile["tax_mentions"]}
    cost_topics = {item["topic"] for item in profile["cost_mentions"]}

    assert "financial_income_comprehensive_tax" in topics
    assert "isa" in topics
    assert "overseas_stock_capital_gains_tax" in topics
    assert "transaction_cost" in cost_topics
    assert profile["facts"]["isa_current_year_contribution_krw"] == 15_000_000
    assert profile["facts"]["isa_recent_3yr_comprehensive_taxed"] is False
    assert "tax_sensitivity" not in profile


def test_tax_parser_routes_gift_to_liquidity_constraint():
    profile = parse_tax_text("3년 뒤 자녀에게 5억 원을 증여할 계획입니다.")
    topics = {item["topic"] for item in profile["tax_mentions"]}
    assert "gift_tax" in topics
    assert profile["facts"]["transfer_amount_krw"] == 500_000_000
    assert profile["facts"]["transfer_horizon_years"] == 3.0


def test_swagger_request_has_real_ips_json_properties():
    schema = PortfolioCalculateRequest.model_json_schema()
    assert "ips_json" in schema["properties"]
    ref = schema["properties"]["ips_json"]["$ref"]
    definition_name = ref.rsplit("/", 1)[-1]
    ips_schema = schema["$defs"][definition_name]
    assert set(
        ["Goal", "Asset", "Return", "Risk", "Time", "Tax", "Liquidity", "Legal", "Unique"]
    ).issubset(ips_schema["properties"])
