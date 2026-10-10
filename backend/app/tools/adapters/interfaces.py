"""Integration adapter interfaces. Mock implementations back the prototype; real ones are stubs."""
from abc import ABC, abstractmethod
from typing import Any


class TicketingAdapter(ABC):
    """Jira (or ServiceNow, Linear...)."""

    @abstractmethod
    def create_ticket(self, project: str, summary: str, description: str, fields: dict[str, Any]) -> dict: ...


class ChatAdapter(ABC):
    """Slack / Google Chat / Teams."""

    @abstractmethod
    def send_message(self, target: str, text: str, sender: str) -> dict: ...


class CalendarAdapter(ABC):
    """Google Calendar free/busy."""

    @abstractmethod
    def availability(self, person_ids: list[str]) -> dict[str, dict]: ...


class MonitoringAdapter(ABC):
    """Cloud Monitoring / Datadog / Prometheus + deploy history + feature flags."""

    @abstractmethod
    def service_status(self, service: str) -> dict: ...
