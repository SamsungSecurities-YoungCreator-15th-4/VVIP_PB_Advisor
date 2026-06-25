"""corp_name/corp_code → 확정 corp_code 선택(디스앰비규에이션).

확정 규칙(게이트 ①②-b 통과):
  - 단일매칭(3,902건): DART 호출 없이 그대로 채택.
  - 동명 충돌(34쌍): 충돌 corp_code 들의 corp_cls 를 DART 기업개황으로 확인하여
      · 현상장(Y/K/N) 후보 1개  → 그 corp_code 채택(disambiguated)
      · 현상장 후보 0개(둘 다 E) → 제외(excluded_delisted), 사유 기록
      · 현상장 후보 2개 이상     → 수동확인(manual_review)
  ※ max(modify_date) 는 채택하지 않는다 — 폐지 법인이 현존 법인보다 modify_date 가
    더 최신인 반례(원바이오젠·원텍)가 실재하므로 corp_cls 가 유일한 판별자다.

결정성: random/now 의존 없음. corp_cls 는 resolve 1회 내에서 corp_code 당 1번만
조회(로컬 캐시)하여 중복 호출을 막는다.
감사추적: 제외/수동확인도 사유와 후보별 corp_cls 를 ResolveResult 에 담아 호출부가
추적·로깅할 수 있게 한다.
"""

from dataclasses import dataclass, field
from typing import Literal

from app.db.supabase import get_supabase
from app.services.dart_client import get_company_overview
from app.services.dart_corp import normalize_corp_name

ResolveStatus = Literal[
    "matched",            # 단일매칭 또는 corp_code 직접 검증 통과
    "disambiguated",      # 충돌이었으나 corp_cls 로 현존 유일 확정
    "excluded_delisted",  # 충돌 후보가 모두 폐지(E) — 재무 fetch 제외
    "manual_review",      # 현상장 후보 2개 이상 — 사람이 확인 필요
    "not_found",          # 매칭 없음
]

_LISTED_CLS = {"Y", "K", "N"}

# 흔한 약칭 → DART 등록명. DART 는 정식 등록명만 보유해 약칭(현대차·네이버 등)이
# 정규화 정확일치에서 누락된다. DB 로 등록명을 검증한 매핑만 둔다(추정 금지).
# 키는 normalize_corp_name 으로 정규화해 보관한다(아래 _NAME_ALIASES).
_RAW_NAME_ALIASES = {
    "현대차": "현대자동차",
    "기아차": "기아",
    "네이버": "NAVER",
    "하이닉스": "SK하이닉스",
    "LG엔솔": "LG에너지솔루션",
    "엘지엔솔": "LG에너지솔루션",
    "삼바": "삼성바이오로직스",
    "카뱅": "카카오뱅크",
}
_NAME_ALIASES = {
    normalize_corp_name(alias): canonical
    for alias, canonical in _RAW_NAME_ALIASES.items()
}


@dataclass
class CandidateInfo:
    corp_code: str
    corp_name: str
    stock_code: str
    corp_cls: str | None = None  # 충돌 해소 시에만 채워진다(단일매칭은 None)


@dataclass
class ResolveResult:
    status: ResolveStatus
    corp_code: str | None
    corp_name: str | None
    reason: str
    candidates: list[CandidateInfo] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        """재무 fetch 로 진행 가능한 상태인지(채택/확정만 True)."""
        return self.status in ("matched", "disambiguated")


def _looks_like_corp_code(value: str) -> bool:
    """DART corp_code 형식(8자리 숫자)인지."""
    return value.isdigit() and len(value) == 8


def _rows_by_corp_code(corp_code: str) -> list[dict]:
    return (
        get_supabase()
        .table("dart_corp_code")
        .select("corp_code,corp_name,stock_code,modify_date")
        .eq("corp_code", corp_code)
        .execute()
        .data
    )


def _rows_by_normalized(normalized: str) -> list[dict]:
    # eq(정확일치)로 조회한다. 저장 컬럼은 .lower() 재적재로 이미 소문자이고 normalize 도
    # 소문자를 내보내므로 정확일치가 성립한다. ilike 와 달리 입력의 %·_ 가 와일드카드로
    # 해석되지 않아 대량 매칭→DART 호출 폭주(DoS) 위험이 없다.
    return (
        get_supabase()
        .table("dart_corp_code")
        .select("corp_code,corp_name,stock_code,modify_date")
        .eq("corp_name_normalized", normalized)
        .execute()
        .data
    )


def resolve_corp_code(query: str) -> ResolveResult:
    """corp_name 또는 corp_code 를 받아 확정 corp_code 를 선택한다."""
    q = (query or "").strip()
    if not q:
        return ResolveResult("not_found", None, None, "빈 입력")

    # 1) corp_code 직접 입력 → DB 존재 검증 후 통과(현/폐 판단은 호출부가 필요 시).
    if _looks_like_corp_code(q):
        rows = _rows_by_corp_code(q)
        if not rows:
            return ResolveResult("not_found", None, None, f"corp_code {q} 미적재")
        r = rows[0]
        return ResolveResult(
            "matched", r["corp_code"], r["corp_name"],
            "corp_code 직접 매칭",
            [CandidateInfo(r["corp_code"], r["corp_name"], r.get("stock_code", ""))],
        )

    # 2) corp_name → 정규화(.lower 포함) 매칭.
    normalized = normalize_corp_name(q)
    if not normalized:
        return ResolveResult("not_found", None, None, "정규화 결과 빈 문자열")
    rows = _rows_by_normalized(normalized)

    if not rows:
        # 흔한 약칭이면 등록명으로 한 번 더 시도(현대차→현대자동차, 네이버→NAVER 등).
        canonical = _NAME_ALIASES.get(normalized)
        if canonical:
            normalized = normalize_corp_name(canonical)
            rows = _rows_by_normalized(normalized)

    if not rows:
        return ResolveResult("not_found", None, None, f"'{q}'(정규화 '{normalized}') 매칭 없음")

    if len(rows) == 1:
        r = rows[0]
        return ResolveResult(
            "matched", r["corp_code"], r["corp_name"], "단일매칭",
            [CandidateInfo(r["corp_code"], r["corp_name"], r.get("stock_code", ""))],
        )

    # 3) 동명 충돌 → corp_cls 로 디스앰비규에이션.
    cls_cache: dict[str, str] = {}
    candidates: list[CandidateInfo] = []
    for r in rows:
        code = r["corp_code"]
        if code not in cls_cache:
            cls_cache[code] = get_company_overview(code).get("corp_cls", "")
        candidates.append(
            CandidateInfo(code, r["corp_name"], r.get("stock_code", ""), cls_cache[code])
        )

    listed = [c for c in candidates if c.corp_cls in _LISTED_CLS]

    if len(listed) == 1:
        sel = listed[0]
        return ResolveResult(
            "disambiguated", sel.corp_code, sel.corp_name,
            f"corp_cls 현존 유일 ({sel.corp_cls})", candidates,
        )
    if len(listed) == 0:
        return ResolveResult(
            "excluded_delisted", None, candidates[0].corp_name,
            "상장폐지 법인 corp_cls=E (모든 후보) — 재무 fetch 제외", candidates,
        )
    return ResolveResult(
        "manual_review", None, candidates[0].corp_name,
        f"현상장 후보 {len(listed)}개 — 수동확인 필요", candidates,
    )
