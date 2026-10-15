"""Organizational dependency map: people, teams, service ownership, dependencies and on-call.

Read from the state store (Firestore `org/*` documents, editable live) with a short cache; falls back to
the seed file when the store has no org graph yet."""
import json
import threading
import time
from pathlib import Path

from app.state.base import StateStore


class OrgGraph:
    def __init__(self, seed_path: Path, state: StateStore | None = None, ttl_seconds: int = 30):
        self._seed = json.loads(seed_path.read_text(encoding="utf-8"))
        self._state, self._ttl = state, ttl_seconds
        self._raw, self._loaded_at = self._seed, 0.0
        self._lock = threading.Lock()

    @property
    def raw(self) -> dict:
        if self._state is not None and time.monotonic() - self._loaded_at > self._ttl:
            with self._lock:
                if time.monotonic() - self._loaded_at > self._ttl:
                    self._raw = self._state.load_org() or self._seed
                    self._loaded_at = time.monotonic()
        return self._raw

    @property
    def people(self) -> dict:
        return self.raw["people"]

    @property
    def teams(self) -> dict:
        return self.raw["teams"]

    @property
    def services(self) -> dict:
        return self.raw["services"]

    @property
    def oncall(self) -> dict:
        return self.raw["oncall"]

    def person(self, pid: str) -> dict:
        p = self.people.get(pid)
        return {"id": pid, **p} if p else {"id": pid, "error": "unknown person"}

    def team_oncall(self, team: str) -> dict:
        rota = self.oncall.get(team)
        if not rota:
            return {"team": team, "error": f"unknown team; known teams: {sorted(self.oncall)}"}
        return {
            "team": team,
            "channel": self.teams[team]["channel"],
            "primary": self.person(rota["primary"]),
            "secondary": self.person(rota["secondary"]),
        }

    def team_for_channel(self, channel: str) -> str | None:
        return next((t for t, v in self.teams.items() if v.get("channel") == channel), None)

    def service_info(self, service: str) -> dict:
        svc = self.services.get(service)
        if not svc:
            return {"service": service, "error": f"unknown service; known services: {sorted(self.services)}"}
        team = svc["owner_team"]
        return {
            "service": service,
            "tier": svc["tier"],
            "owner_team": team,
            "team_lead": self.person(self.teams[team]["lead"]),
            "team_channel": self.teams[team]["channel"],
            "oncall": self.team_oncall(team),
            "depends_on": svc["depends_on"],
            "depended_on_by": sorted(s for s, v in self.services.items() if service in v["depends_on"]),
        }
