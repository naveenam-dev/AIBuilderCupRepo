import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { InboxPanel, PersonaSwitcher, SourcesPanel, Toasts, TurnView } from "./components";
import { enablePush, firebaseEnabled, initFirebase, watchActions, watchInbox } from "./firebase";
import type { Action, AgentEvent, ClientConfig, Health, InboxMessage, Persona, Turn } from "./types";

type PushState = "off" | "on" | "blocked" | "unsupported";

const SUGGESTIONS = [
  "payments-api is throwing 502s, started about 20 minutes ago. What do I do?",
  "What's the workaround for PAY-1287 and who needs to know?",
  "Who owns ledger-service and who can I reach right now?",
];

export default function App() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [persona, setPersona] = useState<Persona>();
  const [health, setHealth] = useState<Health>();
  const [cfg, setCfg] = useState<ClientConfig>();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [actions, setActions] = useState<Record<string, Action>>({});
  const [inbox, setInbox] = useState<InboxMessage[]>([]);
  const [toasts, setToasts] = useState<InboxMessage[]>([]);
  const [push, setPush] = useState<PushState>("off");
  const [input, setInput] = useState("");
  const [highlight, setHighlight] = useState<string>();
  const [bootError, setBootError] = useState<string>();
  const endRef = useRef<HTMLDivElement>(null);
  const busy = turns.some((t) => t.running);
  const live = cfg?.state_store === "firestore" && !!cfg.firebase;

  useEffect(() => {
    Promise.all([api.config(), api.personas(), api.health()])
      .then(async ([c, ps, h]) => {
        if (c.firebase) initFirebase(c.firebase);
        setCfg(c);
        setPersonas(ps);
        setHealth(h);
        await api.login(ps[0].user_id);
        setPersona(ps[0]);
      })
      .catch((e) => setBootError(String(e)));
  }, []);

  // Live Firestore listeners for the signed-in user: approval card status and their inbox of pages.
  useEffect(() => {
    if (!persona || !live || !firebaseEnabled()) return;
    setInbox([]);
    const report = (what: string) => (e: Error) => console.warn(`Live ${what} unavailable:`, e.message);
    const stopActions = watchActions(
      persona.user_id,
      (a) => setActions((all) => (all[a.id] ? { ...all, [a.id]: { ...all[a.id], ...a } } : all)),
      report("approval status"),
    );
    const stopInbox = watchInbox(
      persona.user_id,
      (all, fresh) => {
        setInbox(all);
        if (fresh.length) setToasts((t) => [...fresh, ...t].slice(0, 3));
      },
      report("inbox"),
    );
    return () => {
      stopActions();
      stopInbox();
    };
  }, [persona?.user_id, live]);

  useEffect(() => {
    if (!toasts.length) return;
    const timer = setTimeout(() => setToasts((t) => t.slice(0, -1)), 8000);
    return () => clearTimeout(timer);
  }, [toasts]);

  async function turnOnAlerts() {
    try {
      const token = await enablePush();
      if (!token) {
        setPush(typeof Notification !== "undefined" && Notification.permission === "denied" ? "blocked" : "unsupported");
        return;
      }
      await api.registerDevice(token);
      setPush("on");
    } catch {
      setPush("unsupported");
    }
  }

  async function signInWithGoogle() {
    try {
      setPersona(await api.loginWithGoogle());
      setPush("off");
    } catch (err) {
      alert(`Google sign-in failed: ${err}`);
    }
  }

  // Block body on purpose: scrollIntoView returns a Promise in newer browsers, and an effect's return
  // value is treated as its cleanup function.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length]);

  async function switchPersona(p: Persona) {
    await api.login(p.user_id);
    setPersona(p);
    setPush("off"); // the device token is registered per signed-in user
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
          <div className="health" title={`Embeddings: ${health.embed_model} · sign-in: ${health.auth} · chat: ${health.chat}`}>
            <span className="dot ok" /> {health.llm_model} · {health.vector_store} · {health.state_store} · {health.chunks} chunks
          </div>
        )}
      </header>

      <div className="persona-bar">
        <span className="label">Signed in as</span>
        <PersonaSwitcher personas={personas} active={persona} onSelect={switchPersona} disabled={busy} />
        {cfg?.auth === "firebase" && (
          persona && !personas.some((p) => p.user_id === persona.user_id) ? (
            <span className="signed-in" title={`Roles: ${persona.roles.join(", ") || "none (public documents only)"}`}>
              Google: {persona.name}
            </span>
          ) : (
            <button className="btn ghost" onClick={signInWithGoogle} disabled={busy}>Sign in with Google</button>
          )
        )}
        {cfg?.push && persona && (
          <button className="btn ghost" onClick={turnOnAlerts} disabled={push === "on"}>
            {push === "on" ? "🔔 Alerts on" : push === "blocked" ? "Alerts blocked in browser" : push === "unsupported" ? "Alerts unavailable" : "Turn on alerts"}
          </button>
        )}
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
          {live && (
            <>
              <h3>Inbox {inbox.length > 0 && <span className="count">{inbox.length}</span>}</h3>
              <InboxPanel messages={inbox} />
            </>
          )}
          <h3 className={live ? "spaced" : ""}>Sources</h3>
          <SourcesPanel sources={latestSources} highlight={highlight} />
        </aside>
      </main>
      <Toasts items={toasts} onDismiss={(id) => setToasts((t) => t.filter((m) => m.id !== id))} />

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
