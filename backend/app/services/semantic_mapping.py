"""LLM 기반 자유문장 의미 매핑.

이 모듈은 포트폴리오를 계산하거나 AI 인사이트를 생성하지 않는다.
이미 생성된 Unique 문자열 또는 RAG AI 인사이트 answer를 Azure OpenAI
Structured Output으로 구조화하여, 계산 가능한 항목과 설명 전용 항목을 구분한다.

핵심 원칙
- 입력에 없는 사실·수치·자산을 추가하지 않는다.
- 키워드 1:1 파서가 아니라 문맥 단위로 의미를 분류한다.
- 입력을 먼저 segment로 나눈 뒤 모든 segment가 결과에 연결됐는지 코드로 검사한다.
- 모델이 놓친 segment는 자동으로 unmapped_segments에 남겨 조용히 누락되지 않게 한다.
- AI 인사이트 매핑 결과는 advisory_only이며 포트폴리오 비중 계산에 자동 반영하지 않는다.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal, TypedDict

from app.core.azure_openai import get_llm_client, get_llm_deployment


SUPPORTED_ASSETS = [
    "domestic_equity",
    "overseas_blue_chip",
    "overseas_growth",
    "overseas_dividend",
    "general_bond",
    "separate_tax_bond",
    "low_coupon_bond",
    "reit",
    "gold",
    "commodity",
    "dollar",
    "cash",
]

BENCHMARK_KEYS = ["kospi", "sp500", "msci_acwi"]


class SourceSegment(TypedDict):
    id: int
    text: str


def split_source_segments(text: str) -> list[SourceSegment]:
    """자유문장을 의미 추출 누락 점검용 최소 segment로 분리한다.

    이 함수는 의미를 해석하지 않는다. 줄바꿈·파이프·세미콜론·문장부호만
    사용하므로 특정 금융 키워드가 없어도 모든 원문 조각이 coverage 검사 대상이 된다.
    """
    normalized = str(text or "").strip()
    if not normalized:
        return []

    pieces = re.split(
        r"(?:\r?\n)+|[|;；]+|(?<=[.!?。！？])\s+",
        normalized,
    )
    cleaned = [piece.strip(" \t-•·") for piece in pieces]
    cleaned = [piece for piece in cleaned if piece]

    # 문장부호가 거의 없는 긴 나열문은 쉼표 기준으로 한 번 더 나눈다.
    result: list[str] = []
    for piece in cleaned:
        if len(piece) >= 160 and piece.count(",") >= 2:
            result.extend(
                part.strip()
                for part in re.split(r",\s*", piece)
                if part.strip()
            )
        else:
            result.append(piece)

    return [{"id": idx, "text": value} for idx, value in enumerate(result, start=1)]


UNIQUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": ["string", "null"]},
        "mappings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "source_segment_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                    "source_text": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": [
                            "liquidity_need",
                            "asset_preference",
                            "asset_exclusion",
                            "account_fact",
                            "tax_or_legal",
                            "corporate_or_succession",
                            "personal_constraint",
                            "other",
                        ],
                    },
                    "intent": {
                        "type": "string",
                        "enum": ["must", "prefer", "avoid", "informational"],
                    },
                    "canonical_assets": {
                        "type": "array",
                        "items": {"type": "string", "enum": SUPPORTED_ASSETS},
                    },
                    "freeform_target": {"type": ["string", "null"]},
                    "amount_krw": {"type": ["number", "null"]},
                    "time_horizon_years": {"type": ["number", "null"]},
                    "account_type": {
                        "type": "string",
                        "enum": ["isa", "irp", "pension", "taxable", "none"],
                    },
                    "account_exists": {"type": ["boolean", "null"]},
                    "account_start_year": {"type": ["integer", "null"]},
                    "cumulative_contribution_krw": {"type": ["number", "null"]},
                    "current_year_contribution_krw": {"type": ["number", "null"]},
                    "calculation_field": {
                        "type": "string",
                        "enum": [
                            "unique_need_amount",
                            "unique_asset",
                            "asset_exclusion",
                            "isa_status",
                            "irp_status",
                            "client_context",
                            "none",
                        ],
                    },
                    "mapping_status": {
                        "type": "string",
                        "enum": ["mapped", "advisory_only", "unmapped"],
                    },
                    "mapping_reason": {"type": "string"},
                },
                "required": [
                    "source_segment_ids",
                    "source_text",
                    "category",
                    "intent",
                    "canonical_assets",
                    "freeform_target",
                    "amount_krw",
                    "time_horizon_years",
                    "account_type",
                    "account_exists",
                    "account_start_year",
                    "cumulative_contribution_krw",
                    "current_year_contribution_krw",
                    "calculation_field",
                    "mapping_status",
                    "mapping_reason",
                ],
            },
        },
        "coverage_complete": {"type": "boolean"},
    },
    "required": ["summary", "mappings", "coverage_complete"],
}


INSIGHT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": ["string", "null"]},
        "signals": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "source_segment_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                    "source_text": {"type": "string"},
                    "factor": {
                        "type": "string",
                        "enum": [
                            "interest_rate",
                            "inflation",
                            "fx",
                            "equity_market",
                            "credit",
                            "commodity",
                            "liquidity",
                            "tax_or_regulation",
                            "geopolitical",
                            "other",
                        ],
                    },
                    "direction": {
                        "type": "string",
                        "enum": ["up", "down", "mixed", "unclear"],
                    },
                    "affected_assets": {
                        "type": "array",
                        "items": {"type": "string", "enum": SUPPORTED_ASSETS},
                    },
                    "freeform_target": {"type": ["string", "null"]},
                    "horizon": {
                        "type": "string",
                        "enum": ["short", "medium", "long", "unspecified"],
                    },
                    "strength": {
                        "type": "string",
                        "enum": ["weak", "moderate", "strong", "unspecified"],
                    },
                    "explicit_numeric_limit": {"type": ["number", "null"]},
                    "explicit_numeric_unit": {"type": ["string", "null"]},
                    "mapping_status": {
                        "type": "string",
                        "enum": ["mapped", "advisory_only", "unmapped"],
                    },
                    "mapping_reason": {"type": "string"},
                },
                "required": [
                    "source_segment_ids",
                    "source_text",
                    "factor",
                    "direction",
                    "affected_assets",
                    "freeform_target",
                    "horizon",
                    "strength",
                    "explicit_numeric_limit",
                    "explicit_numeric_unit",
                    "mapping_status",
                    "mapping_reason",
                ],
            },
        },
        "coverage_complete": {"type": "boolean"},
    },
    "required": ["summary", "signals", "coverage_complete"],
}


def _call_structured_output(
    *,
    system_prompt: str,
    user_prompt: str,
    schema_name: str,
    schema: dict[str, Any],
) -> dict[str, Any]:
    response = get_llm_client().chat.completions.create(
        model=get_llm_deployment(),
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ],
        temperature=0,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": schema,
            },
        },
    )
    if not response.choices:
        raise ValueError("Azure OpenAI 응답에 choices가 없습니다.")

    content = response.choices[0].message.content
    if not content:
        raise ValueError("Azure OpenAI 구조화 응답이 비어 있습니다.")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("Azure OpenAI 구조화 응답을 JSON으로 해석하지 못했습니다.") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Azure OpenAI 구조화 응답의 최상위 값은 객체여야 합니다.")
    return parsed


def _validate_and_attach_coverage(
    *,
    segments: list[SourceSegment],
    result: dict[str, Any],
    item_key: Literal["mappings", "signals"],
) -> dict[str, Any]:
    valid_ids = {segment["id"] for segment in segments}
    covered_ids: set[int] = set()
    invalid_references: list[int] = []

    items = result.get(item_key)
    if not isinstance(items, list):
        items = []
        result[item_key] = items

    for item in items:
        if not isinstance(item, dict):
            continue
        raw_ids = item.get("source_segment_ids")
        if not isinstance(raw_ids, list):
            raw_ids = []
        normalized_ids: list[int] = []
        for raw_id in raw_ids:
            if isinstance(raw_id, bool):
                continue
            try:
                segment_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if segment_id in valid_ids:
                normalized_ids.append(segment_id)
                covered_ids.add(segment_id)
            else:
                invalid_references.append(segment_id)
        item["source_segment_ids"] = sorted(set(normalized_ids))

    missing = [
        segment
        for segment in segments
        if segment["id"] not in covered_ids
    ]
    result["unmapped_segments"] = missing
    result["invalid_segment_references"] = sorted(set(invalid_references))
    result["coverage_complete"] = (
        bool(result.get("coverage_complete"))
        and not missing
        and not invalid_references
    )
    result["source_segments"] = segments
    return result


def empty_unique_mapping(text: str = "") -> dict[str, Any]:
    segments = split_source_segments(text)
    return {
        "summary": None,
        "mappings": [],
        "coverage_complete": not segments,
        "unmapped_segments": segments,
        "invalid_segment_references": [],
        "source_segments": segments,
        "mapping_engine": "azure_openai_structured_output",
    }


def map_unique_text(text: str) -> dict[str, Any]:
    """Unique 자유문장을 의미 기반 구조로 변환한다.

    계산 엔진이 지원하지 않는 사실도 삭제하지 않고 advisory_only 또는
    unmapped로 남긴다.
    """
    segments = split_source_segments(text)
    if not segments:
        return empty_unique_mapping(text)

    system_prompt = """
    너는 PB 상담의 Unique circumstances 문장을 구조화하는 정보 추출기다.

    절대 규칙:
    1. 제공된 source_segments 안에 명시된 내용만 사용한다.
    2. 추측하거나 일반 금융상식을 추가하지 않는다.
    3. 각 서로 다른 사실을 별도 mapping으로 만든다.
    4. 모든 source segment id는 최소 한 개 mapping에 연결해야 한다.
    5. 현재 계산 필드에 직접 연결할 수 없어도 삭제하지 말고
       mapping_status=advisory_only 또는 unmapped로 남긴다.
    6. 금액은 원(KRW), 기간은 년으로 정규화한다.
    7. 고객의 단순 선호는 강제 비중으로 바꾸지 않는다.
    8. 자산 제외 의사가 명시된 경우에만 asset_exclusion으로 분류한다.
    9. 수정·정정 표현이 있으면 최종 표현만 유효하게 정리하되,
       source_segment_ids에는 관련 segment를 모두 연결한다.
    10. source_text는 입력 원문을 그대로 또는 최소 범위로 인용한다.
    """

    user_prompt = (
        "다음 source_segments를 구조화하라.\n"
        f"{json.dumps(segments, ensure_ascii=False, indent=2)}"
    )
    result = _call_structured_output(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema_name="unique_semantic_mapping",
        schema=UNIQUE_SCHEMA,
    )
    result = _validate_and_attach_coverage(
        segments=segments,
        result=result,
        item_key="mappings",
    )
    result["mapping_engine"] = "azure_openai_structured_output"
    return result


def empty_insight_mapping(answer: str = "") -> dict[str, Any]:
    segments = split_source_segments(answer)
    return {
        "summary": None,
        "signals": [],
        "coverage_complete": not segments,
        "unmapped_segments": segments,
        "invalid_segment_references": [],
        "source_segments": segments,
        "mapping_engine": "azure_openai_structured_output",
        "advisory_only": True,
        "calculation_applied": False,
    }


def map_ai_insight_answer(answer: str) -> dict[str, Any]:
    """다른 팀의 RAG/LLM이 만든 answer만 의미 매핑한다.

    citations나 외부 지식에서 새 사실을 보충하지 않는다. 결과는 화면 연결용
    advisory이며 포트폴리오 계산에는 자동 반영하지 않는다.
    """
    segments = split_source_segments(answer)
    if not segments:
        return empty_insight_mapping(answer)

    system_prompt = """
    너는 이미 생성된 AI 인사이트 answer를 포트폴리오 화면의 자산군·시장요인에
    연결하는 의미 매퍼다. 새로운 인사이트를 생성하는 역할이 아니다.

    절대 규칙:
    1. 제공된 source_segments 안의 내용만 사용한다.
    2. 외부 지식, citations 원문, 일반적인 시장 상식을 추가하지 않는다.
    3. 모든 source segment id는 최소 한 개 signal에 연결해야 한다.
    4. 연결이 불확실하면 affected_assets를 비우고 mapping_status=unmapped로 둔다.
    5. answer에 숫자 상한·하한이 명시되지 않았다면 explicit_numeric_limit=null이다.
    6. 자산 비중 변경값을 새로 만들지 않는다.
    7. 모든 결과는 advisory_only이며 자동 매매·자동 비중변경을 의미하지 않는다.
    8. source_text는 입력 원문을 그대로 또는 최소 범위로 인용한다.
    """

    user_prompt = (
        "다음 AI 인사이트 answer의 source_segments만 구조화하라.\n"
        f"{json.dumps(segments, ensure_ascii=False, indent=2)}"
    )
    result = _call_structured_output(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema_name="ai_insight_semantic_mapping",
        schema=INSIGHT_SCHEMA,
    )
    result = _validate_and_attach_coverage(
        segments=segments,
        result=result,
        item_key="signals",
    )
    result["mapping_engine"] = "azure_openai_structured_output"
    result["advisory_only"] = True
    result["calculation_applied"] = False
    return result
