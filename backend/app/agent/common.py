"""Tool execution shared by both agent runtimes (native Gemini loop and ADK): RBAC check, approval
queue for write tools, audit logging, and the helpers that shape results for the model and the UI."""
import json
import logging
from typing import Any

from app.models import Principal
from app.tools.actions import ActionService
from app.tools.base import ToolContext
from app.tools.registry import ToolRegistry

log = logging.getLogger(__name__)
Event = dict[str, Any]


def plain(value: Any) -> Any:
    """Normalize SDK argument objects into JSON-safe Python values."""
    return json.loads(json.dumps(value, default=str))


def preview(result: Any) -> str:
    if isinstance(result, dict) and isinstance(result.get("results"), list):
        return f"{len(result['results'])} result(s): " + "; ".join(r["title"] for r in result["results"][:4])
    text = json.dumps(result, default=str)
    return text if len(text) <= 240 else text[:237] + "..."


def tool_payload(result: dict) -> dict:
    """What the model sees: the UI-only "action" object is dropped."""
    return {k: v for k, v in result.items() if k != "action"}


def execute_tool(registry: ToolRegistry, actions: ActionService, name: str, args: dict, ctx: ToolContext,
                 principal: Principal, proposed: set[str]) -> dict:
    tool = registry.get(name)
    if tool is None or not tool.permitted(principal):
        actions.log(principal, name, args, "denied")
        return {"error": f"Tool '{name}' is not available to this user."}
    if tool.requires_approval:
        action = actions.propose(principal, name, args)
        proposed.add(action.id)
        return {
            "status": "pending_user_approval",
            "action_id": action.id,
            "note": "Queued for the user's approval. Reference this action_id in the matching SOP step.",
            "action": action.model_dump(mode="json"),
        }
    try:
        result = tool.execute(args, ctx)
        ctx.tools_called.add(name)
        actions.log(principal, name, args, "ok")
        return result
    except Exception as e:
        log.exception("Tool %s failed", name)
        actions.log(principal, name, args, f"error: {e}")
        return {"error": str(e)}
