"""Live integration stubs. Implement and select via env (e.g. JIRA_ADAPTER=real) after shortlisting."""
from app.tools.adapters.interfaces import CalendarAdapter, ChatAdapter, MonitoringAdapter, TicketingAdapter


class JiraCloudTicketing(TicketingAdapter):
    """POST /rest/api/3/issue with an API token or OAuth 2.0 (3LO)."""

    def create_ticket(self, project, summary, description, fields):
        raise NotImplementedError("Jira Cloud integration is not implemented in the prototype")


class SlackChat(ChatAdapter):
    """chat.postMessage with a bot token (or Google Chat spaces.messages.create)."""

    def send_message(self, target, text, sender):
        raise NotImplementedError("Slack integration is not implemented in the prototype")


class GoogleCalendarAvailability(CalendarAdapter):
    """Calendar API freebusy.query with domain-wide delegation."""

    def availability(self, person_ids):
        raise NotImplementedError("Google Calendar integration is not implemented in the prototype")


class CloudMonitoringStatus(MonitoringAdapter):
    """Cloud Monitoring timeSeries.list for error rate/latency + deploy and feature-flag APIs."""

    def service_status(self, service):
        raise NotImplementedError("Cloud Monitoring integration is not implemented in the prototype")
