"""Offline tests (fake embedder, in-memory store): ingestion, hybrid ranking and RBAC isolation."""
import pytest

from app.config import Settings
from app.container import build_container
from app.models import Principal

RESTRICTED = {"conf-postmortem-2026-03-mtls", "jira-SEC-77", "slack-sre-gateway-timeouts", "email-hr-comp-review"}


@pytest.fixture(scope="module")
def c():
    container = build_container(Settings(_env_file=None, embedder="fake", vector_store="memory"), use_llm=False)
    container.ingest()
    return container


def who(c, uid) -> Principal:
    return c.auth.personas[uid]


def doc_ids(hits):
    return {h.chunk.doc_id for h in hits}


def test_ingest_covers_all_sources(c):
    stats = c.ingest()
    assert stats["documents"] == 16
    assert set(stats["by_source"]) == {"confluence", "slack", "jira", "email"}


def test_keyword_retrieval_finds_exact_ticket_id(c):
    hits = c.retrieval.search("PAY-1287", who(c, "alex"))
    ticket = next(h for h in hits if h.chunk.doc_id == "jira-PAY-1287")
    assert ticket.keyword_rank == 1  # title boost beats docs that merely mention the id
    assert ticket in hits[:3]  # fused position also depends on the (fake) dense ranker


def test_sre_sees_restricted_postmortem(c):
    hits = c.retrieval.search("payments-api 502 mTLS certificate expired", who(c, "priya"), k=10)
    assert "conf-postmortem-2026-03-mtls" in doc_ids(hits)


@pytest.mark.parametrize(
    "query",
    ["payments-api 502 mTLS certificate expired", "certctl status", "compensation review", "502 vs 504 gateway"],
)
def test_engineer_never_sees_restricted_docs(c, query):
    hits = c.retrieval.search(query, who(c, "alex"), k=20)
    assert not doc_ids(hits) & RESTRICTED


def test_contractor_only_sees_public_docs(c):
    hits = c.retrieval.search("payments-api 502 errors rollback runbook", who(c, "jordan"), k=20)
    assert hits, "contractor should still get public guidance"
    assert all("all" in h.chunk.acl_roles for h in hits)


def test_tools_are_rbac_filtered(c):
    contractor_tools = {t.name for t in c.registry.for_principal(who(c, "jordan"))}
    assert "create_incident_ticket" not in contractor_tools
    assert "get_service_status" not in contractor_tools
    assert "send_chat_message" in contractor_tools


def test_actions_require_requesting_user(c):
    action = c.actions.propose(who(c, "alex"), "send_chat_message", {"target": "#sre", "text": "hi"})
    with pytest.raises(PermissionError):
        c.actions.decide(action.id, who(c, "priya"), approve=True)
    done = c.actions.decide(action.id, who(c, "alex"), approve=True)
    assert done.status == "executed" and done.result["delivered"]
