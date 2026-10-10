"""Composition root: wires settings, stores, adapters and services together."""
import logging
from dataclasses import dataclass

from app.agent.orchestrator import Orchestrator
from app.auth.provider import DemoAuthProvider
from app.config import Settings
from app.connectors.seed import seed_connectors
from app.ingestion.embedder import Embedder, FakeEmbedder, VertexEmbedder
from app.ingestion.pipeline import ingest
from app.retrieval.memory_store import InMemoryStore
from app.retrieval.service import RetrievalService
from app.retrieval.store import VectorStore
from app.tools.actions import ActionService
from app.tools.registry import ToolRegistry, build_registry

log = logging.getLogger(__name__)


@dataclass
class Container:
    settings: Settings
    embedder: Embedder
    store: VectorStore
    retrieval: RetrievalService
    registry: ToolRegistry
    actions: ActionService
    auth: DemoAuthProvider
    orchestrator: Orchestrator | None

    def ingest(self) -> dict:
        return ingest(seed_connectors(self.settings.seed_dir), self.embedder, self.store, self.settings)


def build_container(settings: Settings, llm_client=None, use_llm: bool = True) -> Container:
    """`use_llm=False` builds a fully offline container (requires EMBEDDER=fake); used by tests."""
    if llm_client is None and (use_llm or settings.embedder == "vertex"):
        from app.gcp import get_genai_client

        llm_client = get_genai_client()
    embedder = (
        VertexEmbedder(llm_client, settings.embed_model, settings.embed_dim, settings.cache_dir)
        if settings.embedder == "vertex"
        else FakeEmbedder()
    )
    if settings.vector_store == "alloydb":
        from app.retrieval.alloydb_store import AlloyDBStore

        store: VectorStore = AlloyDBStore(settings)
    else:
        store = InMemoryStore()
    retrieval = RetrievalService(store, embedder, settings)
    registry = build_registry(settings, retrieval)
    actions = ActionService(registry)
    return Container(
        settings=settings,
        embedder=embedder,
        store=store,
        retrieval=retrieval,
        registry=registry,
        actions=actions,
        auth=DemoAuthProvider(settings.seed_dir / "personas.json", settings.jwt_secret, settings.jwt_ttl_minutes),
        orchestrator=Orchestrator(llm_client, settings, registry, actions) if use_llm else None,
    )
