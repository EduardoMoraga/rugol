"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Play,
  Pencil,
  FileCode2,
  Wrench,
  BookOpen,
  Network,
  ListTree,
} from "lucide-react";
import {
  fetchAgent,
  fetchAgentRuns,
  fetchAgentSource,
  fetchOntologyEdges,
  fetchOntologyNodes,
  runAgentNow,
} from "@/lib/api";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Card, CardSection, PageHeader, Stat } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { toast } from "@/components/ui/toast";

export default function AgentDetail() {
  const params = useParams<{ id: string }>();
  const agentId = Number(params.id);
  const router = useRouter();
  const qc = useQueryClient();

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

  const [prompt, setPrompt] = useState("");
  const run = useMutation({
    mutationFn: (p: string) => runAgentNow(agentId, p),
    onSuccess: ({ run_id }) => {
      qc.invalidateQueries({ queryKey: ["agent-runs", agentId] });
      qc.invalidateQueries({ queryKey: ["agent", agentId] });
      setPrompt("");
      toast({ tone: "success", title: `Run #${run_id} queued` });
      router.push(`/runs/${run_id}`);
    },
    onError: (e: Error) => toast({ tone: "error", title: "Failed to queue run", body: e.message }),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!prompt.trim()) return;
    run.mutate(prompt.trim());
  }

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
          <Link href={`/agents/${agentId}/edit`}>
            <Button variant="secondary" size="sm">
              <Pencil size={13} /> Edit spec
            </Button>
          </Link>
        }
      />

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
          <Card>
            <form onSubmit={onSubmit} className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold tracking-tight">Run now</h2>
                <span className="text-xs text-[--color-fg-muted] font-mono">
                  {a.model}
                </span>
              </div>
              <Textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={3}
                placeholder={`Ask ${a.name} to do something specific…`}
              />
              <div className="flex items-center justify-between">
                <span className="text-xs text-[--color-fg-muted]">
                  {a.status === "running"
                    ? "This agent is busy — your run will queue."
                    : "You'll be redirected to the live run view."}
                </span>
                <Button type="submit" variant="primary" disabled={run.isPending || !prompt.trim()}>
                  <Play size={13} /> {run.isPending ? "Queueing…" : "Run"}
                </Button>
              </div>
            </form>
          </Card>

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
          <ToolsPane />
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

function ToolsPane() {
  const tools = [
    { name: "Read", body: "Read any file under the workspace." },
    { name: "Write", body: "Create new files or overwrite existing ones." },
    { name: "Edit", body: "Make targeted edits to a file." },
    { name: "Glob", body: "Find files by pattern (e.g. **/*.tsx)." },
    { name: "Grep", body: "Search file contents with ripgrep." },
    { name: "Bash", body: "Run shell commands inside the workspace." },
    { name: "WebFetch", body: "Pull content from a public URL." },
    { name: "TaskCreate", body: "Plan multi-step work as tracked tasks." },
  ];
  return (
    <Card className="space-y-3">
      <header>
        <h2 className="text-sm font-semibold tracking-tight">Available tools</h2>
        <p className="text-xs text-[--color-fg-muted] mt-1">
          Inherited from Claude Code via{" "}
          <code className="font-mono text-[--color-accent-strong]">claude-agent-sdk</code> with the
          <code className="font-mono ml-1">claude_code</code> preset. Per-agent tool whitelisting
          is on the roadmap.
        </p>
      </header>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {tools.map((t) => (
          <div key={t.name} className="flex items-start gap-3 px-3 py-2 rounded-md border border-[--color-border]">
            <Wrench size={12} className="mt-1 text-[--color-fg-subtle]" />
            <div className="text-xs">
              <p className="font-mono text-[--color-fg]">{t.name}</p>
              <p className="text-[--color-fg-muted] mt-0.5">{t.body}</p>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
