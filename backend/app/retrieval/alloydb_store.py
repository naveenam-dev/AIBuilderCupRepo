"""AlloyDB (PostgreSQL + pgvector) hybrid store.

Hybrid query in a single SQL statement:
  * ACL pre-filter: `acl_roles && :roles` (GIN index)
  * dense ranking: cosine distance on an HNSW index
  * sparse ranking: Postgres full-text search (OR-semantics tsquery, ts_rank_cd)
  * Reciprocal Rank Fusion computed in SQL
Connects through the AlloyDB Python Connector (IAM-authorized TLS, no proxy or VPC needed for public IP).
"""
import json
from pathlib import Path

from app.config import Settings
from app.models import Chunk, Document, SearchHit
from app.retrieval.store import VectorStore

_HYBRID_SQL = """
WITH allowed AS (
    SELECT * FROM chunks WHERE acl_roles && %s::text[]
),
q AS (
    SELECT to_tsquery('english', replace(plainto_tsquery('english', %s)::text, '&', '|')) AS tsq
),
vec AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> %s::vector) AS r
    FROM allowed ORDER BY embedding <=> %s::vector LIMIT %s
),
kw AS (
    SELECT a.id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(a.tsv, q.tsq) DESC) AS r
    FROM allowed a, q WHERE a.tsv @@ q.tsq
    ORDER BY ts_rank_cd(a.tsv, q.tsq) DESC LIMIT %s
)
SELECT c.id, c.doc_id, c.ordinal, c.text, c.source, c.title, c.url, c.acl_roles, c.updated_at,
       vec.r AS vector_rank, kw.r AS keyword_rank,
       COALESCE(1.0 / (%s + vec.r), 0) + COALESCE(1.0 / (%s + kw.r), 0) AS score
FROM chunks c
LEFT JOIN vec ON vec.id = c.id
LEFT JOIN kw ON kw.id = c.id
WHERE vec.id IS NOT NULL OR kw.id IS NOT NULL
ORDER BY score DESC
LIMIT %s
"""


def _vec_literal(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in v) + "]"


class AlloyDBStore(VectorStore):
    def __init__(self, settings: Settings):
        from google.cloud.alloydbconnector import Connector  # optional dependency, imported lazily

        from app.gcp import get_credentials

        self.s = settings
        self._connector = Connector(
            credentials=get_credentials(), enable_iam_auth=settings.alloydb_iam_auth, ip_type=settings.alloydb_ip_type
        )
        self._ensure_schema()

    def _connect(self):
        auth = {} if self.s.alloydb_iam_auth else {"password": self.s.alloydb_password}
        return self._connector.connect(
            self.s.alloydb_instance_uri, "pg8000", user=self.s.alloydb_user, db=self.s.alloydb_database, **auth
        )

    def _ensure_schema(self) -> None:
        ddl = Path(__file__).with_name("schema.sql").read_text().format(dim=self.s.embed_dim)
        ddl = "\n".join(line.split("--", 1)[0] for line in ddl.splitlines())
        conn = self._connect()
        try:
            cur = conn.cursor()
            # The runtime identity is not the table owner, so only run DDL when bootstrapping a fresh database.
            cur.execute("SELECT to_regclass('public.chunks') IS NOT NULL")
            if cur.fetchone()[0]:
                return
            for stmt in (s.strip() for s in ddl.split(";")):
                if stmt:
                    cur.execute(stmt)
            conn.commit()
        finally:
            conn.close()

    def upsert(self, docs: list[Document], chunks: list[Chunk], vectors: list[list[float]]) -> None:
        conn = self._connect()
        try:
            cur = conn.cursor()
            for d in docs:
                cur.execute(
                    """INSERT INTO documents (id, source, title, url, author, updated_at, acl_roles, metadata)
                       VALUES (%s, %s, %s, %s, %s, %s, %s::text[], %s::jsonb)
                       ON CONFLICT (id) DO UPDATE SET source=EXCLUDED.source, title=EXCLUDED.title, url=EXCLUDED.url,
                         author=EXCLUDED.author, updated_at=EXCLUDED.updated_at, acl_roles=EXCLUDED.acl_roles,
                         metadata=EXCLUDED.metadata""",
                    (d.id, d.source, d.title, d.url, d.author, d.updated_at, d.acl_roles, json.dumps(d.metadata)),
                )
                cur.execute("DELETE FROM chunks WHERE doc_id = %s", (d.id,))
            for c, v in zip(chunks, vectors):
                cur.execute(
                    """INSERT INTO chunks (id, doc_id, ordinal, text, source, title, url, acl_roles, updated_at, embedding)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s::text[], %s, %s::vector)""",
                    (c.id, c.doc_id, c.ordinal, c.text, c.source, c.title, c.url, c.acl_roles, c.updated_at,
                     _vec_literal(v)),
                )
            conn.commit()
        finally:
            conn.close()

    def count(self) -> int:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM chunks")
            return int(cur.fetchone()[0])
        finally:
            conn.close()

    def hybrid_search(self, query, query_vector, roles, k, candidates, rrf_k) -> list[SearchHit]:
        qv = _vec_literal(query_vector)
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(_HYBRID_SQL, (sorted(roles), query, qv, qv, candidates, candidates, rrf_k, rrf_k, k))
            rows = cur.fetchall()
        finally:
            conn.close()
        return [
            SearchHit(
                chunk=Chunk(id=r[0], doc_id=r[1], ordinal=r[2], text=r[3], source=r[4], title=r[5], url=r[6] or "",
                            acl_roles=list(r[7]), updated_at=r[8]),
                score=float(r[11]), vector_rank=r[9], keyword_rank=r[10],
            )
            for r in rows
        ]
