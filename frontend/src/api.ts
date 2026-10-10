import type { Action, AgentEvent, Persona } from "./types";

let token = "";

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init.headers },
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export const api = {
  health: () => call<{ chunks: number; vector_store: string; llm_model: string; embed_model: string }>("/api/health"),
  personas: () => call<Persona[]>("/api/personas"),
  async login(userId: string) {
    const r = await call<{ token: string }>("/api/auth/demo-login", { method: "POST", body: JSON.stringify({ user_id: userId }) });
    token = r.token;
  },
  decide: (id: string, decision: "approve" | "reject") => call<Action>(`/api/actions/${id}/${decision}`, { method: "POST" }),

  /** POST /api/chat and parse the server-sent event stream. */
  async chat(message: string, history: { role: string; text: string }[], onEvent: (e: AgentEvent) => void) {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ message, history }),
    });
    if (!res.ok || !res.body) throw new Error(`${res.status} ${await res.text()}`);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sep;
      while ((sep = buffer.indexOf("\n\n")) >= 0) {
        const frame = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        if (frame.startsWith("data: ")) onEvent(JSON.parse(frame.slice(6)));
      }
    }
  },
};
