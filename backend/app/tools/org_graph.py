"""Organizational dependency map: people, teams, service ownership, dependencies and on-call."""
import json
from pathlib import Path


class OrgGraph:
    def __init__(self, path: Path):
        self.raw = json.loads(path.read_text(encoding="utf-8"))
        self.people, self.teams = self.raw["people"], self.raw["teams"]
        self.services, self.oncall = self.raw["services"], self.raw["oncall"]

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
