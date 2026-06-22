# 회의 후 확정 — 값은 환경변수로 주입하고, 미설정 시 아래 기본값을 사용한다.
import os

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "")  # 회의 후 확정 (예: "text-embedding-3-small")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "512"))    # 회의 후 확정
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))  # 회의 후 확정
TOP_K = int(os.getenv("TOP_K", "5"))                # 회의 후 확정
LLM_MODEL = os.getenv("LLM_MODEL", "")              # 회의 후 확정 (예: "gpt-4o")
