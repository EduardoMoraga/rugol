"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Pencil,
  FileCode2,
  Wrench,
  BookOpen,
  Network,
  ListTree,
  Plug,
  GitBranch,
} from "lucide-react";
import {
  AVAILABLE_TOOLS,
  createAgentMemory,
  deleteAgentMemory,
  fetchAgent,
  fetchAgentMemories,
  fetchAgentRuns,
  fetchAgentSource,
  fetchOntologyEdges,
  fetchOntologyNodes,
  fetchProject,
  fetchProjects,
  moveAgent,
  testAgentMcp,
  updateAgent,
  type AgentMemory,
  type AgentSource,
  type McpTestResult,
} from "@/lib/api";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/input";
import { Card, CardSection, PageHeader, Stat } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { toast } from "@/components/ui/toast";
import { ProjectBadge } from "@/components/projects/project-badge";
import { AgentChat } from "@/components/agents/agent-chat";

export default function AgentDetail() {
  const params = useParams<{ id: string }>();
  const agentId = Number(params.id);

  const agent = useQuery({
    queryKey: ["agent", agentId],
    queryFn: () => fetchAgent(agentId),
    refetchInterval: (q) => (q.state.data?.status === "running" ? 3000 : false),
    enabled: !Number.isNaN(agentId),
  });
  const runs = useQuery({
    queryKey: ["agent-runs", agentId],
    queryFn: () => fetchAgentRuns(agentId),
    refetchInterval: 5000,
    enabled: !Number.isNaN(agentId),
  });
  const projectSlug = agent.data?.project_slug ?? null;
  const project = useQuery({
    queryKey: ["project", projectSlug],
    queryFn: () => fetchProject(projectSlug as string),
    enabled: !!projectSlug,
  });

  if (agent.isLoading) return <div className="p-8 text-sm text-[--color-fg-muted]">Loading…</div>;
  if (!agent.data) return <div className="p-8 text-sm text-[--color-fg-muted]">Agent not found.</div>;

  const a = agent.data;
  const totalRuns = runs.data?.length ?? 0;
  const totalCost = (runs.data ?? []).reduce((s, r) => s + (Number(r.cost_usd) || 0), 0);
  const successRate =
    totalRuns === 0
      ? 0
      : ((runs.data ?? []).filter((r) => r.status === "completed").length / totalRuns) * 100;

  return (
    <div className="p-8 space-y-6 max-w-5xl mx-auto">
      <PageHeader
        title={a.name}
        description={a.description || "No description provided."}
        actions={
          <div className="flex items-center gap-2">
            <ProjectMover agent={a} />
            <Link href={`/agents/${agentId}/evolution`}>
              <Button variant="ghost" size="sm">
                <GitBranch size={13} /> Evolution
              </Button>
            </Link>
            <Link href={`/agents/${agentId}/edit`}>
              <Button variant="secondary" size="sm">
                <Pencil size={13} /> Edit spec
              </Button>
            </Link>
          </div>
        }
      />
      {a.project_slug && (
        <div className="-mt-3">
          <ProjectBadge
            slug={a.project_slug}
            name={a.project_name}
            color={a.project_color}
            icon={a.project_icon}
            size="md"
          />
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Status" value={a.status} accent={a.status === "running"} />
        <Stat label="Model" value={a.model.replace("claude-", "")} />
        <Stat label="Total runs" value={totalRuns} />
        <Stat
          label="Total cost"
          value={`$${totalCost.toFixed(3)}`}
          hint={totalRuns ? `${successRate.toFixed(0)}% success` : undefined}
        />
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">
            <ListTree size={12} />
            <span className="ml-1.5">Overview</span>
          </TabsTrigger>
          <TabsTrigger value="spec">
            <FileCode2 size={12} />
            <span className="ml-1.5">Spec</span>
          </TabsTrigger>
          <TabsTrigger value="memory">
            <BookOpen size={12} />
            <span className="ml-1.5">Memory</span>
          </TabsTrigger>
          <TabsTrigger value="tools">
            <Wrench size={12} />
            <span className="ml-1.5">Tools</span>
          </TabsTrigger>
          <TabsTrigger value="mcp">
            <Plug size={12} />
            <span className="ml-1.5">MCP</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-5 space-y-6">
          <AgentChat
            agentId={agentId}
            agentName={a.name}
            modelLabel={a.model}
            agentBusy={a.status === "running"}
            projectSlug={a.project_slug}
            projectName={project.data?.name ?? a.project_name}
            projectMission={project.data?.mission ?? null}
            projectLessonCount={project.data?.lessons.length ?? 0}
          />

          <CardSection>
            <div className="flex items-baseline justify-between">
              <h2 className="text-sm font-semibold tracking-tight">Recent runs</h2>
              <span className="text-xs text-[--color-fg-muted]">{totalRuns} total</span>
            </div>
            {totalRuns === 0 ? (
              <Card>
                <p className="text-sm text-[--color-fg-muted]">
                  No runs yet — kick the tires above.
                </p>
              </Card>
            ) : (
              <div className="space-y-1.5">
                {(runs.data ?? []).map((r) => (
                  <Link
                    key={r.id}
                    href={`/runs/${r.id}`}
                    className="surface surface-hover px-4 py-3 flex items-center justify-between text-sm"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="text-xs font-mono text-[--color-fg-subtle]">#{r.id}</span>
                      <StatusBadge status={r.status} />
                      {r.track && (
                        <span
                          className={
                            "pill text-[10px] " +
                            (r.track === "s1" ? "pill-idle" : "pill-accent")
                          }
                          title={r.track === "s1" ? "System 1 — fast track" : "System 2 — deliberate track"}
                        >
                          {r.track.toUpperCase()}
                        </span>
                      )}
                      {r.agent_version_id && (
                        <span
                          className="text-[10px] text-[--color-fg-subtle] font-mono"
                          title="Agent version that executed this run"
                        >
                          v{r.agent_version_id}
                        </span>
                      )}
                      <span className="text-xs text-[--color-fg-muted]">{r.source}</span>
                      <span className="text-xs text-[--color-fg-muted] truncate hidden md:inline max-w-md">
                        {r.prompt}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-[--color-fg-muted] shrink-0 font-mono tabular-nums">
                      <span>{(r.input_tokens + r.output_tokens).toLocaleString()} tok</span>
                      <span>${r.cost_usd.toFixed(4)}</span>
                      <span>{new Date(r.started_at).toLocaleTimeString()}</span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </CardSection>
        </TabsContent>

        <TabsContent value="spec" className="mt-5">
          <SpecPane agentId={agentId} />
        </TabsContent>

        <TabsContent value="memory" className="mt-5">
          <MemoryPane agentId={agentId} agentName={a.name} />
        </TabsContent>

        <TabsContent value="tools" className="mt-5">
          <ToolsPane agentId={agentId} />
        </TabsContent>

        <TabsContent value="mcp" className="mt-5">
          <McpPane agentId={agentId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function SpecPane({ agentId }: { agentId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["agent-source", agentId],
    queryFn: () => fetchAgentSource(agentId),
  });
  if (isLoading || !data) {
    return <p className="text-sm text-[--color-fg-muted]">Loading spec…</p>;
  }
  return (
    <Card className="space-y-3">
      <header className="flex items-center justify-between">
        <h2 className="text-sm font-semibold tracking-tight">Prompt body</h2>
        <Link href={`/agents/${agentId}/edit`} className="text-xs text-[--color-fg-muted] hover:text-[--color-fg]">
          Edit →
        </Link>
      </header>
      <p className="text-[11px] text-[--color-fg-subtle] font-mono">{data.source_path}</p>
      <pre className="text-[12px] whitespace-pre-wrap font-mono text-[--color-fg-muted] leading-relaxed bg-[--color-bg] p-4 rounded-md border border-[--color-border] max-h-[640px] overflow-y-auto">
        {data.body}
      </pre>
    </Card>
  );
}

function MemoryPane({ agentId, agentName }: { agentId: number; agentName: string }) {
  return (
    <div className="space-y-4">
      <PersistentMemoriesSection agentId={agentId} agentName={agentName} />
      <SharedOntologySection agentName={agentName} />
    </div>
  );
}


function PersistentMemoriesSection({
  agentId,
  agentName,
}: {
  agentId: number;
  agentName: string;
}) {
  const qc = useQueryClient();
  const memories = useQuery({
    queryKey: ["agent-memories", agentId],
    queryFn: () => fetchAgentMemories(agentId),
  });

  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newBody, setNewBody] = useState("");
  const [newKind, setNewKind] = useState<"note" | "fact" | "preference" | "reference" | "episode">("note");

  const create = useMutation({
    mutationFn: () =>
      createAgentMemory(agentId, {
        name: newName.trim(),
        description: newDesc.trim() || newName.trim(),
        body: newBody.trim(),
        kind: newKind,
      }),
    onSuccess: () => {
      toast({ tone: "success", title: "Memoria guardada" });
      qc.invalidateQueries({ queryKey: ["agent-memories", agentId] });
      setNewName("");
      setNewDesc("");
      setNewBody("");
      setNewKind("note");
      setAdding(false);
    },
    onError: (e: Error) =>
      toast({ tone: "error", title: "No se pudo guardar", body: e.message }),
  });

  const remove = useMutation({
    mutationFn: (file: string) => deleteAgentMemory(agentId, file),
    onSuccess: () => {
      toast({ tone: "info", title: "Memoria borrada" });
      qc.invalidateQueries({ queryKey: ["agent-memories", agentId] });
    },
  });

  const list = memories.data ?? [];
  const canSave = newName.trim().length > 0 && newBody.trim().length > 0;

  return (
    <Card>
      <header className="flex items-center justify-between mb-3">
        <div>
          <h2 className="text-sm font-semibold tracking-tight inline-flex items-center gap-2">
            <BookOpen size={13} className="text-[--color-accent-strong]" />
            Memoria persistente de {agentName}
          </h2>
          <p className="text-[11px] text-[--color-fg-muted] mt-0.5">
            Notas durables que el agente lee antes de cada run. Sobreviven restarts.
            También se pueden agregar por Telegram con <code className="font-mono">/remember</code>.
          </p>
        </div>
        {!adding && (
          <Button variant="primary" size="sm" onClick={() => setAdding(true)}>
            <Pencil size={12} /> Nueva
          </Button>
        )}
      </header>

      {adding && (
        <Card className="space-y-3 border border-dashed mb-3">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <div className="space-y-1 md:col-span-2">
              <label className="text-[11px] text-[--color-fg-muted]">Título</label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Ej: edu prefiere videos en español de más de 30 min"
                className="w-full px-3 py-2 bg-transparent border border-[--color-border] rounded-md text-sm focus:outline-none focus:border-[--color-accent]"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[11px] text-[--color-fg-muted]">Tipo</label>
              <select
                value={newKind}
                onChange={(e) => setNewKind(e.target.value as any)}
                className="w-full px-3 py-2 bg-transparent border border-[--color-border] rounded-md text-sm focus:outline-none focus:border-[--color-accent]"
              >
                <option value="note">note</option>
                <option value="fact">fact</option>
                <option value="preference">preference</option>
                <option value="reference">reference</option>
                <option value="episode">episode</option>
              </select>
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-[11px] text-[--color-fg-muted]">
              Descripción corta (lo que ve el agente como hint)
            </label>
            <input
              type="text"
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              placeholder="(opcional, se usa el título si lo dejás vacío)"
              className="w-full px-3 py-2 bg-transparent border border-[--color-border] rounded-md text-sm focus:outline-none focus:border-[--color-accent]"
            />
          </div>
          <div className="space-y-1">
            <label className="text-[11px] text-[--color-fg-muted]">
              Contenido (lo que el agente lee al inicio de cada run)
            </label>
            <textarea
              value={newBody}
              onChange={(e) => setNewBody(e.target.value)}
              rows={4}
              placeholder="Texto libre. Markdown OK."
              className="w-full px-3 py-2 bg-transparent border border-[--color-border] rounded-md text-sm focus:outline-none focus:border-[--color-accent]"
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setAdding(false)}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => create.mutate()}
              disabled={create.isPending || !canSave}
            >
              {create.isPending ? "Guardando…" : "Guardar"}
            </Button>
          </div>
        </Card>
      )}

      {memories.isLoading && (
        <p className="text-sm text-[--color-fg-muted]">Cargando memorias…</p>
      )}

      {!memories.isLoading && list.length === 0 && (
        <Card className="text-center py-8">
          <p className="text-sm text-[--color-fg-muted]">
            {agentName} no tiene memorias persistentes todavía. Agregá una arriba o
            mandá <code className="font-mono">/remember</code> al bot por Telegram.
          </p>
        </Card>
      )}

      {list.length > 0 && (
        <ul className="space-y-2">
          {list.map((m) => (
            <li key={m.file} className="surface px-4 py-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-medium text-[--color-fg]">{m.name}</p>
                    <Badge tone="accent">{m.kind}</Badge>
                  </div>
                  {m.description && m.description !== m.name && (
                    <p className="text-[11px] text-[--color-fg-muted]">
                      {m.description}
                    </p>
                  )}
                  <p className="text-[12.5px] text-[--color-fg-muted] whitespace-pre-wrap">
                    {m.body}
                  </p>
                  <p className="text-[10px] text-[--color-fg-subtle] font-mono">
                    {m.file} · {m.created_at?.slice(0, 16) || "—"}
                  </p>
                </div>
                <button
                  onClick={() => {
                    if (confirm(`¿Borrar la memoria "${m.name}"?`)) {
                      remove.mutate(m.file);
                    }
                  }}
                  className="opacity-50 hover:opacity-100 hover:text-[--color-error] transition px-1.5 py-0.5 text-base leading-none shrink-0"
                  title="Borrar"
                >
                  ×
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}


function SharedOntologySection({ agentName }: { agentName: string }) {
  const nodes = useQuery({ queryKey: ["onto-nodes"], queryFn: fetchOntologyNodes });
  const edges = useQuery({ queryKey: ["onto-edges"], queryFn: fetchOntologyEdges });

  const nodeById = new Map<number, { label: string; type: string }>();
  (nodes.data ?? []).forEach((n) => nodeById.set(n.id, { label: n.label, type: n.type }));
  const triples = (edges.data ?? []).slice(0, 30).map((e) => ({
    src: nodeById.get(e.src)?.label ?? `#${e.src}`,
    predicate: e.predicate,
    dst: nodeById.get(e.dst)?.label ?? `#${e.dst}`,
  }));

  return (
    <Card>
      <header className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold tracking-tight inline-flex items-center gap-2">
          <Network size={13} className="text-[--color-accent-strong]" />
          Ontología compartida
        </h2>
        <Link href="/ontology" className="text-xs text-[--color-fg-muted] hover:text-[--color-fg]">
          Abrir grafo →
        </Link>
      </header>
      {triples.length === 0 ? (
        <p className="text-sm text-[--color-fg-muted]">
          Sin hechos en el grafo todavía. A medida que <code className="font-mono">{agentName}</code>{" "}
          corre, puede escribir tripletas que cualquier otro agente puede leer.
        </p>
      ) : (
        <ul className="text-xs font-mono space-y-1 text-[--color-fg-muted]">
          {triples.map((t, i) => (
            <li key={`${t.src}-${t.predicate}-${t.dst}-${i}`} className="flex items-center gap-2">
              <span className="text-[--color-fg]">{t.src}</span>
              <span className="text-[--color-accent-strong]">{t.predicate}</span>
              <span className="text-[--color-fg]">{t.dst}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="text-[11px] text-[--color-fg-subtle] mt-3">
        Filtrado por agente queda en roadmap (cada edge ya guarda el run que la escribió
        en <code className="font-mono">created_by_run</code>).
      </p>
    </Card>
  );
}

function McpPane({ agentId }: { agentId: number }) {
  const qc = useQueryClient();
  const source = useQuery({
    queryKey: ["agent-source", agentId],
    queryFn: () => fetchAgentSource(agentId),
  });
  const initial = source.data?.mcp_servers ?? null;
  const [draft, setDraft] = useState<Record<string, any>>({});

  // Form state — used both for adding and editing.
  const [editingName, setEditingName] = useState<string | null>(null);
  const [formName, setFormName] = useState("");
  const [formCommand, setFormCommand] = useState("");
  const [formArgs, setFormArgs] = useState("");
  const [formEnv, setFormEnv] = useState("");

  // Per-server test result state (Sprint 1 v0.6).
  // null = never tested, "loading" = test running, otherwise the result.
  const [testState, setTestState] = useState<Record<string, "loading" | McpTestResult>>({});

  // Sync draft when the source loads/changes.
  useEffect(() => {
    setDraft(initial ? { ...initial } : {});
  }, [JSON.stringify(initial)]);

  const save = useMutation({
    mutationFn: (mcp_servers: Record<string, any> | null) => {
      if (!source.data) throw new Error("source not loaded");
      const s = source.data as AgentSource;
      return updateAgent(agentId, {
        name: s.name,
        model: s.model,
        description: s.description,
        body: s.body,
        project_slug: s.project_slug ?? undefined,
        tools: s.tools ?? undefined,
        mcp_servers,
      });
    },
    onSuccess: () => {
      toast({ tone: "success", title: "MCP servers actualizados" });
      qc.invalidateQueries({ queryKey: ["agent-source", agentId] });
      qc.invalidateQueries({ queryKey: ["agent", agentId] });
    },
    onError: (e: Error) =>
      toast({ tone: "error", title: "No se pudo guardar", body: e.message }),
  });

  if (source.isLoading) {
    return <p className="text-sm text-[--color-fg-muted]">Cargando spec…</p>;
  }

  function resetForm() {
    setEditingName(null);
    setFormName("");
    setFormCommand("");
    setFormArgs("");
    setFormEnv("");
  }

  function startEdit(name: string) {
    const cfg = draft[name];
    if (!cfg) return;
    setEditingName(name);
    setFormName(name);
    setFormCommand(cfg.command || "");
    setFormArgs((cfg.args || []).join(" "));
    const envLines = Object.entries(cfg.env || {})
      .map(([k, v]) => `${k}=${v}`)
      .join("\n");
    setFormEnv(envLines);
  }

  function commitForm() {
    if (!formName.trim() || !formCommand.trim()) return;
    const argsList = formArgs.trim() ? formArgs.trim().split(/\s+/) : [];
    const envObj: Record<string, string> = {};
    formEnv.split("\n").forEach((line) => {
      const [k, ...rest] = line.split("=");
      if (k && rest.length > 0) envObj[k.trim()] = rest.join("=").trim();
    });
    const next = { ...draft };
    // If editing under a different name, remove the old entry first.
    if (editingName && editingName !== formName.trim()) {
      delete next[editingName];
    }
    next[formName.trim()] = {
      type: "stdio",
      command: formCommand.trim(),
      ...(argsList.length ? { args: argsList } : {}),
      ...(Object.keys(envObj).length ? { env: envObj } : {}),
    };
    setDraft(next);
    resetForm();
  }

  function removeServer(name: string) {
    const next = { ...draft };
    delete next[name];
    setDraft(next);
    if (editingName === name) resetForm();
    setTestState((prev) => {
      const { [name]: _, ...rest } = prev;
      return rest;
    });
  }

  async function runTest(name: string) {
    // Tests run against the SAVED config — if there are unsaved drafts, warn.
    if (dirty) {
      toast({
        tone: "warning",
        title: "Guardá primero",
        body: "El test usa la config guardada en el agente. Apretá Guardar y volvé a probar.",
      });
      return;
    }
    setTestState((prev) => ({ ...prev, [name]: "loading" }));
    try {
      const result = await testAgentMcp(agentId, name);
      setTestState((prev) => ({ ...prev, [name]: result }));
    } catch (e: any) {
      setTestState((prev) => ({
        ...prev,
        [name]: {
          ok: false,
          tools: [],
          error: e?.message || "test request failed",
          error_kind: "spawn_failed",
          stderr_tail: null,
          duration_ms: 0,
        },
      }));
    }
  }

  function persist() {
    save.mutate(Object.keys(draft).length === 0 ? null : draft);
  }

  const dirty = JSON.stringify(draft) !== JSON.stringify(initial ?? {});
  const serverNames = Object.keys(draft);
  const isEditing = editingName !== null;

  return (
    <Card className="space-y-4">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold tracking-tight">MCP servers del agente</h2>
          <p className="text-xs text-[--color-fg-muted] mt-1 max-w-xl">
            Conecta MCP servers extra solo para este agente — Asana, Notion, Slack,
            tu propio server local. Se pasan a Claude vía{" "}
            <code className="font-mono">ClaudeAgentOptions.mcp_servers</code>. Los MCP
            globales del workspace siguen disponibles igual.
          </p>
        </div>
        <Button
          variant="primary"
          size="sm"
          onClick={persist}
          disabled={save.isPending || !dirty}
        >
          {save.isPending ? "Guardando…" : dirty ? "Guardar" : "Sin cambios"}
        </Button>
      </header>

      {serverNames.length === 0 ? (
        <Card className="text-center py-8">
          <p className="text-sm text-[--color-fg-muted]">
            Este agente todavía no tiene MCP servers extra. Agrega uno abajo.
          </p>
        </Card>
      ) : (
        <ul className="space-y-2">
          {serverNames.map((name) => {
            const cfg = draft[name];
            const result = testState[name];
            return (
              <li key={name} className="surface px-4 py-3 space-y-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1 space-y-1">
                    <p className="text-sm font-mono text-[--color-fg]">{name}</p>
                    <p className="text-[11px] text-[--color-fg-muted] font-mono break-all">
                      {cfg?.type ?? "stdio"} · {cfg?.command || cfg?.url}
                      {cfg?.args && ` ${cfg.args.join(" ")}`}
                    </p>
                    {cfg?.env && Object.keys(cfg.env).length > 0 && (
                      <p className="text-[10px] text-[--color-fg-subtle] font-mono">
                        env: {Object.keys(cfg.env).join(", ")}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      onClick={() => runTest(name)}
                      disabled={result === "loading"}
                      className="text-[11px] px-2 py-1 rounded border border-[--color-border] hover:border-[--color-accent] hover:text-[--color-accent] transition disabled:opacity-50"
                      title="Probar conexión"
                    >
                      {result === "loading" ? "Probando…" : "Probar"}
                    </button>
                    <button
                      onClick={() => startEdit(name)}
                      className="text-[11px] px-2 py-1 rounded border border-[--color-border] hover:border-[--color-accent] hover:text-[--color-accent] transition"
                      title="Editar"
                    >
                      Editar
                    </button>
                    <button
                      onClick={() => removeServer(name)}
                      className="opacity-50 hover:opacity-100 hover:text-[--color-error] transition px-1.5 py-0.5 text-base leading-none"
                      title="Quitar"
                    >
                      ×
                    </button>
                  </div>
                </div>
                {result && result !== "loading" && (
                  <McpTestBadge result={result} />
                )}
              </li>
            );
          })}
        </ul>
      )}

      <Card className="space-y-3 border border-dashed">
        <div className="flex items-center justify-between">
          <p className="text-xs uppercase tracking-widest text-[--color-fg-muted] font-medium">
            {isEditing ? `Editando: ${editingName}` : "Agregar MCP server (stdio)"}
          </p>
          {isEditing && (
            <button
              onClick={resetForm}
              className="text-[11px] text-[--color-fg-muted] hover:text-[--color-fg] underline"
            >
              cancelar edición
            </button>
          )}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label className="text-[11px] text-[--color-fg-muted]">Nombre</label>
            <input
              type="text"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="my-asana"
              className="w-full px-3 py-2 bg-transparent border border-[--color-border] rounded-md text-sm font-mono focus:outline-none focus:border-[--color-accent]"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-[11px] text-[--color-fg-muted]">Comando</label>
            <input
              type="text"
              value={formCommand}
              onChange={(e) => setFormCommand(e.target.value)}
              placeholder="npx"
              className="w-full px-3 py-2 bg-transparent border border-[--color-border] rounded-md text-sm font-mono focus:outline-none focus:border-[--color-accent]"
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <label className="text-[11px] text-[--color-fg-muted]">
            Args (separados por espacio)
          </label>
          <input
            type="text"
            value={formArgs}
            onChange={(e) => setFormArgs(e.target.value)}
            placeholder="-y @asana/mcp-server"
            className="w-full px-3 py-2 bg-transparent border border-[--color-border] rounded-md text-sm font-mono focus:outline-none focus:border-[--color-accent]"
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-[11px] text-[--color-fg-muted]">
            Variables de entorno (KEY=value, una por línea)
          </label>
          <textarea
            value={formEnv}
            onChange={(e) => setFormEnv(e.target.value)}
            rows={3}
            placeholder="ASANA_TOKEN=xxxx&#10;ASANA_WORKSPACE=123"
            spellCheck={false}
            className="w-full px-3 py-2 bg-transparent border border-[--color-border] rounded-md text-sm font-mono focus:outline-none focus:border-[--color-accent]"
          />
        </div>
        <div className="flex justify-end">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={commitForm}
            disabled={!formName.trim() || !formCommand.trim()}
          >
            {isEditing
              ? "Aplicar cambios al borrador (Guardar arriba para persistir)"
              : "Agregar (no guarda hasta tocar Guardar arriba)"}
          </Button>
        </div>
        <p className="text-[10.5px] text-[--color-fg-subtle]">
          Para SSE/HTTP, edita el JSON manualmente desde Edit spec por ahora.
          Próxima iteración: tipo SSE/HTTP en este formulario.
        </p>
      </Card>
    </Card>
  );
}


function McpTestBadge({ result }: { result: McpTestResult }) {
  const [open, setOpen] = useState(false);
  if (result.ok) {
    return (
      <div className="rounded border border-emerald-500/30 bg-emerald-500/5 px-3 py-2 space-y-1">
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-emerald-400 font-medium">
            OK · {result.tools.length} {result.tools.length === 1 ? "herramienta" : "herramientas"} ·{" "}
            {result.duration_ms} ms
          </span>
          {result.tools.length > 0 && (
            <button
              onClick={() => setOpen(!open)}
              className="text-[--color-fg-muted] hover:text-[--color-fg] underline"
            >
              {open ? "ocultar" : "ver tools"}
            </button>
          )}
        </div>
        {open && (
          <div className="text-[10px] font-mono text-[--color-fg-muted] flex flex-wrap gap-1">
            {result.tools.map((t) => (
              <span key={t} className="px-1.5 py-0.5 rounded bg-[--color-bg]">
                {t}
              </span>
            ))}
          </div>
        )}
      </div>
    );
  }
  // Error variant
  return (
    <div className="rounded border border-red-500/30 bg-red-500/5 px-3 py-2 space-y-1">
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-red-400 font-medium">
          Falló · {result.error_kind || "error"} · {result.duration_ms} ms
        </span>
        {(result.error || result.stderr_tail) && (
          <button
            onClick={() => setOpen(!open)}
            className="text-[--color-fg-muted] hover:text-[--color-fg] underline"
          >
            {open ? "ocultar" : "ver detalle"}
          </button>
        )}
      </div>
      {open && (
        <div className="text-[10.5px] text-[--color-fg-muted] space-y-1">
          {result.error && (
            <p className="whitespace-pre-wrap">{result.error}</p>
          )}
          {result.stderr_tail && (
            <pre className="text-[10px] font-mono bg-[--color-bg] p-2 rounded overflow-x-auto whitespace-pre-wrap">
              {result.stderr_tail}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}


function ProjectMover({ agent }: { agent: any }) {
  const qc = useQueryClient();
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => fetchProjects(false) });
  const move = useMutation({
    mutationFn: (slug: string) => moveAgent(agent.id, slug),
    onSuccess: () => {
      toast({ tone: "success", title: "Agente reasignado" });
      qc.invalidateQueries({ queryKey: ["agent", agent.id] });
      qc.invalidateQueries({ queryKey: ["agents"] });
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: (e: Error) =>
      toast({ tone: "error", title: "No se pudo mover", body: e.message }),
  });
  return (
    <Select
      value={agent.project_slug ?? "workspace"}
      onChange={(e) => {
        if (e.target.value !== agent.project_slug) move.mutate(e.target.value);
      }}
      className="text-xs h-8 py-0"
      disabled={move.isPending || projects.isLoading}
      title="Mover a otro proyecto"
    >
      {(projects.data ?? []).map((p) => (
        <option key={p.slug} value={p.slug}>
          {p.name}
        </option>
      ))}
    </Select>
  );
}

function ToolsPane({ agentId }: { agentId: number }) {
  const qc = useQueryClient();
  const source = useQuery({
    queryKey: ["agent-source", agentId],
    queryFn: () => fetchAgentSource(agentId),
  });
  const initial = source.data?.tools ?? null;
  const [draft, setDraft] = useState<string[] | null>(null);
  // Sync draft when the source loads or refetches.
  useEffect(() => {
    setDraft(initial ? [...initial] : null);
  }, [initial?.join(",")]);

  const save = useMutation({
    mutationFn: (tools: string[] | null) => {
      if (!source.data) throw new Error("source not loaded");
      const s = source.data as AgentSource;
      return updateAgent(agentId, {
        name: s.name,
        model: s.model,
        description: s.description,
        body: s.body,
        project_slug: s.project_slug ?? undefined,
        tools,
      });
    },
    onSuccess: () => {
      toast({ tone: "success", title: "Tools actualizadas" });
      qc.invalidateQueries({ queryKey: ["agent-source", agentId] });
      qc.invalidateQueries({ queryKey: ["agent", agentId] });
    },
    onError: (e: Error) =>
      toast({ tone: "error", title: "No se pudo guardar", body: e.message }),
  });

  if (source.isLoading) {
    return <p className="text-sm text-[--color-fg-muted]">Cargando spec…</p>;
  }
  const isWhitelisted = draft !== null;

  function toggle(name: string) {
    if (draft === null) {
      // turning off "use full preset" → start with the existing preset list
      setDraft([name]);
      return;
    }
    if (draft.includes(name)) {
      const next = draft.filter((t) => t !== name);
      setDraft(next.length === 0 ? null : next);
    } else {
      setDraft([...draft, name]);
    }
  }

  function reset() {
    setDraft(null);
  }

  function persist() {
    save.mutate(draft);
  }

  return (
    <Card className="space-y-4">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold tracking-tight">Tools del agente</h2>
          <p className="text-xs text-[--color-fg-muted] mt-1 max-w-xl">
            Decidí qué herramientas built-in puede usar este agente. Sin selección, hereda
            el preset completo de Claude Code (todas las tools). Restringilo cuando quieras
            un agente solo-lectura, un revisor sin Bash, o un investigador con WebFetch.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isWhitelisted && (
            <Button variant="ghost" size="sm" onClick={reset} disabled={save.isPending}>
              Volver al preset
            </Button>
          )}
          <Button
            variant="primary"
            size="sm"
            onClick={persist}
            disabled={save.isPending || (draft?.join(",") === (initial?.join(",") ?? null))}
          >
            {save.isPending ? "Guardando…" : "Guardar"}
          </Button>
        </div>
      </header>
      {!isWhitelisted && (
        <div className="text-xs text-[--color-fg-muted] surface px-3 py-2 inline-flex items-center gap-2">
          <Wrench size={12} className="text-[--color-accent-strong]" />
          Modo preset completo: marca una tool abajo para activar el whitelist.
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {AVAILABLE_TOOLS.map((t) => {
          const checked = isWhitelisted ? draft!.includes(t.name) : true;
          return (
            <label
              key={t.name}
              className={`flex items-start gap-3 px-3 py-2 rounded-md border cursor-pointer transition ${
                isWhitelisted && !checked
                  ? "border-[--color-border] bg-transparent opacity-50"
                  : "border-[--color-border]"
              }`}
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={() => toggle(t.name)}
                className="mt-0.5 accent-[--color-accent-strong]"
              />
              <div className="text-xs">
                <p className="font-mono text-[--color-fg]">{t.name}</p>
                <p className="text-[--color-fg-muted] mt-0.5">{t.description}</p>
              </div>
            </label>
          );
        })}
      </div>
      <p className="text-[11px] text-[--color-fg-subtle]">
        El cambio se persiste reescribiendo el frontmatter del{" "}
        <code className="font-mono">.md</code>: <code className="font-mono">tools: [Read, Grep, …]</code>.
        MCP tools custom se manejan en una capa siguiente.
      </p>
    </Card>
  );
}
