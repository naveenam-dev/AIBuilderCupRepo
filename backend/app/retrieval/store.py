"""Vector store interface. Implementations MUST apply the ACL filter before ranking so restricted
content never becomes a candidate (a post-filter could still leak via scores or truncation)."""
from abc import ABC, abstractmethod

from app.models import Chunk, Document, SearchHit


class VectorStore(ABC):
    @abstractmethod
    def upsert(self, docs: list[Document], chunks: list[Chunk], vectors: list[list[float]]) -> None: ...

    @abstractmethod
    def hybrid_search(
        self, query: str, query_vector: list[float], roles: set[str], k: int, candidates: int, rrf_k: int
    ) -> list[SearchHit]: ...

    @abstractmethod
    def count(self) -> int: ...
