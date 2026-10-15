"""In-process state for local development and tests. Lost on restart; single instance only."""
import threading
from datetime import UTC, datetime

from app.state.base import AuditEntry, InboxMessage, PendingAction, StateStore


class MemoryStateStore(StateStore):
    def __init__(self):
        self._actions: dict[str, PendingAction] = {}
        self._audit: list[AuditEntry] = []
        self.inboxes: dict[str, list[InboxMessage]] = {}
        self._tokens: dict[str, set[str]] = {}
        self._lock = threading.Lock()

    def put_action(self, action):
        with self._lock:
            self._actions[action.id] = action

    def get_action(self, action_id):
        return self._actions.get(action_id)

    def claim_action(self, action_id, check):
        with self._lock:
            action = self._actions.get(action_id)
            if action is None:
                raise KeyError(action_id)
            new_status = check(action)
            if new_status:
                action.status = new_status
                action.decided_at = datetime.now(UTC)
            return action.model_copy()

    def save_result(self, action_id, status, result):
        with self._lock:
            action = self._actions[action_id]
            action.status, action.result = status, result

    def append_audit(self, entry):
        with self._lock:
            self._audit.append(entry)

    def list_audit(self, user_id=None, limit=100):
        entries = [e for e in self._audit if user_id is None or e.user_id == user_id]
        return entries[-limit:]

    def deliver(self, user_id, message):
        with self._lock:
            self.inboxes.setdefault(user_id, []).append(message)

    def add_device_token(self, user_id, token):
        with self._lock:
            self._tokens.setdefault(user_id, set()).add(token)

    def device_tokens(self, user_id):
        return sorted(self._tokens.get(user_id, ()))

    def remove_device_token(self, user_id, token):
        with self._lock:
            self._tokens.get(user_id, set()).discard(token)

    def load_org(self):
        return None
