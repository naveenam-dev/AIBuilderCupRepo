"""Core domain models shared across connectors, retrieval, agent and API layers."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# The ACL role that every authenticated user implicitly holds.
PUBLIC_ROLE = "all"

SourceType = Literal["confluence", "slack", "jira", "email", "gdrive"]


class Document(BaseModel):
    """A normalized artifact from any source system."""

    id: str
    source: SourceType
    title: str
    content: str
    url: str = ""
    author: str = ""
    updated_at: datetime | None = None
    acl_roles: list[str] = Field(default_factory=lambda: [PUBLIC_ROLE])
    metadata: dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    id: str  # "<doc_id>#<n>"
    doc_id: str
    ordinal: int
    text: str
    source: SourceType
    title: str
    url: str = ""
    acl_roles: list[str]
    updated_at: datetime | None = None


class SearchHit(BaseModel):
    chunk: Chunk
    score: float
    vector_rank: int | None = None
    keyword_rank: int | None = None


class Principal(BaseModel):
    """The authenticated user on whose behalf retrieval and actions run."""

    user_id: str
    name: str
    title: str = ""
    team: str = ""
    roles: list[str]

    @property
    def effective_roles(self) -> set[str]:
        return {*self.roles, PUBLIC_ROLE}

    def can_access(self, acl_roles: list[str]) -> bool:
        return bool(self.effective_roles.intersection(acl_roles))
