# ruff: noqa: E501
"""Legal 자유문장을 감사 가능한 전문가 검토 항목으로 구조화한다.

설계 원칙
- Unique/Tax와 도메인 스키마·캐시·prompt·결과를 섞지 않는다.
- Azure 클라이언트·마스킹·Structured Output 호출만 semantic_common.py를 공유한다.
- 결정론적 최소 안전망이 세 페르소나의 핵심 Legal 문구를 우선 포착한다.
- LLM은 미분류 Legal 원문의 범주만 보완하며 법률 결론·세율·의무를 창작하지 않는다.
- 결과는 전문가 검토용 메타데이터일 뿐 포트폴리오 비중·점수·자산 제외에 반영하지 않는다.
"""

from __future__ import annotations

import copy
import json
import logging
import re
import threading
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Sequence, Tuple

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

LEGAL_SEMANTIC_VERSION = "legal-semantic-advisory-only-v1"
LEGAL_CACHE_MAX_SIZE = 256

LEGAL_CATEGORY_LABELS: Dict[str, str] = {
    "business_succession": "가업·기업승계 및 상속공제 요건 검토",
    "gift_fund_source": "증여세·자금출처 소명 검토",
    "overseas_stock_reporting": "해외주식 대주주·신고의무 검토",
    "inheritance_gift": "상속·증여 구조 및 절차 검토",
    "corporate_governance": "법인·지분·경영권 구조 검토",
    "cross_border": "해외자산·외환·국경간 규제 검토",
    "reporting_disclosure": "신고·공시·허가 의무 검토",
    "contractual_restriction": "계약·약정상 투자제한 검토",
    "other_legal_review": "기타 법률전문가 검토",
}

_ALLOWED_CATEGORIES = list(LEGAL_CATEGORY_LABELS)

# 구체적인 문구를 먼저 검사한다. 한 segment에서 최초로 일치한 범주만 결정론적으로 채택한다.
_DETERMINISTIC_RULES: Sequence[Tuple[str, re.Pattern[str]]] = (
    (
        "business_succession",
        re.compile(
            r"가업\s*(?:승계|상속)|기업\s*(?:승계|상속)|"
            r"가업상속공제|기업\s*상속\s*공제|상속\s*공제\s*요건",
            re.IGNORECASE,
        ),
    ),
    (
        "overseas_stock_reporting",
        re.compile(
            r"(?:해외|미국|국외)\s*주식.{0,35}?(?:대주주|신고|공시|의무)|"
            r"(?:대주주|신고|공시|의무).{0,35}?(?:해외|미국|국외)\s*주식",
            re.IGNORECASE,
        ),
    ),
    (
        "gift_fund_source",
        re.compile(
            r"증여세법|증여세|자금\s*출처(?:\s*조사)?|자금출처조사|출처\s*소명",
            re.IGNORECASE,
        ),
    ),
    (
        "inheritance_gift",
        re.compile(r"상속|증여|유언|유류분|상속인|수증자", re.IGNORECASE),
    ),
    (
        "corporate_governance",
        re.compile(
            r"법인|지분|주주간\s*계약|경영권|의결권|정관|이사회|주주총회",
            re.IGNORECASE,
        ),
    ),
    (
        "cross_border",
        re.compile(
            r"해외\s*자산|국외\s*재산|해외\s*계좌|외국환|외환\s*신고|역외|FATCA|CRS",
            re.IGNORECASE,
        ),
    ),
    (
        "reporting_disclosure",
        re.compile(
            r"신고\s*의무|공시\s*의무|허가\s*요건|등록\s*의무|보고\s*의무|제출\s*의무",
            re.IGNORECASE,
        ),
    ),
    (
        "contractual_restriction",
        re.compile(
            r"계약상|약정상|투자\s*제한|처분\s*제한|보호예수|락업|lock[- ]?up|질권|담보\s*제한",
            re.IGNORECASE,
        ),
    ),
)

LEGAL_LLM_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": _ALLOWED_CATEGORIES},
                    "evidence": {"type": "string"},
                },
                "required": ["category", "evidence"],
                "additionalProperties": False,
            },
        },
        "unmatched_segments": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["issues", "unmatched_segments"],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = """
너는 VVIP 고객 IPS의 Legal 자유문장을 분류하는 보조 정보 추출기다.
법률 판단을 내리거나 의무·요건·세율·기한을 창작하지 말고, 입력에 명시된 검토 주제만 분류한다.

[절대 규칙]
1. 입력에 없는 사실, 법률 결론, 신고의무, 세율, 기한, 공제 가능 여부를 만들지 않는다.
2. evidence는 입력에서 그대로 복사한 연속 문자열이어야 한다.
3. 포트폴리오 자산, 비중, 추천 점수, 투자 제외 조건을 생성하지 않는다.
4. 단순한 투자 선호나 세금 걱정은 Legal 이슈로 확장하지 않는다.
5. 한 문구가 여러 범주로 보이더라도 입력에 직접 드러난 범주만 반환한다.
6. 분류할 수 없는 원문은 unmatched_segments에 그대로 남긴다.

[category]
- business_succession: 가업·기업승계, 가업상속공제, 기업 상속공제 요건
- gift_fund_source: 증여세, 자금출처 조사·소명
- overseas_stock_reporting: 해외주식 대주주·신고·공시 의무
- inheritance_gift: 일반 상속·증여·유언·유류분 구조
- corporate_governance: 법인·지분·경영권·정관·주주간계약
- cross_border: 해외자산·외환·국외재산·해외계좌 등 국경간 규제
- reporting_disclosure: 명시적인 신고·공시·허가·등록·보고 의무
- contractual_restriction: 계약·약정·담보·보호예수·처분제한
- other_legal_review: 위 범주에 속하지 않지만 명시적으로 법률전문가 검토가 필요한 내용
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
        while len(_CACHE) > LEGAL_CACHE_MAX_SIZE:
            _CACHE.popitem(last=False)


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _evidence_exists(text: str, evidence: Any) -> bool:
    if not isinstance(evidence, str) or not evidence.strip():
        return False
    return _normalize_for_match(evidence) in _normalize_for_match(text)


def _split_segments(text: str) -> List[str]:
    segments = [item.strip(" \t\r\n-•·") for item in re.split(r"[\n|;]+", text)]
    return [item for item in segments if item]


def _issue(category: str, evidence: str, source: str) -> Dict[str, Any]:
    return {
        "category": category,
        "review_topic": LEGAL_CATEGORY_LABELS[category],
        "evidence": evidence,
        "source": source,
        "policy": "advisory_only_no_portfolio_effect",
    }


def _dedupe_issues(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    seen = set()
    for item in issues:
        key = (item.get("category"), _normalize_for_match(str(item.get("evidence") or "")))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _extract_deterministic(text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    issues: List[Dict[str, Any]] = []
    unmatched: List[str] = []

    for segment in _split_segments(text):
        matched = False
        for category, pattern in _DETERMINISTIC_RULES:
            if pattern.search(segment):
                issues.append(_issue(category, segment, "deterministic"))
                matched = True
                break
        if not matched:
            unmatched.append(segment)

    return _dedupe_issues(issues), unmatched


def _call_legal_llm(masked_text: str) -> Tuple[Dict[str, Any], Optional[str]]:
    user_prompt = (
        "[Legal 미분류 원문]\n"
        f"{masked_text}\n\n"
        "위 원문만 사용해 strict schema로 분류하라. evidence는 반드시 원문에서 그대로 복사하라."
    )
    response = create_structured_completion(
        schema_name="legal_semantic_extraction",
        schema=LEGAL_LLM_SCHEMA,
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=800,
    )
    payload = json.loads(extract_message_content(response))
    return payload, getattr(response, "system_fingerprint", None)


def _validate_llm_payload(masked_text: str, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[Dict[str, Any]] = []
    discarded: List[Dict[str, Any]] = []

    for raw in raw_payload.get("issues") or []:
        category = str(raw.get("category") or "")
        evidence = str(raw.get("evidence") or "").strip()
        if category not in LEGAL_CATEGORY_LABELS:
            discarded.append({"reason": "unsupported_category", "candidate": raw})
            continue
        if not _evidence_exists(masked_text, evidence):
            discarded.append({"reason": "evidence_not_found", "candidate": raw})
            continue
        issues.append(_issue(category, evidence, "legal_llm_fallback"))

    unmatched = [
        item
        for item in (raw_payload.get("unmatched_segments") or [])
        if isinstance(item, str) and _evidence_exists(masked_text, item)
    ]
    return {
        "issues": _dedupe_issues(issues),
        "discarded_claims": discarded,
        "unmatched_segments": unmatched,
    }


def parse_legal_semantic(legal_value: Any) -> Dict[str, Any]:
    """Legal 원문을 전문가 검토 항목으로만 구조화한다.

    반환값은 포트폴리오 생성·점수화에 사용하지 않는다.
    """

    text = normalize_semantic_text(legal_value)
    if not text:
        return {
            "raw": legal_value,
            "text": "",
            "issues": [],
            "unmatched_segments": [],
            "discarded_claims": [],
            "llm_audit": {
                "status": "empty",
                "version": LEGAL_SEMANTIC_VERSION,
                "separation_policy": "legal_only_no_tax_unique_input",
                "portfolio_policy": "advisory_only_no_weight_score_or_exclusion",
            },
        }

    deterministic_issues, unmatched = _extract_deterministic(text)
    if not unmatched:
        return {
            "raw": legal_value,
            "text": text,
            "issues": deterministic_issues,
            "unmatched_segments": [],
            "discarded_claims": [],
            "llm_audit": {
                "status": "not_needed",
                "version": LEGAL_SEMANTIC_VERSION,
                "applied_issues": [],
                "separation_policy": "legal_only_no_tax_unique_input",
                "portfolio_policy": "advisory_only_no_weight_score_or_exclusion",
            },
        }

    if not env_enabled("PORTFOLIO_LEGAL_LLM_ENABLED", default=True):
        return {
            "raw": legal_value,
            "text": text,
            "issues": deterministic_issues,
            "unmatched_segments": unmatched,
            "discarded_claims": [],
            "llm_audit": {
                "status": "disabled",
                "version": LEGAL_SEMANTIC_VERSION,
                "applied_issues": [],
                "separation_policy": "legal_only_no_tax_unique_input",
                "portfolio_policy": "advisory_only_no_weight_score_or_exclusion",
            },
        }

    unmatched_text = "\n".join(unmatched)
    masked_text = mask_sensitive_text(unmatched_text)
    cache_key = stable_hash(
        "legal",
        LEGAL_SEMANTIC_VERSION,
        get_semantic_deployment(),
        masked_text,
    )
    cached = _cache_get(cache_key)
    if cached is not None:
        cached["raw"] = legal_value
        cached["text"] = text
        cached["llm_audit"]["status"] = "cache_hit"
        return cached

    try:
        raw_payload, fingerprint = _call_legal_llm(masked_text)
        validated = _validate_llm_payload(masked_text, raw_payload)
        combined = _dedupe_issues([*deterministic_issues, *validated["issues"]])
        result = {
            "raw": legal_value,
            "text": text,
            "issues": combined,
            "unmatched_segments": validated["unmatched_segments"],
            "discarded_claims": validated["discarded_claims"],
            "llm_audit": {
                "status": "live",
                "version": LEGAL_SEMANTIC_VERSION,
                "input_hash": cache_key,
                "system_fingerprint": fingerprint,
                "applied_issues": validated["issues"],
                "separation_policy": "legal_only_no_tax_unique_input",
                "portfolio_policy": "advisory_only_no_weight_score_or_exclusion",
            },
        }
        _cache_put(cache_key, result)
        return copy.deepcopy(result)
    except Exception:
        logger.warning("Legal 의미 해석 LLM 실패 — 결정론적 Legal 검토 항목만 사용합니다.")
        return {
            "raw": legal_value,
            "text": text,
            "issues": deterministic_issues,
            "unmatched_segments": unmatched,
            "discarded_claims": [],
            "llm_audit": {
                "status": "failed",
                "version": LEGAL_SEMANTIC_VERSION,
                "applied_issues": [],
                "separation_policy": "legal_only_no_tax_unique_input",
                "portfolio_policy": "advisory_only_no_weight_score_or_exclusion",
            },
        }


def apply_legal_profile_to_ips_payload(
    ips_payload: Dict[str, Any],
    legal_value: Any,
) -> Dict[str, Any]:
    """새 Legal 원문 분석 결과를 기존 IPS에 연결한다.

    사용자가 Legal 원문을 수정한 뒤 재계산할 수 있으므로 이전 issues/audit보다
    현재 원문의 분석 결과를 우선한다. 그 외 커스텀 필드는 보존한다.
    """

    profile = parse_legal_semantic(legal_value)
    result = dict(ips_payload)
    existing = dict(result.get("legal_profile") or {})
    result["legal_text"] = profile["text"]
    result["legal_profile"] = {
        **profile,
        **existing,
        "raw": profile.get("raw"),
        "text": profile.get("text", ""),
        "issues": list(profile.get("issues") or []),
        "unmatched_segments": list(profile.get("unmatched_segments") or []),
        "discarded_claims": list(profile.get("discarded_claims") or []),
        "llm_audit": dict(profile.get("llm_audit") or {}),
    }
    return result
