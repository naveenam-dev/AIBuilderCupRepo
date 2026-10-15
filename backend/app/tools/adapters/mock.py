"""Mock adapters backed by seed data and in-process state. Deterministic for live demos."""
import itertools
import json
from datetime import UTC, datetime
from pathlib import Path

from app.tools.adapters.interfaces import CalendarAdapter, ChatAdapter, MonitoringAdapter, TicketingAdapter


class MockTicketing(TicketingAdapter):
    def __init__(self):
        self._seq = itertools.count(512)
        self.tickets: list[dict] = []

    def create_ticket(self, project, summary, description, fields):
        key = f"{project}-{next(self._seq)}"
        ticket = {
            "key": key,
            "url": f"https://acmepay.atlassian.net/browse/{key}",
            "summary": summary,
            "description": description,
            "fields": fields,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self.tickets.append(ticket)
        return ticket


class MockChat(ChatAdapter):
    def __init__(self):
        self.messages: list[dict] = []

    def send_message(self, target, text, sender):
        msg = {"target": target, "text": text, "sender": sender, "sent_at": datetime.now(UTC).isoformat(), "delivered": True}
        self.messages.append(msg)
        return msg


class MockCalendar(CalendarAdapter):
    """Uses a fixed demo clock so availability is reproducible."""

    def __init__(self, org, demo_time: str = "09:45"):
        self.org = org  # OrgGraph: calendars live alongside the org graph and are re-read with it
        self.now = demo_time

    def availability(self, person_ids):
        calendars: dict[str, list[dict]] = self.org.raw.get("calendar", {})
        out = {}
        for pid in person_ids:
            events = calendars.get(pid)
            if events is None:
                out[pid] = {"error": "unknown person"}
                continue
            current = next((e for e in events if e["start"] <= self.now < e["end"]), None)
            out[pid] = {
                "busy_now": current is not None,
                "current_event": current["title"] if current else None,
                "free_at": current["end"] if current else self.now,
                "today": events,
            }
        return out


class MockMonitoring(MonitoringAdapter):
    def __init__(self, path: Path):
        self.data = json.loads(path.read_text(encoding="utf-8"))["services"]

    def service_status(self, service):
        return self.data.get(service, {"error": f"no telemetry for service '{service}'"})
