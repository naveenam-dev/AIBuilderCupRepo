"""Source connector interface.

Each enterprise system (Slack, Confluence, Drive, Jira, Gmail, ...) implements `SourceConnector`
and emits normalized `Document`s, including the ACL roles that govern who may retrieve them.
"""
from abc import ABC, abstractmethod
from collections.abc import Iterator

from app.models import Document, SourceType


class SourceConnector(ABC):
    source: SourceType

    @abstractmethod
    def list_documents(self) -> Iterator[Document]:
        """Yield every document visible to the connector's service account."""

    def fetch(self, doc_id: str) -> Document | None:
        """Fetch a single document. Default: linear scan; real connectors should override."""
        return next((d for d in self.list_documents() if d.id == doc_id), None)
