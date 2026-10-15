"""Agent loop: Gemini function calling over the tool registry, streamed as events.

Event types: status, tool_call, tool_result, action_proposed, sop, error, done.
"""
import logging
import time
from collections.abc import Iterator

from google.genai import types

from app.agent.common import Event, execute_tool, plain, preview, tool_payload
from app.agent.grounding import verify_sop
from app.agent.prompts import SUBMIT_SOP, system_prompt
from app.config import Settings
from app.models import Principal
from app.tools.actions import ActionService
from app.tools.base import ToolContext
from app.tools.registry import ToolRegistry

log = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, client, settings: Settings, registry: ToolRegistry, actions: ActionService, clock: str = "09:45 UTC"):
        self.client, self.s, self.registry, self.actions, self.clock = client, settings, registry, actions, clock

    def run(self, question: str, principal: Principal, history: list[dict] | None = None) -> Iterator[Event]:
        started = time.monotonic()
        tools = self.registry.for_principal(principal)
        declarations = [
            types.FunctionDeclaration(name=t.name, description=t.description, parameters_json_schema=t.parameters)
            for t in tools
        ] + [types.FunctionDeclaration(name=SUBMIT_SOP["name"], description=SUBMIT_SOP["description"],
                                       parameters_json_schema=SUBMIT_SOP["parameters"])]
        config = types.GenerateContentConfig(
            system_instruction=system_prompt(principal, [t.name for t in tools], self.clock),
            tools=[types.Tool(function_declarations=declarations)],
            temperature=self.s.llm_temperature,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            thinking_config=types.ThinkingConfig(thinking_level=self.s.llm_thinking_level)
            if self.s.llm_thinking_level else None,
        )
        contents = [
            types.Content(role="user" if m["role"] == "user" else "model", parts=[types.Part.from_text(text=m["text"])])
            for m in (history or [])
        ] + [types.Content(role="user", parts=[types.Part.from_text(text=question)])]

        ctx = ToolContext(principal=principal)
        proposed: set[str] = set()
        call_seq = 0
        yield {"type": "status", "message": f"Planning with {len(tools)} tools available to {principal.name}"}

        for step in range(self.s.max_agent_steps + 1):
            if step == self.s.max_agent_steps:  # budget exhausted: force the final answer
                config.tool_config = types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(mode="ANY", allowed_function_names=["submit_sop"])
                )
            try:
                resp = self.client.models.generate_content(model=self.s.llm_model, contents=contents, config=config)
            except Exception as e:
                log.exception("LLM call failed")
                yield {"type": "error", "message": f"Model call failed: {e}"}
                return
            candidate = resp.candidates[0].content if resp.candidates else None
            calls = resp.function_calls or []
            if candidate is None:
                yield {"type": "error", "message": "Empty model response"}
                return
            contents.append(candidate)

            if not calls:
                # Model answered in prose instead of submitting: nudge once, then force on the next turn.
                contents.append(types.Content(role="user", parts=[types.Part.from_text(
                    text="Now call submit_sop with the grounded procedure.")]))
                config.tool_config = types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(mode="ANY", allowed_function_names=["submit_sop"])
                )
                continue

            responses = []
            for fc in calls:
                args = plain(fc.args or {})
                if fc.name == "submit_sop":
                    sop = verify_sop(args, ctx, proposed)
                    sop["elapsed_s"] = round(time.monotonic() - started, 1)
                    self.actions.log(principal, "submit_sop", {"question": question}, "answered")
                    yield {"type": "sop", "sop": sop}
                    yield {"type": "done"}
                    return

                if call_seq >= self.s.max_tool_calls:
                    responses.append(types.Part.from_function_response(
                        name=fc.name, response={"error": "Tool budget exhausted. Call submit_sop now."}))
                    continue
                call_seq += 1
                call_id = f"c{call_seq}"
                yield {"type": "tool_call", "id": call_id, "name": fc.name, "args": args}
                result = self._execute(fc.name, args, ctx, principal, proposed)
                if "action" in result:
                    yield {"type": "action_proposed", "id": call_id, "action": result["action"]}
                yield {"type": "tool_result", "id": call_id, "name": fc.name, "preview": preview(result),
                       "ok": "error" not in result}
                responses.append(types.Part.from_function_response(name=fc.name, response=tool_payload(result)))
            contents.append(types.Content(role="user", parts=responses))
            if call_seq >= self.s.max_tool_calls:
                config.tool_config = types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(mode="ANY", allowed_function_names=["submit_sop"])
                )

        yield {"type": "error", "message": "Agent did not produce a procedure within the step budget"}

    def _execute(self, name: str, args: dict, ctx: ToolContext, principal: Principal, proposed: set[str]) -> dict:
        return execute_tool(self.registry, self.actions, name, args, ctx, principal, proposed)
