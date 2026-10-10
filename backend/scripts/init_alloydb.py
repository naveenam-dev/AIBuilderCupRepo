"""One-time AlloyDB bootstrap, run locally as the `postgres` user (password from backend/.env):
creates the schema, ingests the corpus, and grants the Cloud Run service account's IAM database user access.

    python -m scripts.init_alloydb [iam_db_user]
    e.g. iam_db_user = second-brain-sa@aibuildercupprj.iam
"""
import sys

from app.config import get_settings
from app.container import build_container


def main() -> None:
    s = get_settings().model_copy(update={"vector_store": "alloydb", "alloydb_iam_auth": False})
    assert s.alloydb_instance_uri and s.alloydb_password, "Set ALLOYDB_INSTANCE_URI and ALLOYDB_PASSWORD in backend/.env"
    c = build_container(s, use_llm=False)
    print("ingest:", c.ingest())
    print("chunks in AlloyDB:", c.store.count())

    if len(sys.argv) > 1:
        user = sys.argv[1]
        conn = c.store._connect()
        try:
            cur = conn.cursor()
            for stmt in (
                f'GRANT ALL ON SCHEMA public TO "{user}"',
                f'GRANT ALL ON ALL TABLES IN SCHEMA public TO "{user}"',
            ):
                cur.execute(stmt)
            conn.commit()
            print("granted access to", user)
        finally:
            conn.close()

    hits = c.retrieval.search("payments-api 502 ledger latency", c.auth.personas["alex"])
    print("smoke search (alex):", [(h.chunk.id, h.vector_rank, h.keyword_rank) for h in hits])


if __name__ == "__main__":
    main()
