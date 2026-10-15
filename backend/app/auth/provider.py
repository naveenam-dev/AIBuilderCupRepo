"""Authentication.

* `DemoAuthProvider`: signed JWTs for the seeded personas (offline dev and tests).
* `FirebaseAuthProvider`: Firebase Authentication. Demo personas sign in with Firebase custom tokens minted
  here; anyone else signs in with Google. Every request carries a Firebase ID token that is verified server-side.

Roles never come from the client: personas get theirs from the server-side directory, Google users from
custom claims set by an admin (`python -m scripts.grant_roles`)."""
import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt

from app.models import Principal


def load_personas(path: Path) -> dict[str, Principal]:
    return {p["user_id"]: Principal(**p) for p in json.loads(path.read_text(encoding="utf-8"))}


class AuthProvider(ABC):
    personas: dict[str, Principal]
    # How the browser uses the token from `issue`: "bearer" sends it as-is, "firebase_custom_token"
    # exchanges it with Firebase Auth and then sends Firebase ID tokens.
    token_type: str

    @abstractmethod
    def issue(self, user_id: str) -> str:
        """Sign-in token for a demo persona."""

    @abstractmethod
    def authenticate(self, token: str) -> Principal: ...


class DemoAuthProvider(AuthProvider):
    token_type = "bearer"

    def __init__(self, personas_path: Path, secret: str, ttl_minutes: int):
        self.personas = load_personas(personas_path)
        self.secret, self.ttl = secret, ttl_minutes

    def issue(self, user_id: str) -> str:
        if user_id not in self.personas:
            raise KeyError(user_id)
        now = datetime.now(UTC)
        return jwt.encode({"sub": user_id, "iat": now, "exp": now + timedelta(minutes=self.ttl)}, self.secret, "HS256")

    def authenticate(self, token: str) -> Principal:
        claims = jwt.decode(token, self.secret, algorithms=["HS256"])
        return self.personas[claims["sub"]]


class FirebaseAuthProvider(AuthProvider):
    token_type = "firebase_custom_token"

    def __init__(self, personas_path: Path, app):
        from firebase_admin import auth

        self._auth, self.app = auth, app
        self.personas = load_personas(personas_path)

    def issue(self, user_id: str) -> str:
        p = self.personas[user_id]
        token = self._auth.create_custom_token(user_id, {"persona": True, "roles": p.roles}, app=self.app)
        return token.decode() if isinstance(token, bytes) else token

    def authenticate(self, token: str) -> Principal:
        claims = self._auth.verify_id_token(token, app=self.app)
        uid = claims["uid"]
        if claims.get("persona") and uid in self.personas:
            return self.personas[uid]
        # Google sign-in: identity from Google, roles only from admin-set custom claims.
        return Principal(
            user_id=uid,
            name=claims.get("name") or claims.get("email") or "Signed-in user",
            title=claims.get("email", ""),
            team=claims.get("team", ""),
            roles=[r for r in claims.get("roles", []) if isinstance(r, str)],
        )
