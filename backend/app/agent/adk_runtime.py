"""Agent runtime on Google's Agent Development Kit (ADK).

Same contract as the native loop (`Orchestrator.run`): yields the UI events status, tool_call,
tool_result, action_proposed, sop, error, done; but the agent loop, parallel tool execution and
session handling are ADK's:

* every registry tool becomes an ADK `BaseTool` with its existing JSON schema; RBAC still decides
  which tools this user's agent is built with, and execution goes through the shared `execute_tool`
* `submit_sop` is a terminal tool: it runs the grounding guard and ends the turn (skip_summarization)
* the tool budget is a `before_tool_callback`; once it is spent (or the model answers in prose), a
  `before_model_callback` allows only submit_sop, so every run ends in a structured, verified procedure
* the model-turn budget is `RunConfig.max_llm_calls`
"""
import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.agents.run_config import RunConfig
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.base_tool import BaseTool
from google.genai import types

from app.agent.common import Event, execute_tool, plain, preview, tool_payload
from app.agent.grounding import verify_sop
from app.agent.prompts import SUBMIT_SOP, system_prompt
from app.config import Settings
from app.models import Principal
from app.tools.actions import ActionService
from app.tools.base import ActionTool, ToolContext
from app.tools.registry import ToolRegistry

log = logging.getLogger(__name__)
APP_NAME = "second_brain"


@dataclass
class _Run:
    """Per-question state shared by the tools and the event stream."""
    principal: Principal
    ctx: ToolContext
    proposed: set[str] = field(default_factory=set)
    calls: int = 0
    actions_by_call: dict[str, dict] = field(default_factory=dict)  # function_call_id -> proposed action (UI only)
    sop: dict | None = None
    force_submit: bool = False


class _RegistryTool(BaseTool):
    def __init__(self, tool: ActionTool, run: _Run, rt: "AdkOrchestrator"):
        super().__init__(name=tool.name, description=tool.description)
        self._tool, self._run, self._rt = tool, run, rt

    def _get_declaration(self):
        return types.FunctionDeclaration(name=self.name, description=self.description,
                                         parameters_json_schema=self._tool.parameters)

    async def run_async(self, *, args: dict[str, Any], tool_context) -> Any:
        r = self._run
        r.calls += 1
        result = await asyncio.to_thread(  # tools do blocking I/O (AlloyDB, Firestore, Vertex embeddings)
            execute_tool, self._rt.registry, self._rt.actions, self.name, plain(args), r.ctx, r.principal, r.proposed)
        if "action" in result:
            r.actions_by_call[tool_context.function_call_id] = result["action"]
        return tool_payload(result)


class _SubmitSopTool(BaseTool):
    def __init__(self, run: _Run, rt: "AdkOrchestrator", started: float, question: str):
        super().__init__(name=SUBMIT_SOP["name"], description=SUBMIT_SOP["description"])
        self._run, self._rt, self._started, self._question = run, rt, started, question

    def _get_declaration(self):
        return types.FunctionDeclaration(name=self.name, description=self.description,
                                         parameters_json_schema=SUBMIT_SOP["parameters"])

    async def run_async(self, *, args: dict[str, Any], tool_context) -> Any:
        r = self._run
        sop = verify_sop(plain(args), r.ctx, r.proposed)
        sop["elapsed_s"] = round(time.monotonic() - self._started, 1)
        r.sop = sop
        self._rt.actions.log(r.principal, "submit_sop", {"question": self._question}, "answered")
        tool_context.actions.skip_summarization = True  # the verified procedure is the final answer
        return {"status": "submitted", "steps_grounded": sop["verification"]["steps_grounded"]}


class AdkOrchestrator:
    runtime = "adk"

    def __init__(self, client, settings: Settings, registry: ToolRegistry, actions: ActionService, clock: str = "09:45 UTC"):
        self.s, self.registry, self.actions, self.clock = settings, registry, actions, clock
        self.model = Gemini(model=settings.llm_model, client=client)  # reuse the app's Vertex AI client
        self.sessions = InMemorySessionService()

    def _agent(self, principal: Principal, run: _Run, started: float, question: str) -> LlmAgent:
        allowed = self.registry.for_principal(principal)  # RBAC on actions: the agent is built with only these
        instruction = system_prompt(principal, [t.name for t in allowed], self.clock)
        max_tools = self.s.max_tool_calls

        def budget(tool, args, tool_context):
            if tool.name != SUBMIT_SOP["name"] and run.calls >= max_tools:
                return {"error": "Tool budget exhausted. Call submit_sop now."}
            return None

        def force_final_answer(callback_context, llm_request):
            # The model chooses freely until the tool budget is spent (or it answered in prose); then the only
            # call it may make is submit_sop, so every run ends in a verified, structured procedure.
            if run.force_submit or run.calls >= max_tools:
                llm_request.config.tool_config = types.ToolConfig(function_calling_config=types.FunctionCallingConfig(
                    mode="ANY", allowed_function_names=[SUBMIT_SOP["name"]]))
            return None

        return LlmAgent(
            name="oncall_copilot",
            model=self.model,
            description="Turns enterprise knowledge and live system state into a verified on-call procedure.",
            instruction=lambda _ctx: instruction,  # a provider, so ADK does not template the braces
            tools=[_RegistryTool(t, run, self) for t in allowed] + [_SubmitSopTool(run, self, started, question)],
            generate_content_config=types.GenerateContentConfig(
                temperature=self.s.llm_temperature,
                thinking_config=types.ThinkingConfig(thinking_level=self.s.llm_thinking_level)
                if self.s.llm_thinking_level else None,
            ),
            before_model_callback=force_final_answer,
            before_tool_callback=budget,
        )

    async def run(self, question: str, principal: Principal, history: list[dict] | None = None) -> AsyncIterator[Event]:
        started = time.monotonic()
        run = _Run(principal=principal, ctx=ToolContext(principal=principal))
        agent = self._agent(principal, run, started, question)
        runner = Runner(app_name=APP_NAME, agent=agent, session_service=self.sessions)
        session = await self.sessions.create_session(app_name=APP_NAME, user_id=principal.user_id,
                                                     session_id=uuid.uuid4().hex)
        prior = "".join(f"{'User' if m['role'] == 'user' else 'You'}: {m['text']}\n" for m in (history or []))
        text = f"Earlier in this conversation:\n{prior}\nNew question: {question}" if prior else question
        message = types.Content(role="user", parts=[types.Part.from_text(text=text)])

        yield {"type": "status", "message": f"ADK agent planning with {len(agent.tools) - 1} tools available to {principal.name}"}
        ids: dict[str, str] = {}
        nudge = types.Content(role="user", parts=[types.Part.from_text(text="Now call submit_sop with the grounded procedure.")])
        try:
            for attempt in (message, nudge):  # second pass only if the model answered in prose
                if run.sop is not None:
                    break
                run.force_submit = attempt is nudge
                async for ev in runner.run_async(user_id=principal.user_id, session_id=session.id, new_message=attempt,
                                                 run_config=RunConfig(max_llm_calls=self.s.max_agent_steps + 2)):
                    for fc in ev.get_function_calls():
                        if fc.name == SUBMIT_SOP["name"]:
                            continue
                        ids[fc.id] = f"c{len(ids) + 1}"
                        yield {"type": "tool_call", "id": ids[fc.id], "name": fc.name, "args": plain(fc.args or {})}
                    for fr in ev.get_function_responses():
                        if fr.name == SUBMIT_SOP["name"]:
                            continue
                        call_id = ids.get(fr.id, fr.id)
                        if fr.id in run.actions_by_call:
                            yield {"type": "action_proposed", "id": call_id, "action": run.actions_by_call[fr.id]}
                        response = fr.response or {}
                        yield {"type": "tool_result", "id": call_id, "name": fr.name, "preview": preview(response),
                               "ok": "error" not in response}
        except Exception as e:
            log.exception("ADK run failed")
            if run.sop is None:
                yield {"type": "error", "message": f"Agent run failed: {e}"}
                return
        finally:
            await self.sessions.delete_session(app_name=APP_NAME, user_id=principal.user_id, session_id=session.id)

        if run.sop is None:
            yield {"type": "error", "message": "Agent did not produce a procedure within the step budget"}
            return
        yield {"type": "sop", "sop": run.sop}
        yield {"type": "done"}
