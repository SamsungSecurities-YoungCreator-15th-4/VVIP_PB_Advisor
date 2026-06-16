"""DART 단일회사 주요계정 fetch + 파싱 (PB 인사이트용 핵심 재무지표).

엔드포인트 선택 이유: 주요계정(fnlttSinglAcnt)을 쓴다. PB 인사이트에 필요한 헤드라인
계정(매출액·영업이익·당기순이익·자산/부채/자본총계)이 정확히 이 응답에 들어 있어,
전체 XBRL(fnlttSinglAcntAll)을 파싱할 필요가 없다(가볍고 충분).

연결(CFS) 우선, 없으면 별도(OFS). 보고서는 가장 최근 확정 사업보고서(연간, 11011)를
연도를 내려가며 시도해 첫 유효 응답을 쓴다. 데이터 없으면 직전 연도로 폴백(사유 기록).

⚠️ 재무 데이터는 조회 시점 fetch 이며 RAG 임베딩 금지(시세·실시간성 데이터 벡터화 안 함
= 우리 차별점). 이 모듈은 파싱만 하고 벡터화하지 않는다.
결정성: 파싱에 random/now 의존 없음. "최신 연도" 자동결정은 today_year 인자로 덮어쓸 수
있어 재현 가능하다(now() 가 결과를 비결정적으로 바꾸지 않게).
"""

from dataclasses import dataclass, field
from datetime import date

from app.services.dart_client import get_single_account

_ANNUAL_REPORT_CODE = "11011"  # 사업보고서(연간)

# 가장 최근 연도부터 몇 년 거슬러 시도할지(상장폐지 직전·신규상장 등 데이터 공백 대비).
_YEAR_LOOKBACK = 3

# DART 계정명 → 우리 표준 필드. 손익 계정은 표기 변형("(손실)" 등) 대비 startswith.
_BS_EXACT = {
    "자산총계": "total_assets",
    "부채총계": "total_liabilities",
    "자본총계": "total_equity",
}


def _canon(text: str) -> str:
    return (text or "").replace(" ", "")


def _match_field(account_nm: str) -> str | None:
    a = _canon(account_nm)
    if a in _BS_EXACT:
        return _BS_EXACT[a]
    if a.startswith("매출액") or a in {"영업수익", "수익(매출액)"}:
        return "revenue"
    if a.startswith("영업이익"):
        return "operating_income"
    if a.startswith("당기순이익"):
        return "net_income"
    return None


def _parse_amount(raw: str) -> int | None:
    """'42,103,238,027,336' → 42103238027336. 빈값·'-' 등은 None(값 지어내지 않음)."""
    if raw is None:
        return None
    s = str(raw).replace(",", "").strip()
    if s in ("", "-"):
        return None
    try:
        return int(s)
    except ValueError:
        return None


# 응답에 노출할 표준 필드 순서/라벨(필드 스키마).
FINANCE_FIELDS: dict[str, str] = {
    "revenue": "매출액",
    "operating_income": "영업이익",
    "net_income": "당기순이익",
    "total_assets": "자산총계",
    "total_liabilities": "부채총계",
    "total_equity": "자본총계",
}


@dataclass
class FinancialResult:
    corp_code: str
    bsns_year: int
    reprt_code: str
    rcept_no: str            # 접수번호(공시 원문 식별자) — 감사추적
    fs_div: str              # CFS(연결)/OFS(별도)
    fs_label: str            # 연결/별도
    currency: str            # 원 단위(KRW)
    values: dict[str, int | None]  # FINANCE_FIELDS 키 → 금액(원). 없으면 None
    fallback_used: bool
    source_note: str
    candidates_tried: list[str] = field(default_factory=list)


def _parse_items(items: list[dict]) -> tuple[str, str, dict[str, int | None]]:
    """주요계정 list → (fs_div, rcept_no, {표준필드: 금액}). CFS 우선, 없으면 OFS."""
    fs_div = "CFS" if any(it.get("fs_div") == "CFS" for it in items) else "OFS"
    values: dict[str, int | None] = {k: None for k in FINANCE_FIELDS}
    rcept_no = ""
    for it in items:
        if it.get("fs_div") != fs_div:
            continue
        rcept_no = rcept_no or (it.get("rcept_no") or "")
        field_key = _match_field(it.get("account_nm", ""))
        if field_key and values.get(field_key) is None:
            values[field_key] = _parse_amount(it.get("thstrm_amount"))
    return fs_div, rcept_no, values


def fetch_financials(
    corp_code: str,
    bsns_year: int | None = None,
    today_year: int | None = None,
) -> FinancialResult | None:
    """corp_code 의 최신 확정 사업보고서 주요계정을 fetch·파싱한다.

    bsns_year 지정 시 그 연도만 조회(재현용). 미지정 시 today_year(기본 오늘 연도)
    기준으로 직전 연도부터 _YEAR_LOOKBACK 년 내려가며 첫 유효 응답을 쓴다.
    유효 응답이 없으면 None.
    """
    if bsns_year is not None:
        candidate_years = [bsns_year]
    else:
        seed = today_year if today_year is not None else date.today().year
        # 사업보고서(연간 Y)는 보통 Y+1 봄에 공시 → 직전 연도부터 시도.
        candidate_years = [seed - 1 - i for i in range(_YEAR_LOOKBACK)]

    tried: list[str] = []
    for idx, year in enumerate(candidate_years):
        tried.append(str(year))
        data = get_single_account(corp_code, year, _ANNUAL_REPORT_CODE)
        items = data.get("list") or []
        if data.get("status") != "000" or not items:
            continue
        fs_div, rcept_no, values = _parse_items(items)
        # 핵심 손익(매출/영업이익/순이익) 중 하나도 못 뽑으면 다음 연도 시도.
        if all(values.get(k) is None for k in ("revenue", "operating_income", "net_income")):
            continue
        return FinancialResult(
            corp_code=corp_code,
            bsns_year=year,
            reprt_code=_ANNUAL_REPORT_CODE,
            rcept_no=rcept_no,
            fs_div=fs_div,
            fs_label="연결" if fs_div == "CFS" else "별도",
            currency="KRW",
            values=values,
            fallback_used=idx > 0,
            source_note=(
                f"{year} 사업보고서({_ANNUAL_REPORT_CODE}) "
                f"{'연결' if fs_div=='CFS' else '별도'} 기준"
                + (" · 최신연도 데이터 없어 직전연도 폴백" if idx > 0 else "")
            ),
            candidates_tried=tried,
        )
    return None
