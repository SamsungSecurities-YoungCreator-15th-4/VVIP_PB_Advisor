# ruff: noqa: E501
"""Unique 자연어를 감사 가능한 포트폴리오 제약으로 변환한다.

핵심 원칙
- 기존 adapters.extract_unique_profile()의 결정론적 금액·ISA·IRP 파서를 먼저 사용한다.
- LLM은 원문에 명시된 사실/방향만 구조화하며 포트폴리오 비중을 직접 생성하지 않는다.
- 원문 인용(evidence)이 실제 입력에 없거나 숫자가 맞지 않으면 폐기한다.
- 명시 비중은 hard constraint, 방향성은 현재 포트폴리오 대비 >= / <= hard constraint다.
- 후보를 제약에 맞게 사후 보정하지 않고, 제약을 만족하지 않는 후보를 탈락시킨다.
"""

from __future__ import annotations

import copy
from functools import lru_cache
import json
import logging
import re
import threading
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from zoneinfo import ZoneInfo

from .assets import (
    ALTERNATIVE_ASSETS,
    ASSET_TICKERS,
    BOND_ASSETS,
    CASH_LIKE_ASSETS,
    OVERSEAS_STOCK_CAPITAL_GAIN_ASSETS,
    STOCK_ASSETS,
)
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

UNIQUE_SEMANTIC_VERSION = "unique-semantic-hard-soft-v3"
UNIQUE_CACHE_MAX_SIZE = 256
_EPSILON = 1e-10

SEMANTIC_GROUP_ASSETS: Dict[str, List[str]] = {
    "equity": list(STOCK_ASSETS),
    "bond": list(BOND_ASSETS),
    "alternative": list(ALTERNATIVE_ASSETS),
    "cash": ["cash"],
    "cash_like": list(CASH_LIKE_ASSETS),
    "overseas_equity": list(OVERSEAS_STOCK_CAPITAL_GAIN_ASSETS),
}

_ASSET_ALIASES: Dict[str, Sequence[str]] = {
    "domestic_equity": ("코스피", "국내주식", "한국주식", "국내 주식"),
    "overseas_blue_chip": ("s&p500", "s&p 500", "에스앤피500", "미국 대형주", "미국 우량주"),
    "overseas_growth": ("나스닥", "미국 성장주", "해외 성장주", "성장주"),
    "overseas_dividend": ("schd", "미국 배당주", "해외 배당주", "배당주", "배당 etf"),
    "general_bond": ("일반채", "일반 채권", "국내채권", "국채", "단기채"),
    "separate_tax_bond": ("분리과세채", "분리과세 채권", "분리과세 국채"),
    "low_coupon_bond": ("저쿠폰채", "저쿠폰 채권", "장기채", "미국 장기채", "미 장기채"),
    "reit": ("리츠", "reit", "부동산 etf"),
    "gold": ("금", "골드"),
    "commodity": ("원자재", "커머더티"),
    "dollar": ("달러", "미국 달러", "달러자산", "달러 자산"),
    "cash": ("현금", "현금성", "예수금"),
}

_GROUP_ALIASES: Dict[str, Sequence[str]] = {
    "equity": ("주식", "주식형", "주식 자산"),
    "bond": ("채권", "채권형", "채권 자산"),
    "alternative": ("대체자산", "대체 자산"),
    "cash": ("현금", "현금 자산"),
    "cash_like": (
        "안전자산",
        "안전 자산",
        "현금성 자산",
        "유동성 자산",
        "비상자금",
        "여유자금",
        "대기자금",
    ),
    "overseas_equity": ("해외주식", "해외 주식", "미국주식", "미국 주식"),
}

_INCREASE_PATTERN = re.compile(r"늘|확대|높|더\s*(?:담|편입|보유)|비중\s*상향|강화")
_DECREASE_PATTERN = re.compile(r"줄|축소|낮|덜\s*(?:담|편입|보유)|비중\s*하향|감소")
_EXCLUDE_PATTERN = re.compile(
    r"투자하지|편입하지|보유하지|사지\s*않|빼(?:고|줘|달)|제외|없애|0\s*%|제로"
)
_MINIMUM_PATTERN = re.compile(r"이상|최소|적어도|하한")
_MAXIMUM_PATTERN = re.compile(r"이하|최대|넘지|상한")
_TARGET_PATTERN = re.compile(r"(?:로|까지|수준으로|정도로)\s*(?:맞|유지|조정)|목표")
_SOFT_PREFER_PATTERN = re.compile(
    r"관심|선호|좋아|좋게\s*보|긍정|괜찮게\s*보|호감|마음에\s*들|"
    r"고려해\s*주|염두에\s*두|"
    r"(?:비상|여유|대기)자금.{0,20}(?:남겨|확보|필요|유지)|"
    r"(?:남겨|확보|유지).{0,20}(?:현금|현금성|비상|여유|대기)"
)
_SOFT_AVOID_PATTERN = re.compile(
    r"선호하지|관심\s*없|꺼리|부담|피하고\s*싶|"
    r"가급적.{0,12}(?:적게|피하|줄이)|별로|부정적|우려"
)
_EXPLICIT_SOFT_AVOID_INTENT_PATTERN = re.compile(
    r"선호하지|관심\s*없|꺼리|피하고\s*싶|"
    r"가급적.{0,12}(?:적게|피하|줄이)|별로"
)
_TAX_CONTEXT_PATTERN = re.compile(
    r"세금|과세|양도세|배당세|금융소득|종합과세|세율|절세"
)
_APPROVED_AI_TAG = "[AI 인사이트 승인]"

_NULLABLE_NUMBER = {"anyOf": [{"type": "number"}, {"type": "null"}]}
_NULLABLE_INTEGER = {"anyOf": [{"type": "integer"}, {"type": "null"}]}
_NULLABLE_BOOLEAN = {"anyOf": [{"type": "boolean"}, {"type": "null"}]}
_NULLABLE_STRING = {"anyOf": [{"type": "string"}, {"type": "null"}]}

_ALLOWED_SUBJECTS = [*ASSET_TICKERS.keys(), *SEMANTIC_GROUP_ASSETS.keys()]
_ASSET_MAPPING_GUIDE = "\n".join(
    f"- {key}: {', '.join(aliases)}" for key, aliases in _ASSET_ALIASES.items()
)
_GROUP_MAPPING_GUIDE = "\n".join(
    f"- {key}: {', '.join(aliases)}" for key, aliases in _GROUP_ALIASES.items()
)

UNIQUE_SEMANTIC_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "constraints": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "subject_type": {"type": "string", "enum": ["asset", "group"]},
                    "subject": {"type": "string", "enum": _ALLOWED_SUBJECTS},
                    "operator": {
                        "type": "string",
                        "enum": [
                            "increase",
                            "decrease",
                            "minimum",
                            "maximum",
                            "target",
                            "exclude",
                        ],
                    },
                    "value_pct": _NULLABLE_NUMBER,
                    "precision_digits": _NULLABLE_INTEGER,
                    "evidence": {"type": "string"},
                },
                "required": [
                    "subject_type",
                    "subject",
                    "operator",
                    "value_pct",
                    "precision_digits",
                    "evidence",
                ],
                "additionalProperties": False,
            },
        },
        "soft_preferences": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "subject_type": {"type": "string", "enum": ["asset", "group"]},
                    "subject": {"type": "string", "enum": _ALLOWED_SUBJECTS},
                    "direction": {"type": "string", "enum": ["prefer", "avoid"]},
                    "evidence": {"type": "string"},
                },
                "required": ["subject_type", "subject", "direction", "evidence"],
                "additionalProperties": False,
            },
        },
        "liquidity": {
            "type": "object",
            "properties": {
                "amount_krw": _NULLABLE_NUMBER,
                "years_until_need": _NULLABLE_NUMBER,
                "evidence": _NULLABLE_STRING,
            },
            "required": ["amount_krw", "years_until_need", "evidence"],
            "additionalProperties": False,
        },
        "accounts": {
            "type": "object",
            "properties": {
                "isa": {
                    "type": "object",
                    "properties": {
                        "account_exists": _NULLABLE_BOOLEAN,
                        "opened_year": _NULLABLE_INTEGER,
                        "cumulative_contribution_krw": _NULLABLE_NUMBER,
                        "current_year_contribution_krw": _NULLABLE_NUMBER,
                        "evidence": _NULLABLE_STRING,
                    },
                    "required": [
                        "account_exists",
                        "opened_year",
                        "cumulative_contribution_krw",
                        "current_year_contribution_krw",
                        "evidence",
                    ],
                    "additionalProperties": False,
                },
                "irp": {
                    "type": "object",
                    "properties": {
                        "account_exists": _NULLABLE_BOOLEAN,
                        "opened_year": _NULLABLE_INTEGER,
                        "cumulative_contribution_krw": _NULLABLE_NUMBER,
                        "current_year_contribution_krw": _NULLABLE_NUMBER,
                        "evidence": _NULLABLE_STRING,
                    },
                    "required": [
                        "account_exists",
                        "opened_year",
                        "cumulative_contribution_krw",
                        "current_year_contribution_krw",
                        "evidence",
                    ],
                    "additionalProperties": False,
                },
            },
            "required": ["isa", "irp"],
            "additionalProperties": False,
        },
        "advisory_only": {"type": "array", "items": {"type": "string"}},
        "unmatched_segments": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "constraints",
        "soft_preferences",
        "liquidity",
        "accounts",
        "advisory_only",
        "unmatched_segments",
    ],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = f"""
너는 VVIP 고객의 IPS Unique 자유문장을 구조화하는 정보 추출기다.
포트폴리오를 추천하거나 비중을 창작하지 말고, 입력 문장에 명시된 내용만 추출한다.

[절대 규칙]
1. 입력에 없는 사실·숫자·세율·비중·기간을 만들지 않는다.
2. 각 결과의 evidence는 입력에서 그대로 복사한 연속 문자열이어야 한다.
3. 약한 관심·선호·호감은 soft_preferences의 prefer로 넣는다.
   부담·꺼림·가급적 피하고 싶다는 표현은 soft_preferences의 avoid로 넣는다.
   세금 우려만으로 자산 선호나 제약을 만들지 않는다.
4. 고객이 실제 운용 방향을 명시한 숫자 없는 지시는 constraints에 넣는다:
   - 늘리기/확대/높이기 → increase
   - 줄이기/축소/낮추기 → decrease
   - 투자하지 않기/제외/0% → exclude
5. 숫자가 있는 경우:
   - '20% 이상/최소 20%' → minimum 20
   - '20% 이하/최대 20%' → maximum 20
   - '20%로 늘리기' → minimum 20
   - '20%로 줄이기' → maximum 20
   - 단순히 '20%로 맞추기/20% 목표' → target 20
6. value_pct는 퍼센트 숫자 그대로 쓴다. 숫자가 없으면 null이다.
6-1. soft_preferences에는 비중·강도·점수를 만들지 않는다. direction과 evidence만 구조화한다.
6-2. 동일 원문이 명시적 increase/decrease/minimum/maximum/target/exclude에 해당하면
     soft_preferences에 중복하지 않고 constraints만 사용한다.
6-3. 같은 evidence가 구체 자산과 상위 자산군에 모두 해당하면 가장 구체적인 subject 하나만 추출한다.
7. '채권/주식/대체자산/안전자산'처럼 넓은 표현은 group으로, 구체적 상품·자산은 asset으로 분류한다.
8. ISA/IRP와 필요자금은 Unique 문장에 명시된 경우만 accounts/liquidity에 넣는다.
9. {_APPROVED_AI_TAG}가 붙은 구간은 PB가 승인한 AI 인사이트다. 그 구간에서는 자산 방향성만 constraints에 넣고,
   고객 자신의 soft_preferences나 실제 계좌·소득·필요자금 사실로 해석하지 않는다.
10. 계산으로 직접 연결할 수 없는 승계·상속·법률·법인 문맥은 advisory_only에 원문 그대로 남긴다.
11. 해석하지 못한 문장은 unmatched_segments에 원문 그대로 남긴다.

[asset 매핑]
{_ASSET_MAPPING_GUIDE}

[group 매핑]
{_GROUP_MAPPING_GUIDE}
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
        while len(_CACHE) > UNIQUE_CACHE_MAX_SIZE:
            _CACHE.popitem(last=False)


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _evidence_exists(text: str, evidence: Any) -> bool:
    if not isinstance(evidence, str) or not evidence.strip():
        return False
    return _normalize_for_match(evidence) in _normalize_for_match(text)


def _subject_aliases(subject_type: str, subject: str) -> Sequence[str]:
    if subject_type == "asset":
        return _ASSET_ALIASES.get(subject, ())
    return _GROUP_ALIASES.get(subject, ())


def _alias_is_supported_by_evidence(alias: str, evidence: str) -> bool:
    """짧거나 일반적인 별칭의 부분 문자열 오탐을 막는다."""

    if alias == "금":
        # 허용: "금", "금을", "금 비중", "금에는"
        # 차단: "금리", "지금", "연금", "금융"
        return bool(
            re.search(
                r"(?<![가-힣A-Za-z0-9])금"
                r"(?=(?:\s|[,.;:!?/]|$|은|는|이|가|을|를|에|에서|으로|로|과|와|도|만|부터|까지|의|비중))",
                evidence,
            )
        )

    normalized = _normalize_for_match(evidence)
    return _normalize_for_match(alias) in normalized


def _subject_is_supported_by_evidence(subject_type: str, subject: str, evidence: str) -> bool:
    return any(
        _alias_is_supported_by_evidence(alias, evidence)
        for alias in _subject_aliases(subject_type, subject)
    )


def _percent_tokens(text: str) -> List[Tuple[float, int]]:
    values: List[Tuple[float, int]] = []
    for match in re.finditer(r"([0-9]+(?:\.([0-9]+))?)\s*%", text):
        number_text = match.group(1)
        decimals = len(match.group(2) or "")
        values.append((float(number_text), decimals))
    return values


def _matching_percent_precision(evidence: str, value_pct: float) -> Optional[int]:
    for candidate, digits in _percent_tokens(evidence):
        if abs(candidate - value_pct) <= 1e-9:
            return digits
    return None


def _parse_korean_money_candidates(text: str) -> List[float]:
    """공통 한국식 금액 파서를 사용해 evidence 속 금액 후보를 반환한다."""

    return extract_korean_money_candidates(text)



def _money_matches_evidence(evidence: str, value: float) -> bool:
    return any(abs(candidate - value) <= max(1.0, abs(value) * 1e-9) for candidate in _parse_korean_money_candidates(evidence))


def _year_matches_evidence(evidence: str, value: int) -> bool:
    return bool(re.search(rf"(?<!\d){int(value)}\s*년", evidence))


def _years_until_need_matches(evidence: str, value: float) -> bool:
    normalized_value = float(value)
    for number in re.findall(r"([0-9]+(?:\.[0-9]+)?)\s*년\s*(?:후|뒤|내|안|이내)", evidence):
        if abs(float(number) - normalized_value) <= 1e-9:
            return True
    for number in re.findall(r"([0-9]+(?:\.[0-9]+)?)\s*개월\s*(?:후|뒤|내|안|이내)?", evidence):
        if abs(float(number) / 12.0 - normalized_value) <= 1e-9:
            return True
    relative_words = {"올해": 0.0, "내년": 1.0, "내후년": 2.0, "반년": 0.5}
    return any(word in evidence and abs(expected - normalized_value) <= 1e-9 for word, expected in relative_words.items())


def _is_approved_ai_evidence(text: str, evidence: str) -> bool:
    normalized_evidence = _normalize_for_match(evidence)
    for segment in re.split(r"[\n|]+", text):
        if _APPROVED_AI_TAG in segment and normalized_evidence in _normalize_for_match(segment):
            return True
    return False


def _validate_constraint(text: str, raw: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    subject_type = str(raw.get("subject_type") or "")
    subject = str(raw.get("subject") or "")
    operator = str(raw.get("operator") or "")
    evidence = str(raw.get("evidence") or "").strip()

    if subject_type not in {"asset", "group"}:
        return None, "unsupported_subject_type"
    if subject_type == "asset" and subject not in ASSET_TICKERS:
        return None, "unsupported_asset"
    if subject_type == "group" and subject not in SEMANTIC_GROUP_ASSETS:
        return None, "unsupported_group"
    if not _evidence_exists(text, evidence):
        return None, "evidence_not_found"
    if not _subject_is_supported_by_evidence(subject_type, subject, evidence):
        return None, "subject_not_supported_by_evidence"

    value_pct = raw.get("value_pct")
    precision_digits: Optional[int] = None

    if operator == "exclude":
        if not _EXCLUDE_PATTERN.search(evidence):
            return None, "exclude_language_not_found"
        value_ratio = 0.0
    elif operator in {"minimum", "maximum", "target"}:
        if value_pct is None:
            return None, "numeric_operator_without_value"
        try:
            value_pct = float(value_pct)
        except (TypeError, ValueError):
            return None, "invalid_percentage"
        if not 0.0 <= value_pct <= 100.0:
            return None, "percentage_out_of_range"
        precision_digits = _matching_percent_precision(evidence, value_pct)
        if precision_digits is None:
            return None, "percentage_not_found_in_evidence"
        if operator == "minimum" and not (_MINIMUM_PATTERN.search(evidence) or _INCREASE_PATTERN.search(evidence)):
            return None, "minimum_language_not_found"
        if operator == "maximum" and not (_MAXIMUM_PATTERN.search(evidence) or _DECREASE_PATTERN.search(evidence)):
            return None, "maximum_language_not_found"
        if operator == "target" and not _TARGET_PATTERN.search(evidence):
            return None, "target_language_not_found"
        value_ratio = value_pct / 100.0
    elif operator == "increase":
        if not _INCREASE_PATTERN.search(evidence):
            return None, "increase_language_not_found"
        value_ratio = None
    elif operator == "decrease":
        if not _DECREASE_PATTERN.search(evidence):
            return None, "decrease_language_not_found"
        value_ratio = None
    else:
        return None, "unsupported_operator"

    return {
        "subject_type": subject_type,
        "subject": subject,
        "operator": operator,
        "value_ratio": value_ratio,
        "value_pct": None if value_ratio is None else float(value_ratio) * 100.0,
        "precision_digits": precision_digits,
        "evidence": evidence,
        "source_kind": "approved_ai_insight" if _is_approved_ai_evidence(text, evidence) else "customer_unique",
        "policy": "hard_filter_no_post_adjustment",
    }, None


def _validate_soft_preference(
    text: str,
    raw: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """LLM이 추출한 약한 선호를 원문 근거로 다시 검증한다."""

    subject_type = str(raw.get("subject_type") or "")
    subject = str(raw.get("subject") or "")
    direction = str(raw.get("direction") or "")
    evidence = str(raw.get("evidence") or "").strip()

    if subject_type not in {"asset", "group"}:
        return None, "unsupported_subject_type"
    if subject_type == "asset" and subject not in ASSET_TICKERS:
        return None, "unsupported_asset"
    if subject_type == "group" and subject not in SEMANTIC_GROUP_ASSETS:
        return None, "unsupported_group"
    if direction not in {"prefer", "avoid"}:
        return None, "unsupported_direction"
    if not _evidence_exists(text, evidence):
        return None, "evidence_not_found"
    if not _subject_is_supported_by_evidence(subject_type, subject, evidence):
        return None, "subject_not_supported_by_evidence"
    if _is_approved_ai_evidence(text, evidence):
        return None, "approved_ai_not_customer_preference"

    if (
        _INCREASE_PATTERN.search(evidence)
        or _DECREASE_PATTERN.search(evidence)
        or _EXCLUDE_PATTERN.search(evidence)
        or bool(_percent_tokens(evidence))
    ):
        return None, "explicit_instruction_not_soft_preference"

    if direction == "prefer" and not _SOFT_PREFER_PATTERN.search(evidence):
        return None, "prefer_language_not_found"
    if direction == "avoid" and not _SOFT_AVOID_PATTERN.search(evidence):
        return None, "avoid_language_not_found"

    # "해외주식 양도세가 부담된다"처럼 세금 우려만 있는 문장을
    # 자산 회피로 바꾸지 않는다. 실제 회피 의사가 명시된 경우만 허용한다.
    if (
        direction == "avoid"
        and _TAX_CONTEXT_PATTERN.search(evidence)
        and not _EXPLICIT_SOFT_AVOID_INTENT_PATTERN.search(evidence)
    ):
        return None, "tax_context_not_asset_preference"

    return {
        "subject_type": subject_type,
        "subject": subject,
        "direction": direction,
        "evidence": evidence,
        "source_kind": "customer_unique",
        "policy": "secondary_ranking_only_no_invented_weight",
    }, None


def _dedupe_soft_preferences(
    preferences: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """같은 근거에서 asset과 상위 group이 겹치면 구체 asset만 남긴다."""

    kept: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []

    for preference in preferences:
        evidence_key = _normalize_for_match(str(preference.get("evidence") or ""))
        direction = str(preference.get("direction") or "")
        subject_type = str(preference.get("subject_type") or "")
        preference_assets = _constraint_subject_assets(preference)

        if subject_type == "asset":
            survivors: List[Dict[str, Any]] = []
            for existing in kept:
                same_evidence = (
                    _normalize_for_match(str(existing.get("evidence") or ""))
                    == evidence_key
                )
                same_direction = str(existing.get("direction") or "") == direction
                overlaps = bool(
                    preference_assets
                    & _constraint_subject_assets(existing)
                )
                if (
                    existing.get("subject_type") == "group"
                    and same_evidence
                    and same_direction
                    and overlaps
                ):
                    dropped.append(existing)
                    continue
                survivors.append(existing)
            kept = survivors

        elif subject_type == "group":
            has_more_specific_asset = any(
                existing.get("subject_type") == "asset"
                and _normalize_for_match(str(existing.get("evidence") or ""))
                == evidence_key
                and str(existing.get("direction") or "") == direction
                and bool(
                    preference_assets
                    & _constraint_subject_assets(existing)
                )
                for existing in kept
            )
            if has_more_specific_asset:
                dropped.append(preference)
                continue

        kept.append(preference)

    return kept, dropped


def _validate_account(text: str, key: str, raw: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    evidence = raw.get("evidence")
    discarded: List[str] = []
    if not evidence or not _evidence_exists(text, evidence):
        return {}, [f"{key}.evidence_not_found"] if any(raw.get(field) is not None for field in raw if field != "evidence") else []
    evidence = str(evidence)
    if _is_approved_ai_evidence(text, evidence):
        return {}, [f"{key}.approved_ai_not_customer_fact"]

    aliases = _ASSET_ALIASES.get(key, ())
    account_aliases = ("isa", "개인종합자산관리") if key == "isa" else ("irp", "개인형퇴직연금", "퇴직연금")
    if not any(_normalize_for_match(alias) in _normalize_for_match(evidence) for alias in (*aliases, *account_aliases)):
        return {}, [f"{key}.account_alias_not_found"]

    validated: Dict[str, Any] = {"evidence": evidence}

    account_exists = raw.get("account_exists")
    if account_exists is not None:
        negative = bool(re.search(r"미가입|없음|없다|안\s*만들|가입하지\s*않", evidence, flags=re.IGNORECASE))
        positive = bool(re.search(r"가입|개설|보유|있음|있다", evidence, flags=re.IGNORECASE))
        if bool(account_exists) and positive and not negative:
            validated["account_exists"] = True
        elif not bool(account_exists) and negative:
            validated["account_exists"] = False
        else:
            discarded.append(f"{key}.account_exists_not_supported")

    opened_year = raw.get("opened_year")
    if opened_year is not None:
        try:
            opened_year = int(opened_year)
        except (TypeError, ValueError):
            discarded.append(f"{key}.invalid_opened_year")
        else:
            if 1900 <= opened_year <= datetime.now(KST).year and _year_matches_evidence(evidence, opened_year):
                validated["opened_year"] = opened_year
            else:
                discarded.append(f"{key}.opened_year_not_supported")

    for raw_key, output_key in (
        ("cumulative_contribution_krw", "cumulative_contribution_krw"),
        ("current_year_contribution_krw", "current_year_contribution_krw"),
    ):
        value = raw.get(raw_key)
        if value is None:
            continue
        try:
            value = float(value)
        except (TypeError, ValueError):
            discarded.append(f"{key}.{raw_key}_invalid")
            continue
        explicit_zero = value == 0.0 and bool(re.search(r"(?:없|0\s*원|미납입|납입하지\s*않)", evidence))
        if value >= 0 and (explicit_zero or _money_matches_evidence(evidence, value)):
            validated[output_key] = value
        else:
            discarded.append(f"{key}.{raw_key}_not_supported")

    return validated, discarded


def _validate_liquidity(text: str, raw: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    evidence = raw.get("evidence")
    if not evidence or not _evidence_exists(text, evidence):
        return {}, ["liquidity.evidence_not_found"] if raw.get("amount_krw") is not None or raw.get("years_until_need") is not None else []
    evidence = str(evidence)
    if _is_approved_ai_evidence(text, evidence):
        return {}, ["liquidity.approved_ai_not_customer_fact"]

    validated: Dict[str, Any] = {"evidence": evidence}
    discarded: List[str] = []
    amount = raw.get("amount_krw")
    if amount is not None:
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            discarded.append("liquidity.invalid_amount")
        else:
            if amount >= 0 and _money_matches_evidence(evidence, amount):
                validated["amount_krw"] = amount
            else:
                discarded.append("liquidity.amount_not_supported")

    years = raw.get("years_until_need")
    if years is not None:
        try:
            years = float(years)
        except (TypeError, ValueError):
            discarded.append("liquidity.invalid_years")
        else:
            if years >= 0 and _years_until_need_matches(evidence, years):
                validated["years_until_need"] = years
            else:
                discarded.append("liquidity.years_not_supported")

    return validated, discarded


def _validate_llm_payload(text: str, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    constraints: List[Dict[str, Any]] = []
    discarded: List[Dict[str, Any]] = []
    seen: Set[Tuple[Any, ...]] = set()

    for raw_constraint in raw_payload.get("constraints") or []:
        constraint, reason = _validate_constraint(text, raw_constraint)
        if constraint is None:
            discarded.append({"kind": "constraint", "reason": reason, "candidate": raw_constraint})
            continue
        dedupe_key = (
            constraint["subject_type"],
            constraint["subject"],
            constraint["operator"],
            constraint.get("value_ratio"),
            constraint.get("evidence"),
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        constraints.append(constraint)

    soft_preferences: List[Dict[str, Any]] = []
    soft_seen: Set[Tuple[Any, ...]] = set()
    for raw_preference in raw_payload.get("soft_preferences") or []:
        preference, reason = _validate_soft_preference(text, raw_preference)
        if preference is None:
            discarded.append(
                {
                    "kind": "soft_preference",
                    "reason": reason,
                    "candidate": raw_preference,
                }
            )
            continue
        dedupe_key = (
            preference["subject_type"],
            preference["subject"],
            preference["direction"],
            preference.get("evidence"),
        )
        if dedupe_key in soft_seen:
            continue
        soft_seen.add(dedupe_key)
        soft_preferences.append(preference)

    # LLM이 hard constraint 문장에서 선호 표현 일부만 잘라
    # soft preference로 중복 추출하더라도 Rule 6-2를 강제한다.
    # evidence가 서로 포함 관계이고 실제 대상 자산이 하나라도 겹칠 때만 제거한다.
    filtered_soft_preferences: List[Dict[str, Any]] = []
    for preference in soft_preferences:
        preference_evidence = _normalize_for_match(
            str(preference.get("evidence") or "")
        )
        preference_assets = _constraint_subject_assets(preference)

        duplicate_of_hard_constraint = False
        for constraint in constraints:
            constraint_evidence = _normalize_for_match(
                str(constraint.get("evidence") or "")
            )
            constraint_assets = _constraint_subject_assets(constraint)

            evidence_overlaps = bool(
                preference_evidence
                and constraint_evidence
                and (
                    preference_evidence in constraint_evidence
                    or constraint_evidence in preference_evidence
                )
            )
            subject_overlaps = bool(preference_assets & constraint_assets)

            if evidence_overlaps and subject_overlaps:
                duplicate_of_hard_constraint = True
                break

        if duplicate_of_hard_constraint:
            discarded.append(
                {
                    "kind": "soft_preference",
                    "reason": "duplicate_of_hard_constraint",
                    "candidate": preference,
                }
            )
            continue

        filtered_soft_preferences.append(preference)

    soft_preferences, less_specific_preferences = _dedupe_soft_preferences(
        filtered_soft_preferences
    )
    for preference in less_specific_preferences:
        discarded.append(
            {
                "kind": "soft_preference",
                "reason": "less_specific_group_duplicate",
                "candidate": preference,
            }
        )

    liquidity, liquidity_discarded = _validate_liquidity(text, raw_payload.get("liquidity") or {})
    for reason in liquidity_discarded:
        discarded.append({"kind": "liquidity", "reason": reason})

    accounts: Dict[str, Any] = {}
    raw_accounts = raw_payload.get("accounts") or {}
    for key in ("isa", "irp"):
        validated, reasons = _validate_account(text, key, raw_accounts.get(key) or {})
        accounts[key] = validated
        for reason in reasons:
            discarded.append({"kind": "account", "reason": reason})

    advisory_only = [
        item
        for item in (raw_payload.get("advisory_only") or [])
        if isinstance(item, str) and _evidence_exists(text, item)
    ]
    unmatched_segments = [
        item
        for item in (raw_payload.get("unmatched_segments") or [])
        if isinstance(item, str) and _evidence_exists(text, item)
    ]

    return {
        "constraints": constraints,
        "soft_preferences": soft_preferences,
        "liquidity": liquidity,
        "accounts": accounts,
        "advisory_only": advisory_only,
        "unmatched_segments": unmatched_segments,
        "discarded_claims": discarded,
    }


def _call_unique_llm(masked_text: str) -> Tuple[Dict[str, Any], Optional[str]]:
    user_prompt = (
        "[Unique 원문]\n"
        f"{masked_text}\n\n"
        "위 원문만 사용해 strict schema로 구조화하라. evidence는 반드시 원문에서 그대로 복사하라."
    )
    response = create_structured_completion(
        schema_name="unique_semantic_extraction",
        schema=UNIQUE_SEMANTIC_SCHEMA,
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=1_500,
    )
    payload = json.loads(extract_message_content(response))
    fingerprint = getattr(response, "system_fingerprint", None)
    return payload, fingerprint


def parse_unique_semantic(unique_value: Any) -> Dict[str, Any]:
    text = normalize_semantic_text(unique_value)
    if not text:
        return {
            "status": "empty",
            "constraints": [],
            "soft_preferences": [],
            "liquidity": {},
            "accounts": {"isa": {}, "irp": {}},
            "advisory_only": [],
            "unmatched_segments": [],
            "discarded_claims": [],
            "version": UNIQUE_SEMANTIC_VERSION,
        }
    if not env_enabled("PORTFOLIO_UNIQUE_LLM_ENABLED", default=True):
        return {
            "status": "disabled",
            "constraints": [],
            "soft_preferences": [],
            "liquidity": {},
            "accounts": {"isa": {}, "irp": {}},
            "advisory_only": [],
            "unmatched_segments": [text],
            "discarded_claims": [],
            "version": UNIQUE_SEMANTIC_VERSION,
        }

    masked_text = mask_sensitive_text(text)
    cache_key = stable_hash(
        "unique",
        UNIQUE_SEMANTIC_VERSION,
        get_semantic_deployment(),
        masked_text,
    )
    cached = _cache_get(cache_key)
    if cached is not None:
        cached["status"] = "cache_hit"
        return cached

    try:
        raw_payload, fingerprint = _call_unique_llm(masked_text)
        validated = _validate_llm_payload(masked_text, raw_payload)
        result = {
            "status": "live",
            **validated,
            "version": UNIQUE_SEMANTIC_VERSION,
            "input_hash": cache_key,
            "system_fingerprint": fingerprint,
        }
        _cache_put(cache_key, result)
        return copy.deepcopy(result)
    except Exception:
        logger.warning("Unique 의미 해석 LLM 실패 — 기존 결정론적 파서 결과만 사용합니다.")
        return {
            "status": "failed",
            "constraints": [],
            "soft_preferences": [],
            "liquidity": {},
            "accounts": {"isa": {}, "irp": {}},
            "advisory_only": [],
            "unmatched_segments": [text],
            "discarded_claims": [],
            "version": UNIQUE_SEMANTIC_VERSION,
        }


def _account_age(opened_year: Optional[int]) -> float:
    if opened_year is None:
        return 0.0
    return float(max(datetime.now(KST).year - int(opened_year), 0))


def _append_unique_item_once(items: List[Dict[str, Any]], item: Dict[str, Any]) -> None:
    signature = (
        item.get("type"),
        item.get("source"),
        item.get("amount"),
        item.get("account_exists"),
        item.get("start_year"),
    )
    for existing in items:
        existing_signature = (
            existing.get("type"),
            existing.get("source"),
            existing.get("amount"),
            existing.get("account_exists"),
            existing.get("start_year"),
        )
        if existing_signature == signature:
            return
    items.append(item)


def enrich_unique_profile(profile: Dict[str, Any], unique_value: Any) -> Dict[str, Any]:
    """기존 결정론적 profile을 보존하면서 LLM 검증 결과로 빈 항목만 보완한다."""

    result = copy.deepcopy(profile)
    semantic = parse_unique_semantic(unique_value)
    existing_constraints = list(
        result.get("semantic_constraints")
        or []
    )
    result["semantic_constraints"] = [
        *existing_constraints,
        *semantic.get("constraints", []),
    ]

    existing_soft_preferences = [
        item
        for item in (
            result.get("soft_preferences")
            or []
        )
        if isinstance(item, dict)
    ]
    incoming_soft_preferences = [
        item
        for item in (
            semantic.get("soft_preferences")
            or []
        )
        if isinstance(item, dict)
    ]
    merged_soft_preferences: List[
        Dict[str, Any]
    ] = []
    seen_soft_preferences: Set[
        Tuple[Any, ...]
    ] = set()
    for preference in [
        *existing_soft_preferences,
        *incoming_soft_preferences,
    ]:
        signature = (
            preference.get("subject_type"),
            preference.get("subject"),
            preference.get("direction"),
            preference.get("evidence"),
        )
        if signature in seen_soft_preferences:
            continue
        seen_soft_preferences.add(signature)
        merged_soft_preferences.append(
            copy.deepcopy(preference)
        )
    result["soft_preferences"] = (
        merged_soft_preferences
    )
    result["semantic_audit"] = {
        "status": semantic.get("status"),
        "version": semantic.get("version"),
        "input_hash": semantic.get("input_hash"),
        "system_fingerprint": semantic.get("system_fingerprint"),
        "applied_constraints": semantic.get("constraints", []),
        "applied_soft_preferences": semantic.get("soft_preferences", []),
        "advisory_only": semantic.get("advisory_only", []),
        "unmatched_input": semantic.get("unmatched_segments", []),
        "discarded_claims": semantic.get("discarded_claims", []),
        "separation_policy": "unique_only_no_tax_input",
        "recommendation_policy": (
            "hard_constraints_filter_then_soft_preferences_secondary_ranking"
        ),
    }

    items = list(result.get("items") or [])
    liquidity = semantic.get("liquidity") or {}
    current_liquidity_amount = float(result.get("liquidity_need_amount") or 0.0)
    if current_liquidity_amount <= 0 and liquidity.get("amount_krw") is not None:
        result["liquidity_need_amount"] = float(liquidity["amount_krw"])
        _append_unique_item_once(
            items,
            {
                "type": "liquidity_need",
                "amount": float(liquidity["amount_krw"]),
                "years_until_need": liquidity.get("years_until_need"),
                "source": "unique_llm_fallback",
                "evidence": liquidity.get("evidence"),
            },
        )
    if result.get("liquidity_need_years") is None and liquidity.get("years_until_need") is not None:
        result["liquidity_need_years"] = float(liquidity["years_until_need"])

    semantic_accounts = semantic.get("accounts") or {}
    for key in ("isa", "irp"):
        current = dict(result.get(key) or {})
        fallback = semantic_accounts.get(key) or {}
        if fallback:
            was_detected = bool(current.get("detected"))
            current["detected"] = True
            if not was_detected and fallback.get("account_exists") is not None:
                current["account_exists"] = bool(fallback["account_exists"])
            if current.get("start_year") is None and fallback.get("opened_year") is not None:
                current["start_year"] = int(fallback["opened_year"])
                current["account_age_years"] = _account_age(int(fallback["opened_year"]))
            if float(current.get("cumulative_contribution") or 0.0) <= 0 and fallback.get("cumulative_contribution_krw") is not None:
                current["cumulative_contribution"] = float(fallback["cumulative_contribution_krw"])
            if current.get("current_year_contribution") is None and fallback.get("current_year_contribution_krw") is not None:
                current["current_year_contribution"] = float(fallback["current_year_contribution_krw"])
            result[key] = current
            _append_unique_item_once(
                items,
                {
                    "type": f"{key}_account",
                    "account_exists": current.get("account_exists"),
                    "start_year": current.get("start_year"),
                    "account_age_years": current.get("account_age_years", 0.0),
                    "cumulative_contribution": current.get("cumulative_contribution", 0.0),
                    "current_year_contribution": current.get("current_year_contribution"),
                    "source": "unique_llm_fallback",
                    "evidence": fallback.get("evidence"),
                },
            )

    result["items"] = items
    result["parser_note"] = (
        str(result.get("parser_note") or "").rstrip()
        + " Unique LLM은 기존 규칙 파서가 놓친 계좌·유동성 사실을 빈 필드에만 보완하고, "
        "명시적 운용 지시는 hard constraint, 약한 관심·선호는 임의 비중 없이 "
        "동률 후보의 secondary ranking으로만 제공합니다."
    ).strip()
    return result


def _constraint_subject_assets(constraint: Dict[str, Any]) -> Set[str]:
    subject_type = constraint.get("subject_type")
    subject = constraint.get("subject")
    if subject_type == "asset" and subject in ASSET_TICKERS:
        return {str(subject)}
    if subject_type == "group" and subject in SEMANTIC_GROUP_ASSETS:
        return set(SEMANTIC_GROUP_ASSETS[str(subject)])
    return set()


def get_excluded_assets(profile: Optional[Dict[str, Any]]) -> Set[str]:
    excluded: Set[str] = set()
    for constraint in (profile or {}).get("semantic_constraints") or []:
        if constraint.get("operator") == "exclude":
            excluded.update(_constraint_subject_assets(constraint))
    return excluded


def _normalize_weight_map(weights: Optional[Dict[str, float]]) -> Optional[Dict[str, float]]:
    if not weights:
        return None
    cleaned = {
        asset: max(float(weights.get(asset, 0.0)), 0.0)
        for asset in ASSET_TICKERS
    }
    total = sum(cleaned.values())
    if total <= 0:
        return None
    return {asset: value / total for asset, value in cleaned.items()}


@lru_cache(maxsize=128)
def _normalize_weight_items(
    items: Tuple[Tuple[str, float], ...],
) -> Optional[Tuple[Tuple[str, float], ...]]:
    """동일한 현재 포트폴리오 비중의 정규화 결과를 재사용한다."""

    normalized = _normalize_weight_map(dict(items))
    if normalized is None:
        return None
    return tuple(normalized.items())


def _normalize_current_weight_map(
    weights: Optional[Dict[str, float]],
) -> Optional[Dict[str, float]]:
    """동일한 current_weights를 시뮬레이션 후보마다 다시 정규화하지 않는다."""

    if not isinstance(weights, dict) or not weights:
        return None

    try:
        # 실제 정규화에 사용되는 자산군만 캐시 키에 포함한다.
        # request_id 같은 무관한 메타데이터가 달라도 동일한 비중이면 캐시를 재사용한다.
        cache_key = tuple(
            sorted(
                (asset, float(value))
                for asset, value in weights.items()
                if asset in ASSET_TICKERS
            )
        )
    except (TypeError, ValueError):
        return _normalize_weight_map(weights)

    if not cache_key:
        return _normalize_weight_map(weights)

    cached = _normalize_weight_items(cache_key)
    return dict(cached) if cached is not None else None


def _subject_weight(weights: Dict[str, float], constraint: Dict[str, Any]) -> float:
    assets = _constraint_subject_assets(constraint)
    return float(sum(float(weights.get(asset, 0.0)) for asset in assets))


def calculate_soft_preference_alignment(
    *,
    candidate_weights: Dict[str, float],
    unique_profile: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """후보 비중과 고객의 약한 선호 간 정렬도를 계산한다."""

    candidate = _normalize_weight_map(candidate_weights)
    profile_dict = unique_profile if isinstance(unique_profile, dict) else {}
    raw_preferences = profile_dict.get("soft_preferences")
    preferences = (
        [item for item in raw_preferences if isinstance(item, dict)]
        if isinstance(raw_preferences, list)
        else []
    )
    if candidate is None or not preferences:
        return {
            "score": 0.0,
            "preference_count": 0,
            "details": [],
            "policy": "secondary_ranking_only_no_invented_weight",
        }

    components: List[float] = []
    details: List[Dict[str, Any]] = []
    for preference in preferences:
        direction = str(preference.get("direction") or "")
        assets = _constraint_subject_assets(preference)
        if direction not in {"prefer", "avoid"} or not assets:
            continue
        actual_ratio = min(
            max(float(sum(float(candidate.get(asset, 0.0)) for asset in assets)), 0.0),
            1.0,
        )
        component = actual_ratio if direction == "prefer" else 1.0 - actual_ratio
        components.append(component)
        details.append(
            {
                "subject_type": preference.get("subject_type"),
                "subject": preference.get("subject"),
                "direction": direction,
                "actual_ratio": actual_ratio,
                "alignment_component": component,
                "evidence": preference.get("evidence"),
            }
        )

    score = float(sum(components) / len(components)) if components else 0.0
    return {
        "score": score,
        "preference_count": len(components),
        "details": details,
        "policy": "secondary_ranking_only_no_invented_weight",
    }


def evaluate_unique_constraints(
    *,
    candidate_weights: Dict[str, float],
    unique_profile: Optional[Dict[str, Any]],
    current_weights: Optional[Dict[str, float]],
) -> Tuple[bool, List[Dict[str, Any]]]:
    """후보를 수정하지 않고 semantic hard constraint 통과 여부만 판단한다."""

    candidate = _normalize_weight_map(candidate_weights)
    if candidate is None:
        return False, [{"reason": "invalid_candidate_weights"}]
    current = _normalize_current_weight_map(current_weights)
    violations: List[Dict[str, Any]] = []

    for constraint in (unique_profile or {}).get("semantic_constraints") or []:
        operator = constraint.get("operator")
        actual = _subject_weight(candidate, constraint)
        expected = constraint.get("value_ratio")

        if operator == "exclude":
            passed = actual <= _EPSILON
        elif operator == "increase":
            if current is None:
                continue
            passed = actual + _EPSILON >= _subject_weight(current, constraint)
        elif operator == "decrease":
            if current is None:
                continue
            passed = actual <= _subject_weight(current, constraint) + _EPSILON
        elif operator == "minimum":
            passed = expected is not None and actual + _EPSILON >= float(expected)
        elif operator == "maximum":
            passed = expected is not None and actual <= float(expected) + _EPSILON
        elif operator == "target":
            if expected is None:
                passed = False
            else:
                digits = max(0, min(int(constraint.get("precision_digits") or 0), 4))
                passed = round(actual * 100.0, digits) == round(float(expected) * 100.0, digits)
        else:
            passed = True

        if not passed:
            violations.append(
                {
                    "subject_type": constraint.get("subject_type"),
                    "subject": constraint.get("subject"),
                    "operator": operator,
                    "actual_ratio": actual,
                    "expected_ratio": expected,
                    "evidence": constraint.get("evidence"),
                }
            )

    return not violations, violations


def validate_unique_constraint_consistency(
    unique_profile: Optional[Dict[str, Any]],
) -> List[str]:
    """시뮬레이션 전에 명백히 모순인 Unique 제약만 검출한다.

    현재 비중이 있어야 판단할 수 있는 increase/decrease는 여기서 막지 않고
    기존 후보 평가 단계에서 처리한다.
    """

    constraints = list((unique_profile or {}).get("semantic_constraints") or [])
    if not constraints:
        return []

    conflicts: List[str] = []
    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for constraint in constraints:
        subject_type = str(constraint.get("subject_type") or "")
        subject = str(constraint.get("subject") or "")
        if not _constraint_subject_assets(constraint):
            continue

        state = grouped.setdefault(
            (subject_type, subject),
            {
                "minimum": 0.0,
                "maximum": 1.0,
                "targets": [],
                "excluded": False,
            },
        )
        operator = constraint.get("operator")
        value = constraint.get("value_ratio")

        if operator == "exclude":
            state["excluded"] = True
            state["maximum"] = 0.0
        elif operator == "minimum" and value is not None:
            state["minimum"] = max(float(state["minimum"]), float(value))
        elif operator == "maximum" and value is not None:
            state["maximum"] = min(float(state["maximum"]), float(value))
        elif operator == "target" and value is not None:
            target = float(value)
            if not any(
                abs(target - existing) <= _EPSILON
                for existing in state["targets"]
            ):
                state["targets"].append(target)

    excluded_assets = get_excluded_assets(unique_profile)
    if excluded_assets >= set(ASSET_TICKERS):
        conflicts.append(
            "모든 자산이 투자 제외 대상으로 지정되어 추천 후보를 만들 수 없습니다."
        )

    required_by_exact_asset: Dict[str, float] = {}

    for (subject_type, subject), state in grouped.items():
        label = f"{subject_type}:{subject}"
        minimum = float(state["minimum"])
        maximum = float(state["maximum"])
        targets = list(state["targets"])

        if minimum > maximum + _EPSILON:
            conflicts.append(
                f"{label}의 최소 비중 {minimum:.2%}가 "
                f"최대 비중 {maximum:.2%}보다 큽니다."
            )

        if len(targets) > 1:
            formatted = ", ".join(
                f"{value:.2%}" for value in sorted(targets)
            )
            conflicts.append(
                f"{label}에 서로 다른 목표 비중이 동시에 지정되었습니다: "
                f"{formatted}."
            )

        target = targets[0] if len(targets) == 1 else None
        if target is not None and not (
            minimum - _EPSILON <= target <= maximum + _EPSILON
        ):
            conflicts.append(
                f"{label}의 목표 비중 {target:.2%}가 허용 범위 "
                f"{minimum:.2%}~{maximum:.2%} 밖입니다."
            )

        subject_assets = _constraint_subject_assets(
            {"subject_type": subject_type, "subject": subject}
        )
        positive_requirement = max(minimum, target or 0.0)
        if (
            subject_assets
            and subject_assets.issubset(excluded_assets)
            and positive_requirement > _EPSILON
        ):
            conflicts.append(
                f"{label}은 전부 제외된 자산으로 구성되지만 "
                f"{positive_requirement:.2%} 이상의 비중을 동시에 요구합니다."
            )

        if subject_type == "asset" and subject in ASSET_TICKERS:
            required_by_exact_asset[subject] = max(
                minimum,
                target or 0.0,
            )

    exact_asset_minimum_sum = sum(required_by_exact_asset.values())
    if exact_asset_minimum_sum > 1.0 + _EPSILON:
        conflicts.append(
            "개별 자산의 최소/목표 비중 합계가 "
            f"{exact_asset_minimum_sum:.2%}로 100%를 초과합니다."
        )

    return list(dict.fromkeys(conflicts))

def build_unique_constraint_warnings(request: Any) -> List[str]:
    profile = getattr(request, "unique_profile", {}) or {}
    constraints = profile.get("semantic_constraints") or []
    warnings: List[str] = []
    if any(item.get("operator") in {"increase", "decrease"} for item in constraints) and not getattr(request, "current_weights", None):
        warnings.append(
            "Unique에 현재 대비 확대/축소 지시가 있으나 current_weights가 없어 해당 방향성 제약은 이번 계산에서 적용하지 않았습니다."
        )
    status = (profile.get("semantic_audit") or {}).get("status")
    if status == "failed":
        warnings.append(
            "Unique LLM 의미 해석에 실패해 기존 결정론적 금액·ISA·IRP 파서 결과만 사용했습니다."
        )
    if status == "disabled":
        warnings.append(
            "PORTFOLIO_UNIQUE_LLM_ENABLED가 비활성화되어 기존 결정론적 Unique 파서만 사용했습니다."
        )
    return warnings
