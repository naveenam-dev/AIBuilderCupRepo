export interface Persona {
  user_id: string;
  name: string;
  title: string;
  team: string;
  roles: string[];
}

export interface Action {
  id: string;
  tool: string;
  args: Record<string, unknown>;
  summary: string;
  status: "pending" | "executed" | "rejected" | "failed";
  result: Record<string, unknown> | null;
}

export interface SopStep {
  title: string;
  detail: string;
  owner?: string;
  citations: string[];
  action_ids: string[];
  grounded: boolean;
}

export interface Source {
  chunk_id: string;
  doc_id: string;
  title: string;
  source: string;
  url: string;
  excerpt: string;
}

export interface Sop {
  summary: string;
  severity: string;
  confidence: "high" | "medium" | "low";
  steps: SopStep[];
  gaps: string[];
  sources: Source[];
  elapsed_s: number;
  verification: { steps_total: number; steps_grounded: number; dropped_citations: string[]; documents_retrieved: number };
}

export interface TraceItem {
  id: string;
  name: string;
  args: Record<string, unknown>;
  preview?: string;
  ok?: boolean;
}

export interface Turn {
  question: string;
  persona: Persona;
  trace: TraceItem[];
  actionIds: string[];
  sop?: Sop;
  error?: string;
  running: boolean;
}

export type AgentEvent =
  | { type: "status"; message: string }
  | { type: "tool_call"; id: string; name: string; args: Record<string, unknown> }
  | { type: "tool_result"; id: string; name: string; preview: string; ok: boolean }
  | { type: "action_proposed"; id: string; action: Action }
  | { type: "sop"; sop: Sop }
  | { type: "error"; message: string }
  | { type: "done" };
