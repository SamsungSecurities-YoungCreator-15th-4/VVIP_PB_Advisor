"""DART OpenAPI 저수준 호출 헬퍼 (stage-2).

- corp_cls 확인(기업개황 company.json) — 동명 충돌 디스앰비규에이션에 사용.
- 단일회사 주요계정(fnlttSinglAcnt.json) — PB 인사이트용 핵심 재무계정.

보안: crtfc_key 는 환경변수(DART_API_KEY)에서만 읽고, 요청 URL·키 값을 예외 메시지/
로그/반환값 어디에도 넣지 않는다(stage-1 ingest_corp_code.py 와 동일 원칙).
재무 데이터는 조회 시점 fetch 이며 RAG 임베딩 대상이 아니다(시세·실시간성 데이터
벡터화 금지 = 우리 차별점). 이 모듈은 fetch·파싱만 하고 벡터화하지 않는다.
"""

import os

import httpx

# DART OpenAPI 엔드포인트. 키는 params 로만 전달하고 URL 을 출력하지 않는다.
_COMPANY_URL = "https://opendart.fss.or.kr/api/company.json"
_SINGLE_ACCOUNT_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcnt.json"

_TIMEOUT = 30.0


def _get_api_key() -> str:
    """DART_API_KEY 를 환경변수에서 읽는다. 값 자체는 예외에 절대 넣지 않는다."""
    key = os.getenv("DART_API_KEY")
    if not key:
        raise RuntimeError(
            "DART_API_KEY 환경변수가 설정되지 않았습니다. backend/.env 를 확인하세요 "
            "(.env.example 참고)."
        )
    return key


def _dart_get(url: str, params: dict) -> dict:
    """DART GET 호출. crtfc_key 를 주입해 JSON 을 반환한다(키/URL 미노출).

    네트워크 예외는 타입만 표면화한다(메시지에 URL·키가 섞이는 것을 방지).
    """
    key = _get_api_key()
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(url, params={"crtfc_key": key, **params})
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"DART 호출 실패: {type(exc).__name__}") from None


def get_company_overview(corp_code: str) -> dict:
    """기업개황. 디스앰비규에이션에 필요한 최소 필드만 추려 반환한다.

    반환: {status, message, corp_cls, corp_name, stock_code}
      · corp_cls: Y(코스피)·K(코스닥)·N(코넥스)=현상장, E(기타/비상장)=폐지·비상장.
        status=000(정상)은 폐지 여부와 무관하므로 corp_cls 가 실제 상장상태 판별자다.
    """
    data = _dart_get(_COMPANY_URL, {"corp_code": corp_code})
    return {
        "status": data.get("status", ""),
        "message": data.get("message", ""),
        "corp_cls": data.get("corp_cls", ""),
        "corp_name": data.get("corp_name", ""),
        "stock_code": data.get("stock_code", ""),
    }


def get_single_account(corp_code: str, bsns_year: int, reprt_code: str) -> dict:
    """단일회사 주요계정(fnlttSinglAcnt). 원본 응답(status, message, list)을 그대로 반환.

    reprt_code: 11011=사업보고서(연간)·11012=반기·11013=1분기·11014=3분기.
    데이터 없음이면 status='013'(조회된 데이타가 없습니다)이 온다(호출부에서 폴백 판단).
    """
    return _dart_get(
        _SINGLE_ACCOUNT_URL,
        {
            "corp_code": corp_code,
            "bsns_year": str(bsns_year),
            "reprt_code": reprt_code,
        },
    )
