# Acme Second Brain: on-call co-pilot

An agentic knowledge fabric for engineering on-call. It turns runbooks, Slack threads, Jira tickets and emails, plus live telemetry and the org graph, into a **verified, step-by-step procedure with approvable actions**. Retrieval and actions are filtered by the user's role.

**Core loop:** question → RBAC-filtered hybrid retrieval → live telemetry and org-graph lookups → agent proposes actions → grounded SOP with citations → human approves → action executes → the person paged sees it live.

**Live:** UI on Firebase Hosting at https://aibuildercupprj.web.app (API on Cloud Run).

## Architecture

```
Firebase Hosting (React UI) ──/api/**──► Cloud Run: FastAPI
        │   └─ /api/chat streams (SSE) directly from Cloud Run (Hosting rewrites buffer streams)
        │
        ├─ Firebase Auth ── persona custom tokens · Google sign-in ── ID token on every API call
        ├─ Firestore (live listeners) ── own approval cards · own inbox of pages
        └─ FCM web push ── pages arrive as notifications

Cloud Run: FastAPI
  ├─ Agent orchestrator ── Gemini (Vertex AI) function calling
  │     └─ Tool registry ── search_knowledge · get_service_status · get_service_info · get_oncall
  │                         check_availability · create_incident_ticket* · send_chat_message*  (*approval)
  ├─ Grounding guard: citations must point at evidence this user retrieved
  ├─ Retrieval: dense (gemini-embedding-001) + BM25/FTS → Reciprocal Rank Fusion, ACL pre-filter
  ├─ AlloyDB (knowledge): pgvector HNSW + GIN FTS + ACL, one SQL query, IAM database auth
  └─ Firestore (operational state): approvals (transactional), audit log, inboxes, device tokens, org graph
```

Two databases, each for what it does best: **AlloyDB** answers "which authorized chunks are most relevant" in one hybrid SQL query; **Firestore** holds small per-user, transactional state that the browser watches live.

| Concern | Where |
|---|---|
| Source connectors (Slack/Confluence/Drive/Jira/Gmail stubs) | `backend/app/connectors/` |
| Hybrid search + RBAC | `backend/app/retrieval/` (`alloydb_store.py` has the single-query hybrid SQL) |
| Agent loop, prompts, grounding | `backend/app/agent/` |
| Tools and adapters (incl. Firebase chat: Firestore inbox + FCM) | `backend/app/tools/` |
| Operational state: memory or Firestore | `backend/app/state/` |
| Auth: demo JWT or Firebase Auth | `backend/app/auth/` |
| Firestore security rules (browser reads only its own data) | `firestore.rules` |
| Seed corpus (fictional Acme Pay) | `backend/seed_data/` |

### Extending integrations
- **New knowledge source:** subclass `SourceConnector`, map the source's permissions to `acl_roles`, and add it to `seed_connectors`.
- **New action system:** implement the matching interface in `tools/adapters/interfaces.py` and select it with an env var (`JIRA_ADAPTER=real`, …).
- **Roles for Google sign-in users:** `python -m scripts.grant_roles someone@example.com engineering sre` (Firebase custom claims).

## Run locally (no Docker)

Prerequisites: Python 3.11+, Node 20+, and gcloud logged in to a project with Vertex AI enabled.

```powershell
gcloud auth application-default login      # recommended; otherwise the app falls back to gcloud CLI tokens

# backend
cd backend
python -m venv .venv; .venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --port 8000

# frontend (second terminal)
cd frontend
npm install; npm run dev                    # http://localhost:5173
```
Alternatively, run `npm run build` once; FastAPI then serves the UI at http://localhost:8000. Firebase features are off by default; see `backend/.env.example` to turn them on.

To run the agent from the CLI: `.venv\Scripts\python -m scripts.ask priya "payments-api is throwing 502s"`

To run the tests (offline: fake embedder, in-memory state): `.venv\Scripts\python -m pytest -q`

## Deploy
```powershell
./infra/setup_alloydb.ps1                                      # AlloyDB (billable, ~20 min); reads ALLOYDB_PASSWORD from backend/.env
cd backend
.venv\Scripts\python -m scripts.init_alloydb second-brain-sa@aibuildercupprj.iam   # schema + ingest + grants
.venv\Scripts\python -m scripts.setup_firebase                 # Firestore rules + org graph seed (once)
cd ..; ./infra/deploy_cloudrun.ps1                             # Cloud Run: AlloyDB + Firestore + Firebase Auth + FCM
cd frontend; npm run build; cd ../backend
.venv\Scripts\python -m scripts.deploy_hosting                 # UI to Firebase Hosting (/api/** → Cloud Run)
```
No passwords live in the cloud: Cloud Run reaches AlloyDB with IAM database auth, and signs Firebase custom tokens as its own service account.

## Demo script (about 5 minutes)
1. **Open two windows** on https://aibuildercupprj.web.app: one as **Sofia** (ledger on-call), one as **Priya** (SRE on-call). Optionally click **Turn on alerts** in Sofia's window.
2. **Priya:** "payments-api is throwing 502s, started about 20 minutes ago. What do I do?"
   - Watch the trace. The agent finds the runbook, checks telemetry (ledger p99 2.9 s, `ledger_async_writes` on), and links it to **PAY-1287** and the Slack thread.
   - It checks the on-call rota (from Firestore) and calendars, then drafts a ticket and pages.
3. **Approve** the page to `#ledger-oncall`: the card says "Paged Sofia Martins, Marcus Okafor", and **Sofia's window shows it instantly** (Firestore listener, plus a push notification if alerts are on). Approve the Jira ticket: it returns `INC-5xx`.
4. **Switch to Alex (engineer)** and ask again. The restricted mTLS postmortem and SEC-77 no longer appear in sources.
5. **Switch to Jordan (contractor)** and ask again. Jordan has no runbooks and no telemetry tool, so severity is "unknown" with honest gaps, and the procedure is to escalate.
6. Optional: change `org/oncall` in the Firebase console; within 30 seconds the agent pages the new on-call engineer.
