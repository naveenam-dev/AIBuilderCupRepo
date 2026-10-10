"""Ingestion: connectors -> chunk -> embed -> upsert into the vector store."""
import logging

from app.config import Settings
from app.connectors.base import SourceConnector
from app.ingestion.chunker import chunk_document
from app.ingestion.embedder import Embedder
from app.retrieval.store import VectorStore

log = logging.getLogger(__name__)


def ingest(connectors: list[SourceConnector], embedder: Embedder, store: VectorStore, settings: Settings) -> dict:
    docs = [d for c in connectors for d in c.list_documents()]
    chunks = [ch for d in docs for ch in chunk_document(d, settings.chunk_size_chars, settings.chunk_overlap_chars)]
    vectors = embedder.embed_documents([c.text for c in chunks])
    store.upsert(docs, chunks, vectors)
    stats = {"documents": len(docs), "chunks": len(chunks), "by_source": {}}
    for d in docs:
        stats["by_source"][d.source] = stats["by_source"].get(d.source, 0) + 1
    log.info("Ingested %s", stats)
    return stats
