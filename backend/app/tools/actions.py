"""Human-in-the-loop approval queue and audit log for agent actions (in-process for the prototype)."""
import threading
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models import Principal
from app.tools.base import ToolContext
from app.tools.registry import ToolRegistry


class PendingAction(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    tool: str
    args: dict[str, Any]
    summary: str
    requested_by: str
    status: Literal["pending", "executed", "rejected", "failed"] = "pending"
    result: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditEntry(BaseModel):
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    user_id: str
    tool: str
    args: dict[str, Any]
    outcome: str


class ActionService:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.pending: dict[str, PendingAction] = {}
        self.audit: list[AuditEntry] = []
        self._lock = threading.Lock()

    def log(self, principal: Principal, tool: str, args: dict, outcome: str) -> None:
        with self._lock:
            self.audit.append(AuditEntry(user_id=principal.user_id, tool=tool, args=args, outcome=outcome))

    def propose(self, principal: Principal, tool: str, args: dict) -> PendingAction:
        action = PendingAction(
            tool=tool, args=args, summary=self.registry.get(tool).describe_proposal(args), requested_by=principal.user_id
        )
        with self._lock:
            self.pending[action.id] = action
        self.log(principal, tool, args, f"proposed:{action.id}")
        return action

    def decide(self, action_id: str, principal: Principal, approve: bool) -> PendingAction:
        with self._lock:
            action = self.pending.get(action_id)
            if action is None:
                raise KeyError(action_id)
            if action.requested_by != principal.user_id:
                raise PermissionError("Only the requesting user can approve this action")
            if action.status != "pending":
                return action
            action.status = "executed" if approve else "rejected"  # claim it before releasing the lock
        if approve:
            tool = self.registry.get(action.tool)
            if not tool.permitted(principal):
                action.status = "failed"
                action.result = {"error": "not permitted"}
            else:
                try:
                    action.result = tool.execute(action.args, ToolContext(principal=principal))
                except Exception as e:  # surface adapter failures on the card instead of a 500
                    action.status = "failed"
                    action.result = {"error": str(e)}
        self.log(principal, action.tool, action.args, action.status)
        return action
