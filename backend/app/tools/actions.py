"""Human-in-the-loop approval queue and audit log for agent actions, persisted through a StateStore."""
from app.models import Principal
from app.state.base import AuditEntry, PendingAction, StateStore
from app.tools.base import ToolContext
from app.tools.registry import ToolRegistry

__all__ = ["ActionService", "AuditEntry", "PendingAction"]


class ActionService:
    def __init__(self, registry: ToolRegistry, state: StateStore):
        self.registry = registry
        self.state = state

    def log(self, principal: Principal, tool: str, args: dict, outcome: str) -> None:
        self.state.append_audit(AuditEntry(user_id=principal.user_id, tool=tool, args=args, outcome=outcome))

    def propose(self, principal: Principal, tool: str, args: dict) -> PendingAction:
        action = PendingAction(
            tool=tool, args=args, summary=self.registry.get(tool).describe_proposal(args), requested_by=principal.user_id
        )
        self.state.put_action(action)
        self.log(principal, tool, args, f"proposed:{action.id}")
        return action

    def decide(self, action_id: str, principal: Principal, approve: bool) -> PendingAction:
        claimed = False

        def check(action: PendingAction):
            nonlocal claimed
            if action.requested_by != principal.user_id:
                raise PermissionError("Only the requesting user can approve this action")
            if action.status != "pending":
                return None
            claimed = True
            return "executed" if approve else "rejected"  # claim it atomically before running anything

        action = self.state.claim_action(action_id, check)
        if not claimed:
            return action
        if approve:
            tool = self.registry.get(action.tool)
            if not tool.permitted(principal):
                action.status, action.result = "failed", {"error": "not permitted"}
            else:
                try:
                    action.result = tool.execute(action.args, ToolContext(principal=principal))
                except Exception as e:  # surface adapter failures on the card instead of a 500
                    action.status, action.result = "failed", {"error": str(e)}
            self.state.save_result(action.id, action.status, action.result)
        self.log(principal, action.tool, action.args, action.status)
        return action
