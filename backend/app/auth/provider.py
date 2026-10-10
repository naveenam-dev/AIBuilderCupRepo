"""Authentication. `DemoAuthProvider` issues signed tokens for seeded personas; a production provider
would verify Google Identity / IAP tokens and map Workspace groups to roles."""
import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt

from app.models import Principal


class AuthProvider(ABC):
    @abstractmethod
    def authenticate(self, token: str) -> Principal: ...


class DemoAuthProvider(AuthProvider):
    def __init__(self, personas_path: Path, secret: str, ttl_minutes: int):
        self.personas = {p["user_id"]: Principal(**p) for p in json.loads(personas_path.read_text(encoding="utf-8"))}
        self.secret, self.ttl = secret, ttl_minutes

    def issue(self, user_id: str) -> str:
        if user_id not in self.personas:
            raise KeyError(user_id)
        now = datetime.now(UTC)
        return jwt.encode({"sub": user_id, "iat": now, "exp": now + timedelta(minutes=self.ttl)}, self.secret, "HS256")

    def authenticate(self, token: str) -> Principal:
        claims = jwt.decode(token, self.secret, algorithms=["HS256"])
        # Roles come from the server-side directory, never from the client.
        return self.personas[claims["sub"]]


class GoogleIdentityAuthProvider(AuthProvider):
    """Verify an IAP / Firebase ID token and resolve roles from Workspace group membership."""

    def authenticate(self, token: str) -> Principal:
        raise NotImplementedError("Google Identity auth is not implemented in the prototype")
