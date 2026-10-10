"""In-process hybrid store: cosine similarity (numpy) + Okapi BM25, fused with RRF.
Used for local development without a database; mirrors the AlloyDB store's semantics."""
import math
import re
from collections import Counter

import numpy as np

from app.models import Chunk, Document, SearchHit
from app.retrieval.fusion import rrf
from app.retrieval.store import VectorStore

# Keeps identifiers like PAY-1287, v2.42.0 and ledger_async_writes intact as single tokens.
_TOKEN = re.compile(r"[a-z0-9](?:[a-z0-9_.\-]*[a-z0-9])?")
_STOP = frozenset("a an and are as at be by do for from how i in is it of on or our the this to what when with".split())


_PART_WEIGHT = 0.3  # partial matches on compound-token pieces count less than exact identifiers


def _split(text: str) -> tuple[list[str], list[str]]:
    toks = [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]
    # Pieces of compound tokens, so "ledger" still matches "ledger_async_writes".
    parts = [p for t in toks if re.search(r"[_.\-]", t) for p in re.split(r"[_.\-]", t) if p and p not in _STOP]
    return toks, parts


def tokenize(text: str) -> list[str]:
    toks, parts = _split(text)
    return toks + parts


class InMemoryStore(VectorStore):
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.chunks: list[Chunk] = []
        self.matrix = np.zeros((0, 0), dtype=np.float32)
        self._tfs: list[Counter] = []
        self._df: Counter = Counter()
        self._avg_len = 0.0

    def upsert(self, docs: list[Document], chunks: list[Chunk], vectors: list[list[float]]) -> None:
        by_id = {c.id: (c, v) for c, v in zip(self.chunks, self.matrix)} if self.chunks else {}
        by_id.update({c.id: (c, np.asarray(v, dtype=np.float32)) for c, v in zip(chunks, vectors)})
        self.chunks = [c for c, _ in by_id.values()]
        self.matrix = np.vstack([v for _, v in by_id.values()])
        # Title terms are counted twice (title boost), mirroring setweight('A') in the AlloyDB schema.
        self._tfs = [Counter(tokenize(c.text)) + Counter(tokenize(c.title)) for c in self.chunks]
        self._df = Counter(t for tf in self._tfs for t in tf)
        self._avg_len = sum(sum(tf.values()) for tf in self._tfs) / max(len(self._tfs), 1)

    def count(self) -> int:
        return len(self.chunks)

    def _bm25(self, query_terms: dict[str, float], idx: int) -> float:
        tf, n = self._tfs[idx], len(self.chunks)
        length = sum(tf.values())
        score = 0.0
        for t, weight in query_terms.items():
            if t not in tf:
                continue
            idf = math.log(1 + (n - self._df[t] + 0.5) / (self._df[t] + 0.5))
            norm = tf[t] + self.k1 * (1 - self.b + self.b * length / self._avg_len)
            score += weight * idf * tf[t] * (self.k1 + 1) / norm
        return score

    def hybrid_search(self, query, query_vector, roles, k, candidates, rrf_k) -> list[SearchHit]:
        # RBAC pre-filter: only chunks the caller may see are ever scored.
        allowed = [i for i, c in enumerate(self.chunks) if roles.intersection(c.acl_roles)]
        if not allowed:
            return []
        sims = self.matrix[allowed] @ np.asarray(query_vector, dtype=np.float32)
        vec_rank = [self.chunks[allowed[i]].id for i in np.argsort(-sims)[:candidates]]

        toks, parts = _split(query)
        q_terms = {p: _PART_WEIGHT for p in parts} | {t: 1.0 for t in toks}
        kw_scores = [(self._bm25(q_terms, i), self.chunks[i].id) for i in allowed]
        kw_rank = [cid for s, cid in sorted(kw_scores, reverse=True) if s > 0][:candidates]

        by_id = {c.id: c for c in self.chunks}
        return [
            SearchHit(chunk=by_id[cid], score=score, vector_rank=r.get("vector"), keyword_rank=r.get("keyword"))
            for cid, score, r in rrf({"vector": vec_rank, "keyword": kw_rank}, k=rrf_k)[:k]
        ]
