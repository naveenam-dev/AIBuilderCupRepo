import { idToken, signInGoogle, signInPersona } from "./firebase";
import type { Action, AgentEvent, ClientConfig, Health, Persona } from "./types";

// Demo mode sends the backend's JWT; Firebase mode sends a fresh Firebase ID token on every call.
let bearer: () => Promise<string> = async () => "";
// Origin for the streaming chat call. Firebase Hosting rewrites buffer server-sent events, so a page served
// from Hosting streams straight from Cloud Run; everything else stays same-origin.
let streamBase = "";

async function headers(): Promise<Record<string, string>> {
  const t = await bearer();
  return { "Content-Type": "application/json", ...(t ? { Authorization: `Bearer ${t}` } : {}) };
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, { ...init, headers: { ...(await headers()), ...init.headers } });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export const api = {
  async config() {
    const c = await call<ClientConfig>("/api/client-config");
    // Only a page served by Firebase Hosting needs the direct route; any Cloud Run URL already serves the API itself.
    if (c.stream_url && !window.location.hostname.endsWith(".run.app") && new URL(c.stream_url).origin !== window.location.origin) {
      streamBase = c.stream_url.replace(/\/$/, "");
    }
    return c;
  },
  health: () => call<Health>("/api/health"),
  personas: () => call<Persona[]>("/api/personas"),
  async login(userId: string) {
    const r = await call<{ token: string; token_type: string }>("/api/auth/demo-login", {
      method: "POST",
      body: JSON.stringify({ user_id: userId }),
    });
    if (r.token_type === "firebase_custom_token") {
      await signInPersona(r.token);
      bearer = idToken;
    } else {
      bearer = async () => r.token;
    }
  },
  /** Google sign-in through Firebase Auth; returns the server's view of the user (roles come from the server). */
  async loginWithGoogle(): Promise<Persona> {
    await signInGoogle();
    bearer = idToken;
    return call<Persona>("/api/me");
  },
  registerDevice: (token: string) => call<{ registered: boolean }>("/api/devices", { method: "POST", body: JSON.stringify({ token }) }),
  decide: (id: string, decision: "approve" | "reject") => call<Action>(`/api/actions/${id}/${decision}`, { method: "POST" }),

  /** POST /api/chat and parse the server-sent event stream. */
  async chat(message: string, history: { role: string; text: string }[], onEvent: (e: AgentEvent) => void) {
    const res = await fetch(`${streamBase}/api/chat`, { method: "POST", headers: await headers(), body: JSON.stringify({ message, history }) });
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
