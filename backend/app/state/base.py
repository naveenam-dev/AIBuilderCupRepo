"""Operational state interface: approval queue, audit log, per-user inboxes, push device tokens and the
org graph. Kept separate from the knowledge store (AlloyDB): this is small, transactional, per-user data
that the browser can also watch live."""
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ActionStatus = Literal["pending", "executed", "rejected", "failed"]


class PendingAction(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    tool: str
    args: dict[str, Any]
    summary: str
    requested_by: str
    status: ActionStatus = "pending"
    result: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    decided_at: datetime | None = None


class AuditEntry(BaseModel):
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    user_id: str
    tool: str
    args: dict[str, Any]
    outcome: str


class InboxMessage(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:10])
    target: str  # the channel or @person it was addressed to
    text: str
    sender: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StateStore(ABC):
    # --- approvals ---
    @abstractmethod
    def put_action(self, action: PendingAction) -> None: ...

    @abstractmethod
    def get_action(self, action_id: str) -> PendingAction | None: ...

    @abstractmethod
    def claim_action(self, action_id: str, check: Callable[[PendingAction], ActionStatus | None]) -> PendingAction:
        """Atomically move a pending action to the status `check` returns (None = leave as is).
        Raises KeyError if missing; `check` may raise to refuse. Returns the action after the update."""

    @abstractmethod
    def save_result(self, action_id: str, status: ActionStatus, result: dict[str, Any]) -> None: ...

    # --- audit ---
    @abstractmethod
    def append_audit(self, entry: AuditEntry) -> None: ...

    @abstractmethod
    def list_audit(self, user_id: str | None = None, limit: int = 100) -> list[AuditEntry]: ...

    # --- inboxes and push tokens ---
    @abstractmethod
    def deliver(self, user_id: str, message: InboxMessage) -> None: ...

    @abstractmethod
    def add_device_token(self, user_id: str, token: str) -> None: ...

    @abstractmethod
    def device_tokens(self, user_id: str) -> list[str]: ...

    @abstractmethod
    def remove_device_token(self, user_id: str, token: str) -> None: ...

    # --- org graph ---
    @abstractmethod
    def load_org(self) -> dict | None:
        """The org graph in org.json shape, or None to fall back to the seed file."""
