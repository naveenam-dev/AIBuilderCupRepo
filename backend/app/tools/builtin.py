"""The agent's toolbox for the on-call vertical."""
from typing import Any

from app.retrieval.service import RetrievalService
from app.tools.adapters.interfaces import CalendarAdapter, ChatAdapter, MonitoringAdapter, TicketingAdapter
from app.tools.base import ActionTool, ToolContext
from app.tools.org_graph import OrgGraph

_ENGINEERING = frozenset({"engineering", "sre"})


class SearchKnowledge(ActionTool):
    name = "search_knowledge"
    description = (
        "Hybrid (semantic + keyword) search over internal runbooks, Confluence pages, Slack threads, Jira tickets "
        "and emails the current user is authorized to see. Returns chunks with chunk_id for citation. "
        "Call it several times with focused queries (symptoms, service names, error codes, ticket ids)."
    )
    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "Focused search query"}},
        "required": ["query"],
    }

    def __init__(self, retrieval: RetrievalService):
        self.retrieval = retrieval

    def execute(self, args, ctx):
        hits = self.retrieval.search(args["query"], ctx.principal)
        for h in hits:
            ctx.citable_chunks[h.chunk.id] = h.chunk
        return {
            "results": [
                {
                    "chunk_id": h.chunk.id,
                    "title": h.chunk.title,
                    "source": h.chunk.source,
                    "updated_at": h.chunk.updated_at.date().isoformat() if h.chunk.updated_at else None,
                    "text": h.chunk.text,
                }
                for h in hits
            ]
            or "No authorized documents matched. Do not guess; tell the user and suggest escalation."
        }


class GetServiceInfo(ActionTool):
    name = "get_service_info"
    description = "Org graph lookup for a service: owner team, team lead, on-call engineers, upstream and downstream dependencies."
    parameters = {
        "type": "object",
        "properties": {"service": {"type": "string", "description": "Service name, e.g. payments-api"}},
        "required": ["service"],
    }

    def __init__(self, org: OrgGraph):
        self.org = org

    def execute(self, args, ctx):
        return self.org.service_info(args["service"])


class GetOncall(ActionTool):
    name = "get_oncall"
    description = "Current primary and secondary on-call engineer for a team (sre, payments, ledger, security)."
    parameters = {"type": "object", "properties": {"team": {"type": "string"}}, "required": ["team"]}

    def __init__(self, org: OrgGraph):
        self.org = org

    def execute(self, args, ctx):
        return self.org.team_oncall(args["team"])


class CheckAvailability(ActionTool):
    name = "check_availability"
    description = "Calendar free/busy for people (by person id, e.g. 'sofia'). Use before deciding whom to contact."
    parameters = {
        "type": "object",
        "properties": {"person_ids": {"type": "array", "items": {"type": "string"}}},
        "required": ["person_ids"],
    }

    def __init__(self, calendar: CalendarAdapter):
        self.calendar = calendar

    def execute(self, args, ctx):
        return self.calendar.availability(args["person_ids"])


class GetServiceStatus(ActionTool):
    name = "get_service_status"
    description = (
        "Live telemetry for a service: status, error rate, dominant status code, p99 latency, last deploy, "
        "feature flags, recent log signatures."
    )
    parameters = {"type": "object", "properties": {"service": {"type": "string"}}, "required": ["service"]}
    allowed_roles = _ENGINEERING

    def __init__(self, monitoring: MonitoringAdapter):
        self.monitoring = monitoring

    def execute(self, args, ctx):
        return self.monitoring.service_status(args["service"])


class CreateIncidentTicket(ActionTool):
    name = "create_incident_ticket"
    description = "Create a Jira incident ticket in project INC. Requires user approval before it is executed."
    parameters = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "severity": {"type": "string", "enum": ["Sev1", "Sev2", "Sev3"]},
            "service": {"type": "string"},
            "description": {"type": "string", "description": "Impact, timeline so far, suspected cause, related tickets"},
        },
        "required": ["summary", "severity", "service", "description"],
    }
    requires_approval = True
    allowed_roles = _ENGINEERING

    def __init__(self, ticketing: TicketingAdapter):
        self.ticketing = ticketing

    def execute(self, args, ctx):
        return self.ticketing.create_ticket(
            "INC",
            args["summary"],
            args["description"],
            {"severity": args["severity"], "service": args["service"], "reporter": ctx.principal.user_id},
        )

    def describe_proposal(self, args):
        return f"Create {args.get('severity', '')} ticket in INC: {args.get('summary', '')}"


class SendChatMessage(ActionTool):
    name = "send_chat_message"
    description = (
        "Send a chat message to a channel (e.g. #ledger-oncall, #incidents) or a person (@sofia). "
        "Use to page or notify people. Requires user approval before it is executed."
    )
    parameters = {
        "type": "object",
        "properties": {"target": {"type": "string"}, "text": {"type": "string"}},
        "required": ["target", "text"],
    }
    requires_approval = True

    def __init__(self, chat: ChatAdapter):
        self.chat = chat

    def execute(self, args, ctx):
        return self.chat.send_message(args["target"], args["text"], sender=ctx.principal.name)

    def describe_proposal(self, args: dict[str, Any]) -> str:
        return f"Message {args.get('target', '')}: \"{args.get('text', '')}\""
