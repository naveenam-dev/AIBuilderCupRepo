# Acme Second Brain: on-call co-pilot

An agentic knowledge fabric for engineering on-call. It turns runbooks, Slack threads, Jira tickets and emails, plus live telemetry and the org graph, into a **verified, step-by-step procedure with approvable actions**. Retrieval and actions are filtered by the user's role.

**Core loop:** question → RBAC-filtered hybrid retrieval → live telemetry and org-graph lookups → agent proposes actions → grounded SOP with citations → human approves → action executes.

## Architecture

```
React (Vite)  ──SSE──►  FastAPI (Cloud Run)
                          ├─ Agent orchestrator ── Gemini (Vertex AI) function calling
                          │     └─ Tool registry ── adapters: mock now, real later
                          │          search_knowledge · get_service_status · get_service_info
                          │          get_oncall · check_availability
                          │          create_incident_ticket* · send_chat_message*   (*approval required)
                          ├─ Grounding guard: citations must point at evidence this user retrieved
                          ├─ Retrieval: dense (gemini-embedding-001) + BM25/FTS → Reciprocal Rank Fusion,
                          │             ACL pre-filter before ranking
                          ├─ Ingestion: SourceConnector → heading-aware chunking → embeddings → VectorStore
                          └─ VectorStore: InMemoryStore (dev) | AlloyDBStore (pgvector HNSW + GIN FTS, one SQL query)
```

| Concern | Where |
|---|---|
| Source connectors (Slack/Confluence/Drive/Jira/Gmail stubs) | `backend/app/connectors/` |
| Hybrid search + RBAC | `backend/app/retrieval/` (`alloydb_store.py` has the single-query hybrid SQL) |
| Agent loop, prompts, grounding | `backend/app/agent/` |
| Tools, adapters, approval queue and audit log | `backend/app/tools/` |
| Auth (demo personas; Google Identity stub) | `backend/app/auth/` |
| Seed corpus (fictional Acme Pay) | `backend/seed_data/` |

### Extending integrations
- **New knowledge source:** subclass `SourceConnector`, map the source's permissions to `acl_roles`, and add it to `seed_connectors`.
- **New action system:** implement the matching interface in `tools/adapters/interfaces.py` and select it with an env var (`JIRA_ADAPTER=real`, …).
- **Real SSO:** implement `GoogleIdentityAuthProvider` (IAP or Firebase token → Workspace groups → roles).

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
Alternatively, run `npm run build` once; FastAPI then serves the UI at http://localhost:8000.

To run the agent from the CLI: `.venv\Scripts\python -m scripts.ask priya "payments-api is throwing 502s"`

To run the tests (offline, fake embedder): `.venv\Scripts\python -m pytest -q`

## Deploy
```powershell
./infra/setup_alloydb.ps1                                     # AlloyDB (billable, ~20 min); reads ALLOYDB_PASSWORD from backend/.env
cd backend; .venv\Scripts\python -m scripts.init_alloydb second-brain-sa@aibuildercupprj.iam   # schema + ingest + grants
cd ..; ./infra/deploy_cloudrun.ps1                            # Cloud Run, passwordless IAM DB auth
```
The `postgres` password is used only locally to bootstrap the database. Cloud Run logs in as its service account through AlloyDB IAM database authentication, so the cloud holds no password.

## Demo script (about 4 minutes)
1. **Priya (SRE on-call):** "payments-api is throwing 502s, started about 20 minutes ago. What do I do?"
   - Watch the trace. The agent finds the runbook, checks telemetry (ledger p99 2.9 s, `ledger_async_writes` on), and links it to **PAY-1287** and the Slack thread.
   - It checks the on-call rota and calendars (Sofia is in a meeting), then drafts a ticket and pages.
   - Point out the citation chips, the "5/5 steps grounded" line, and the live-data chips.
2. **Approve** the Jira ticket. It returns `INC-512`. Approve the page to `#ledger-oncall`.
3. **Switch to Alex (engineer)** and ask the same question. The restricted mTLS postmortem and SEC-77 no longer appear in sources.
4. **Switch to Jordan (contractor)** and ask the same question. Jordan has no runbooks and no telemetry tool, so severity is "unknown" with honest gaps, and the procedure is to escalate: a page to `#sre` for approval.
5. Optional: `GET /api/search?q=...` shows the vector rank, keyword rank and fused score per persona.
