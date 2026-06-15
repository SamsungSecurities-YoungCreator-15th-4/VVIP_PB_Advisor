"""DART 회사명 매핑 공용 헬퍼.

회사명 정규화(normalize_corp_name)는 적재(scripts/ingest_corp_code.py)와
조회(향후 /dart/insight) 양쪽에서 같은 규칙을 써야 매칭이 일관되므로 여기 둔다.
적재 시 dart_corp_code.corp_name_normalized 에 저장하는 값과, 조회 시 사용자
질의에서 뽑은 회사명을 정규화한 값이 정확히 같은 함수를 거쳐야 한다.

정규화 규칙(확정): 법인 표기 마커와 모든 공백을 제거한다(오타 fuzzy 매칭은 안 함).
  · "주식회사", "(주)" 제거 — 확정 규칙
  · "㈜"(U+321C), "（주）"(전각 괄호) 도 같은 마커의 표기 변형이라 함께 제거한다.
    DART corp_name 실데이터에 섞여 들어와 미제거 시 정확일치가 깨지기 때문이다.
  · 모든 공백 제거 — \\s 는 전각 공백(U+3000)까지 포함(파이썬 str 정규식은 유니코드 기본).
예) "삼성전자(주)" → "삼성전자", "(주)카카오" → "카카오", "주식회사 우아한형제들" → "우아한형제들"
"""

import re

# 제거 대상 법인 표기 마커. 모두 같은 "회사" 표기의 변형이다.
_CORP_MARKERS = ("주식회사", "(주)", "（주）", "㈜")

# 연속 공백(스페이스·탭·개행·전각공백 등)을 한 번에 제거하기 위한 패턴.
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_corp_name(name: str) -> str:
    """회사명에서 법인 마커와 모든 공백을 제거한 정규화 문자열을 반환한다."""
    normalized = name
    for marker in _CORP_MARKERS:
        normalized = normalized.replace(marker, "")
    return _WHITESPACE_RE.sub("", normalized)
