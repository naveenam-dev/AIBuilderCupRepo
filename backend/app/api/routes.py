import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.container import Container
from app.models import Principal

router = APIRouter(prefix="/api")
_bearer = HTTPBearer(auto_error=False)


def container(request: Request) -> Container:
    return request.app.state.container


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), c: Container = Depends(container)
) -> Principal:
    if creds is None:
        raise HTTPException(401, "Missing bearer token")
    try:
        return c.auth.authenticate(creds.credentials)
    except Exception:
        raise HTTPException(401, "Invalid or expired token")


class LoginRequest(BaseModel):
    user_id: str


class ChatMessage(BaseModel):
    role: str
    text: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = []


@router.get("/health")
def health(c: Container = Depends(container)):
    s = c.settings
    return {"status": "ok", "chunks": c.store.count(), "vector_store": s.vector_store, "llm_model": s.llm_model,
            "embed_model": s.embed_model if s.embedder == "vertex" else "fake"}


@router.get("/personas")
def personas(c: Container = Depends(container)):
    return [p.model_dump() for p in c.auth.personas.values()]


@router.post("/auth/demo-login")
def demo_login(body: LoginRequest, c: Container = Depends(container)):
    try:
        return {"token": c.auth.issue(body.user_id), "user": c.auth.personas[body.user_id].model_dump()}
    except KeyError:
        raise HTTPException(404, "Unknown persona")


@router.get("/search")
def search(q: str, user: Principal = Depends(current_user), c: Container = Depends(container)):
    """Raw hybrid retrieval, useful for demonstrating RBAC filtering and rank fusion."""
    return [
        {"chunk_id": h.chunk.id, "title": h.chunk.title, "source": h.chunk.source, "score": round(h.score, 5),
         "vector_rank": h.vector_rank, "keyword_rank": h.keyword_rank, "acl_roles": h.chunk.acl_roles}
        for h in c.retrieval.search(q, user)
    ]


@router.post("/chat")
def chat(body: ChatRequest, user: Principal = Depends(current_user), c: Container = Depends(container)):
    if c.orchestrator is None:
        raise HTTPException(503, "LLM is not configured")

    def stream() -> Iterator[str]:
        for event in c.orchestrator.run(body.message, user, [m.model_dump() for m in body.history]):
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.post("/actions/{action_id}/{decision}")
def decide(action_id: str, decision: str, user: Principal = Depends(current_user), c: Container = Depends(container)):
    if decision not in ("approve", "reject"):
        raise HTTPException(400, "decision must be approve or reject")
    try:
        return c.actions.decide(action_id, user, approve=decision == "approve").model_dump(mode="json")
    except KeyError:
        raise HTTPException(404, "Unknown action")
    except PermissionError as e:
        raise HTTPException(403, str(e))


@router.get("/audit")
def audit(user: Principal = Depends(current_user), c: Container = Depends(container)):
    entries = c.actions.audit if "sre" in user.roles else [e for e in c.actions.audit if e.user_id == user.user_id]
    return [e.model_dump(mode="json") for e in entries[-100:]]


@router.post("/ingest")
def reingest(user: Principal = Depends(current_user), c: Container = Depends(container)):
    if "sre" not in user.roles:
        raise HTTPException(403, "Only platform admins (sre) can trigger ingestion")
    return c.ingest()
