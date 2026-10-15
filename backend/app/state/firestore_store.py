"""Firestore-backed operational state. Survives restarts and lets Cloud Run run several instances.

Layout (Native mode):
  actions/{actionId}                    approval queue (the browser watches its own via onSnapshot)
  audit/{autoId}                        append-only audit log
  users/{uid}/inbox/{messageId}         pages and notifications delivered to a person (watched live)
  users/{uid}/devices/{tokenHash}       FCM web-push registration tokens
  org/{people|teams|services|oncall|calendar}   org graph, editable in the Firebase console
"""
import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from google.cloud import firestore

from app.state.base import AuditEntry, InboxMessage, PendingAction, StateStore

_ORG_SECTIONS = ("people", "teams", "services", "oncall", "calendar")


class FirestoreStateStore(StateStore):
    def __init__(self, project: str, database: str, credentials=None):
        self.db = firestore.Client(project=project, database=database, credentials=credentials)
        self._writer = ThreadPoolExecutor(max_workers=2, thread_name_prefix="audit-writer")

    # --- approvals ---
    def put_action(self, action):
        self.db.collection("actions").document(action.id).set(action.model_dump())

    def get_action(self, action_id):
        snap = self.db.collection("actions").document(action_id).get()
        return PendingAction(**snap.to_dict()) if snap.exists else None

    def claim_action(self, action_id, check):
        ref = self.db.collection("actions").document(action_id)

        @firestore.transactional
        def claim(tx: firestore.Transaction) -> PendingAction:
            snap = ref.get(transaction=tx)
            if not snap.exists:
                raise KeyError(action_id)
            action = PendingAction(**snap.to_dict())
            new_status = check(action)
            if new_status:
                action.status = new_status
                action.decided_at = datetime.now(UTC)
                tx.update(ref, {"status": new_status, "decided_at": action.decided_at})
            return action

        return claim(self.db.transaction())

    def save_result(self, action_id, status, result):
        self.db.collection("actions").document(action_id).update({"status": status, "result": result})

    # --- audit ---
    def append_audit(self, entry):
        # Off the request path: the agent loop logs every tool call and should not wait on each write.
        self._writer.submit(self.db.collection("audit").add, entry.model_dump())

    def list_audit(self, user_id=None, limit=100):
        q = self.db.collection("audit")
        if user_id:
            q = q.where(filter=firestore.FieldFilter("user_id", "==", user_id))
        docs = q.order_by("at", direction=firestore.Query.DESCENDING).limit(limit).stream()
        return list(reversed([AuditEntry(**d.to_dict()) for d in docs]))

    # --- inboxes and push tokens ---
    def deliver(self, user_id, message):
        self.db.collection("users").document(user_id).collection("inbox").document(message.id).set(message.model_dump())

    def _device(self, user_id, token):
        key = hashlib.sha256(token.encode()).hexdigest()[:32]
        return self.db.collection("users").document(user_id).collection("devices").document(key)

    def add_device_token(self, user_id, token):
        self._device(user_id, token).set({"token": token, "updated_at": firestore.SERVER_TIMESTAMP})

    def device_tokens(self, user_id):
        devices = self.db.collection("users").document(user_id).collection("devices").stream()
        return [d.to_dict()["token"] for d in devices]

    def remove_device_token(self, user_id, token):
        self._device(user_id, token).delete()

    # --- org graph ---
    def load_org(self):
        docs = {d.id: d.to_dict() for d in self.db.collection("org").stream()}
        if not all(s in docs for s in _ORG_SECTIONS):
            return None
        return {s: docs[s] for s in _ORG_SECTIONS}

    def seed_org(self, org: dict) -> None:
        batch = self.db.batch()
        for section in _ORG_SECTIONS:
            batch.set(self.db.collection("org").document(section), org[section])
        batch.commit()
