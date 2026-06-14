"""Azure OpenAI 공용 클라이언트 팩토리.

엔드포인트·API 키는 공용(AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY)이고,
용도별로 배포명·api_version 만 다르다.

- 임베딩(RAG 검색): rag/retrieval.py 가 EMBEDDING_API_VERSION 으로 사용.
- LLM(생성형 인사이트): get_llm_client() — AZURE_OPENAI_LLM_DEPLOYMENT(gpt-4o
  배포 ai-insight-llm) + AZURE_OPENAI_LLM_API_VERSION 사용. IPS 추출용
  AZURE_OPENAI_DEPLOYMENT 와는 별개 배포다.

환경변수는 호출 시점에 읽으므로(아래 함수들), env 미설정 환경에서도 import 는
실패하지 않는다(클라이언트를 실제로 만들 때만 RuntimeError). 키·엔드포인트 값
자체는 예외 메시지/로그에 절대 포함하지 않는다.
"""

import os
from functools import lru_cache

from openai import AzureOpenAI


def build_azure_client(api_version: str) -> AzureOpenAI:
    """공용 ENDPOINT/API_KEY 로 AzureOpenAI 클라이언트를 만든다(api_version 만 가변)."""
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    if not endpoint or not api_key:
        # 키·엔드포인트 값 자체는 절대 메시지/로그에 포함하지 않는다.
        raise RuntimeError(
            "AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY 환경변수가 설정되지 "
            "않았습니다. backend/.env 에 추가하세요 (.env.example 참고)."
        )
    return AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=api_version,
    )


def get_llm_deployment() -> str:
    """인사이트 LLM 배포명. IPS 추출용 AZURE_OPENAI_DEPLOYMENT 와 다른 변수다."""
    return os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT", "ai-insight-llm")


@lru_cache(maxsize=1)
def get_llm_client() -> AzureOpenAI:
    """chat completion(gpt-4o)용 Azure 클라이언트. env 미설정 시 RuntimeError."""
    api_version = os.getenv("AZURE_OPENAI_LLM_API_VERSION", "2025-01-01-preview")
    return build_azure_client(api_version)
