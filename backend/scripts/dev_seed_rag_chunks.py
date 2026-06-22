"""[dev 전용] RAG 검증용 더미 문서 시드 스크립트 — 서버 코드 아님.

/rag/insight 스모크 테스트를 위해 document / document_chunk 에 검증된
국세청 문구 기반 문서 3건을 넣고, 각 청크를 Azure OpenAI 임베딩 배포
(ai-insight-embedding)로 실제 임베딩한다(검색부 embed_query 재사용).
문구의 사실관계는 supabase/seed.sql(tax_rule, 국세청 2026 세금절약가이드
근거)에서 검증 완료된 수치를 재활용했다. 운영 인제스천 파이프라인은
별도 단계에서 만든다.

실행법:
  cd backend
  source .venv/bin/activate
  python scripts/dev_seed_rag_chunks.py

요구 환경변수(backend/.env): AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY,
SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
재실행 안전: 고정 UUID 로 document upsert + (document_id, chunk_index) upsert.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.retrieval import (  # noqa: E402
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    embed_query,
    get_supabase_client,
)


def join_text(*parts: str) -> str:
    return "".join(parts)


# dev 시드 식별용 고정 UUID(재실행 시 같은 행을 갱신).
# meta.dev_seed 로 표시해 운영 데이터와 구분한다.
DEV_DOCUMENTS = [
    {
        "id": "d0000000-0000-4000-8000-000000000001",
        "title": "금융소득 종합과세 안내 (dev)",
        "source_type": "tax_law",
        "meta": {
            "dev_seed": True,
            "published_date": "2026-01-01",
            "source_note": "국세청 2026 세금절약가이드 1권 / 소득세법 §14·§62",
        },
        "chunks": [
            join_text(
                "금융소득 종합과세는 이자소득과 배당소득을 합한 ",
                "금융소득이 ",
                "연 2,000만원을 초과하는 경우, 그 초과분을 다른 종합소득과 ",
                "합산해 누진세율로 과세하는 제도다. 연 2,000만원 이하의 ",
                "금융소득은 15.4%(지방소득세 포함) 원천징수로 분리과세 ",
                "효과가 있다. (소득세법 제14조·제62조)",
            ),
            join_text(
                "금융소득이 연 2,000만원을 초과하면 초과분은 종합소득에 ",
                "합산되어 누진세율이 적용되며, 지방소득세를 포함한 ",
                "최고세율은 49.5%에 이른다. 종합과세 시에도 원천징수세액과 ",
                "비교해 큰 금액으로 과세하는 비교과세 방식이 적용된다.",
            ),
        ],
    },
    {
        "id": "d0000000-0000-4000-8000-000000000002",
        "title": "ISA(개인종합자산관리계좌) 세제 혜택 안내 (dev)",
        "source_type": "tax_law",
        "meta": {
            "dev_seed": True,
            "published_date": "2026-01-01",
            "source_note": join_text(
                "국세청 2026 세금절약가이드 1권 / ",
                "조세특례제한법 §88의2",
            ),
        },
        "chunks": [
            join_text(
                "개인종합자산관리계좌(ISA)는 계좌 내 운용수익에 대해 ",
                "일반형 200만원, 서민형 400만원까지 비과세하고, ",
                "비과세 한도 초과분은 9.9%(지방소득세 포함)로 저율 ",
                "분리과세한다. (조세특례제한법 제88조의2)",
            ),
            join_text(
                "ISA는 의무가입기간이 3년이라 중도 해지 시 세제 혜택이 ",
                "제한될 수 있다. 따라서 자금의 유동성 계획과 함께 ",
                "가입 여부를 검토해야 한다.",
            ),
        ],
    },
    {
        "id": "d0000000-0000-4000-8000-000000000003",
        "title": "해외주식 양도소득세 안내 (dev)",
        "source_type": "tax_law",
        "meta": {
            "dev_seed": True,
            "published_date": "2026-01-01",
            "source_note": join_text(
                "국세청 2026 세금가이드 2권 / ",
                "소득세법 양도소득(국외주식)",
            ),
        },
        "chunks": [
            join_text(
                "해외주식 양도소득세는 양도차익에서 연 250만원 기본공제를 ",
                "적용한 뒤 22%(국세 20% + 지방소득세 2%) 세율로 과세된다. ",
                "양도한 해의 다음 해 5월에 양도소득세 확정신고를 ",
                "해야 한다.",
            ),
            join_text(
                "같은 해에 실현한 해외주식 양도차익과 양도차손은 서로 ",
                "통산할 수 있다. 일반 개인 투자자는 국내 상장주식이나 ",
                "해외 파생상품의 손익과는 통산할 수 없으므로, ",
                "해외주식 양도손익끼리만 상계된다.",
            ),
        ],
    },
]


def main() -> None:
    supabase = get_supabase_client()
    for doc in DEV_DOCUMENTS:
        print(f"[doc] {doc['title']}")
        supabase.table("document").upsert(
            {
                "id": doc["id"],
                "title": doc["title"],
                "source_type": doc["source_type"],
                "meta": doc["meta"],
            },
            on_conflict="id",
        ).execute()

        for idx, content in enumerate(doc["chunks"]):
            # embed_query 는 단일 텍스트 임베딩 함수라 청크 임베딩에도 쓴다.
            embedding = embed_query(content)
            supabase.table("document_chunk").upsert(
                {
                    "document_id": doc["id"],
                    "chunk_index": idx,
                    "content": content,
                    "embedding": embedding,
                    "embedding_model": EMBEDDING_MODEL,
                    "embedding_dim": EMBEDDING_DIM,
                },
                on_conflict="document_id,chunk_index",
            ).execute()
            print(f"  - chunk {idx}: 임베딩 {len(embedding)}차원 저장 완료")

    print(f"\ndev 시드 완료: 문서 {len(DEV_DOCUMENTS)}건 / 모델 {EMBEDDING_MODEL}")


if __name__ == "__main__":
    main()
