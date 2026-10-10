"""Retrieval facade used by the agent and the API: embeds the query and runs RBAC-filtered hybrid search."""
from app.config import Settings
from app.ingestion.embedder import Embedder
from app.models import Principal, SearchHit
from app.retrieval.store import VectorStore


class RetrievalService:
    def __init__(self, store: VectorStore, embedder: Embedder, settings: Settings):
        self.store, self.embedder, self.s = store, embedder, settings

    def search(self, query: str, principal: Principal, k: int | None = None) -> list[SearchHit]:
        return self.store.hybrid_search(
            query=query,
            query_vector=self.embedder.embed_query(query),
            roles=principal.effective_roles,
            k=k or self.s.retrieval_top_k,
            candidates=self.s.retrieval_candidates,
            rrf_k=self.s.rrf_k,
        )
