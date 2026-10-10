"""Extension points for live integrations. Not implemented in the prototype.

Each stub documents the API it should call and how source permissions map to `Document.acl_roles`.
"""
from collections.abc import Iterator

from app.connectors.base import SourceConnector
from app.models import Document


class SlackConnector(SourceConnector):
    """conversations.list + conversations.history/replies via a Slack bot token.
    ACL: public channels -> ["all"]; private channels -> ["slack:<channel_id>"] or mapped team roles."""

    source = "slack"

    def list_documents(self) -> Iterator[Document]:
        raise NotImplementedError("SlackConnector is not implemented in the prototype")


class ConfluenceConnector(SourceConnector):
    """Confluence Cloud REST v2 /wiki/api/v2/pages with body-format=storage.
    ACL: space permissions + page restrictions -> roles."""

    source = "confluence"

    def list_documents(self) -> Iterator[Document]:
        raise NotImplementedError("ConfluenceConnector is not implemented in the prototype")


class GoogleDriveConnector(SourceConnector):
    """Drive API files.list + files.export (Docs -> text/plain), domain-wide delegation.
    ACL: permissions.list -> group emails mapped to roles."""

    source = "gdrive"

    def list_documents(self) -> Iterator[Document]:
        raise NotImplementedError("GoogleDriveConnector is not implemented in the prototype")


class JiraConnector(SourceConnector):
    """Jira Cloud REST /rest/api/3/search with JQL, issue + comments.
    ACL: project roles / issue security levels -> roles."""

    source = "jira"

    def list_documents(self) -> Iterator[Document]:
        raise NotImplementedError("JiraConnector is not implemented in the prototype")


class GmailConnector(SourceConnector):
    """Gmail API users.messages.list/get for shared mailboxes or opted-in users.
    ACL: recipients/distribution lists -> roles."""

    source = "email"

    def list_documents(self) -> Iterator[Document]:
        raise NotImplementedError("GmailConnector is not implemented in the prototype")
