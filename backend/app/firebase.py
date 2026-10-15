"""Shared firebase-admin app (Auth custom tokens / ID-token verification and Cloud Messaging)."""
from functools import lru_cache

import firebase_admin
from firebase_admin import credentials as fb_credentials

from app.config import get_settings
from app.gcp import get_credentials


class _GoogleCredential(fb_credentials.Base):
    """Adapts our google-auth credentials (ADC, or gcloud CLI tokens in dev) to firebase-admin."""

    def get_credential(self):
        return get_credentials()


@lru_cache
def get_firebase_app() -> firebase_admin.App:
    s = get_settings()
    options = {"projectId": s.gcp_project}
    if s.firebase_signer_sa:
        # Custom tokens are signed through the IAM signBlob API as this service account.
        options["serviceAccountId"] = s.firebase_signer_sa
    return firebase_admin.initialize_app(_GoogleCredential(), options, name="second-brain")
