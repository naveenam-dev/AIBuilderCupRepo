"""Chat adapter backed by Firebase: each message lands in the recipients' Firestore inbox (shown live in
the UI) and is pushed to their registered browsers with Firebase Cloud Messaging.

Addressing: "@sofia" reaches that person; "#ledger-oncall" reaches the owning team's primary and
secondary on-call; any other channel reaches the sender only as a delivery receipt."""
import logging

from firebase_admin import exceptions, messaging

from app.state.base import InboxMessage, StateStore
from app.tools.adapters.interfaces import ChatAdapter
from app.tools.org_graph import OrgGraph

log = logging.getLogger(__name__)


class FirebaseChat(ChatAdapter):
    def __init__(self, state: StateStore, org: OrgGraph, app):
        self.state, self.org, self.app = state, org, app

    def recipients(self, target: str) -> list[str]:
        if target.startswith("@"):
            pid = target[1:]
            return [pid] if pid in self.org.people else []
        team = self.org.team_for_channel(target)
        if team and team in self.org.oncall:
            rota = self.org.oncall[team]
            return list(dict.fromkeys([rota["primary"], rota["secondary"]]))
        return []

    def send_message(self, target, text, sender):
        people = self.recipients(target)
        msg = InboxMessage(target=target, text=text, sender=sender)
        pushed = failed = 0
        for pid in people:
            self.state.deliver(pid, msg)
            for token in self.state.device_tokens(pid):
                try:
                    messaging.send(
                        messaging.Message(
                            token=token,
                            notification=messaging.Notification(title=f"{target} · from {sender}", body=text[:240]),
                            data={"target": target, "message_id": msg.id},
                            webpush=messaging.WebpushConfig(fcm_options=messaging.WebpushFCMOptions(link="/")),
                        ),
                        app=self.app,
                    )
                    pushed += 1
                except (messaging.UnregisteredError, messaging.SenderIdMismatchError, exceptions.InvalidArgumentError):
                    self.state.remove_device_token(pid, token)  # stale or malformed browser registration
                    failed += 1
                except Exception:
                    log.exception("FCM send failed")
                    failed += 1
        return {
            "target": target,
            "text": text,
            "sender": sender,
            "delivered": bool(people),
            "recipients": [self.org.person(p).get("name", p) for p in people],
            "push_notifications": pushed,
            "push_failures": failed,
        }
