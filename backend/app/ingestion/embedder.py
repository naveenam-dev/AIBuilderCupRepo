"""Embedding providers. `VertexEmbedder` for real use, `FakeEmbedder` for offline dev and tests."""
import hashlib
import json
import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
from google.genai import types

log = logging.getLogger(__name__)


class Embedder(ABC):
    dim: int

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def embed_query(self, text: str) -> list[float]: ...


class VertexEmbedder(Embedder):
    """Gemini embeddings on Vertex AI with asymmetric task types and a local on-disk cache."""

    _BATCH = 20

    def __init__(self, client, model: str, dim: int, cache_dir: Path):
        self.client, self.model, self.dim = client, model, dim
        self._cache_path = cache_dir / f"embeddings-{model}-{dim}.json"
        self._cache: dict[str, list[float]] = (
            json.loads(self._cache_path.read_text()) if self._cache_path.exists() else {}
        )

    def _call(self, texts: list[str], task: str) -> list[list[float]]:
        resp = self.client.models.embed_content(
            model=self.model,
            contents=texts,
            config=types.EmbedContentConfig(task_type=task, output_dimensionality=self.dim),
        )
        return [_normalize(e.values) for e in resp.embeddings]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        keys = [hashlib.sha256(t.encode()).hexdigest() for t in texts]
        missing = [(k, t) for k, t in zip(keys, texts) if k not in self._cache]
        for i in range(0, len(missing), self._BATCH):
            batch = missing[i : i + self._BATCH]
            for (k, _), vec in zip(batch, self._call([t for _, t in batch], "RETRIEVAL_DOCUMENT")):
                self._cache[k] = vec
        if missing:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(json.dumps(self._cache))
            log.info("Embedded %d new chunks (%d cached)", len(missing), len(texts) - len(missing))
        return [self._cache[k] for k in keys]

    def embed_query(self, text: str) -> list[float]:
        return self._call([text], "RETRIEVAL_QUERY")[0]


class FakeEmbedder(Embedder):
    """Deterministic hashed bag-of-words vectors. No network; good enough to exercise the pipeline."""

    def __init__(self, dim: int = 256):
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        v = np.zeros(self.dim)
        for tok in re.findall(r"[a-z0-9]+", text.lower()):
            v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.dim] += 1.0
        return _normalize(v)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


def _normalize(values) -> list[float]:
    v = np.asarray(values, dtype=np.float32)
    n = np.linalg.norm(v)
    return (v / n if n else v).tolist()
