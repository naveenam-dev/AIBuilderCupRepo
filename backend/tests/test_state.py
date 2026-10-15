"""Offline tests for the approval flow on the state store and FCM chat addressing."""
import pytest

from app.config import Settings
from app.container import build_container
from app.state.memory import MemoryStateStore
from app.tools.adapters.firebase_chat import FirebaseChat


@pytest.fixture(scope="module")
def c():
    return build_container(Settings(_env_file=None, embedder="fake", vector_store="memory", state_store="memory"), use_llm=False)


def test_decide_is_idempotent_and_audited(c):
    alex = c.auth.personas["alex"]
    action = c.actions.propose(alex, "send_chat_message", {"target": "#sre", "text": "hi"})
    first = c.actions.decide(action.id, alex, approve=True)
    second = c.actions.decide(action.id, alex, approve=False)  # already decided: no second execution
    assert first.status == second.status == "executed"
    outcomes = [e.outcome for e in c.state.list_audit("alex") if e.args.get("text") == "hi"]
    assert outcomes == [f"proposed:{action.id}", "executed"]


def test_reject_does_not_execute(c):
    alex = c.auth.personas["alex"]
    action = c.actions.propose(alex, "send_chat_message", {"target": "#sre", "text": "nope"})
    assert c.actions.decide(action.id, alex, approve=False).result is None


def test_chat_addressing_resolves_oncall(c):
    chat = FirebaseChat(MemoryStateStore(), c.org, app=None)
    assert chat.recipients("#ledger-oncall") == ["sofia", "marcus"]
    assert chat.recipients("@priya") == ["priya"]
    assert chat.recipients("@nobody") == []


def test_firebase_chat_delivers_to_inbox_without_devices(c):
    state = MemoryStateStore()
    result = FirebaseChat(state, c.org, app=None).send_message("#ledger-oncall", "disable the flag", "Priya Sharma")
    assert result["delivered"] and result["push_notifications"] == 0
    assert state.inboxes["sofia"][0].text == "disable the flag"
