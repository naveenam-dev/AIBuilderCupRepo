"""Shared Google Gen AI client (Vertex AI mode).

Credential resolution:
1. Application Default Credentials (Cloud Run service account, or `gcloud auth application-default login`).
2. Dev fallback: short-lived tokens from the logged-in gcloud CLI, refreshed automatically.
"""
import datetime as dt
import logging
import shutil
import subprocess
from functools import lru_cache

import google.auth
import google.auth.credentials
from google import genai
from google.genai import types
from google.auth.exceptions import DefaultCredentialsError

from app.config import get_settings

log = logging.getLogger(__name__)
_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


class GcloudCliCredentials(google.auth.credentials.Credentials):
    """Fetches access tokens via `gcloud auth print-access-token`. Local development only."""

    def refresh(self, request) -> None:
        gcloud = shutil.which("gcloud") or "gcloud"
        out = subprocess.run([gcloud, "auth", "print-access-token"], capture_output=True, text=True, check=True)
        self.token = out.stdout.strip()
        # google-auth compares against naive UTC datetimes.
        self.expiry = dt.datetime.now(dt.UTC).replace(tzinfo=None) + dt.timedelta(minutes=45)


@lru_cache
def get_credentials() -> google.auth.credentials.Credentials:
    try:
        creds, _ = google.auth.default(scopes=_SCOPES)
        return creds
    except DefaultCredentialsError:
        log.warning("No Application Default Credentials; falling back to gcloud CLI tokens (dev only).")
        return GcloudCliCredentials()


@lru_cache
def get_genai_client() -> genai.Client:
    s = get_settings()
    # Bounded requests with retries: a stalled connection fails over instead of hanging an agent run.
    http = types.HttpOptions(timeout=s.llm_timeout_ms, retry_options=types.HttpRetryOptions(attempts=3))
    return genai.Client(vertexai=True, project=s.gcp_project, location=s.gcp_location, credentials=get_credentials(),
                        http_options=http)
