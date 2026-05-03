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
} from "lucide-react";
import {
  AVAILABLE_TOOLS,
  fetchAgent,
  fetchAgentRuns,
  fetchAgentSource,
  fetchOntologyEdges,
  fetchOntologyNodes,
  fetchProjects,
  moveAgent,
  updateAgent,
  type AgentSource,
} from "@/lib/api";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { Button } from "@/components/ui/button";
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
        </TabsList>

        <TabsContent value="overview" className="mt-5 space-y-6">
          <AgentChat
            agentId={agentId}
            agentName={a.name}
            modelLabel={a.model}
            agentBusy={a.status === "running"}
            projectSlug={a.project_slug}
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
          <MemoryPane agentName={a.name} />
        </TabsContent>

        <TabsContent value="tools" className="mt-5">
          <ToolsPane agentId={agentId} />
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

function MemoryPane({ agentName }: { agentName: string }) {
  const nodes = useQuery({ queryKey: ["onto-nodes"], queryFn: fetchOntologyNodes });
  const edges = useQuery({ queryKey: ["onto-edges"], queryFn: fetchOntologyEdges });

  // We don't yet have per-agent ontology filtering on the backend, so we surface all triples
  // with a hint about how the linkage will tighten later.
  const nodeById = new Map<number, { label: string; type: string }>();
  (nodes.data ?? []).forEach((n) => nodeById.set(n.id, { label: n.label, type: n.type }));
  const triples = (edges.data ?? []).slice(0, 30).map((e) => ({
    src: nodeById.get(e.src)?.label ?? `#${e.src}`,
    predicate: e.predicate,
    dst: nodeById.get(e.dst)?.label ?? `#${e.dst}`,
  }));

  return (
    <div className="space-y-4">
      <Card>
        <header className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold tracking-tight inline-flex items-center gap-2">
            <Network size={13} className="text-[--color-accent-strong]" />
            Shared ontology
          </h2>
          <Link href="/ontology" className="text-xs text-[--color-fg-muted] hover:text-[--color-fg]">
            Open graph →
          </Link>
        </header>
        {triples.length === 0 ? (
          <p className="text-sm text-[--color-fg-muted]">
            No facts in the graph yet. As <code className="font-mono">{agentName}</code> runs, it can
            write triples that any other agent can read.
          </p>
        ) : (
          <ul className="text-xs font-mono space-y-1 text-[--color-fg-muted]">
            {triples.map((t, i) => (
              <li key={i} className="flex items-center gap-2">
                <span className="text-[--color-fg]">{t.src}</span>
                <span className="text-[--color-accent-strong]">{t.predicate}</span>
                <span className="text-[--color-fg]">{t.dst}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="text-[11px] text-[--color-fg-subtle] mt-3">
          Per-agent provenance filtering is roadmap (each edge already records the run that wrote it
          via <code className="font-mono">created_by_run</code>).
        </p>
      </Card>
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
          Modo preset completo: tildá una tool abajo para activar el whitelist.
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
