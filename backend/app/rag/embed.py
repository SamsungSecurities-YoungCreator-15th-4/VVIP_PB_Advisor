from pathlib import Path


def build_index(nodes: list, index_path: str | Path) -> None:
    """Node 리스트를 임베딩하고 FAISS 인덱스를 index_path에 저장한다."""
    raise NotImplementedError


def load_index(index_path: str | Path):
    """저장된 FAISS 인덱스를 불러와 반환한다."""
    raise NotImplementedError
