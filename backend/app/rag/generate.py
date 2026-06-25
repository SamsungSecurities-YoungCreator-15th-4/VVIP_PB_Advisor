"""RAG 생성부 — 검색된 청크로부터 answer 텍스트를 만든다.

"할루시네이션=즉사" 원칙: 생성기는 검색된 청크 밖의 내용을 만들 수 없고,
응답에는 citations 가 반드시 동반된다(라우터에서 강제).
생성기는 인터페이스(Generator)로 추상화하며, 추출형이 기본 구현이다.
"""

import re
from abc import ABC, abstractmethod
from typing import Any

from app.core.azure_openai import (
    get_insight_summary_client,
    get_insight_summary_deployment,
    get_llm_client,
    get_llm_deployment,
)


class Generator(ABC):
    """answer 생성기 인터페이스. chunks 는 retrieval.search_chunks 의 citation 구조."""

    @abstractmethod
    def generate(self, query: str, chunks: list[dict[str, Any]]) -> str:
        """검색된 청크만을 근거로 query 에 대한 answer 텍스트를 만든다."""


class ExtractiveGenerator(Generator):
    """추출형 생성기(기본): 검색된 청크 원문만 조립하고 새 사실을 추가하지 않는다."""

    def generate(self, query: str, chunks: list[dict[str, Any]]) -> str:
        if not chunks:
            raise ValueError("청크가 없으면 answer 를 생성할 수 없습니다 (라우터에서 404 처리).")

        # 유사도순 정렬은 RPC 가 보장하므로 입력 순서를 그대로 신뢰한다.
        lines = [f'"{query}" 관련 근거 문서에서 발췌한 내용입니다.', ""]
        for i, chunk in enumerate(chunks, start=1):
            title = chunk.get("title") or "제목 없음"
            lines.append(f"[근거 {i} · {title}]")
            lines.append(chunk["chunk"].strip())
            lines.append("")
        lines.append(
            "위 내용은 검색된 원문을 그대로 발췌한 것이며, "
            "자세한 근거는 아래 출처(citations)를 참조하세요."
        )
        return "\n".join(lines)


def strip_markdown(text: str) -> str:
    """LLM answer 에서 화면에 그대로 노출되면 안 되는 마크다운 기호를 제거한다.

    프론트는 answer 를 일반 텍스트로 렌더하므로 ``**굵게**``·``## 제목``·``` `code` ```
    같은 기호가 그대로 보인다. 모델에 마크다운 금지를 지시하지만(프롬프트 규칙),
    모델이 새어 보내는 경우를 대비한 방어적 후처리다. 내용(텍스트)은 보존하고 기호만 없앤다.
    """
    if not text:
        return text
    # 코드펜스(```lang ... ```)의 여는/닫는 펜스 마커만 제거하고 안쪽 코드는 보존한다.
    # 펜스 마커와 같은 줄의 info string(``` 다음 언어 라벨)까지 한 번에 지운다.
    # 부분식이 모두 선형(역참조·중첩수량자 없음)이라 ReDoS 위험이 없다.
    text = re.sub(r"```[^\n`]*", "", text)
    # 줄머리 ATX 헤더(## 제목)·인용(> )·리스트 불릿(- / * ) 기호만 제거(내용 보존).
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"^\s{0,3}#{1,6}\s+", "", line)
        line = re.sub(r"^\s{0,3}>\s?", "", line)
        line = re.sub(r"^(\s*)[*+-]\s+", r"\1", line)
        lines.append(line)
    text = "\n".join(lines)
    # 굵게/기울임 강조 기호 제거(**, __, *, _) — 안쪽 텍스트는 그대로 둔다.
    # 모두 부정 문자클래스 기반 선형 패턴이라 중첩 수량자로 인한 ReDoS 가 없다.
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", text)
    text = re.sub(r"__([^_\n]+)__", r"\1", text)
    # 기울임은 구분자 안쪽 첫 글자가 공백이 아닐 때만(예: '2 * 3' 같은 곱셈 오인 방지).
    text = re.sub(r"\*([^*\s\n][^*\n]*)\*", r"\1", text)
    text = re.sub(r"(?<!\w)_([^_\s\n][^_\n]*)_(?!\w)", r"\1", text)
    # 인라인 코드 백틱 제거.
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip()


def _format_chunks_for_prompt(chunks: list[dict[str, Any]]) -> str:
    """검색된 청크를 LLM 프롬프트용 근거 블록으로 묶는다(원문 그대로, 가공 없음)."""
    blocks = []
    for i, chunk in enumerate(chunks, start=1):
        title = chunk.get("title") or "제목 없음"
        chunk_text = chunk.get("chunk") or ""
        blocks.append(f"[근거 {i} · {title}]\n{chunk_text.strip()}")
    return "\n\n".join(blocks)


def normalize_insight_summary(text: str, max_chars: int = 90, min_chars: int = 35) -> str:
    """IPS unique 에 붙일 요약을 한 줄·명사형·완화된 최대 길이로 정규화한다."""
    summary = " ".join(text.split())
    summary = summary.strip("`\"'“”‘’")
    for prefix in ("요약:", "요약："):
        if summary.startswith(prefix):
            summary = summary.removeprefix(prefix).strip()
    summary = _normalize_summary_as_noun_phrase(summary)
    if len(summary) > max_chars:
        candidate = summary[:max_chars].rstrip(" ,.;:·-")
        last_space = candidate.rfind(" ")
        if last_space >= min_chars:
            candidate = candidate[:last_space].rstrip(" ,.;:·-")
        summary = candidate
    return _normalize_summary_as_noun_phrase(summary)


def _normalize_summary_as_noun_phrase(text: str) -> str:
    """LLM 또는 fallback 이 문장형을 반환해도 화면에는 명사형 구문으로 노출한다."""
    summary = text.strip().rstrip(" .。!?！？")
    if not summary:
        return summary

    summary = re.sub(
        r"^(?P<subject>[가-힣A-Za-z0-9]{2,})(?:이|가|은|는)\s+",
        r"\g<subject> ",
        summary,
    )
    summary = re.sub(r"(?<=\S{2})(?:이|가|은|는)\s+(?=\d)", " ", summary)
    sentence_endings = (
        ("확인되었습니다", "확인"),
        ("확인됐습니다", "확인"),
        ("확인됩니다", "확인"),
        ("상승했습니다", "상승"),
        ("하락했습니다", "하락"),
        ("증가했습니다", "증가"),
        ("감소했습니다", "감소"),
        ("예상됩니다", "예상"),
        ("전망됩니다", "전망"),
        ("판단됩니다", "판단"),
        ("보입니다", "보임"),
        ("높입니다", "높임"),
        ("줄입니다", "줄임"),
        ("나타납니다", "나타남"),
        ("미칩니다", "미침"),
        ("어렵습니다", "어려움"),
        ("하였습니다", "함"),
        ("했습니다", "함"),
        ("하겠습니다", "예정"),
        ("합니다", "함"),
        ("되었습니다", "됨"),
        ("됐습니다", "됨"),
        ("됩니다", "됨"),
        ("있습니다", "있음"),
        ("없습니다", "없음"),
        ("입니다", ""),
    )
    for ending, replacement in sentence_endings:
        if summary.endswith(ending):
            summary = summary[: -len(ending)] + replacement
            break

    noun_keywords = (
        r"상승|하락|증가|감소|확인|필요|부각|확대|축소|개선|악화|유지|전환|"
        r"강화|완화|부담|효과|영향|리스크|니즈|선호|검토|대응|관리|"
        r"예상|전망|우려|기대|가능성|판단|보임|높임|줄임|나타남|미침|어려움"
    )
    summary = re.sub(
        rf"(?:이|가|은|는|을|를)\s+(?=(?:함께\s+)?(?:{noun_keywords})(?:\s|$))",
        " ",
        summary,
    )
    return " ".join(summary.split()).strip(" ,.;:·-")


# answer 앞머리에 붙는 도입 인사말 패턴 — 폴백 요약이 이런 문장을 집지 않게 거른다.
_PREAMBLE_MARKERS = (
    "요약해",
    "요약하면",
    "정리해",
    "정리하면",
    "설명해",
    "안내해",
    "말씀드리",
    "알려드리",
    "다음과 같습니다",
    "아래와 같습니다",
)


def _is_substantive_sentence(sentence: str) -> bool:
    """실질 정보가 담긴 문장이면 True. 도입 인사말·번호머리·짧은 조각은 거른다."""
    # 'N.'·'N)' 같은 리스트 번호 머리를 떼고 내용만 본다(번호가 문장으로 잘리는 것 방지).
    stripped = re.sub(r"^\s*\d+[.)]\s*", "", sentence).strip().rstrip(" .。!?！？")
    if len(stripped) < 5:  # '1', '미국' 같은 토막은 실질 문장으로 보지 않는다.
        return False
    if stripped.endswith("드리겠습니다"):
        return False
    return not any(marker in stripped for marker in _PREAMBLE_MARKERS)


_NUMERIC_TOKEN_RE = re.compile(
    r"\d+(?:[,.]\d+)*(?:\s?(?:%|bp|bps|억원|조원|만원|원|년|개월|일|배|회|p))?"
)


def _contains_numeric_evidence(text: str) -> bool:
    """답변 원문에 있는 수치 근거를 포함한 문장인지 판별한다. 문장 앞 리스트 번호는 제외한다."""
    stripped = re.sub(r"^\s*\d+[.)]\s*", "", text)
    return bool(_NUMERIC_TOKEN_RE.search(stripped))


def fallback_insight_summary(answer: str) -> str:
    """mini 요약 실패 시 answer 의 수치 기반 '실질' 문장을 명사형으로 줄여 반환한다.

    answer 가 '~요약해 드리겠습니다' 같은 도입 인사말로 시작하면 그 문장은 건너뛰고
    실제 정보가 담긴 첫 문장을 고른다. 그중 수치가 있는 문장을 우선해 두루뭉실한
    요약이 노출되는 것을 줄인다.
    """
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.?!])\s+", answer.strip())
        if sentence.strip()
    ]
    substantive = [s for s in sentences if _is_substantive_sentence(s)]
    numeric_substantive = [s for s in substantive if _contains_numeric_evidence(s)]
    chosen = (numeric_substantive or substantive or sentences or [answer])[0]
    # 고른 문장 앞 리스트 번호 머리는 요약에 들어가지 않게 떼고 정규화한다.
    chosen = re.sub(r"^\s*\d+[.)]\s*", "", chosen)
    summary = normalize_insight_summary(chosen)
    if summary:
        return summary
    return "인사이트 요약 생성 실패"


class LLMGenerator(Generator):
    """LLM 생성기 — Azure OpenAI gpt-4o(배포 ai-insight-llm)로 답변을 생성한다.

    "할루시네이션=즉사" 원칙: 검색된 청크(chunks) 밖의 사실·숫자를 새로 만들지 않는다.
    LLM 은 청크 내용을 한국어로 '설명·요약'만 하고, 계산·사실은 청크에서만 가져온다.
    재현성을 위해 temperature=0 으로 호출한다. citations 는 라우터가 chunks 에서
    생성하므로 이 생성기는 answer 문자열만 반환한다.

    호출/타임아웃/키 미설정 등으로 실패하면 예외를 그대로 올린다 — 라우터가 받아
    ExtractiveGenerator 로 폴백한다(데모가 죽지 않게).
    """

    _SYSTEM_PROMPT = (
        "너는 삼성증권 PB가 VVIP 고객에게 설명할 답변을 작성하는 보조자다.\n"
        "반드시 다음 규칙을 지킨다.\n"
        "1. 아래 '근거 문서'에 있는 내용만 사용한다. 근거 밖의 사실·숫자·통계·날짜를 "
        "지어내지 않는다.\n"
        "2. 근거에서 답을 찾을 수 없으면 '제공된 자료로는 확인되지 않습니다'라고 답한다.\n"
        "3. 수치·계산·사실은 근거에서 그대로 인용하고, 너는 설명·요약·정리만 한다.\n"
        "4. 한국어로, PB가 고객에게 설명하듯 정중하고 명확하게 쓴다.\n"
        "5. 단정적 수익 보장이나 투자 권유 표현은 피하고 자료 근거 설명에 한정한다.\n"
        "6. '요약해 드리겠습니다', '안내해 드리겠습니다' 같은 도입 인사말이나 "
        "'추가 정보가 필요하시면 말씀해 주십시오' 같은 맺음말 없이 곧바로 핵심 내용만 쓴다.\n"
        "7. 마크다운 기호를 쓰지 않는다. **굵게**, ## 제목, 백틱(`), 별표·하이픈 불릿 "
        "없이 일반 문장과 줄바꿈으로만 작성한다."
    )

    def generate(self, query: str, chunks: list[dict[str, Any]]) -> str:
        if not chunks:
            raise ValueError("청크가 없으면 answer 를 생성할 수 없습니다 (라우터에서 404 처리).")

        context = _format_chunks_for_prompt(chunks)
        user_prompt = (
            f"[근거 문서]\n{context}\n\n"
            f"[질의]\n{query}\n\n"
            "위 근거 문서만을 사용해 한국어로 답변을 작성하라."
        )
        response = get_llm_client().chat.completions.create(
            model=get_llm_deployment(),
            messages=[
                {"role": "system", "content": self._SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )
        # content 필터·정책 등으로 choices 가 비어 올 수 있어 접근 전에 검증한다.
        if not response.choices:
            raise ValueError("LLM 응답에 choices 가 없습니다.")
        answer = response.choices[0].message.content
        if not answer or not answer.strip():
            raise ValueError("LLM 이 빈 answer 를 반환했습니다.")
        return answer.strip()


class InsightSummaryGenerator:
    """AI 인사이트 answer 를 IPS unique 반영용 수치 기반 명사형 요약으로 압축한다.

    answer 는 이미 검색 근거 기반으로 생성된 텍스트이므로, 요약기는 새 사실·숫자를 만들지
    않고 화면 반영용 짧은 문장만 만든다. 글자 수는 고정하지 않되 너무 길어지지 않게
    후처리한다. 실패하면 라우터가 fallback_insight_summary() 로 답변 원문 기반 요약을
    내려준다.
    """

    _SYSTEM_PROMPT = (
        "너는 PB 상담 대시보드에서 IPS 구조화 항목 중 Unique에 추가할 짧은 문구를 "
        "작성하는 보조자다.\n"
        "반드시 다음 규칙을 지킨다.\n"
        "1. 입력된 AI 인사이트 답변에 있는 내용만 사용한다.\n"
        "2. 새로운 사실, 숫자, 투자 권유, 수익 보장 표현을 만들지 않는다.\n"
        "3. 답변에 수치가 있으면 가장 의사결정에 중요한 수치 1~2개를 원문 그대로 포함한다.\n"
        "4. 수치가 여러 개면 금리·수익률·비중·세금·변동성처럼 상담 판단에 직접 연결되는 "
        "수치를 우선한다.\n"
        "5. 한국어 명사형 구문으로 작성하되, 한 줄에서 너무 길어지지 않게 핵심만 남긴다.\n"
        "6. '-했습니다', '-됩니다', '-입니다' 같은 문장형 종결어미를 쓰지 않는다.\n"
        "7. 마크다운, 따옴표, '요약:' 같은 접두사는 쓰지 않는다."
    )

    def summarize(self, answer: str) -> str:
        if not answer or not answer.strip():
            raise ValueError("빈 answer 는 요약할 수 없습니다.")

        user_prompt = (
            "[AI 인사이트 답변]\n"
            f"{answer.strip()}\n\n"
            "위 답변만 근거로 IPS Unique에 붙일 한국어 명사형 요약 구문을 작성하라. "
            "답변에 숫자·비율·기간·금액이 있으면 핵심 수치 1~2개를 반드시 포함하라. "
            "예: '금리가 상승했습니다'가 아니라 '10년물 금리 4.1% 상승'처럼 작성하라."
        )
        response = get_insight_summary_client().chat.completions.create(
            model=get_insight_summary_deployment(),
            messages=[
                {"role": "system", "content": self._SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=120,
            timeout=30.0,
        )
        if not response.choices:
            raise ValueError("요약 LLM 응답에 choices 가 없습니다.")
        summary = response.choices[0].message.content
        if not summary or not summary.strip():
            raise ValueError("요약 LLM 이 빈 summary 를 반환했습니다.")
        return normalize_insight_summary(summary)
