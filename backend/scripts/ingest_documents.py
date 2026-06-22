"""RAG 운영 인제스천 스크립트 — backend/data 의 PDF를 pgvector(document/
document_chunk)에 적재한다.

검색형 /rag/insight 용 실문서 적재 파이프라인이다(절세 요약은 RAG를 쓰지 않으므로
이 스크립트와 무관). 더미 시드(dev_seed_rag_chunks.py)와 달리 실제 PDF 텍스트를
청킹·임베딩한다.

처리 흐름
  1) backend/data/<category>/*.pdf 수집 (category = house_view | tax | macro)
  2) pypdf 로 텍스트 추출 (스캔 PDF = 추출 0자 → 경고 후 skip, OCR은 범위 밖)
  3) tiktoken(cl100k_base) 토큰 기준 청킹 (CHUNK_SIZE/CHUNK_OVERLAP, 환경변수로 override 가능)
  4) 청크별 Azure 임베딩(text-embedding-3-small, 1536) — retrieval.embed_query 재사용
  5) document + document_chunk upsert (dev_seed 패턴 재사용)

메타 결정 (조사 결과 backend/data 가 3분류 폴더로 정리돼 있어 폴더명 매핑 채택)
  · source_type : 폴더명 매핑 house_view→house_view / tax→tax_law / macro→macro
  · published_date : 파일명의 YYYYMM(→YYYY-MM-01) 또는 YYYY(→YYYY-01-01), 없으면 None
  · meta.source_file : 상대경로 — 실문서 표식(더미의 meta.dev_seed 와 구분)

멱등성
  · document.id = uuid5(상대경로) 로 고정 → 재실행 시 같은 행 갱신
  · document.source_url = 상대경로 (추적·키)
  · 재적재 전 해당 document 의 기존 청크를 전부 삭제 후 재삽입
    (재실행 시 청크 수가 줄어도 stale 청크가 남지 않게)

실행법
  cd backend && source .venv/bin/activate
  python scripts/ingest_documents.py --dry-run            # 청킹만(과금 0) 사전 검증
  python scripts/ingest_documents.py --file macro/fed_fomc_202601.pdf
  python scripts/ingest_documents.py --category macro --limit 1
  python scripts/ingest_documents.py                      # data 전체 적재

요구 환경변수(backend/.env): AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY,
SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""

import argparse
import os
import re
import sys
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

import tiktoken
from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.retrieval import (  # noqa: E402
    EMBEDDING_DEPLOYMENT,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    get_openai_client,
    get_supabase_client,
)

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "512"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))

# 배치 임베딩 크기. 청크당 순차 호출(2000+회)은 느려 한 번에 여러 청크를 임베딩한다.
# Azure text-embedding-3-small 입력 한도(8191토큰/입력)와 별개로, 한 요청의 입력
# 개수 상한이 있어 보수적으로 64로 둔다.
EMBED_BATCH_SIZE = 64

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# 폴더명 → document.source_type 매핑. document.source_type 은 free text(CHECK 없음)이며
# baseline_v0_1.sql 주석의 예시(house_view | afpk | tax_law | internal)를 따른다.
CATEGORY_SOURCE_TYPE = {
    "house_view": "house_view",
    "tax": "tax_law",
    "macro": "macro",
}

# uuid5 네임스페이스(임의 고정값). 같은 상대경로 → 항상 같은 document.id.
DOC_NAMESPACE = uuid.UUID("a8f5c2e0-0000-4000-8000-000000000000")

# text-embedding-3-small 입력 한도는 8191 토큰. CHUNK_SIZE(기본 512)는 충분히 작다.
_TOKENIZER = tiktoken.get_encoding("cl100k_base")


def parse_published_date(filename: str) -> str | None:
    """파일명에서 발행일 추정. YYYYMM → YYYY-MM-01, YYYY → YYYY-01-01, 없으면 None."""
    # YYYYMM(6자리)을 먼저 시도(202601 등). 2020~2099 / 01~12 만 인정.
    m = re.search(r"(20\d{2})(0[1-9]|1[0-2])(?!\d)", filename)
    if m:
        return f"{m.group(1)}-{m.group(2)}-01"
    m = re.search(r"(20\d{2})(?!\d)", filename)
    if m:
        return f"{m.group(1)}-01-01"
    return None


def humanize_title(rel_path: Path, source_type: str) -> str:
    """파일명 기반 사람이 읽을 제목(예: 'macro/fed_fomc_202601.pdf' → 'fed fomc 202601')."""
    stem = rel_path.stem.replace("_", " ").strip()
    return f"{stem} ({source_type})"


def extract_text(pdf_path: Path) -> str:
    """pypdf 로 전체 페이지 텍스트를 추출해 합친다(스캔 PDF면 빈 문자열에 가깝다)."""
    reader = PdfReader(str(pdf_path))
    parts: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            parts.append(text)
    return "\n".join(parts)


def chunk_text(text: str) -> list[tuple[str, int]]:
    """tiktoken 토큰 기준 슬라이딩 윈도우 청킹. (청크 텍스트, 토큰수) 리스트 반환."""
    tokens = _TOKENIZER.encode(text)
    if not tokens:
        return []
    step = max(1, CHUNK_SIZE - CHUNK_OVERLAP)
    chunks: list[tuple[str, int]] = []
    for start in range(0, len(tokens), step):
        window = tokens[start : start + CHUNK_SIZE]
        if not window:
            break
        chunk = _TOKENIZER.decode(window).strip()
        if chunk:
            chunks.append((chunk, len(window)))
        if start + CHUNK_SIZE >= len(tokens):
            break
    return chunks


def embed_batch(texts: list[str]) -> list[list[float]]:
    """여러 청크를 배치로 임베딩한다(retrieval.embed_query 와 같은 Azure 배포 사용).

    검색부 embed_query 는 단일 텍스트용이라, 2000+ 청크를 순차 호출하면 느리다.
    같은 클라이언트/배포에 input 을 리스트로 넘겨 호출 수를 1/EMBED_BATCH_SIZE 로 줄인다.
    응답의 index 순서가 입력 순서와 일치함을 보장하기 위해 index 로 재정렬한다.
    """
    client = get_openai_client()
    embeddings: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]
        resp = client.embeddings.create(model=EMBEDDING_DEPLOYMENT, input=batch)
        for item in sorted(resp.data, key=lambda d: d.index):
            embeddings.append(item.embedding)
    return embeddings


def collect_pdfs(category: str | None, file: str | None) -> list[Path]:
    """적재 대상 PDF 경로(절대) 목록을 모은다. file > category > 전체 순으로 좁힌다."""
    if file:
        path = (DATA_DIR / file).resolve()
        if not path.is_file():
            raise SystemExit(f"파일을 찾을 수 없습니다: {path}")
        return [path]

    categories = [category] if category else list(CATEGORY_SOURCE_TYPE)
    pdfs: list[Path] = []
    for cat in categories:
        if cat not in CATEGORY_SOURCE_TYPE:
            raise SystemExit(
                f"알 수 없는 category: {cat} (가능: {', '.join(CATEGORY_SOURCE_TYPE)})"
            )
        cat_dir = DATA_DIR / cat
        # 카테고리 폴더가 아직 없을 수 있어(예: data 일부만 준비) glob 전 존재 확인.
        if cat_dir.is_dir():
            pdfs.extend(sorted(cat_dir.glob("*.pdf")))
    return pdfs


def ingest_one(pdf_path: Path, *, dry_run: bool) -> dict:
    """PDF 1개를 처리한다. dry_run 이면 청킹까지만(임베딩·DB 없음)."""
    rel_path = pdf_path.relative_to(DATA_DIR)
    category = rel_path.parts[0]
    source_type = CATEGORY_SOURCE_TYPE[category]
    rel_str = str(rel_path).replace("\\", "/")  # 윈도우 경로 구분자 정규화

    text = extract_text(pdf_path)
    if not text.strip():
        print(f"  ⚠️  텍스트 추출 0자 — 스캔 PDF 추정, 건너뜀: {rel_str}")
        return {"file": rel_str, "skipped": True, "chunks": 0}

    chunks = chunk_text(text)
    published_date = parse_published_date(pdf_path.name)
    doc_id = str(uuid.uuid5(DOC_NAMESPACE, rel_str))
    title = humanize_title(rel_path, source_type)

    print(
        f"  · {rel_str} → source_type={source_type}, "
        f"published_date={published_date}, 청크={len(chunks)}"
    )

    if dry_run:
        return {"file": rel_str, "skipped": False, "chunks": len(chunks)}

    supabase = get_supabase_client()
    supabase.table("document").upsert(
        {
            "id": doc_id,
            "title": title,
            "source_type": source_type,
            "source_url": rel_str,
            "meta": {
                "source_file": rel_str,  # 실문서 표식(더미의 dev_seed 와 구분)
                "published_date": published_date,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            },
        },
        on_conflict="id",
    ).execute()

    # 배치 임베딩 후 한 번에 적재. 임베딩이 끝난 뒤 DB에 반영하므로(아래),
    # 임베딩 단계에서 실패하면 기존 적재분은 그대로 보존된다(부분 손상 방지).
    embeddings = embed_batch([content for content, _ in chunks])
    rows = [
        {
            "document_id": doc_id,
            "chunk_index": idx,
            "content": content,
            "embedding": embeddings[idx],
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dim": EMBEDDING_DIM,
            "token_count": token_count,
        }
        for idx, (content, token_count) in enumerate(chunks)
    ]

    # 재실행 시: 새 청크를 먼저 upsert(unique(document_id,chunk_index) 갱신)한 뒤,
    # 이전 실행보다 청크 수가 줄었을 때 남는 stale 청크(chunk_index >= 현재 개수)만
    # 삭제한다. delete→insert 와 달리 문서가 0청크로 비는 창이 없어, insert 실패 시
    # 검색에서 문서가 통째로 누락되는 문제를 막는다(Gemini 리뷰 반영).
    supabase.table("document_chunk").upsert(
        rows, on_conflict="document_id,chunk_index"
    ).execute()
    supabase.table("document_chunk").delete().eq("document_id", doc_id).gte(
        "chunk_index", len(chunks)
    ).execute()
    print(f"    └ {len(chunks)}청크 임베딩·적재 완료 (model={EMBEDDING_MODEL})")
    return {"file": rel_str, "skipped": False, "chunks": len(chunks)}


def main() -> None:
    parser = argparse.ArgumentParser(description="backend/data PDF → pgvector 인제스천")
    parser.add_argument(
        "--category", choices=list(CATEGORY_SOURCE_TYPE), help="특정 분류만 적재"
    )
    parser.add_argument(
        "--file", help="data 기준 상대경로 PDF 1개만 (예: macro/fed_fomc_202601.pdf)"
    )
    parser.add_argument("--limit", type=int, help="앞에서부터 N개만 처리(소량 검증용)")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="제외할 상대경로(반복 지정 가능). 예: --exclude tax/nts_taxguide_2026_vol2_errata.pdf",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="임베딩·DB 없이 청킹만 — 과금 0, 청크 수 사전 확인",
    )
    args = parser.parse_args()

    pdfs = collect_pdfs(args.category, args.file)
    if args.exclude:
        excluded = {e.replace("\\", "/") for e in args.exclude}
        pdfs = [
            p for p in pdfs
            if str(p.relative_to(DATA_DIR)).replace("\\", "/") not in excluded
        ]
    if args.limit is not None:
        pdfs = pdfs[: args.limit]
    if not pdfs:
        raise SystemExit("적재 대상 PDF 가 없습니다.")

    mode = "DRY-RUN(청킹만)" if args.dry_run else "적재"
    print(f"[{mode}] 대상 {len(pdfs)}개 — CHUNK_SIZE={CHUNK_SIZE}, OVERLAP={CHUNK_OVERLAP}")

    # 개별 PDF 처리 실패(텍스트 추출 오류·네트워크·DB 제약 등)가 전체 배치를 중단시키지
    # 않도록 파일 단위로 예외를 잡고 다음 파일로 진행한다(Gemini 리뷰 반영).
    results = []
    for p in pdfs:
        # rel_str 은 except 안에서도 쓰이므로 미리 안전하게 계산한다. try 안에서 구하면
        # relative_to 실패(ValueError) 시 except 에서 다시 터져 배치가 통째 죽는다(Gemini 리뷰).
        try:
            rel_str = str(p.relative_to(DATA_DIR)).replace("\\", "/")
        except ValueError:
            # DATA_DIR 밖 경로면 절대경로(내부 구조) 노출 방지 위해 파일명만 사용(Gemini 리뷰).
            rel_str = p.name
        try:
            results.append(ingest_one(p, dry_run=args.dry_run))
        except Exception as e:
            print(f"  ❌  적재 실패 ({rel_str}): {e}", file=sys.stderr)
            # 운영 중 장애 원인 규명을 위해 상세 스택트레이스도 함께 남긴다(Gemini 리뷰).
            traceback.print_exc(file=sys.stderr)
            results.append({"file": rel_str, "skipped": True, "chunks": 0})
    total_chunks = sum(r["chunks"] for r in results)
    skipped = sum(1 for r in results if r["skipped"])
    print(
        f"\n완료: 문서 {len(results) - skipped}건 적재 / "
        f"{skipped}건 skip / 총 {total_chunks}청크"
    )


if __name__ == "__main__":
    main()
