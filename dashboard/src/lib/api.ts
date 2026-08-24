// Typed API client. All requests go through Next.js rewrites → FastAPI core.

export interface Lesson {
  kind: "lesson" | "bias" | "fact";
  text: string;
  source: "user" | "reflection";
  added_at: string;
}

export interface Project {
  id: number;
  slug: string;
  name: string;
  description: string;
  mission: string;
  // En HRO un proyecto ES una búsqueda; este campo guarda la descripción de cargo.
  job_description?: string;
  // Carpeta del sistema con los CVs a analizar (HRO). String simple (ruta).
  cv_folder?: string;
  // Perfil de entrevista de Sofía para esta búsqueda (HRO).
  interview_profile?: string;
  color: string;
  icon: string;
  status: "active" | "archived";
  lessons: Lesson[];
  agent_count: number;
  runs_24h: number;
  cost_24h: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  slug?: string;
  description?: string;
  mission?: string;
  job_description?: string;
  cv_folder?: string;
  interview_profile?: string;
  color?: string;
  icon?: string;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  mission?: string;
  job_description?: string;
  cv_folder?: string;
  interview_profile?: string;
  color?: string;
  icon?: string;
  status?: "active" | "archived";
}

export interface ProjectAgent {
  id: number;
  name: string;
  model: string;
  description: string;
  status: string;
  last_run_at: string | null;
}

export interface ProjectRun {
  id: number;
  agent_id: number;
  agent_name: string;
  source: string;
  status: string;
  started_at: string;
  ended_at: string | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  prompt: string;
}

export interface McpStdioServer {
  type?: "stdio";
  command: string;
  args?: string[];
  env?: Record<string, string>;
}
export interface McpHttpServer {
  type: "http" | "sse";
  url: string;
  headers?: Record<string, string>;
}
export type McpServer = McpStdioServer | McpHttpServer;

export interface Agent {
  /** Motor de ejecución: "claude" | "codex". */
  engine?: string;
  id: number;
  name: string;
  model: string;
  description: string;
  status: "idle" | "running" | "error" | "offline";
  last_run_at: string | null;
  project_id: number | null;
  project_slug: string | null;
  project_name: string | null;
  project_color: string | null;
  project_icon: string | null;
  tools: string[] | null;
  mcp_servers: Record<string, McpServer> | null;
}

/** Estados en los que una corrida ya terminó y no hay que seguir consultándola.
 *
 *  Una sola lista, a propósito: cuando el backend agregó `interrupted` (una
 *  corrida cortada por un reinicio de la máquina), este chequeo vivía duplicado
 *  en tres archivos, se actualizó en cero, y el chat quedaba refrescando para
 *  siempre una corrida que nunca iba a cambiar. */
export const TERMINAL_RUN_STATUSES = [
  "completed",
  "failed",
  "cancelled",
  "interrupted",
] as const;

export type TerminalRunStatus = (typeof TERMINAL_RUN_STATUSES)[number];

export function isTerminalRunStatus(status: string): boolean {
  return (TERMINAL_RUN_STATUSES as readonly string[]).includes(status);
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
  /** Motor que la corrió: "claude" | "codex". */
  engine?: string | null;
  // Soul-2 (ADR-007): dual-track dispatcher metadata.
  track?: "s1" | "s2" | null;
  // Soul-3 (ADR-008): which lineage version executed.
  agent_version_id?: string | null;
}

export interface RunDetail extends RunSummary {
  agent_id: number;
  prompt: string;
  session_id?: string | null;
  final_text?: string | null;
  // Soul-2 extra detail.
  classifier_confidence?: number | null;
  classifier_rationale?: string | null;
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

async function readError(r: Response): Promise<string> {
  // FastAPI returns {"detail": "..."} on validation errors. Surface that
  // verbatim so the dashboard can show what actually went wrong instead of
  // a meaningless "422 Unprocessable Entity".
  try {
    const j = await r.clone().json();
    if (j && typeof j.detail === "string") return j.detail;
    if (j && Array.isArray(j.detail)) return j.detail.map((d: any) => d.msg).join("; ");
    if (j && typeof j === "object") return JSON.stringify(j);
  } catch {
    // not JSON — fall through
  }
  try {
    const t = await r.text();
    if (t) return t.slice(0, 1200);
  } catch {}
  return `${r.status} ${r.statusText}`;
}

// Friendly error wrapper: cuando el backend está caído (typical: usuario
// recién instaló, olvidó arrancar uvicorn), `fetch` tira TypeError. Lo
// convertimos en un mensaje accionable en vez de "Failed to fetch".
function networkErrorMessage(): Error {
  return new Error(
    "No se puede conectar al backend de TeamAgent en :8000. " +
      "Revisa que `uvicorn core.main:app --port 8000` esté corriendo en otra terminal.",
  );
}

async function get<T>(path: string): Promise<T> {
  let r: Response;
  try {
    r = await fetch(path, { cache: "no-store" });
  } catch {
    throw networkErrorMessage();
  }
  if (!r.ok) throw new Error(await readError(r));
  return r.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  let r: Response;
  try {
    r = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw networkErrorMessage();
  }
  if (!r.ok) throw new Error(await readError(r));
  return r.json();
}

export const fetchAgents = (project?: string) =>
  get<Agent[]>(project ? `/api/agents?project=${encodeURIComponent(project)}` : "/api/agents");
export const fetchAgent = (id: number) => get<Agent>(`/api/agents/${id}`);
export const fetchAgentRuns = (id: number) => get<RunSummary[]>(`/api/agents/${id}/runs`);
export const moveAgent = (id: number, project_slug: string) =>
  post<Agent>(`/api/agents/${id}/move`, { project_slug });

// --- Soul-3 evolutionary archive (ADR-008) ---
export interface EvolutionVersion {
  id: string;
  parent: string | null;
  created_at: string;
  status: "active" | "archived" | "proposed" | "rejected" | "accepted";
  rationale: string;
  hypothesis: string;
  metrics: { runs: number; avg_cost_usd: number; avg_latency_ms: number };
  validation_score: number | null;
}

export interface EvolutionLineage {
  agent_id: number;
  agent_name: string;
  current: string;
  active: string[];
  versions: EvolutionVersion[];
}

export interface EvolutionValidation {
  score: number;
  verdict: "improve" | "neutral" | "regress" | "unknown";
  rationale: string;
  concerns: string[];
}

export const fetchEvolution = (agentId: number) =>
  get<EvolutionLineage>(`/api/agents/${agentId}/evolution`);
export const fetchVersionBody = (agentId: number, versionId: string) =>
  get<{ version_id: string; body: string }>(
    `/api/agents/${agentId}/evolution/${versionId}/body`,
  );
export const proposeEvolution = (agentId: number, max_candidates = 2) =>
  post<{ proposed_version_ids: string[] }>(
    `/api/agents/${agentId}/evolution/propose?max_candidates=${max_candidates}`,
  );
export const validateEvolution = (agentId: number, versionId: string) =>
  post<EvolutionValidation>(
    `/api/agents/${agentId}/evolution/${versionId}/validate`,
  );
export const acceptEvolution = (agentId: number, versionId: string) =>
  post<{ status: string; version_id: string }>(
    `/api/agents/${agentId}/evolution/${versionId}/accept`,
  );
export const rejectEvolution = (agentId: number, versionId: string) =>
  post<{ status: string; version_id: string }>(
    `/api/agents/${agentId}/evolution/${versionId}/reject`,
  );
export const branchEvolution = (agentId: number, versionId: string) =>
  post<{ status: string; version_id: string }>(
    `/api/agents/${agentId}/evolution/${versionId}/branch`,
  );
export const rollbackEvolution = (agentId: number, versionId: string) =>
  post<{ status: string; version_id: string }>(
    `/api/agents/${agentId}/evolution/${versionId}/rollback`,
  );

// --- Admin (peligrosos) ---
export const resetInstall = () =>
  post<{ deleted: string[]; skipped: { path: string; reason: string }[]; next_step: string }>(
    "/api/admin/reset?confirm=YES_RESET_EVERYTHING",
  );

// --- Channel bindings (Capa 13) ---
export interface ChannelBinding {
  id: number;
  channel_type: "telegram" | "slack";
  external_id: string;
  agent_id: number;
  agent_name: string;
  project_slug: string | null;
  project_name: string | null;
  label: string | null;
  created_at: string;
}
export interface ChannelBindingCreate {
  channel_type: "telegram" | "slack";
  external_id: string;
  agent_id: number;
  label?: string | null;
}
export const fetchChannelBindings = (channel_type?: "telegram" | "slack") =>
  get<ChannelBinding[]>(
    channel_type ? `/api/channels?channel_type=${channel_type}` : "/api/channels",
  );
export const createChannelBinding = (body: ChannelBindingCreate) =>
  post<ChannelBinding>("/api/channels", body);
export const deleteChannelBinding = async (id: number): Promise<void> => {
  const r = await fetch(`/api/channels/${id}`, { method: "DELETE" });
  if (!r.ok) throw new Error(await readError(r));
};

// --- Templates (Capa 6) ---
export interface TemplateCard {
  id: string;
  title: string;
  pitch: string;
  story: string;
  audience: "casual" | "pro";
  project: { name: string; slug: string; color: string; icon: string; mission: string } | null;
  agent_count: number;
  schedule_count: number;
}
export interface TemplateFull extends TemplateCard {
  proposal: Proposal;
}
export const fetchTemplates = (lang?: string) =>
  get<TemplateCard[]>(`/api/templates${lang ? `?lang=${lang}` : ""}`);
export const fetchTemplate = (id: string, lang?: string) =>
  get<TemplateFull>(`/api/templates/${id}${lang ? `?lang=${lang}` : ""}`);
export const cloneTemplate = (
  id: string,
  body: { slug_override?: string; target_agents_dir?: string; target_skills_dir?: string } = {},
) => post<DeployResult>(`/api/templates/${id}/clone`, body);

// --- Projects (ADR-005) ---
export const fetchProjects = (includeArchived = false) =>
  get<Project[]>(`/api/projects${includeArchived ? "?include_archived=true" : ""}`);
export const fetchProject = (idOrSlug: string | number) =>
  get<Project>(`/api/projects/${idOrSlug}`);
export const fetchProjectAgents = (idOrSlug: string | number) =>
  get<ProjectAgent[]>(`/api/projects/${idOrSlug}/agents`);
export const fetchProjectRuns = (idOrSlug: string | number, limit = 30) =>
  get<ProjectRun[]>(`/api/projects/${idOrSlug}/runs?limit=${limit}`);
export const createProject = (body: ProjectCreate) =>
  post<Project>("/api/projects", body);
export const updateProject = async (idOrSlug: string | number, body: ProjectUpdate): Promise<Project> => {
  const r = await fetch(`/api/projects/${idOrSlug}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await readError(r));
  return r.json();
};
export const deleteProject = async (idOrSlug: string | number): Promise<void> => {
  const r = await fetch(`/api/projects/${idOrSlug}`, { method: "DELETE" });
  if (!r.ok) throw new Error(await readError(r));
};
// HRO: dispara al agente screener sobre la carpeta de CVs de la búsqueda. Lee
// los CVs, los evalúa contra la job description y crea candidatos ligados a la
// búsqueda. Devuelve 202 con {run_id, status, folder}; 400 si no hay carpeta.
export interface ScreenCvsResult {
  run_id: number;
  status: string;
  folder: string;
}
export const screenCvs = (slug: string, folder?: string) =>
  post<ScreenCvsResult>(
    `/api/projects/${slug}/screen-cvs`,
    folder ? { folder } : {},
  );
// HRO: conecta una fuente externa de CVs a una búsqueda. Dispara al agente
// `connector` (Claude Code) que ARMA y EJECUTA la integración real (hits a la
// API/web con el token, descarga) y deja los CVs en la carpeta de la búsqueda.
// Las credenciales NO van en el prompt: el backend las guarda en un archivo
// local que el agente lee. Devuelve 202 con {run_id, status, target_folder};
// 400 si el pedido es inválido.
export type ConnectSourceKind =
  | "api"
  | "pandape"
  | "drive"
  | "onedrive"
  | "web"
  | "folder";
export interface ConnectSourceBody {
  kind: ConnectSourceKind;
  goal: string;
  credentials?: string;
  target_folder?: string;
}
export interface ConnectSourceResult {
  run_id: number;
  status: string;
  target_folder: string;
}
export const connectSource = (slug: string, body: ConnectSourceBody) =>
  post<ConnectSourceResult>(`/api/projects/${slug}/connect`, body);
export const addProjectLesson = (
  idOrSlug: string | number,
  body: { text: string; kind?: "lesson" | "bias" | "fact" },
) => post<Project>(`/api/projects/${idOrSlug}/lessons`, body);
export const removeProjectLesson = async (
  idOrSlug: string | number,
  index: number,
): Promise<Project> => {
  const r = await fetch(`/api/projects/${idOrSlug}/lessons/${index}`, { method: "DELETE" });
  if (!r.ok) throw new Error(await readError(r));
  return r.json();
};
export const fetchRecentRuns = () => get<RunSummary[]>("/api/runs?limit=20");
export const fetchRun = (id: number) => get<RunDetail>(`/api/runs/${id}`);
export const cancelRun = (id: number) => post<{ cancelled: boolean }>(`/api/runs/${id}/cancel`);
export interface RunNowOptions {
  session_id?: string | null;
  task_type?: "fast" | "think" | "deep";
  seek_devils_advocate?: boolean;
}
export const runAgentNow = (id: number, prompt: string, opts: RunNowOptions = {}) =>
  post<{ run_id: number; status: string }>(`/api/agents/${id}/run`, {
    prompt,
    session_id: opts.session_id ?? null,
    task_type: opts.task_type ?? null,
    seek_devils_advocate: opts.seek_devils_advocate ?? false,
  });

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

// Estado real de la cuenta de Claude: el backend corre `claude auth status`
// sobre el binario que realmente usa un run, con el entorno que realmente
// recibe. "Hay un token en el .env" y "el token sirve" son cosas distintas;
// esto responde la segunda.
export interface ClaudeAuthStatus {
  ok: boolean;
  logged_in: boolean;
  cli_path: string | null;
  cli_source: "bundled" | "path" | "wellknown" | "none";
  cli_version: string;
  method: string;
  provider: string;
  account: string;
  organization: string;
  plan: string;
  credential_source: "env-token" | "api-key" | "machine-login" | "none" | string;
  error: string;
  hint: string;
  checked_at: number;
  /** null = configurada pero sin comprobar contra el API. */
  verified: boolean | null;
  verify_error: string;
  verify_status: number | null;
}

/** `verify` hace una llamada real al API (única forma de saber si la credencial
 *  sirve; `auth status` reporta un token revocado como conectado). Cuesta una
 *  fracción de centavo, así que va sólo bajo pedido — nunca en el polling. */
// Los motores disponibles y su estado. El motor Codex existía sólo en el
// frontmatter de un archivo .md — invisible desde la interfaz.
export interface EngineStatus {
  name: "claude" | "codex" | string;
  label: string;
  installed: boolean;
  cli_version: string;
  connected: boolean;
  account: string;
  plan: string;
  method: string;
  credential_source: string;
  verified: boolean | null;
  error: string;
  /** Comando de terminal que conecta la cuenta. */
  connect_command: string;
  /** Comando que instala el CLI, vacío si ya está. */
  install_command: string;
  default: boolean;
  /** Si los agentes en este motor usan la memoria de Rugol. Desde 2.0 los dos
   *  la usan: vive en el core y se sirve por MCP sobre HTTP. */
  supports_memory: boolean;
  /** Lo que este motor NO puede hacer, en palabras del usuario. */
  missing: string[];
  /** Los modelos de ESTE motor. El frontend no mantiene su propia copia:
   *  ofrecer un modelo que el motor rechaza es un error garantizado. */
  models: { value: string; label: string }[];
  default_model: string;
}

export const fetchEngines = (verify = false) =>
  get<{ engines: EngineStatus[] }>(`/api/health/engines${verify ? "?verify=true" : ""}`);

export const fetchClaudeAuth = (opts: { refresh?: boolean; verify?: boolean } = {}) => {
  const q = new URLSearchParams();
  if (opts.refresh) q.set("refresh", "true");
  if (opts.verify) q.set("verify", "true");
  const qs = q.toString();
  return get<ClaudeAuthStatus>(`/api/health/auth${qs ? `?${qs}` : ""}`);
};

export const fetchHealth = () => get<{ status: string; version: string; active_runs: number; brand?: string; accent?: string; accent_strong?: string; tagline?: string; variant?: "rugol" | "crm" | "hro" }>("/api/health");

// --- Domain pipeline (CRM prospectos / HRO candidatos) ---
// El backend (core/api/pipeline.py) lo poblan los agentes runtime y el usuario
// puede operarlo manualmente desde el dashboard kanban.
export type PipelineKind = "lead" | "candidate";

export interface PipelineNote {
  at: string;
  agent: string | null;
  text: string;
}

export interface PipelineItem {
  id: number;
  kind: PipelineKind;
  title: string;
  subtitle: string | null;
  stage: string;
  score: number | null; // 1-5 o null
  source_agent: string | null;
  // Búsqueda (HRO) / proyecto (CRM) al que pertenece el item.
  project_slug: string | null;
  notes: PipelineNote[];
  data: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
}

export interface PipelineStages {
  kind: string;
  stages: string[];
}

export interface PipelineCreate {
  kind: PipelineKind;
  title: string;
  subtitle?: string | null;
  stage?: string | null;
  score?: number | null;
  source_agent?: string | null;
  // Liga el item a una búsqueda (HRO) / proyecto (CRM).
  project_slug?: string | null;
  data?: Record<string, unknown>;
  note?: string | null;
}

export interface PipelineUpdate {
  stage?: string;
  score?: number | null;
  title?: string;
  subtitle?: string | null;
  data?: Record<string, unknown>;
  note?: string;
  note_agent?: string | null;
}

// `fetchPipeline("candidate")` sigue funcionando igual; las opciones agregan
// filtros server-side: `project` (slug de búsqueda) y `q` (texto libre).
export const fetchPipeline = (
  kind: PipelineKind,
  opts: { project?: string; q?: string } = {},
) => {
  const params = new URLSearchParams({ kind });
  if (opts.project) params.set("project", opts.project);
  if (opts.q) params.set("q", opts.q);
  return get<PipelineItem[]>(`/api/pipeline?${params.toString()}`);
};
export const fetchPipelineStages = (kind: PipelineKind) =>
  get<PipelineStages>(`/api/pipeline/stages?kind=${kind}`);

// Banco de talento: recomienda candidatos del pipeline para una posición.
export interface RecommendedCandidate extends PipelineItem {
  rank_score: number;
  why: string;
}
export const recommendCandidates = (
  q: string,
  opts: { project?: string; limit?: number } = {},
) => {
  const params = new URLSearchParams({ q });
  if (opts.project) params.set("project", opts.project);
  if (opts.limit) params.set("limit", String(opts.limit));
  return get<RecommendedCandidate[]>(`/api/pipeline/recommend?${params.toString()}`);
};
export const createPipelineItem = (body: PipelineCreate) =>
  post<PipelineItem>("/api/pipeline", body);
export const updatePipelineItem = async (
  id: number,
  body: PipelineUpdate,
): Promise<PipelineItem> => {
  const r = await fetch(`/api/pipeline/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await readError(r));
  return r.json();
};
export const deletePipelineItem = async (id: number): Promise<void> => {
  const r = await fetch(`/api/pipeline/${id}`, { method: "DELETE" });
  if (!r.ok) throw new Error(await readError(r));
};

// --- Agent CRUD via UI ---
export interface AgentSpec {
  name: string;
  model: string;
  /** Motor de ejecución. Omitir = "claude". */
  engine?: string;
  description: string;
  body: string;
  project_slug?: string;
  tools?: string[] | null;
  mcp_servers?: Record<string, McpServer> | null;
}

export interface AgentSource extends Omit<AgentSpec, "project_slug"> {
  id: number;
  source_path: string;
  project_slug: string | null;
  project_name: string | null;
}

export const AVAILABLE_TOOLS: { name: string; description: string }[] = [
  { name: "Read", description: "Read files from the workspace." },
  { name: "Write", description: "Create new files." },
  { name: "Edit", description: "Targeted edits to existing files." },
  { name: "Glob", description: "Find files by pattern (e.g. **/*.tsx)." },
  { name: "Grep", description: "Search file contents with ripgrep." },
  { name: "Bash", description: "Run shell commands inside the workspace." },
  { name: "WebFetch", description: "Pull content from a public URL." },
  { name: "WebSearch", description: "Search the web." },
  { name: "Task", description: "Spawn a subagent for a focused task." },
  { name: "TaskCreate", description: "Plan multi-step work as tracked tasks." },
  { name: "TaskUpdate", description: "Update a task's state." },
  { name: "TaskList", description: "Read the active task list." },
  { name: "NotebookEdit", description: "Edit Jupyter notebook cells." },
];

export const createAgent = (spec: AgentSpec) => post<Agent>("/api/agents", spec);
export const fetchAgentSource = (id: number) => get<AgentSource>(`/api/agents/${id}/source`);
export const updateAgent = async (id: number, spec: AgentSpec): Promise<Agent> => {
  const r = await fetch(`/api/agents/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(spec),
  });
  if (!r.ok) {
    const txt = await r.text();
    throw new Error(`${r.status} ${r.statusText} — ${txt}`);
  }
  return r.json();
};

// --- Per-agent memories (v0.6 — Sprint B) ---
export interface AgentMemory {
  name: string;
  description: string;
  kind: string;
  created_at: string;
  body: string;
  file: string;
}
export interface NewAgentMemory {
  name: string;
  description: string;
  body: string;
  kind?: string;
}
export const fetchAgentMemories = (id: number) =>
  get<AgentMemory[]>(`/api/agents/${id}/memories`);

// --- Global memory graph (v0.8 — Obsidian-style network) ---
export interface MemoryGraphNode {
  id: string;
  type: "agent" | "memory" | "concept";
  label: string;
  degree: number;
  agent?: string;
  kind?: string;
  description?: string;
  file?: string;
  created_at?: string;
  body?: string;
}
export interface MemoryGraphEdge {
  source: string;
  target: string;
  type: "owns" | "link";
}
export interface MemoryGraphData {
  nodes: MemoryGraphNode[];
  edges: MemoryGraphEdge[];
  stats: { agents: number; memories: number; concepts: number; links: number };
}
export const fetchMemoryGraph = () => get<MemoryGraphData>("/api/memory-graph");

export const createAgentMemory = (id: number, mem: NewAgentMemory) =>
  post<AgentMemory>(`/api/agents/${id}/memories`, mem);

export const deleteAgentMemory = async (id: number, fileOrName: string): Promise<void> => {
  const r = await fetch(
    `/api/agents/${id}/memories/${encodeURIComponent(fileOrName)}`,
    { method: "DELETE" },
  );
  if (!r.ok) {
    const txt = await r.text();
    throw new Error(`${r.status} ${r.statusText} — ${txt}`);
  }
};

// --- Config Assistant (v0.6) ---
export interface ConfigAssistantAction {
  type: string;
  id: string;
  description: string;
  [key: string]: any; // type-specific masked fields
}
export interface ConfigAssistantPlan {
  actions: ConfigAssistantAction[];
  unsure: string[];
}
export interface ConfigAssistantParseResponse {
  plan_token: string;
  plan: ConfigAssistantPlan;
  ttl_seconds: number;
}
export interface ConfigAssistantApplyResult {
  results: Array<{ id: string; ok: boolean; outcome?: string; error?: string }>;
}
export const configAssistantParse = async (
  text: string,
): Promise<ConfigAssistantParseResponse> => {
  const r = await fetch("/api/config-assistant/parse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!r.ok) {
    const txt = await r.text();
    throw new Error(`${r.status} ${r.statusText} — ${txt}`);
  }
  return r.json();
};
export const configAssistantApply = async (
  plan_token: string,
  action_ids: string[],
): Promise<ConfigAssistantApplyResult> => {
  const r = await fetch("/api/config-assistant/apply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan_token, action_ids }),
  });
  if (!r.ok) {
    const txt = await r.text();
    throw new Error(`${r.status} ${r.statusText} — ${txt}`);
  }
  return r.json();
};

// --- MCP test (v0.6) ---
// Asks the backend to spawn the configured MCP server and verify it responds
// to the JSON-RPC handshake. Returns either ok=true with discovered tools, or
// ok=false with an error_kind and a human message.
export interface McpTestResult {
  ok: boolean;
  tools: string[];
  error: string | null;
  error_kind: "not_installed" | "timeout" | "bad_response" | "stderr" | "spawn_failed" | null;
  stderr_tail: string | null;
  duration_ms: number;
}
export const testAgentMcp = async (
  agentId: number,
  name: string,
): Promise<McpTestResult> => {
  const r = await fetch(`/api/agents/${agentId}/mcp/${encodeURIComponent(name)}/test`, {
    method: "POST",
  });
  if (!r.ok) {
    const txt = await r.text();
    throw new Error(`${r.status} ${r.statusText} — ${txt}`);
  }
  return r.json();
};

// --- Settings ---
export interface PublicSettings {
  telegram_bot_token_set: boolean;
  telegram_bot_token_hint: string;
  telegram_allowed_users: string;
  slack_bot_token_set: boolean;
  slack_bot_token_hint: string;
  slack_signing_secret_set: boolean;
  slack_app_token_set: boolean;
  slack_app_token_hint: string;
  agents_dir: string;
  skills_dir: string;
  default_model: string;
  elevenlabs_api_key_set?: boolean;
  elevenlabs_agent_id?: string;
  cv_sources?: CvSourcePublic[];
  onboarding_done?: boolean;
}

export interface SettingsStatus {
  telegram: { configured: boolean; running: boolean; allowed_user_ids: number[] };
  slack: { configured: boolean; running: boolean };
  watcher: { agents_dir: string; skills_dir: string; running: boolean };
  // Voz Sofía (ElevenLabs) — presente cuando la variante es HRO.
  elevenlabs?: { configured: boolean };
}

export interface SettingsUpdate {
  telegram_bot_token?: string;
  telegram_allowed_users?: string;
  slack_bot_token?: string;
  slack_signing_secret?: string;
  slack_app_token?: string;
  agents_dir?: string;
  skills_dir?: string;
  default_model?: string;
  // Voz Sofía (ElevenLabs).
  elevenlabs_api_key?: string;
  elevenlabs_agent_id?: string;
  onboarding_done?: boolean;
}

// --- Fuentes de CV (HRO) ---
export interface CvSourcePublic {
  id: string;
  type: string;
  name: string;
  path: string;
  status: string; // conectada | detectada | falta_ruta | falta_credencial | pendiente | configurada
  credentials_set: boolean;
  credentials_hint: string;
}
export interface CvSourceType {
  id: string;
  label: string;
  needs_credentials: boolean;
  hint: string;
}
export interface DetectedDrive {
  type: string;
  name: string;
  path: string;
  added: boolean;
}
interface CvSourcesResponse {
  sources: CvSourcePublic[];
  types: CvSourceType[];
  detected: DetectedDrive[];
}
export const fetchCvSources = () => get<CvSourcesResponse>("/api/cv-sources");
export const addCvSource = (body: { type: string; name?: string; credentials?: string; path?: string }) =>
  post<CvSourcesResponse>("/api/cv-sources", body);
export const deleteCvSource = async (id: string): Promise<CvSourcesResponse> => {
  const r = await fetch(`/api/cv-sources/${encodeURIComponent(id)}`, { method: "DELETE" });
  if (!r.ok) throw new Error(await readError(r));
  return r.json();
};

// --- Skills ---
export interface Skill {
  id: number;
  name: string;
  description: string;
  source_path: string;
}
export interface SkillSource extends Skill {
  body: string;
}
export interface SkillSpec {
  name: string;
  description: string;
  body: string;
}
export const fetchSkills = () => get<Skill[]>("/api/skills");
export const fetchSkillSource = (id: number) => get<SkillSource>(`/api/skills/${id}`);
export const createSkill = (spec: SkillSpec) => post<Skill>("/api/skills", spec);
export const updateSkillSpec = async (id: number, spec: SkillSpec): Promise<Skill> => {
  const r = await fetch(`/api/skills/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(spec),
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
};

// --- Architect ---
export interface ProposalProject {
  name: string;
  slug?: string;
  description?: string;
  mission?: string;
  color?: string;
  icon?: string;
}
export interface ProposalAgent {
  name: string;
  model: string;
  description: string;
  body: string;
}
export interface ProposalSkill {
  name: string;
  description: string;
  body: string;
}
export interface ProposalSchedule {
  agent_name: string;
  cron_expr: string;
  prompt: string;
}
export interface ProposalTriple {
  src: string;
  predicate: string;
  dst: string;
}
export interface Proposal {
  summary: string;
  rationale: string;
  project: ProposalProject | null;
  agents: ProposalAgent[];
  skills: ProposalSkill[];
  schedules: ProposalSchedule[];
  ontology_seeds: ProposalTriple[];
}
export interface DeployResult {
  project_slug: string | null;
  project_id: number | null;
  project_created: boolean;
  agents_created: string[];
  agents_skipped: { name: string; reason: string }[];
  skills_created: string[];
  skills_skipped: { name: string; reason: string }[];
  schedules_created: number[];
  schedules_skipped: { agent_name: string; reason: string }[];
  ontology_edges_created: number;
}

export const proposeArchitecture = (idea: string, constraints = "") =>
  post<Proposal>("/api/architect/propose", { idea, constraints });
export const deployProposal = (
  proposal: Proposal,
  target_agents_dir?: string,
  target_skills_dir?: string,
) =>
  post<DeployResult>("/api/architect/deploy", {
    proposal,
    target_agents_dir: target_agents_dir || null,
    target_skills_dir: target_skills_dir || null,
  });
export const fetchInstallDirs = () =>
  get<{ agents_dir: string; skills_dir: string }>("/api/architect/install-dirs");

export const fetchSettings = () => get<PublicSettings>("/api/settings");
export const fetchSettingsStatus = () => get<SettingsStatus>("/api/settings/status");
export const updateSettings = (upd: SettingsUpdate) =>
  post<{ ok: boolean; settings: PublicSettings; restarted: Record<string, string> }>("/api/settings", upd);

// `saveSettings` es el alias semántico que usa la UI de voz (acepta los mismos
// campos que `updateSettings`, incluyendo elevenlabs_*). Reusa POST /api/settings.
export const saveSettings = (body: SettingsUpdate) =>
  post<{ ok: boolean; settings: PublicSettings; restarted: Record<string, string> }>("/api/settings", body);

// --- Voz Sofía (ElevenLabs) ---
// Backend en vivo en /api/voice/*. La sincronización trae las entrevistas de
// ElevenLabs, las puntúa con BARS y crea candidatos en el pipeline.
export interface VoiceStatus {
  configured: boolean;
  has_api_key: boolean;
  agent_id: string;
  last_sync: null | Record<string, unknown>;
}

export interface VoiceSyncResult {
  processed: number;
  created: number;
  skipped: number;
  errors: string[];
  details?: unknown[];
}

export const fetchVoiceStatus = () => get<VoiceStatus>("/api/voice/status");

// ---- Entrevista in-app de Sofía (texto) — no requiere ElevenLabs ----
export interface InterviewTurnInput {
  role: "sofia" | "candidate";
  text: string;
}

export interface VoiceProfile {
  id: string;
  label: string;
}
export const fetchVoiceProfiles = () =>
  get<{ profiles: VoiceProfile[] }>("/api/voice/profiles");

// Sofía hace su siguiente pregunta. LLM detrás → puede tardar; sin abortar.
export const interviewTurn = async (
  project_slug: string | null,
  turns: InterviewTurnInput[],
  profile?: string | null,
): Promise<{ message: string }> => {
  let r: Response;
  try {
    r = await fetch("/api/voice/interview-turn", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_slug, turns, profile: profile ?? null }),
    });
  } catch {
    throw networkErrorMessage();
  }
  if (!r.ok) throw new Error(await readError(r));
  return r.json();
};

export interface ScoreTextResult {
  ok: boolean;
  item_id: number;
  overall: number | null;
  recommendation: string | null;
  conversation_id: string;
}

// Crea un link de entrevista ex-ante (lo toma el candidato).
export const createInterviewLink = (body: {
  project_slug?: string | null;
  candidate_name?: string | null;
  profile?: string | null;
}) =>
  post<{ token: string; path: string; project_slug: string | null; candidate_name: string | null; profile: string }>(
    "/api/voice/interview-link",
    body,
  );

export interface InterviewLinkInfo {
  found: boolean;
  project_slug: string | null;
  candidate_name: string | null;
  profile: string;
  job_description: string;
  used: boolean;
}
export const fetchInterviewLink = (token: string) =>
  get<InterviewLinkInfo>(`/api/voice/interview-link/${encodeURIComponent(token)}`);

// Cierra la entrevista: puntúa BARS y registra al candidato en el pipeline.
export const scoreTextInterview = async (input: {
  title: string;
  subtitle?: string | null;
  project_slug?: string | null;
  turns: InterviewTurnInput[];
  token?: string | null;
}): Promise<ScoreTextResult> => {
  let r: Response;
  try {
    r = await fetch("/api/voice/score-text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
  } catch {
    throw networkErrorMessage();
  }
  if (!r.ok) throw new Error(await readError(r));
  return r.json();
};

// La sincronización puede tardar 30-60s POR entrevista. No usamos el helper
// `post` (que va sin timeout explícito pero hereda el del navegador): hacemos
// el fetch directo para que el proxy de Next (proxyTimeout 240s) tenga margen
// y NO abortamos en cliente. El usuario verá el spinner mientras corre.
export const syncVoice = async (): Promise<VoiceSyncResult> => {
  let r: Response;
  try {
    r = await fetch("/api/voice/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // Sin AbortController: dejamos correr la sincronización completa.
    });
  } catch {
    throw networkErrorMessage();
  }
  if (!r.ok) throw new Error(await readError(r));
  return r.json();
};

