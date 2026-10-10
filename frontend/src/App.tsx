import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { PersonaSwitcher, SourcesPanel, TurnView } from "./components";
import type { Action, AgentEvent, Persona, Turn } from "./types";

const SUGGESTIONS = [
  "payments-api is throwing 502s, started about 20 minutes ago. What do I do?",
  "What's the workaround for PAY-1287 and who needs to know?",
  "Who owns ledger-service and who can I reach right now?",
];

export default function App() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [persona, setPersona] = useState<Persona>();
  const [health, setHealth] = useState<Awaited<ReturnType<typeof api.health>>>();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [actions, setActions] = useState<Record<string, Action>>({});
  const [input, setInput] = useState("");
  const [highlight, setHighlight] = useState<string>();
  const [bootError, setBootError] = useState<string>();
  const endRef = useRef<HTMLDivElement>(null);
  const busy = turns.some((t) => t.running);

  useEffect(() => {
    Promise.all([api.personas(), api.health()])
      .then(async ([ps, h]) => {
        setPersonas(ps);
        setHealth(h);
        await api.login(ps[0].user_id);
        setPersona(ps[0]);
      })
      .catch((e) => setBootError(String(e)));
  }, []);

  // Block body on purpose: scrollIntoView returns a Promise in newer browsers, and an effect's return
  // value is treated as its cleanup function.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length]);

  async function switchPersona(p: Persona) {
    await api.login(p.user_id);
    setPersona(p);
  }

  function patchLast(fn: (t: Turn) => Turn) {
    setTurns((ts) => [...ts.slice(0, -1), fn(ts[ts.length - 1])]);
  }

  function onEvent(e: AgentEvent) {
    switch (e.type) {
      case "tool_call":
        return patchLast((t) => ({ ...t, trace: [...t.trace, { id: e.id, name: e.name, args: e.args }] }));
      case "tool_result":
        return patchLast((t) => ({ ...t, trace: t.trace.map((x) => (x.id === e.id ? { ...x, preview: e.preview, ok: e.ok } : x)) }));
      case "action_proposed":
        setActions((a) => ({ ...a, [e.action.id]: e.action }));
        return patchLast((t) => ({ ...t, actionIds: [...t.actionIds, e.action.id] }));
      case "sop":
        return patchLast((t) => ({ ...t, sop: e.sop }));
      case "error":
        return patchLast((t) => ({ ...t, error: e.message }));
    }
  }

  async function ask(question: string) {
    if (!persona || !question.trim() || busy) return;
    const history = turns.filter((t) => t.persona.user_id === persona.user_id && t.sop).slice(-2)
      .flatMap((t) => [{ role: "user", text: t.question }, { role: "model", text: t.sop!.summary }]);
    setInput("");
    setTurns((ts) => [...ts, { question, persona, trace: [], actionIds: [], running: true }]);
    try {
      await api.chat(question, history, onEvent);
    } catch (err) {
      patchLast((t) => ({ ...t, error: String(err) }));
    } finally {
      patchLast((t) => ({ ...t, running: false }));
    }
  }

  async function decide(id: string, decision: "approve" | "reject") {
    try {
      const updated = await api.decide(id, decision);
      setActions((a) => ({ ...a, [id]: updated }));
    } catch (err) {
      alert(`Could not ${decision}: ${err}`);
    }
  }

  function cite(chunkId: string) {
    setHighlight(chunkId);
    document.getElementById(`src-${chunkId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  const latestSources = [...turns].reverse().find((t) => t.sop)?.sop?.sources ?? [];

  return (
    <div className="app">
      <header>
        <div className="brand">
          <div className="logo">◆</div>
          <div>
            <h1>Acme Second Brain</h1>
            <p>On-call co-pilot · knowledge → procedure → action</p>
          </div>
        </div>
        {health && (
          <div className="health" title={`Embeddings: ${health.embed_model}`}>
            <span className="dot ok" /> {health.llm_model} · {health.vector_store} · {health.chunks} chunks
          </div>
        )}
      </header>

      <div className="persona-bar">
        <span className="label">Signed in as</span>
        <PersonaSwitcher personas={personas} active={persona} onSelect={switchPersona} disabled={busy} />
      </div>

      <main>
        <div className="chat">
          {bootError && <div className="error">Backend unreachable: {bootError}</div>}
          {turns.length === 0 && !bootError && (
            <div className="empty">
              <h2>What's going on?</h2>
              <p>Describe the incident. The agent searches runbooks, Slack, Jira and email you're allowed to see,
                checks live telemetry and the org graph, then builds a step-by-step procedure with approvable actions.</p>
            </div>
          )}
          {turns.map((t, i) => <TurnView key={i} turn={t} actions={actions} onDecide={decide} onCite={cite} />)}
          <div ref={endRef} />
        </div>

        <aside>
          <h3>Sources</h3>
          <SourcesPanel sources={latestSources} highlight={highlight} />
        </aside>
      </main>

      <footer>
        <div className="suggestions">
          {SUGGESTIONS.map((s) => <button key={s} className="chip" disabled={busy || !persona} onClick={() => ask(s)}>{s}</button>)}
        </div>
        <form onSubmit={(e) => { e.preventDefault(); ask(input); }}>
          <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Describe the incident or ask a question…" disabled={!persona} />
          <button className="btn primary" disabled={busy || !input.trim()}>{busy ? "Working…" : "Ask"}</button>
        </form>
      </footer>
    </div>
  );
}
