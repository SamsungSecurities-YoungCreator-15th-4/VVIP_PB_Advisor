"""RAG 검색부 — 쿼리 임베딩 + pgvector 유사도 검색.

설계 원칙: 검색부(이 모듈)와 생성부(generate.py)를 분리한다.
- 임베딩: Azure OpenAI 배포 ai-insight-embedding (text-embedding-3-small,
  1536차원, document_chunk.embedding 차원과 일치)
- 검색: supabase-py RPC 전용 — supabase/migrations/20260605000001 의
  match_document_chunks(query_embedding, match_count, similarity_threshold) 호출.
  RPC 반환에 title/published_date 가 없으므로 document 테이블 2차 조회로 보강한다.
"""

import os
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
from openai import AzureOpenAI
from supabase import Client, create_client

load_dotenv()

# 임베딩 모델은 명세 확정값. 변경 시 document_chunk.embedding(vector(1536)) 차원과
# 기존 적재 청크의 재임베딩 여부를 함께 검토해야 한다.
# Azure에서는 모델명이 아니라 "배포명"으로 호출한다(아래 EMBEDDING_DEPLOYMENT).
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

# Azure OpenAI 배포 정보 (배포명/버전은 비밀이 아니라 기본값을 둔다. 키는 .env 전용)
EMBEDDING_DEPLOYMENT = os.getenv(
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "ai-insight-embedding"
)
EMBEDDING_API_VERSION = os.getenv("AZURE_OPENAI_EMBEDDING_API_VERSION", "2023-05-15")

# LLM 생성부(generate.py의 LLMGenerator)에서 쓸 Azure 배포 — 이번 작업 범위 아님.
#   배포명: ai-insight-llm / 모델: gpt-4o / API 버전: 2025-01-01-preview

DEFAULT_TOP_K = 8
DEFAULT_SIMILARITY_THRESHOLD = 0.5


@lru_cache(maxsize=1)
def get_openai_client() -> AzureOpenAI:
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
        api_version=EMBEDDING_API_VERSION,
    )


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 환경변수가 설정되지 않았습니다. "
            "backend/.env 에 추가하세요 (.env.example 참고)."
        )
    return create_client(url, key)


def embed_query(text: str) -> list[float]:
    """질의 텍스트를 Azure 임베딩 배포로 임베딩해 1536차원 벡터를 반환한다."""
    response = get_openai_client().embeddings.create(
        # Azure는 model 인자에 모델명이 아닌 배포명을 받는다.
        model=EMBEDDING_DEPLOYMENT,
        input=text,
    )
    return response.data[0].embedding


def search_chunks(
    query_embedding: list[float],
    top_k: int = DEFAULT_TOP_K,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[dict[str, Any]]:
    """match_document_chunks RPC 로 유사 청크를 검색해 citation 구조로 반환한다.

    반환 원소: doc_id, source_type, title, published_date, chunk, similarity
    임계값 미달로 0건이면 빈 리스트를 반환한다(404 처리는 라우터 책임).
    """
    supabase = get_supabase_client()
    rpc_result = supabase.rpc(
        "match_document_chunks",
        {
            "query_embedding": query_embedding,
            "match_count": top_k,
            "similarity_threshold": similarity_threshold,
        },
    ).execute()
    rows: list[dict[str, Any]] = rpc_result.data or []
    if not rows:
        return []

    # RPC 반환(id, document_id, content, similarity)에는 문서 메타데이터가 없어
    # document 테이블을 한 번 더 조회해 title/source_type 을 보강한다.
    # published_date 는 document 에 전용 컬럼이 없어 meta jsonb 에서 읽는다(없으면 None).
    doc_ids = list({row["document_id"] for row in rows})
    doc_result = (
        supabase.table("document")
        .select("id, title, source_type, meta")
        .in_("id", doc_ids)
        .execute()
    )
    docs_by_id = {doc["id"]: doc for doc in (doc_result.data or [])}

    citations: list[dict[str, Any]] = []
    for row in rows:
        doc = docs_by_id.get(row["document_id"], {})
        meta = doc.get("meta") or {}
        # 빈 문자열("") 등 falsy 값이면 Citation.published_date(date | None)
        # 검증에서 500이 나므로 None 으로 정규화한다.
        pub_date = meta.get("published_date")
        citations.append(
            {
                "doc_id": row["document_id"],
                "source_type": doc.get("source_type", "unknown"),
                "title": doc.get("title", ""),
                "published_date": pub_date if pub_date else None,
                "chunk": row["content"],
                "similarity": row["similarity"],
            }
        )
    return citations
