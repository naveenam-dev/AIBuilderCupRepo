"""One-time database bootstrap, run locally as the `postgres` user: creates the schema and ingests the corpus.

    python -m scripts.init_alloydb [iam_db_user]          managed AlloyDB (ALLOYDB_INSTANCE_URI, ALLOYDB_PASSWORD)
    e.g. iam_db_user = second-brain-sa@aibuildercupprj.iam   also grants that IAM database user access

    python -m scripts.init_alloydb --omni                 AlloyDB Omni on the VM, through an IAP tunnel:
    gcloud compute start-iap-tunnel omni-vm 5432 --local-host-port=localhost:15432 --zone us-central1-b
    (OMNI_PASSWORD in backend/.env; Cloud Run connects as the same `postgres` user, so no grants are needed)
"""
import sys

from app.config import get_settings
from app.container import build_container


def main() -> None:
    args = sys.argv[1:]
    if "--omni" in args:
        args.remove("--omni")
        s = get_settings().model_copy(update={"vector_store": "omni", "omni_host": "localhost", "omni_port": 15432})
        assert s.omni_password, "Set OMNI_PASSWORD in backend/.env"
    else:
        s = get_settings().model_copy(update={"vector_store": "alloydb", "alloydb_iam_auth": False})
        assert s.alloydb_instance_uri and s.alloydb_password, "Set ALLOYDB_INSTANCE_URI and ALLOYDB_PASSWORD in backend/.env"
    c = build_container(s, use_llm=False)
    print("ingest:", c.ingest())
    print("chunks in", s.vector_store, ":", c.store.count())

    if args:
        user = args[0]
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
