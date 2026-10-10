"""Central configuration. Every value can be overridden via environment variables or backend/.env."""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    # --- Google Cloud / Vertex AI ---
    gcp_project: str = "aibuildercupprj"
    gcp_location: str = "global"
    llm_model: str = "gemini-3.5-flash"
    embed_model: str = "gemini-embedding-001"
    embed_dim: int = 768
    # "vertex" for real embeddings, "fake" for offline dev/tests (hashed bag-of-words).
    embedder: Literal["vertex", "fake"] = "vertex"

    # --- Storage ---
    vector_store: Literal["memory", "alloydb"] = "memory"
    # AlloyDB instance URI: projects/<p>/locations/<r>/clusters/<c>/instances/<i>
    alloydb_instance_uri: str = ""
    alloydb_user: str = "postgres"
    alloydb_password: str = ""
    alloydb_database: str = "postgres"
    alloydb_ip_type: Literal["PUBLIC", "PRIVATE", "PSC"] = "PUBLIC"
    # IAM database auth: no password; ALLOYDB_USER is the service account email minus ".gserviceaccount.com".
    alloydb_iam_auth: bool = False

    # --- Data ---
    seed_dir: Path = BACKEND_DIR / "seed_data"
    cache_dir: Path = BACKEND_DIR / ".cache"
    chunk_size_chars: int = 1200
    chunk_overlap_chars: int = 150

    # --- Retrieval ---
    retrieval_top_k: int = 6
    retrieval_candidates: int = 30
    rrf_k: int = 60

    # --- Agent ---
    max_agent_steps: int = 8  # model turns
    max_tool_calls: int = 12  # total tool invocations per question (parallel calls count individually)
    llm_temperature: float = 0.2
    llm_thinking_level: Literal["minimal", "low", "medium", "high", ""] = "low"  # "" = model default

    # --- Integration adapters: "mock" now, "real" once implemented ---
    jira_adapter: Literal["mock", "real"] = "mock"
    chat_adapter: Literal["mock", "real"] = "mock"
    calendar_adapter: Literal["mock", "real"] = "mock"
    monitoring_adapter: Literal["mock", "real"] = "mock"

    # --- Auth ---
    auth_provider: Literal["demo"] = "demo"
    jwt_secret: str = "dev-only-change-me"
    jwt_ttl_minutes: int = 12 * 60

    # --- Web ---
    cors_origins: list[str] = ["http://localhost:5173"]
    frontend_dist: Path = BACKEND_DIR.parent / "frontend" / "dist"


@lru_cache
def get_settings() -> Settings:
    return Settings()
