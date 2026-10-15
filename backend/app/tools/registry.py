"""Builds the tool registry with adapters selected from configuration."""
from app.config import Settings
from app.models import Principal
from app.retrieval.service import RetrievalService
from app.state.base import StateStore
from app.tools import builtin
from app.tools.adapters import mock, real
from app.tools.base import ActionTool
from app.tools.org_graph import OrgGraph


class ToolRegistry:
    def __init__(self, tools: list[ActionTool]):
        self.tools = {t.name: t for t in tools}

    def get(self, name: str) -> ActionTool | None:
        return self.tools.get(name)

    def for_principal(self, principal: Principal) -> list[ActionTool]:
        """RBAC on actions: the model is only offered tools the user may use."""
        return [t for t in self.tools.values() if t.permitted(principal)]


def _chat_adapter(settings: Settings, state: StateStore, org: OrgGraph):
    if settings.chat_adapter == "firebase":
        from app.firebase import get_firebase_app
        from app.tools.adapters.firebase_chat import FirebaseChat

        return FirebaseChat(state, org, get_firebase_app())
    return mock.MockChat() if settings.chat_adapter == "mock" else real.SlackChat()


def build_registry(settings: Settings, retrieval: RetrievalService, state: StateStore, org: OrgGraph) -> ToolRegistry:
    pick = lambda choice, mock_impl, real_cls: mock_impl if choice == "mock" else real_cls()  # noqa: E731
    ticketing = pick(settings.jira_adapter, mock.MockTicketing(), real.JiraCloudTicketing)
    chat = _chat_adapter(settings, state, org)
    calendar = pick(settings.calendar_adapter, mock.MockCalendar(org), real.GoogleCalendarAvailability)
    monitoring = pick(
        settings.monitoring_adapter, mock.MockMonitoring(settings.seed_dir / "monitoring.json"), real.CloudMonitoringStatus
    )
    return ToolRegistry(
        [
            builtin.SearchKnowledge(retrieval),
            builtin.GetServiceStatus(monitoring),
            builtin.GetServiceInfo(org),
            builtin.GetOncall(org),
            builtin.CheckAvailability(calendar),
            builtin.CreateIncidentTicket(ticketing),
            builtin.SendChatMessage(chat),
        ]
    )
