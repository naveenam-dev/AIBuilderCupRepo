"""One-time Firebase setup for the project (idempotent):
  1. deploy firestore.rules (Firebase Rules API)
  2. seed the org graph into Firestore org/* (skipped if already present unless --reseed-org)

    python -m scripts.setup_firebase [--reseed-org]
"""
import json
import sys

import google.auth.transport.requests

from app.config import BACKEND_DIR, get_settings
from app.gcp import get_credentials
from app.state.firestore_store import FirestoreStateStore

RULES_API = "https://firebaserules.googleapis.com/v1"


def deploy_rules(project: str, session) -> None:
    source = (BACKEND_DIR.parent / "firestore.rules").read_text(encoding="utf-8")
    r = session.post(f"{RULES_API}/projects/{project}/rulesets",
                     json={"source": {"files": [{"name": "firestore.rules", "content": source}]}})
    r.raise_for_status()
    ruleset = r.json()["name"]
    release = f"projects/{project}/releases/cloud.firestore"
    body = {"release": {"name": release, "rulesetName": ruleset}}
    r = session.patch(f"{RULES_API}/{release}", json=body)
    if r.status_code == 404:
        r = session.post(f"{RULES_API}/projects/{project}/releases", json=body["release"])
    r.raise_for_status()
    print("rules deployed:", ruleset)


def main() -> None:
    s = get_settings()
    session = google.auth.transport.requests.AuthorizedSession(get_credentials())
    session.headers["x-goog-user-project"] = s.gcp_project
    deploy_rules(s.gcp_project, session)

    store = FirestoreStateStore(s.gcp_project, s.firestore_database, get_credentials())
    if store.load_org() is None or "--reseed-org" in sys.argv:
        store.seed_org(json.loads((s.seed_dir / "org.json").read_text(encoding="utf-8")))
        print("org graph seeded into Firestore org/*")
    else:
        print("org graph already in Firestore (use --reseed-org to overwrite)")


if __name__ == "__main__":
    main()
