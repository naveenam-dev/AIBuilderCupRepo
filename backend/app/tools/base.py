"""Agent tool interface. Each tool is exposed to Gemini as a function declaration."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.models import Chunk, Principal


@dataclass
class ToolContext:
    principal: Principal
    # Chunks returned by search_knowledge during this run: the only knowledge the answer may cite.
    citable_chunks: dict[str, Chunk] = field(default_factory=dict)
    # Names of tools that returned live data during this run (citable as "tool:<name>").
    tools_called: set[str] = field(default_factory=set)


class ActionTool(ABC):
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for the arguments
    # Write actions are proposed by the agent and only executed after explicit user approval.
    requires_approval: bool = False
    # None = any authenticated user; otherwise the principal needs at least one of these roles.
    allowed_roles: frozenset[str] | None = None

    def permitted(self, principal: Principal) -> bool:
        return self.allowed_roles is None or bool(principal.effective_roles & self.allowed_roles)

    @abstractmethod
    def execute(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]: ...

    def describe_proposal(self, args: dict[str, Any]) -> str:
        """Human-readable summary shown on the approval card."""
        return f"{self.name}({args})"
