# ruff: noqa: E501
"""§12-1. API 입력 어댑터 — 프론트 연동용 보조 로직.

검증된 사실: consultations API의 ips_json은 Goal/Asset/Return/Risk/Time/Tax/Liquidity/Legal/Unique
형태이고, 포트폴리오 계산 로직은 AnalysisRequest 형태를 사용한다.
프로젝트용 처리: /portfolio/calculate는 AnalysisRequest와 consultations 응답/ips_json을 모두 받을 수 있게 정규화한다.
"""

from datetime import datetime
from zoneinfo import ZoneInfo
import re
import numpy as np
from typing import Dict, List, Optional, Tuple, Any

from .constants import (
    DEFAULT_RISK_FREE_RATE,
    DEFAULT_CASH_RETURN,
    DEFAULT_BENCHMARK_KEY,
    DEFAULT_RANDOM_SEED,
)
from .assets import (
    ASSET_TICKERS,
    UNIQUE_ASSETS,
)
from .models import AnalysisRequest
from .tax_parser import (
    MONEY_EXPRESSION_PATTERN,
    apply_tax_profile_to_ips_payload,
    parse_tax_text,
    parse_money_krw,
)
from .utils import (
    canonicalize_asset_key,
    normalize_weights,
    safe_float,
    safe_round,
    normalize_target_after_tax_return,
)

KST = ZoneInfo("Asia/Seoul")

KOREAN_MONEY_UNITS = {
    "조": 1_000_000_000_000,
    "억": 100_000_000,
    "천만": 10_000_000,
    "백만": 1_000_000,
    "십만": 100_000,
    "만": 10_000,
    "천": 1_000,
}

# 금액·연도 파싱 정규식의 ReDoS 방어 상한. 정상 IPS·상담 텍스트는 이보다 훨씬 짧다.
# 비정상적으로 긴 입력은 잘라 정규식의 위치 재스캔(O(N^2))을 상수 시간으로 묶는다.
_MAX_TEXT_PARSE_LEN = 2000


def parse_amount_krw(value: Any, default: float = 0.0) -> float:
    """숫자, dict, 한국식 원화 표현에서 첫 번째 금액/숫자를 추출한다."""

    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return safe_float(value, default)

    if isinstance(value, dict):
        for key in (
            "amount",
            "need_amount",
            "unique_need_amount",
            "total_asset",
            "Asset",
            "asset",
            "value",
        ):
            if key in value:
                parsed = parse_amount_krw(value.get(key), default=None)
                if parsed is not None:
                    return parsed
        return default

    text_value = str(value).strip()[:_MAX_TEXT_PARSE_LEN]
    if not text_value:
        return default

    money = parse_money_krw(text_value)
    if money is not None:
        return float(money)

    # 투자기간 '10년'처럼 원화가 아닌 일반 숫자를 쓰는 기존 호출도 유지한다.
    number_match = re.search(
        r"-?[0-9]+(?:\.[0-9]+)?",
        text_value.replace(",", ""),
    )
    if number_match:
        return safe_float(number_match.group(0), default)
    return default





def parse_stt_asset_to_krw(value: Any) -> float:
    """STT Asset 계약을 원 단위로 변환한다.

    숫자/단위 없는 숫자 문자열은 억원 단위다.
    명시적 단위 문자열("18억", "2,000만 원")은 그대로 해석한다.
    내부 AnalysisRequest.total_asset에는 이 함수를 적용하지 않는다.
    """
    if value is None or isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return safe_float(value, 0.0) * 100_000_000

    text_value = str(value).strip()
    if not text_value:
        return 0.0
    if re.search(r"[조억만천원]", text_value):
        return parse_money_krw(text_value) or 0.0

    numeric = safe_float(text_value.replace(",", ""), default=np.nan)
    if not np.isfinite(numeric):
        return 0.0
    return float(numeric * 100_000_000)


def stringify_unique_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            parts.append(f"{key}: {stringify_unique_value(item)}")
        return " | ".join(parts)
    if isinstance(value, list):
        return " | ".join(stringify_unique_value(item) for item in value)
    return str(value)


def find_keyword_window(text: str, keywords: List[str], radius: int = 90) -> str:
    lower_text = text.lower()
    for keyword in keywords:
        index = lower_text.find(keyword.lower())
        if index >= 0:
            start = max(index - radius, 0)
            end = min(index + len(keyword) + radius, len(text))
            return text[start:end]
    return ""



def truncate_at_stop_keywords(text: str, stop_keywords: List[str]) -> str:
    lower_text = text.lower()
    cut_points = [
        lower_text.find(keyword.lower())
        for keyword in stop_keywords
        if lower_text.find(keyword.lower()) > 0
    ]
    if not cut_points:
        return text
    return text[: min(cut_points)]


def find_account_segment(
    text: str,
    keywords: List[str],
    stop_keywords: List[str],
    radius_before: int = 0,
    radius_after: int = 140,
) -> str:
    lower_text = text.lower()
    indexes = [
        lower_text.find(keyword.lower())
        for keyword in keywords
        if lower_text.find(keyword.lower()) >= 0
    ]
    if not indexes:
        return ""

    index = min(indexes)
    start = max(index - radius_before, 0)
    end = min(index + radius_after, len(text))

    stop_indexes = [
        lower_text.find(stop.lower(), index + 1)
        for stop in stop_keywords
        if lower_text.find(stop.lower(), index + 1) > index
    ]
    if stop_indexes:
        end = min(end, min(stop_indexes))

    return text[start:end]


def parse_start_year_from_text(text: str) -> Optional[int]:
    for pattern in (
        r"(19[0-9]{2}|20[0-9]{2})\s*년\s*(?:에\s*)?(?:가입|개설|시작)",
        r"(?:가입|개설|시작)\s*(?:연도|년도)?\s*[:=]?\s*(19[0-9]{2}|20[0-9]{2})",
    ):
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None


def calculate_account_age_years_from_start_year(start_year: Optional[int]) -> float:
    if start_year is None:
        return 0.0
    current_year = datetime.now(KST).year
    return float(max(current_year - int(start_year), 0))


def parse_relative_years_from_text(text: str) -> Optional[float]:
    match = re.search(
        r"([0-9]+(?:\.[0-9]+)?)\s*년\s*(?:후|뒤|내|안|이내)",
        text[:_MAX_TEXT_PARSE_LEN],
    )
    if match:
        return safe_float(match.group(1), 0.0)
    return None


def parse_amount_near_keywords(text: str, keywords: List[str]) -> float:
    window = find_keyword_window(text, keywords)
    if not window:
        return 0.0
    return parse_amount_krw(window)



def parse_explicit_money_amount_krw(value: Any) -> float:
    text_value = stringify_unique_value(value).strip()[:_MAX_TEXT_PARSE_LEN]
    if not text_value:
        return 0.0
    parsed = parse_money_krw(text_value)
    return float(parsed) if parsed is not None else 0.0



def parse_current_year_contribution(text: str, keywords: List[str]) -> Optional[float]:
    """ISA/IRP의 올해 납입액을 복합 한국식 금액 표현까지 포함해 추출한다."""

    window = find_keyword_window(text, keywords, radius=140)
    if not window:
        return None

    if re.search(
        r"(?:올해|금년|당해).{0,30}(?:납입|입금).{0,30}(?:없|무|0\s*원)",
        window,
    ):
        return 0.0
    if re.search(r"(?:납입|입금).{0,30}(?:없|무|0\s*원)", window):
        return 0.0

    money = MONEY_EXPRESSION_PATTERN
    patterns = (
        rf"(?:올해|금년|당해).{{0,45}}?{money}.{{0,15}}?(?:납입|입금)",
        rf"{money}.{{0,15}}?(?:올해|금년|당해).{{0,15}}?(?:납입|입금)",
    )
    for pattern in patterns:
        match = re.search(pattern, window, flags=re.IGNORECASE)
        if match:
            return parse_money_krw(match.group(1)) or 0.0
    return None


def contains_negative_account_signal(text: str, keywords: List[str]) -> bool:
    window = find_keyword_window(text, keywords, radius=80)
    if not window:
        return False
    return bool(re.search(r"(?:미가입|없음|없다|안\s*만듦|안\s*만들)", window))



def parse_liquidity_need_amount(unique_value: Any, text: str) -> float:
    """Unique에서 별도 확보해야 하는 유동성 금액만 추출한다.

    퍼센트와 금액이 같은 문장에 있어도 원화 표현만 골라낸다.
    ISA/IRP 납입액은 개인 필요자금으로 오인하지 않는다.
    """

    if isinstance(unique_value, dict):
        for key in (
            "unique_need_amount",
            "need_amount",
            "liquidity_need_amount",
            "required_amount",
            "personal_need_amount",
        ):
            if key in unique_value:
                return parse_amount_krw(unique_value.get(key))

    personal_liquidity_keywords = [
        "전세",
        "주거",
        "목돈",
        "필요자금",
        "필요 자금",
        "필요",
        "유동성",
        "생활비",
        "학자금",
        "결혼",
        "병원",
        "긴급",
    ]
    for keyword in personal_liquidity_keywords:
        window = find_keyword_window(text, [keyword], radius=120)
        window = truncate_at_stop_keywords(
            window,
            [
                "ISA",
                "isa",
                "IRP",
                "irp",
                "개인종합자산관리",
                "개인형퇴직연금",
                "퇴직연금",
            ],
        )
        amount = parse_explicit_money_amount_krw(window)
        if amount > 0:
            return amount

    has_account_info = bool(
        find_keyword_window(text, ["isa", "개인종합자산관리"], radius=30)
        or find_keyword_window(
            text,
            ["irp", "개인형퇴직연금", "퇴직연금"],
            radius=30,
        )
    )
    if has_account_info:
        return 0.0

    stripped = text.strip()
    if re.fullmatch(r"[0-9,]+(?:\.[0-9]+)?", stripped):
        return parse_amount_krw(stripped)

    # '5억원 필요, 배당주 20% 이상'에서 20%는 무시하고 5억원만 추출한다.
    return parse_explicit_money_amount_krw(stripped)



def extract_generic_client_context(unique_value: Any, text: str) -> Dict[str, Any]:
    """Extract only generic, auditable context flags; never persona-name rules."""
    lower = text.lower()
    has_corporation = bool(
        re.search(r"법인|회사\s*대표|기업\s*대표|사업체|오너|경영권", lower)
    )
    estate_succession_goal = bool(
        re.search(r"가업\s*승계|기업\s*승계|상속|증여|후계", lower)
    )
    corporate_liquidity_window = find_keyword_window(
        text, ["법인", "운전자금", "사업자금", "회사 자금"], radius=140
    )
    corporate_liquidity_window = truncate_at_stop_keywords(
        corporate_liquidity_window,
        ["ISA", "isa", "IRP", "irp", "개인종합자산관리", "개인형퇴직연금"],
    )
    corporate_liquidity_need = 0.0
    if corporate_liquidity_window and re.search(
        r"운전자금|사업자금|법인.{0,20}유동성|회사.{0,20}유동성",
        corporate_liquidity_window,
    ):
        corporate_liquidity_need = parse_amount_krw(corporate_liquidity_window)

    flags: List[str] = []
    if has_corporation:
        flags.append("corporate_finance_review_required")
    if estate_succession_goal:
        flags.append("estate_succession_review_required")

    return {
        "has_corporation": has_corporation,
        "estate_succession_goal": estate_succession_goal,
        "corporate_liquidity_need_amount": safe_round(
            corporate_liquidity_need, 0
        ),
        "advisory_flags": flags,
        "calculation_scope": (
            "개인 투자포트폴리오와 명시된 단기 필요자금만 계산. "
            "법인세·기업가치·지분이전 세액은 별도 법인/세무 모듈 검토 대상."
        ),
    }


def extract_unique_profile(unique_value: Any) -> Dict[str, Any]:
    """Unique 원문에서 현재 엔진이 안전하게 해석 가능한 정보만 추출한다.

    LLM을 붙이지 않는 이상 '무엇이든 의미까지 이해'할 수는 없으므로,
    원문은 raw/text로 보존하고 금액·상대시점·ISA·IRP 같은 명시 패턴만 반영한다.
    """
    text = stringify_unique_value(unique_value).strip()
    client_context = extract_generic_client_context(unique_value, text)
    liquidity_amount = parse_liquidity_need_amount(unique_value, text)
    corporate_need = safe_float(
        client_context.get("corporate_liquidity_need_amount")
    )
    # 동일 문구가 일반 유동성 파서와 법인 파서에 동시에 잡힐 수 있어 합산하지 않고
    # 더 큰 명시 금액을 사용한다. 구조화 입력이 있으면 unique_need_amount로 직접 전달한다.
    liquidity_amount = max(liquidity_amount, corporate_need)
    liquidity_years = parse_relative_years_from_text(text)

    isa_window = find_account_segment(
        text,
        ["isa", "개인종합자산관리"],
        ["irp", "개인형퇴직연금", "퇴직연금"],
    )
    irp_window = find_account_segment(
        text,
        ["irp", "개인형퇴직연금", "퇴직연금"],
        ["isa", "개인종합자산관리"],
    )

    isa_start_year = parse_start_year_from_text(isa_window)
    isa_contribution = parse_explicit_money_amount_krw(isa_window) if isa_window else 0.0
    isa_account_exists = bool(isa_window) and not bool(
        re.search(r"(?:(?:ISA|isa|IRP|irp|개인종합자산관리|개인형퇴직연금|퇴직연금)\s*(?:계좌\s*)?(?:없음|없다)|미가입|계좌\s*없|가입.{0,5}안|개설.{0,5}안|안\s*만듦|안\s*만들)", isa_window)
    )

    irp_start_year = parse_start_year_from_text(irp_window)
    irp_current_year_contribution = parse_current_year_contribution(
        irp_window,
        ["irp", "개인형퇴직연금", "퇴직연금"],
    )
    irp_cumulative_contribution = parse_explicit_money_amount_krw(irp_window) if irp_window else 0.0
    irp_account_exists = bool(irp_window) and not bool(
        re.search(r"(?:(?:ISA|isa|IRP|irp|개인종합자산관리|개인형퇴직연금|퇴직연금)\s*(?:계좌\s*)?(?:없음|없다)|미가입|계좌\s*없|가입.{0,5}안|개설.{0,5}안|안\s*만듦|안\s*만들)", irp_window)
    )

    items: List[Dict[str, Any]] = []
    if liquidity_amount > 0:
        items.append(
            {
                "type": "liquidity_need",
                "amount": safe_round(liquidity_amount, 0),
                "years_until_need": safe_round(liquidity_years, 2)
                if liquidity_years is not None
                else None,
                "source": "unique",
            }
        )
    if isa_window:
        items.append(
            {
                "type": "isa_account",
                "account_exists": isa_account_exists,
                "start_year": isa_start_year,
                "account_age_years": safe_round(
                    calculate_account_age_years_from_start_year(isa_start_year),
                    2,
                ),
                "cumulative_contribution": safe_round(isa_contribution, 0),
                "source": "unique",
            }
        )
    if irp_window:
        items.append(
            {
                "type": "irp_account",
                "account_exists": irp_account_exists,
                "start_year": irp_start_year,
                "account_age_years": safe_round(
                    calculate_account_age_years_from_start_year(irp_start_year),
                    2,
                ),
                "cumulative_contribution": safe_round(irp_cumulative_contribution, 0),
                "current_year_contribution": safe_round(
                    irp_current_year_contribution,
                    0,
                )
                if irp_current_year_contribution is not None
                else None,
                "source": "unique",
            }
        )

    if client_context["advisory_flags"]:
        items.append(
            {
                "type": "advisory_context",
                "flags": client_context["advisory_flags"],
                "source": "unique",
            }
        )

    return {
        "raw": unique_value,
        "text": text,
        "items": items,
        "client_context": client_context,
        "liquidity_need_amount": safe_round(liquidity_amount, 0),
        "liquidity_need_years": safe_round(liquidity_years, 2)
        if liquidity_years is not None
        else None,
        "isa": {
            "detected": bool(isa_window),
            "account_exists": isa_account_exists,
            "start_year": isa_start_year,
            "account_age_years": safe_round(
                calculate_account_age_years_from_start_year(isa_start_year),
                2,
            ),
            "cumulative_contribution": safe_round(isa_contribution, 0),
        },
        "irp": {
            "detected": bool(irp_window),
            "account_exists": irp_account_exists,
            "start_year": irp_start_year,
            "account_age_years": safe_round(
                calculate_account_age_years_from_start_year(irp_start_year),
                2,
            ),
            "cumulative_contribution": safe_round(irp_cumulative_contribution, 0),
            "current_year_contribution": safe_round(
                irp_current_year_contribution,
                0,
            )
            if irp_current_year_contribution is not None
            else None,
        },
        "parser_note": (
            "LLM 미사용 규칙 기반 파서. 금액·n년 후·ISA/IRP 가입연도/납입액처럼 "
            "명시된 패턴만 계산 입력에 반영하고, 그 외 자연어는 raw/text로 보존한다."
        ),
    }


def apply_unique_profile_to_ips_payload(
    ips_payload: Dict[str, Any],
    unique_value: Any,
    adapter_warnings: List[str],
) -> Dict[str, Any]:
    from .unique_semantic import enrich_unique_profile

    profile = enrich_unique_profile(
        extract_unique_profile(unique_value),
        unique_value,
    )
    result = dict(ips_payload)

    existing_unique_profile = dict(result.get("unique_profile") or {})
    result["unique_profile"] = {
        # 원문 Unique를 다시 분석한 profile이 이전 계산에서 남은 값보다 우선한다.
        # 그래야 PB 승인 인사이트를 Unique에 추가한 뒤 재분석할 때 새 제약·금액이 실제로 반영된다.
        # (existing 먼저, profile 나중 → profile 키가 stale 값을 덮어쓴다. existing 전용 키는 보존.)
        **existing_unique_profile,
        **profile,
    }
    result["unique_items"] = result.get("unique_items") or profile["items"]
    result["client_context"] = {
        **profile.get("client_context", {}),
        **(result.get("client_context") or {}),
    }

    if safe_float(result.get("unique_need_amount")) <= 0:
        result["unique_need_amount"] = profile["liquidity_need_amount"]

    if not result.get("unique_asset"):
        result["unique_asset"] = normalize_unique_asset_value(unique_value)

    isa_info = profile["isa"]
    if isa_info["detected"]:
        if "isa_account_exists" not in result:
            result["isa_account_exists"] = isa_info["account_exists"]
        if safe_float(result.get("isa_account_age_years")) <= 0:
            result["isa_account_age_years"] = isa_info["account_age_years"]
        if safe_float(result.get("isa_cumulative_contribution")) <= 0:
            result["isa_cumulative_contribution"] = isa_info["cumulative_contribution"]
        if isa_info.get("current_year_contribution") is not None and safe_float(
            result.get("isa_current_year_contribution")
        ) <= 0:
            result["isa_current_year_contribution"] = isa_info[
                "current_year_contribution"
            ]

    irp_info = profile["irp"]
    if irp_info["detected"]:
        if "irp_account_exists" not in result:
            result["irp_account_exists"] = irp_info["account_exists"]
        if safe_float(result.get("irp_account_age_years")) <= 0:
            result["irp_account_age_years"] = irp_info["account_age_years"]
        if safe_float(result.get("irp_cumulative_contribution")) <= 0:
            result["irp_cumulative_contribution"] = irp_info["cumulative_contribution"]
        if irp_info["current_year_contribution"] is not None and safe_float(
            result.get("irp_current_year_contribution")
        ) <= 0:
            result["irp_current_year_contribution"] = irp_info[
                "current_year_contribution"
            ]

    if profile["text"] and not profile["items"]:
        adapter_warnings.append(
            "Unique 원문은 보존했지만 규칙 기반 파서가 계산에 반영할 수 있는 "
            "금액·시점·ISA·IRP 패턴을 찾지 못했습니다."
        )

    return result


def normalize_risk_profile_value(value: Any) -> str:
    text_value = str(value or "").strip().lower()
    mapping = {
        "안정형": "conservative",
        "보수형": "conservative",
        "conservative": "conservative",
        "균형형": "balanced",
        "중립형": "balanced",
        "balanced": "balanced",
        "공격형": "aggressive",
        "적극형": "aggressive",
        "aggressive": "aggressive",
    }
    if text_value in mapping:
        return mapping[text_value]
    raise ValueError(f"투자성향 값을 해석할 수 없습니다: {value}")


def normalize_liquidity_value(value: Any) -> str:
    text_value = str(value or "").strip().lower()
    mapping = {
        "낮음": "low",
        "낮은": "low",
        "low": "low",
        "중간": "mid",
        "보통": "mid",
        "중": "mid",
        "medium": "mid",
        "mid": "mid",
        "높음": "high",
        "높은": "high",
        "high": "high",
    }
    if text_value in mapping:
        return mapping[text_value]
    raise ValueError(f"유동성 값을 해석할 수 없습니다: {value}")


def normalize_tax_sensitivity_value(value: Any) -> str:
    text_value = str(value or "").strip().lower()
    mapping = {
        "낮음": "low",
        "낮은": "low",
        "low": "low",
        "중간": "medium",
        "보통": "medium",
        "중": "medium",
        "mid": "medium",
        "medium": "medium",
        "높음": "high",
        "높은": "high",
        "high": "high",
    }
    if text_value in mapping:
        return mapping[text_value]
    raise ValueError(f"세금 민감도 값을 해석할 수 없습니다: {value}")


def normalize_unique_asset_value(value: Any) -> str:
    if value is None:
        return "cash"

    if isinstance(value, dict):
        for key in ("unique_asset", "asset_class", "asset", "type"):
            if key in value:
                return normalize_unique_asset_value(value.get(key))
        return "cash"

    text_value = str(value).strip()
    canonical = canonicalize_asset_key(text_value)
    if canonical in UNIQUE_ASSETS:
        return canonical

    personal_liquidity_keywords = (
        "전세",
        "주거",
        "목돈",
        "필요",
        "유동성",
        "생활비",
        "학자금",
        "결혼",
        "병원",
        "긴급",
    )
    if any(keyword in text_value for keyword in personal_liquidity_keywords):
        return "cash"
    if "분리" in text_value:
        return "separate_tax_bond"
    if "저쿠폰" in text_value:
        return "low_coupon_bond"
    if "채" in text_value or "국채" in text_value:
        return "general_bond"
    return "cash"


def extract_flat_ips_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """상담 API 응답 또는 ips_json 자체에서 flat IPS dict를 꺼낸다."""
    candidate = payload

    if "ips_json" in candidate and isinstance(candidate["ips_json"], dict):
        candidate = candidate["ips_json"]
    elif "ips" in candidate and isinstance(candidate["ips"], dict):
        candidate = candidate["ips"]

    rrttllu = candidate.get("RRTTLLU")
    if isinstance(rrttllu, dict):
        flattened = {
            "Goal": candidate.get("Goal"),
            "Asset": candidate.get("Asset"),
        }
        flattened.update(rrttllu)
        candidate = flattened

    required_keys = {"Asset", "Risk", "Time", "Tax", "Liquidity"}
    if not required_keys.issubset(candidate.keys()):
        missing = sorted(required_keys - set(candidate.keys()))
        raise ValueError(
            "AnalysisRequest 또는 상담 IPS 형식으로 해석할 수 없습니다. "
            f"필수 IPS 키 누락: {missing}"
        )

    return candidate



def extract_request_metadata(payload: Dict[str, Any]) -> Dict[str, Any]:
    """명세서 ⑤ 요청에서 고객·상담 식별자를 추출한다."""
    client_id = payload.get("client_id") or payload.get("customer_id")
    consultation_id = payload.get("consultation_id")

    nested_consultation = payload.get("consultation")
    if not consultation_id and isinstance(nested_consultation, dict):
        consultation_id = nested_consultation.get("consultation_id")

    return {
        "client_id": str(client_id) if client_id else None,
        "consultation_id": str(consultation_id) if consultation_id else None,
    }


def extract_current_weights_from_portfolio(
    payload: Dict[str, Any],
    adapter_warnings: List[str],
) -> Optional[Dict[str, float]]:
    """명세서 current_portfolio 배열을 내부 current_weights dict로 변환한다."""
    current_portfolio = payload.get("current_portfolio")

    if current_portfolio is None:
        ips_payload = payload.get("ips")
        if isinstance(ips_payload, dict):
            current_portfolio = ips_payload.get("current_portfolio")

    if current_portfolio is None:
        explicit_weights = payload.get("current_weights")
        if explicit_weights is not None:
            return normalize_weights(explicit_weights)

        ips_payload = payload.get("ips")
        if isinstance(ips_payload, dict) and ips_payload.get("current_weights") is not None:
            return normalize_weights(ips_payload["current_weights"])

        adapter_warnings.append(
            "current_portfolio/current_weights 입력이 없어 현재 포트폴리오는 "
            "현금 100%로 계산했습니다."
        )
        return None

    if not isinstance(current_portfolio, list) or len(current_portfolio) == 0:
        raise ValueError("current_portfolio는 비어 있지 않은 배열이어야 합니다.")

    weights: Dict[str, float] = {}
    total_weight_percent = 0.0

    for item in current_portfolio:
        if not isinstance(item, dict):
            raise ValueError("current_portfolio의 각 항목은 객체여야 합니다.")

        asset_class = item.get("asset_class")
        if asset_class is None:
            raise ValueError("current_portfolio 항목에 asset_class가 필요합니다.")

        asset = canonicalize_asset_key(str(asset_class))
        if asset not in ASSET_TICKERS:
            raise ValueError(f"지원하지 않는 current_portfolio 자산군입니다: {asset_class}")

        weight_percent = safe_float(item.get("weight"), default=np.nan)
        if not np.isfinite(weight_percent) or weight_percent < 0:
            raise ValueError("current_portfolio.weight는 0 이상의 숫자여야 합니다.")

        total_weight_percent += weight_percent
        weights[asset] = weights.get(asset, 0.0) + weight_percent / 100.0

    if abs(total_weight_percent - 100.0) > 1e-6:
        raise ValueError(
            "current_portfolio weight 합계는 100이어야 합니다. "
            f"현재 합계: {total_weight_percent}"
        )

    return normalize_weights(weights)

def extract_optional_age(payload: Dict[str, Any]) -> Optional[int]:
    candidates: List[Any] = [
        payload.get("age"),
        payload.get("customer_age"),
        payload.get("client_age"),
    ]
    for nested_key in ("customer", "client", "persona", "profile", "ips"):
        nested = payload.get(nested_key)
        if isinstance(nested, dict):
            candidates.extend(
                [nested.get("age"), nested.get("customer_age"), nested.get("client_age")]
            )
    for value in candidates:
        if value is None or isinstance(value, bool):
            continue
        match = re.search(r"[0-9]{1,3}", str(value))
        if match:
            age = int(match.group(0))
            if 0 <= age <= 120:
                return age
    return None




def apply_legal_profile_to_ips_payload(
    ips_payload: Dict[str, Any],
    legal_value: Any,
) -> Dict[str, Any]:
    from .legal_semantic import apply_legal_profile_to_ips_payload as _apply_legal

    return _apply_legal(ips_payload, legal_value)

def normalize_analysis_request_payload(
    payload: Dict[str, Any],
) -> Tuple[AnalysisRequest, Dict[str, Any]]:
    """명세서 ⑤용 payload를 내부 AnalysisRequest로 정규화한다.

    허용 입력:
    1. 기존 AnalysisRequest: {"ips": {...}, "scenario": {...}}
    2. 상담 API 응답: {"ips_json": {Goal, Asset, ...}, ...}
    3. flat IPS dict: {Goal, Asset, Return, Risk, Time, Tax, Liquidity, Legal, Unique}
    """
    adapter_warnings: List[str] = []
    request_metadata = extract_request_metadata(payload)
    current_weights_from_portfolio = extract_current_weights_from_portfolio(
        payload,
        adapter_warnings,
    )

    has_analysis_ips = (
        "ips" in payload
        and isinstance(payload.get("ips"), dict)
        and "total_asset" in payload["ips"]
    )
    if has_analysis_ips:
        normalized_payload = dict(payload)
        normalized_ips = dict(normalized_payload["ips"])
        normalized_ips["liquidity_need"] = normalize_liquidity_value(
            normalized_ips.get("liquidity_need")
        )
        if current_weights_from_portfolio is not None:
            normalized_ips["current_weights"] = current_weights_from_portfolio
        scenario_payload = normalized_payload.get("scenario")
        rrttllu_payload = (
            scenario_payload.get("rrttllu")
            if isinstance(scenario_payload, dict)
            else {}
        )
        unique_value = (
            normalized_ips.get("Unique")
            or normalized_ips.get("unique")
            or normalized_ips.get("unique_raw")
        )
        if unique_value is None and isinstance(rrttllu_payload, dict):
            unique_value = rrttllu_payload.get("Unique")
        if unique_value is not None:
            normalized_ips = apply_unique_profile_to_ips_payload(
                normalized_ips,
                unique_value,
                adapter_warnings,
            )

        tax_value = (
            normalized_ips.get("tax_text")
            or normalized_ips.get("Tax")
            or normalized_ips.get("tax")
        )
        if tax_value is None and isinstance(rrttllu_payload, dict):
            tax_value = rrttllu_payload.get("Tax")
        if tax_value is not None:
            normalized_ips = apply_tax_profile_to_ips_payload(
                normalized_ips,
                tax_value,
            )

        legal_value = (
            normalized_ips.get("legal_text")
            or normalized_ips.get("Legal")
            or normalized_ips.get("legal")
        )
        if legal_value is None and isinstance(rrttllu_payload, dict):
            legal_value = rrttllu_payload.get("Legal")
        if legal_value is not None:
            normalized_ips = apply_legal_profile_to_ips_payload(
                normalized_ips,
                legal_value,
            )

        normalized_payload["ips"] = normalized_ips
        return AnalysisRequest(**normalized_payload), {
            "source": "analysis_request",
            "client_id": request_metadata["client_id"],
            "consultation_id": request_metadata["consultation_id"],
            "warnings": adapter_warnings,
        }

    flat_ips = extract_flat_ips_payload(payload)

    total_asset = parse_stt_asset_to_krw(flat_ips.get("Asset"))
    if total_asset <= 0:
        raise ValueError("IPS의 Asset 값을 총자산으로 해석할 수 없습니다.")

    investment_horizon = int(max(parse_amount_krw(flat_ips.get("Time")), 1))
    unique_value = flat_ips.get("Unique")
    from .unique_semantic import enrich_unique_profile

    unique_profile = enrich_unique_profile(
        extract_unique_profile(unique_value),
        unique_value,
    )
    tax_value = flat_ips.get("Tax")
    tax_profile = parse_tax_text(tax_value)
    legal_value = flat_ips.get("Legal")
    from .legal_semantic import parse_legal_semantic

    legal_profile = parse_legal_semantic(legal_value)
    unique_need_amount = safe_float(unique_profile.get("liquidity_need_amount"))
    if unique_need_amount <= 0:
        adapter_warnings.append(
            "IPS의 Unique 값에서 별도 필요자금을 숫자로 추출하지 못해 unique_need_amount=0으로 계산했습니다."
        )

    scenario_input = payload.get("scenario") if isinstance(payload.get("scenario"), dict) else {}
    if not scenario_input:
        adapter_warnings.append(
            "scenario 입력이 없어 stress shock은 0으로 두고, 기준 금리는 기본 risk_free_rate를 사용했습니다."
        )

    base_fx_rate = safe_float(
        scenario_input.get("base_fx_rate_krw_per_usd", payload.get("base_fx_rate_krw_per_usd")),
        1.0,
    )
    if base_fx_rate == 1.0 and "base_fx_rate_krw_per_usd" not in scenario_input:
        adapter_warnings.append(
            "base_fx_rate_krw_per_usd가 없어 1.0을 표시용 기본값으로 사용했습니다. 스트레스 테스트 화면에서는 실제 환율 입력을 넘겨야 합니다."
        )

    analysis_payload = {
        "ips": {
            "total_asset": total_asset,
            "unique_need_amount": unique_need_amount,
            "unique_asset": normalize_unique_asset_value(unique_value),
            "unique_items": unique_profile["items"],
            "unique_profile": unique_profile,
            "age": extract_optional_age(payload),
            "client_context": unique_profile.get("client_context", {}),
            "target_after_tax_return": normalize_target_after_tax_return(
                flat_ips.get("Return"),
                percent_input=True,
            ),
            "risk_profile": normalize_risk_profile_value(flat_ips.get("Risk")),
            "investment_horizon_years": investment_horizon,
            "tax_text": stringify_unique_value(tax_value),
            "tax_profile": tax_profile,
            "tax_sensitivity": None,
            "legal_text": legal_profile.get("text", ""),
            "legal_profile": legal_profile,
            "liquidity_need": normalize_liquidity_value(flat_ips.get("Liquidity")),
            "current_weights": current_weights_from_portfolio,
            "risk_free_rate": safe_float(
                scenario_input.get("risk_free_rate", payload.get("risk_free_rate")),
                DEFAULT_RISK_FREE_RATE,
            ),
            "cash_return": safe_float(
                payload.get("cash_return"),
                DEFAULT_CASH_RETURN,
            ),
            "period": str(payload.get("period", "5y")),
            "benchmark_key": payload.get(
                "benchmark_key",
                payload.get("benchmark", DEFAULT_BENCHMARK_KEY),
            ),
            "num_simulations": int(safe_float(payload.get("num_simulations"), 3000)),
            "expected_return_haircut": safe_float(
                payload.get("expected_return_haircut"),
                0.75,
            ),
            "random_seed": int(
                safe_float(payload.get("random_seed"), DEFAULT_RANDOM_SEED)
            ),
            "overseas_realized_loss": safe_float(
                payload.get("overseas_realized_loss"), 0.0
            ),
            "overseas_realized_gain_krw": (
                safe_float(payload.get("overseas_realized_gain_krw"), 0.0)
                if payload.get("overseas_realized_gain_krw") is not None
                else None
            ),
            "other_financial_income": safe_float(
                payload.get("other_financial_income"), 0.0
            ),
            "external_financial_income_krw": (
                safe_float(payload.get("external_financial_income_krw"), 0.0)
                if payload.get("external_financial_income_krw") is not None
                else None
            ),
            "external_financial_income_manwon": (
                safe_float(payload.get("external_financial_income_manwon"), 0.0)
                if payload.get("external_financial_income_manwon") is not None
                else None
            ),
            "pension_tax_liability_sufficient": bool(
                payload.get("pension_tax_liability_sufficient", True)
            ),
            "isa_account_exists": unique_profile["isa"]["account_exists"],
            "isa_account_age_years": unique_profile["isa"]["account_age_years"],
            "isa_cumulative_contribution": unique_profile["isa"]["cumulative_contribution"],
            "isa_current_year_contribution": (
                safe_float(payload.get("isa_current_year_contribution"), 0.0)
                if payload.get("isa_current_year_contribution") is not None
                else safe_float(
                    unique_profile["isa"].get("current_year_contribution"),
                    0.0,
                )
            ),
            "irp_account_exists": unique_profile["irp"]["account_exists"],
            "irp_account_age_years": unique_profile["irp"]["account_age_years"],
            "irp_cumulative_contribution": unique_profile["irp"]["cumulative_contribution"],
            "irp_current_year_contribution": (
                unique_profile["irp"]["current_year_contribution"]
                if unique_profile["irp"]["current_year_contribution"] is not None
                else 0.0
            ),
        },
        "scenario": {
            "base_interest_rate": safe_float(
                scenario_input.get(
                    "base_interest_rate",
                    payload.get("base_interest_rate"),
                ),
                DEFAULT_RISK_FREE_RATE,
            ),
            "base_fx_rate_krw_per_usd": base_fx_rate,
            "stress_interest_rate_shock": safe_float(
                scenario_input.get(
                    "stress_interest_rate_shock",
                    payload.get("stress_interest_rate_shock"),
                ),
                0.0,
            ),
            "stress_fx_shock": safe_float(
                scenario_input.get("stress_fx_shock", payload.get("stress_fx_shock")),
                0.0,
            ),
            "rrttllu": payload.get("rrttllu") or payload.get("RRTTLLU") or {},
            "stress_affects_scoring": bool(
                scenario_input.get(
                    "stress_affects_scoring",
                    payload.get("stress_affects_scoring", False),
                )
            ),
        },
    }

    analysis_payload["ips"] = apply_tax_profile_to_ips_payload(
        analysis_payload["ips"],
        tax_value,
    )

    return AnalysisRequest(**analysis_payload), {
        "source": "consultation_ips_adapter",
        "client_id": request_metadata["client_id"],
        "consultation_id": request_metadata["consultation_id"],
        "flat_ips_keys_used": sorted(flat_ips.keys()),
        "warnings": adapter_warnings,
    }
