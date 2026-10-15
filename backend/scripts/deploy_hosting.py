"""Deploy the built React app (frontend/dist) to Firebase Hosting through the Hosting REST API, with
/api/** rewritten to the Cloud Run service. Equivalent to `firebase deploy --only hosting` with firebase.json.

    python -m scripts.deploy_hosting
"""
import gzip
import hashlib
import json

import google.auth.transport.requests

from app.config import BACKEND_DIR, get_settings
from app.gcp import get_credentials

API = "https://firebasehosting.googleapis.com/v1beta1"


def main() -> None:
    s = get_settings()
    site = s.gcp_project
    dist = BACKEND_DIR.parent / "frontend" / "dist"
    firebase_json = json.loads((BACKEND_DIR.parent / "firebase.json").read_text(encoding="utf-8"))["hosting"]
    session = google.auth.transport.requests.AuthorizedSession(get_credentials())
    session.headers["x-goog-user-project"] = s.gcp_project

    config = {
        "rewrites": [
            {"glob": r["source"], "run": r["run"]} if "run" in r else {"glob": r["source"], "path": r["destination"]}
            for r in firebase_json["rewrites"]
        ],
        "headers": [{"glob": h["source"], "headers": {x["key"]: x["value"] for x in h["headers"]}}
                    for h in firebase_json.get("headers", [])],
    }
    r = session.post(f"{API}/sites/{site}/versions", json={"config": config})
    r.raise_for_status()
    version = r.json()["name"]

    blobs: dict[str, bytes] = {}
    files: dict[str, str] = {}
    for path in sorted(p for p in dist.rglob("*") if p.is_file()):
        gz = gzip.compress(path.read_bytes(), mtime=0)
        digest = hashlib.sha256(gz).hexdigest()
        files["/" + path.relative_to(dist).as_posix()] = digest
        blobs[digest] = gz
    r = session.post(f"{API}/{version}:populateFiles", json={"files": files})
    r.raise_for_status()
    body = r.json()
    for digest in body.get("uploadRequiredHashes", []):
        up = session.post(f"{body['uploadUrl']}/{digest}", data=blobs[digest],
                          headers={"Content-Type": "application/octet-stream"})
        up.raise_for_status()

    session.patch(f"{API}/{version}?update_mask=status", json={"status": "FINALIZED"}).raise_for_status()
    session.post(f"{API}/sites/{site}/releases", params={"versionName": version}).raise_for_status()
    print(f"released {len(files)} files ({len(body.get('uploadRequiredHashes', []))} uploaded) -> https://{site}.web.app")


if __name__ == "__main__":
    main()
