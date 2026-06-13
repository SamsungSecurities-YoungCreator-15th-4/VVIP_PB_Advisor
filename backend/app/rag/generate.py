"""RAG 생성부 — 검색된 청크로부터 answer 텍스트를 만든다.

"할루시네이션=즉사" 원칙: 생성기는 검색된 청크 밖의 내용을 만들 수 없고,
응답에는 citations 가 반드시 동반된다(라우터에서 강제).
생성기는 인터페이스(Generator)로 추상화하며, 추출형이 기본 구현이다.
"""

from abc import ABC, abstractmethod
from typing import Any


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


class LLMGenerator(Generator):
    """LLM 생성기 스텁 — 미구현.

    6/14 회의 결정 반영, Google AI Studio 연동 예정.
    구현 시에도 검색된 청크 밖의 내용 생성 금지 원칙은 동일하게 적용한다.
    """

    def generate(self, query: str, chunks: list[dict[str, Any]]) -> str:
        raise NotImplementedError(
            "LLMGenerator 는 6/14 회의 결정 반영 후 Google AI Studio 로 연동 예정입니다."
        )
