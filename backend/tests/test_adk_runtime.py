"""Offline checks of the ADK runtime wiring: role-filtered tool set, declarations and the tool budget."""
import pytest

pytest.importorskip("google.adk")

from app.agent.adk_runtime import AdkOrchestrator, _Run  # noqa: E402
from app.agent.prompts import SUBMIT_SOP  # noqa: E402
from app.config import Settings  # noqa: E402
from app.container import build_container  # noqa: E402
from app.tools.base import ToolContext  # noqa: E402


@pytest.fixture(scope="module")
def rt():
    c = build_container(Settings(_env_file=None, embedder="fake", vector_store="memory", state_store="memory"), use_llm=False)
    return c, AdkOrchestrator(client=None, settings=c.settings, registry=c.registry, actions=c.actions)


def agent_for(rt, uid):
    c, orch = rt
    p = c.auth.personas[uid]
    run = _Run(principal=p, ctx=ToolContext(principal=p))
    return orch._agent(p, run, 0.0, "q"), run


def test_agent_tools_follow_roles(rt):
    sre, _ = agent_for(rt, "priya")
    contractor, _ = agent_for(rt, "jordan")
    sre_tools = {t.name for t in sre.tools}
    contractor_tools = {t.name for t in contractor.tools}
    assert {"create_incident_ticket", "get_service_status", SUBMIT_SOP["name"]} <= sre_tools
    assert "create_incident_ticket" not in contractor_tools and "get_service_status" not in contractor_tools
    assert SUBMIT_SOP["name"] in contractor_tools


def test_declarations_reuse_tool_schemas(rt):
    agent, _ = agent_for(rt, "priya")
    decl = {t.name: t._get_declaration() for t in agent.tools}
    assert decl["search_knowledge"].parameters_json_schema["required"] == ["query"]
    assert "steps" in decl[SUBMIT_SOP["name"]].parameters_json_schema["properties"]


def test_tool_budget_blocks_after_limit(rt):
    agent, run = agent_for(rt, "priya")
    search = next(t for t in agent.tools if t.name == "search_knowledge")
    submit = next(t for t in agent.tools if t.name == SUBMIT_SOP["name"])
    run.calls = rt[0].settings.max_tool_calls
    assert "budget" in agent.before_tool_callback(search, {}, None)["error"]
    assert agent.before_tool_callback(submit, {}, None) is None  # the final answer is always allowed
