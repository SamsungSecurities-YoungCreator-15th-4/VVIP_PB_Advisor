# ruff: noqa: E501
"""기존 Tax 결정론적 파서의 비상 보조 LLM.

Tax는 기존 registry/정규식 결과가 우선이다. 이 모듈은 기존 파서가 계산에 필요한
명시 사실을 충분히 추출하지 못한 경우에만 별도 Tax 원문을 Azure OpenAI로 보낸다.
LLM은 허용된 tax fact만 제안하고, 원문 인용·금액·세율·연도를 코드가 다시 검증한다.
자산 선호나 포트폴리오 비중 제약은 절대 생성하지 않는다.
"""

from __future__ import annotations




import hashlib
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import copy
import json
import logging
import re
import threading
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .tax_parser import extract_korean_money_candidates
from .semantic_common import (
    create_structured_completion,
    env_enabled,
    extract_message_content,
    get_semantic_deployment,
    mask_sensitive_text,
    normalize_semantic_text,
    stable_hash,
)

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")

TAX_LLM_FALLBACK_VERSION = "tax-llm-fallback-facts-only-v2"
TAX_CACHE_MAX_SIZE = 256

_ALLOWED_FACT_FIELDS = [
    "external_financial_income_krw",
    "marginal_income_tax_rate",
    "overseas_realized_loss_krw",
    "overseas_realized_gain_krw",
    "isa_account_exists",
    "isa_opened_year",
    "isa_current_year_contribution_krw",
    "isa_cumulative_contribution_krw",
    "isa_recent_3yr_comprehensive_taxed",
    "irp_account_exists",
    "irp_opened_year",
    "irp_current_year_contribution_krw",
    "irp_cumulative_contribution_krw",
    "transfer_amount_krw",
    "transfer_horizon_years",
]

_NULLABLE_NUMBER = {"anyOf": [{"type": "number"}, {"type": "null"}]}
_NULLABLE_BOOLEAN = {"anyOf": [{"type": "boolean"}, {"type": "null"}]}

TAX_LLM_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "enum": _ALLOWED_FACT_FIELDS},
                    "number_value": _NULLABLE_NUMBER,
                    "boolean_value": _NULLABLE_BOOLEAN,
                    "evidence": {"type": "string"},
                },
                "required": ["field", "number_value", "boolean_value", "evidence"],
                "additionalProperties": False,
            },
        },
        "unmatched_segments": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["facts", "unmatched_segments"],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = """
너는 IPS Tax 자유문장에서 세금 계산에 필요한 명시 사실만 추출하는 보조 정보 추출기다.
기존 결정론적 세금 파서가 우선이며, 너는 누락 가능성이 있는 사실 후보만 반환한다.

[절대 규칙]
1. Tax 입력에 없는 사실·숫자·세율·계좌 상태를 추측하지 않는다.
2. evidence는 Tax 입력에서 그대로 복사한 연속 문자열이어야 한다.
3. 자산 선호, 자산 비중, 포트폴리오 추천, 절세 상품 비중을 만들지 않는다.
4. 고객이 걱정한다고 말한 것만으로 소득·세율·과세이력을 true나 숫자로 추정하지 않는다.
5. 금액은 원 단위 number_value로, 세율은 0~1 소수로, 연도는 4자리 숫자로 반환한다.
6. boolean field는 boolean_value만 사용하고 number_value는 null로 둔다.
7. 숫자 field는 number_value만 사용하고 boolean_value는 null로 둔다.
8. '올해 납입 없음/0원'은 명시된 0으로 반환할 수 있다.
9. 해석하지 못한 원문은 unmatched_segments에 그대로 남긴다.
""".strip()

_CACHE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_CACHE_LOCK = threading.Lock()


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    with _CACHE_LOCK:
        value = _CACHE.get(key)
        if value is None:
            return None
        _CACHE.move_to_end(key)
        return copy.deepcopy(value)


def _cache_put(key: str, value: Dict[str, Any]) -> None:
    with _CACHE_LOCK:
        _CACHE[key] = copy.deepcopy(value)
        _CACHE.move_to_end(key)
        while len(_CACHE) > TAX_CACHE_MAX_SIZE:
            _CACHE.popitem(last=False)


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _evidence_exists(text: str, evidence: Any) -> bool:
    if not isinstance(evidence, str) or not evidence.strip():
        return False
    return _normalize_for_match(evidence) in _normalize_for_match(text)


def _money_candidates(text: str) -> List[float]:
    return extract_korean_money_candidates(text)



def _money_supported(evidence: str, value: float) -> bool:
    if value == 0 and re.search(r"(?:없|0\s*원|미납입|납입하지\s*않)", evidence):
        return True
    return any(abs(candidate - value) <= max(1.0, abs(value) * 1e-9) for candidate in _money_candidates(evidence))


def _rate_supported(evidence: str, value: float) -> bool:
    for number in re.findall(r"([0-9]+(?:\.[0-9]+)?)\s*%", evidence):
        if abs(float(number) / 100.0 - value) <= 1e-9:
            return True
    return False


def _year_supported(evidence: str, value: float) -> bool:
    return bool(re.search(rf"(?<!\d){int(value)}\s*년", evidence))


def _years_supported(evidence: str, value: float) -> bool:
    normalized_value = float(value)
    for number in re.findall(r"([0-9]+(?:\.[0-9]+)?)\s*년\s*(?:후|뒤|내|안|이내)", evidence):
        if abs(float(number) - normalized_value) <= 1e-9:
            return True
    for number in re.findall(r"([0-9]+(?:\.[0-9]+)?)\s*개월\s*(?:후|뒤|내|안|이내)?", evidence):
        if abs(float(number) / 12.0 - normalized_value) <= 1e-9:
            return True
    relative_words = {"올해": 0.0, "내년": 1.0, "내후년": 2.0, "반년": 0.5}
    return any(word in evidence and abs(expected - normalized_value) <= 1e-9 for word, expected in relative_words.items())


def _boolean_supported(field: str, evidence: str, value: bool) -> bool:
    if field in {"isa_account_exists", "irp_account_exists"}:
        negative = bool(re.search(r"미가입|없음|없다|가입하지\s*않|안\s*만들", evidence))
        positive = bool(re.search(r"가입|개설|보유|있음|있다", evidence))
        return (value and positive and not negative) or ((not value) and negative)
    if field == "isa_recent_3yr_comprehensive_taxed":
        if not re.search(r"최근\s*3\s*년|최근\s*3개년|3년", evidence):
            return False
        negative = bool(re.search(r"없|미해당|비대상|무", evidence))
        positive = bool(re.search(r"있|대상|해당|이력", evidence))
        return (value and positive and not negative) or ((not value) and negative)
    return False


def _validate_fact(text: str, raw: Dict[str, Any]) -> Tuple[Optional[Tuple[str, Any]], Optional[str]]:
    field = str(raw.get("field") or "")
    evidence = str(raw.get("evidence") or "").strip()
    if field not in _ALLOWED_FACT_FIELDS:
        return None, "unsupported_field"
    if not _evidence_exists(text, evidence):
        return None, "evidence_not_found"

    if field in {"isa_account_exists", "irp_account_exists", "isa_recent_3yr_comprehensive_taxed"}:
        value = raw.get("boolean_value")
        if value is None or not _boolean_supported(field, evidence, bool(value)):
            return None, "boolean_not_supported"
        return (field, bool(value)), None

    value = raw.get("number_value")
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None, "number_missing_or_invalid"

    if field.endswith("_krw"):
        if value < 0 or not _money_supported(evidence, value):
            return None, "money_not_supported"
    elif field == "marginal_income_tax_rate":
        if not 0.06 <= value <= 0.495 or not _rate_supported(evidence, value):
            return None, "rate_not_supported"
    elif field in {"isa_opened_year", "irp_opened_year"}:
        current_year = datetime.now(KST).year
        if not 1900 <= int(value) <= current_year or not _year_supported(evidence, value):
            return None, "year_not_supported"
        value = int(value)
    elif field == "transfer_horizon_years":
        if value < 0 or not _years_supported(evidence, value):
            return None, "years_not_supported"
    else:
        return None, "unhandled_field"

    return (field, value), None


def _call_tax_llm(masked_text: str) -> Tuple[Dict[str, Any], Optional[str]]:
    user_prompt = (
        "[Tax 원문]\n"
        f"{masked_text}\n\n"
        "위 Tax 원문만 사용해 허용된 tax fact 후보를 strict schema로 반환하라."
    )
    response = create_structured_completion(
        schema_name="tax_fallback_extraction",
        schema=TAX_LLM_SCHEMA,
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=1_000,
    )
    payload = json.loads(extract_message_content(response))
    fingerprint = getattr(response, "system_fingerprint", None)
    return payload, fingerprint


def _should_call_fallback(profile: Dict[str, Any]) -> bool:
    text = str(profile.get("normalized_text") or "").strip()
    if not text:
        return False
    if profile.get("unmatched_text"):
        return True
    facts = profile.get("facts") or {}
    if not facts:
        return True
    return any(route.get("missing_inputs") for route in profile.get("routes") or [])


def _parse_tax_fallback(profile: Dict[str, Any]) -> Dict[str, Any]:
    text = normalize_semantic_text(profile.get("normalized_text") or profile.get("raw_text"))
    if not text:
        return {"status": "empty", "facts": {}, "discarded_claims": [], "unmatched_segments": [], "version": TAX_LLM_FALLBACK_VERSION}
    if not env_enabled("PORTFOLIO_TAX_LLM_FALLBACK_ENABLED", default=True):
        return {"status": "disabled", "facts": {}, "discarded_claims": [], "unmatched_segments": [text], "version": TAX_LLM_FALLBACK_VERSION}

    masked_text = mask_sensitive_text(text)
    cache_key = stable_hash("tax", TAX_LLM_FALLBACK_VERSION, get_semantic_deployment(), masked_text)
    cached = _cache_get(cache_key)
    if cached is not None:
        cached["status"] = "cache_hit"
        return cached

    try:
        raw_payload, fingerprint = _call_tax_llm(masked_text)
        facts: Dict[str, Any] = {}
        discarded: List[Dict[str, Any]] = []
        evidence_map: Dict[str, str] = {}
        for raw_fact in raw_payload.get("facts") or []:
            validated, reason = _validate_fact(masked_text, raw_fact)
            if validated is None:
                discarded.append({"reason": reason, "candidate": raw_fact})
                continue
            field, value = validated
            if field not in facts:
                facts[field] = value
                evidence_map[field] = str(raw_fact.get("evidence") or "")

        for prefix in ("isa", "irp"):
            opened_key = f"{prefix}_opened_year"
            if opened_key in facts:
                facts[f"{prefix}_account_age_years"] = float(max(datetime.now(KST).year - int(facts[opened_key]), 0))

        unmatched = [
            item
            for item in (raw_payload.get("unmatched_segments") or [])
            if isinstance(item, str) and _evidence_exists(masked_text, item)
        ]
        result = {
            "status": "live",
            "facts": facts,
            "evidence": evidence_map,
            "discarded_claims": discarded,
            "unmatched_segments": unmatched,
            "version": TAX_LLM_FALLBACK_VERSION,
            "input_hash": cache_key,
            "system_fingerprint": fingerprint,
        }
        _cache_put(cache_key, result)
        return copy.deepcopy(result)
    except Exception:
        logger.warning("Tax 보조 LLM 실패 — 기존 결정론적 Tax 파서 결과만 사용합니다.")
        return {
            "status": "failed",
            "facts": {},
            "discarded_claims": [],
            "unmatched_segments": [text],
            "version": TAX_LLM_FALLBACK_VERSION,
        }


def enrich_tax_profile_with_llm(profile: Dict[str, Any]) -> Dict[str, Any]:
    """기존 tax_profile 사실을 덮어쓰지 않고 빈 fact만 LLM으로 보완한다."""

    result = copy.deepcopy(profile)
    if not _should_call_fallback(result):
        result["llm_fallback"] = {
            "status": "not_needed",
            "version": TAX_LLM_FALLBACK_VERSION,
            "separation_policy": "tax_only_no_unique_input_no_asset_constraints",
        }
        return result

    fallback = _parse_tax_fallback(result)
    facts = dict(result.get("facts") or {})
    applied: Dict[str, Any] = {}
    conflicts: List[Dict[str, Any]] = []
    for key, value in (fallback.get("facts") or {}).items():
        if key in facts and facts[key] is not None:
            if facts[key] != value:
                conflicts.append(
                    {
                        "field": key,
                        "deterministic": facts[key],
                        "llm": value,
                        "selected": "deterministic",
                    }
                )
            continue
        facts[key] = value
        applied[key] = value

    result["facts"] = facts

    # fallback 적용 전 상태가 routes에 남지 않도록 다시 계산한다.
    from .tax_parser import build_tax_routes

    all_mentions = [
        *(result.get("tax_mentions") or []),
        *(result.get("cost_mentions") or []),
    ]
    result["routes"] = build_tax_routes(all_mentions, facts)

    result["llm_fallback"] = {
        "status": fallback.get("status"),
        "version": fallback.get("version"),
        "input_hash": fallback.get("input_hash"),
        "system_fingerprint": fallback.get("system_fingerprint"),
        "applied_facts": applied,
        "evidence": fallback.get("evidence", {}),
        "conflicts": conflicts,
        "discarded_claims": fallback.get("discarded_claims", []),
        "unmatched_input": fallback.get("unmatched_segments", []),
        "separation_policy": "tax_only_no_unique_input_no_asset_constraints",
        "precedence": "deterministic_tax_parser_over_llm_fallback",
    }
    result["parser_note"] = (
        str(result.get("parser_note") or "").rstrip()
        + " Tax LLM은 기존 registry가 계산 사실을 충분히 찾지 못한 경우에만 호출되며, "
        "원문 검증을 통과한 허용 tax fact만 빈 필드에 보완합니다."
    ).strip()
    return result

_TAX_LLM_BACKGROUND_EXECUTOR = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="tax-llm-fallback",
)
_TAX_LLM_BACKGROUND_LOCK = threading.Lock()
_TAX_LLM_BACKGROUND_FUTURES = {}
_TAX_LLM_BACKGROUND_RESULTS = {}
_TAX_LLM_BACKGROUND_CACHE_MAX = 256


def _tax_llm_background_key(profile):
    raw_text = str(
        profile.get("raw_text")
        or profile.get("raw")
        or profile.get("text")
        or ""
    )
    version = str(profile.get("version") or "")
    payload = f"{version}\0{raw_text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _tax_llm_max_wait_seconds():
    raw = os.getenv("PORTFOLIO_TAX_LLM_MAX_WAIT_SECONDS", "0.75")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = 0.75
    return max(0.0, min(value, 2.0))


def _store_tax_llm_background_result(cache_key, result):
    with _TAX_LLM_BACKGROUND_LOCK:
        _TAX_LLM_BACKGROUND_RESULTS[cache_key] = copy.deepcopy(result)
        _TAX_LLM_BACKGROUND_FUTURES.pop(cache_key, None)
        while len(_TAX_LLM_BACKGROUND_RESULTS) > _TAX_LLM_BACKGROUND_CACHE_MAX:
            oldest_key = next(iter(_TAX_LLM_BACKGROUND_RESULTS))
            _TAX_LLM_BACKGROUND_RESULTS.pop(oldest_key, None)


def enrich_tax_profile_with_llm_non_blocking(profile):
    """Parser가 부족할 때만 LLM을 실행하고 calculate 지연을 제한한다."""

    result = copy.deepcopy(profile)
    if not _should_call_fallback(result):
        return result

    cache_key = _tax_llm_background_key(result)

    with _TAX_LLM_BACKGROUND_LOCK:
        cached = _TAX_LLM_BACKGROUND_RESULTS.get(cache_key)
        if cached is not None:
            cached_result = copy.deepcopy(cached)
            audit = dict(cached_result.get("llm_fallback") or {})
            audit["delivery"] = "background_cache_hit"
            cached_result["llm_fallback"] = audit
            return cached_result

        future = _TAX_LLM_BACKGROUND_FUTURES.get(cache_key)
        if future is None:
            future = _TAX_LLM_BACKGROUND_EXECUTOR.submit(
                enrich_tax_profile_with_llm,
                copy.deepcopy(result),
            )
            _TAX_LLM_BACKGROUND_FUTURES[cache_key] = future

    try:
        enriched = future.result(timeout=_tax_llm_max_wait_seconds())
    except FutureTimeoutError:
        audit = dict(result.get("llm_fallback") or {})
        audit.update(
            {
                "status": "scheduled",
                "delivery": "conditional_non_blocking",
                "input_hash": cache_key,
            }
        )
        result["llm_fallback"] = audit
        return result
    except Exception:
        with _TAX_LLM_BACKGROUND_LOCK:
            _TAX_LLM_BACKGROUND_FUTURES.pop(cache_key, None)
        audit = dict(result.get("llm_fallback") or {})
        audit.update(
            {
                "status": "failed_background",
                "delivery": "conditional_non_blocking",
                "input_hash": cache_key,
            }
        )
        result["llm_fallback"] = audit
        return result

    _store_tax_llm_background_result(cache_key, enriched)
    enriched_result = copy.deepcopy(enriched)
    audit = dict(enriched_result.get("llm_fallback") or {})
    audit["delivery"] = "completed_within_budget"
    enriched_result["llm_fallback"] = audit
    return enriched_result

