import { Fragment, useState } from "react";
import type { Action, Persona, Sop, Source, TraceItem, Turn } from "./types";

const TOOL_LABELS: Record<string, string> = {
  search_knowledge: "Searched knowledge",
  get_service_status: "Checked live telemetry",
  get_service_info: "Looked up org graph",
  get_oncall: "Checked on-call rota",
  check_availability: "Checked calendars",
  create_incident_ticket: "Drafted Jira ticket",
  send_chat_message: "Drafted chat message",
};

const SOURCE_LABELS: Record<string, string> = { confluence: "Confluence", slack: "Slack", jira: "Jira", email: "Email", gdrive: "Drive" };

/** Renders `inline code` spans; everything else is plain text. */
export function Rich({ text }: { text: string }) {
  return (
    <>
      {text.split(/(`[^`]+`)/g).map((part, i) =>
        part.startsWith("`") && part.endsWith("`") ? <code key={i}>{part.slice(1, -1)}</code> : <Fragment key={i}>{part}</Fragment>,
      )}
    </>
  );
}

function initials(name: string) {
  return name.split(" ").map((p) => p[0]).join("").slice(0, 2);
}

export function PersonaSwitcher({ personas, active, onSelect, disabled }: {
  personas: Persona[]; active?: Persona; onSelect: (p: Persona) => void; disabled: boolean;
}) {
  return (
    <div className="personas" role="radiogroup" aria-label="Signed-in persona">
      {personas.map((p) => (
        <button
          key={p.user_id}
          role="radio"
          aria-checked={active?.user_id === p.user_id}
          className={`persona ${active?.user_id === p.user_id ? "active" : ""}`}
          onClick={() => onSelect(p)}
          disabled={disabled}
          title={`Roles: ${p.roles.join(", ")}`}
        >
          <span className={`avatar av-${p.user_id}`}>{initials(p.name)}</span>
          <span className="persona-text">
            <strong>{p.name}</strong>
            <small>{p.title}</small>
          </span>
        </button>
      ))}
    </div>
  );
}

export function Trace({ items, running }: { items: TraceItem[]; running: boolean }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="trace">
      <button className="trace-head" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className={`dot ${running ? "pulse" : ""}`} />
        {running ? "Agent working" : "Agent trace"} · {items.length} tool call{items.length === 1 ? "" : "s"}
        <span className="chev">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <ol className="trace-list">
          {items.map((t) => (
            <li key={t.id} className={t.ok === false ? "bad" : t.preview ? "ok" : "pending"}>
              <span className="trace-name">{TOOL_LABELS[t.name] ?? t.name}</span>
              <span className="trace-args">{Object.values(t.args).filter((v) => typeof v === "string" && v.length < 80).join(" · ") ||
                (Array.isArray(t.args.person_ids) ? (t.args.person_ids as string[]).join(", ") : "")}</span>
              {t.preview && <div className="trace-preview">{t.preview}</div>}
            </li>
          ))}
          {running && <li className="pending"><span className="trace-name">Thinking…</span></li>}
        </ol>
      )}
    </div>
  );
}

export function ActionCard({ action, onDecide }: { action: Action; onDecide: (id: string, d: "approve" | "reject") => void }) {
  const r = action.result ?? {};
  return (
    <div className={`action ${action.status}`}>
      <div className="action-body">
        <span className="action-kind">{action.tool === "create_incident_ticket" ? "Jira" : "Chat"}</span>
        <span className="action-summary">{action.summary}</span>
      </div>
      {action.status === "pending" ? (
        <div className="action-buttons">
          <button className="btn primary" onClick={() => onDecide(action.id, "approve")}>Approve</button>
          <button className="btn" onClick={() => onDecide(action.id, "reject")}>Reject</button>
        </div>
      ) : (
        <div className="action-result">
          {action.status === "executed" && typeof r.key === "string" && <>✓ Created <a href={String(r.url)} target="_blank" rel="noreferrer">{r.key}</a></>}
          {action.status === "executed" && r.delivered === true && <>✓ Sent to {String(r.target)}</>}
          {action.status === "rejected" && "Rejected"}
          {action.status === "failed" && `Failed: ${String(r.error ?? "unknown error")}`}
        </div>
      )}
    </div>
  );
}

export function SopCard({ sop, actions, onDecide, onCite }: {
  sop: Sop; actions: Record<string, Action>; onDecide: (id: string, d: "approve" | "reject") => void; onCite: (chunkId: string) => void;
}) {
  const index = new Map(sop.sources.map((s, i) => [s.chunk_id, i + 1]));
  const linked = new Set(sop.steps.flatMap((s) => s.action_ids));
  const v = sop.verification;
  return (
    <div className="sop">
      <div className="sop-meta">
        <span className={`badge sev ${sop.severity.toLowerCase()}`}>{sop.severity}</span>
        <span className={`badge conf ${sop.confidence}`}>{sop.confidence} confidence</span>
        <span className="verify" title={v.dropped_citations.length ? `Dropped unverifiable citations: ${v.dropped_citations.join(", ")}` : "All citations verified"}>
          ✓ {v.steps_grounded}/{v.steps_total} steps grounded · {v.documents_retrieved} docs · {sop.elapsed_s}s
        </span>
      </div>
      <p className="sop-summary"><Rich text={sop.summary} /></p>
      <ol className="steps">
        {sop.steps.map((s, i) => (
          <li key={i} className={s.grounded ? "" : "ungrounded"}>
            <div className="step-head">
              <span className="step-title">{s.title}</span>
              {s.owner && <span className="owner">{s.owner}</span>}
            </div>
            <div className="step-detail"><Rich text={s.detail} /></div>
            <div className="cites">
              {!s.grounded && <span className="warn">⚠ unverified: no supporting source</span>}
              {s.citations.map((c) =>
                c.startsWith("tool:") ? (
                  <span key={c} className="cite live" title="Live data from a tool call">live · {c.slice(5).replaceAll("_", " ")}</span>
                ) : (
                  <button key={c} className="cite" onClick={() => onCite(c)} title={c}>[{index.get(c)}]</button>
                ),
              )}
            </div>
            {s.action_ids.map((id) => actions[id] && <ActionCard key={id} action={actions[id]} onDecide={onDecide} />)}
          </li>
        ))}
      </ol>
      {Object.values(actions).some((a) => !linked.has(a.id)) && (
        <div className="extra-actions">
          <h4>Other proposed actions</h4>
          {Object.values(actions).filter((a) => !linked.has(a.id)).map((a) => <ActionCard key={a.id} action={a} onDecide={onDecide} />)}
        </div>
      )}
      {sop.gaps.length > 0 && (
        <div className="gaps">
          <h4>Gaps &amp; caveats</h4>
          <ul>{sop.gaps.map((g, i) => <li key={i}><Rich text={g} /></li>)}</ul>
        </div>
      )}
    </div>
  );
}

export function TurnView({ turn, actions, onDecide, onCite }: {
  turn: Turn; actions: Record<string, Action>; onDecide: (id: string, d: "approve" | "reject") => void; onCite: (c: string) => void;
}) {
  const own = Object.fromEntries(turn.actionIds.filter((id) => actions[id]).map((id) => [id, actions[id]]));
  return (
    <section className="turn">
      <div className="question">
        <span className={`avatar sm av-${turn.persona.user_id}`}>{initials(turn.persona.name)}</span>
        <div>
          <div className="q-who">{turn.persona.name} <small>{turn.persona.roles.join(" · ")}</small></div>
          <div className="q-text">{turn.question}</div>
        </div>
      </div>
      <Trace items={turn.trace} running={turn.running} />
      {turn.sop && <SopCard sop={turn.sop} actions={own} onDecide={onDecide} onCite={onCite} />}
      {turn.error && <div className="error">⚠ {turn.error}</div>}
    </section>
  );
}

export function SourcesPanel({ sources, highlight }: { sources: Source[]; highlight?: string }) {
  if (!sources.length) {
    return <p className="muted">Sources cited by the agent appear here. Only documents your role can access are ever retrieved.</p>;
  }
  return (
    <ol className="sources">
      {sources.map((s, i) => (
        <li key={s.chunk_id} id={`src-${s.chunk_id}`} className={highlight === s.chunk_id ? "hl" : ""}>
          <div className="src-head">
            <span className="src-n">{i + 1}</span>
            <span className={`src-tag ${s.source}`}>{SOURCE_LABELS[s.source] ?? s.source}</span>
          </div>
          <a className="src-title" href={s.url} target="_blank" rel="noreferrer">{s.title}</a>
          <p className="src-excerpt">{s.excerpt.split("\n").slice(2).join(" ").slice(0, 260)}…</p>
        </li>
      ))}
    </ol>
  );
}
