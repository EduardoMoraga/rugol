// Typed API client. All requests go through Next.js rewrites → FastAPI core.

export interface Project {
  id: number;
  slug: string;
  name: string;
  description: string;
  mission: string;
  color: string;
  icon: string;
  status: "active" | "archived";
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
  color?: string;
  icon?: string;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  mission?: string;
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

export interface Agent {
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

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path, { cache: "no-store" });
  if (!r.ok) throw new Error(await readError(r));
  return r.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(await readError(r));
  return r.json();
}

export const fetchAgents = (project?: string) =>
  get<Agent[]>(project ? `/api/agents?project=${encodeURIComponent(project)}` : "/api/agents");
export const fetchAgent = (id: number) => get<Agent>(`/api/agents/${id}`);
export const fetchAgentRuns = (id: number) => get<RunSummary[]>(`/api/agents/${id}/runs`);
export const moveAgent = (id: number, project_slug: string) =>
  post<Agent>(`/api/agents/${id}/move`, { project_slug });

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
export const fetchTemplates = () => get<TemplateCard[]>("/api/templates");
export const fetchTemplate = (id: string) => get<TemplateFull>(`/api/templates/${id}`);
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

// --- Agent CRUD via UI ---
export interface AgentSpec {
  name: string;
  model: string;
  description: string;
  body: string;
  project_slug?: string;
  tools?: string[] | null;
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
}

export interface SettingsStatus {
  telegram: { configured: boolean; running: boolean; allowed_user_ids: number[] };
  slack: { configured: boolean; running: boolean };
  watcher: { agents_dir: string; skills_dir: string; running: boolean };
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
}

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

