"""RAG 생성부 — 검색된 청크로부터 answer 텍스트를 만든다.

"할루시네이션=즉사" 원칙: 생성기는 검색된 청크 밖의 내용을 만들 수 없고,
응답에는 citations 가 반드시 동반된다(라우터에서 강제).
생성기는 인터페이스(Generator)로 추상화하며, 추출형이 기본 구현이다.
"""

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


def _format_chunks_for_prompt(chunks: list[dict[str, Any]]) -> str:
    """검색된 청크를 LLM 프롬프트용 근거 블록으로 묶는다(원문 그대로, 가공 없음)."""
    blocks = []
    for i, chunk in enumerate(chunks, start=1):
        title = chunk.get("title") or "제목 없음"
        chunk_text = chunk.get("chunk") or ""
        blocks.append(f"[근거 {i} · {title}]\n{chunk_text.strip()}")
    return "\n\n".join(blocks)


def normalize_insight_summary(text: str, max_chars: int = 50, min_chars: int = 30) -> str:
    """IPS unique 에 붙일 짧은 요약을 한 줄·최대 길이로 정규화한다."""
    summary = " ".join(text.split())
    summary = summary.strip("`\"'“”‘’")
    if summary.startswith("요약:"):
        summary = summary.removeprefix("요약:").strip()
    if len(summary) > max_chars:
        candidate = summary[:max_chars].rstrip(" ,.;:·-")
        last_space = candidate.rfind(" ")
        if last_space >= min_chars:
            candidate = candidate[:last_space].rstrip(" ,.;:·-")
        summary = candidate
    return summary


def fallback_insight_summary(answer: str) -> str:
    """mini 요약 실패 시 answer 첫 문장을 최대 50자로 줄여 반환한다."""
    summary = normalize_insight_summary(answer)
    if summary:
        return summary
    return "인사이트 요약을 생성하지 못했습니다."


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
        "5. 단정적 수익 보장이나 투자 권유 표현은 피하고 자료 근거 설명에 한정한다."
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
    """AI 인사이트 answer 를 IPS unique 반영용 30~50자 요약으로 압축한다.

    answer 는 이미 검색 근거 기반으로 생성된 텍스트이므로, 요약기는 새 사실·숫자를 만들지
    않고 화면 반영용 짧은 문장만 만든다. 실패하면 라우터가 fallback_insight_summary()
    로 답변 원문 기반 요약을 내려준다.
    """

    _SYSTEM_PROMPT = (
        "너는 PB 상담 대시보드에서 IPS 구조화 항목 중 Unique에 추가할 짧은 문구를 "
        "작성하는 보조자다.\n"
        "반드시 다음 규칙을 지킨다.\n"
        "1. 입력된 AI 인사이트 답변에 있는 내용만 사용한다.\n"
        "2. 새로운 사실, 숫자, 투자 권유, 수익 보장 표현을 만들지 않는다.\n"
        "3. 한국어 한 문장으로 30자 이상 50자 이하로 작성한다.\n"
        "4. 마크다운, 따옴표, '요약:' 같은 접두사는 쓰지 않는다."
    )

    def summarize(self, answer: str) -> str:
        if not answer or not answer.strip():
            raise ValueError("빈 answer 는 요약할 수 없습니다.")

        user_prompt = (
            "[AI 인사이트 답변]\n"
            f"{answer.strip()}\n\n"
            "위 답변만 근거로 IPS Unique에 붙일 30~50자 한국어 요약 한 문장을 작성하라."
        )
        response = get_insight_summary_client().chat.completions.create(
            model=get_insight_summary_deployment(),
            messages=[
                {"role": "system", "content": self._SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=80,
            timeout=30.0,
        )
        if not response.choices:
            raise ValueError("요약 LLM 응답에 choices 가 없습니다.")
        summary = response.choices[0].message.content
        if not summary or not summary.strip():
            raise ValueError("요약 LLM 이 빈 summary 를 반환했습니다.")
        return normalize_insight_summary(summary)
