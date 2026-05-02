// Typed API client. All requests go through Next.js rewrites → FastAPI core.

export interface Agent {
  id: number;
  name: string;
  model: string;
  description: string;
  status: "idle" | "running" | "error" | "offline";
  last_run_at: string | null;
}

export interface RunSummary {
  id: number;
  agent_id?: number;
  source: string;
  status: string;
  started_at: string;
  ended_at: string | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  prompt?: string;
  error_message?: string | null;
}

export interface RunDetail extends RunSummary {
  agent_id: number;
  prompt: string;
  session_id?: string | null;
  final_text?: string | null;
}

export interface Schedule {
  id: number;
  agent_id: number;
  cron_expr: string;
  prompt: string;
  enabled: boolean;
  next_run_at: string | null;
  last_run_at: string | null;
}

export interface OntologyNode { id: number; label: string; type: string; meta: any; }
export interface OntologyEdge { id: number; src: number; predicate: string; dst: number; weight: number; }

export interface Improvement {
  id: number;
  agent_id: number;
  rationale: string;
  diff: string;
  created_at: string;
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path, { cache: "no-store" });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export const fetchAgents = () => get<Agent[]>("/api/agents");
export const fetchAgent = (id: number) => get<Agent>(`/api/agents/${id}`);
export const fetchAgentRuns = (id: number) => get<RunSummary[]>(`/api/agents/${id}/runs`);
export const fetchRecentRuns = () => get<RunSummary[]>("/api/runs?limit=20");
export const fetchRun = (id: number) => get<RunDetail>(`/api/runs/${id}`);
export const cancelRun = (id: number) => post<{ cancelled: boolean }>(`/api/runs/${id}/cancel`);
export const runAgentNow = (id: number, prompt: string) =>
  post<{ run_id: number; status: string }>(`/api/agents/${id}/run`, { prompt });

export const fetchSchedules = () => get<Schedule[]>("/api/schedules");
export const createSchedule = (agent_id: number, cron_expr: string, prompt: string, enabled = true) =>
  post<Schedule>("/api/schedules", { agent_id, cron_expr, prompt, enabled });
export const deleteSchedule = async (id: number) => {
  const r = await fetch(`/api/schedules/${id}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
};

export const fetchOntologyNodes = () => get<OntologyNode[]>("/api/ontology/nodes");
export const fetchOntologyEdges = () => get<OntologyEdge[]>("/api/ontology/edges");

export const fetchImprovements = (status: string = "proposed") =>
  get<Improvement[]>(`/api/improvements?status=${status}`);
export const approveImprovement = (id: number) => post(`/api/improvements/${id}/approve`);
export const rejectImprovement = (id: number) => post(`/api/improvements/${id}/reject`);

export const fetchHealth = () => get<{ status: string; version: string; active_runs: number }>("/api/health");
