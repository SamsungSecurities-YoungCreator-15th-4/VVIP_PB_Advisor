from pathlib import Path


def load_documents(data_dir: str | Path) -> list:
    """data_dir 안의 PDF 파일을 읽어 Document 객체 리스트로 반환한다."""
    raise NotImplementedError


def chunk_documents(docs: list, chunk_size: int = 512, overlap: int = 50) -> list:
    """Document 리스트를 청킹 설정에 따라 Node 리스트로 분할한다."""
    raise NotImplementedError
