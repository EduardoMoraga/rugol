"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, Pencil, FileCode2 } from "lucide-react";
import { fetchAgent, fetchAgentRuns, runAgentNow } from "@/lib/api";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { PageHeader, Card, CardSection, Stat } from "@/components/ui/card";
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
      toast({ tone: "success", title: `Run #${run_id} queued`, body: "Redirecting to live view." });
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
  const totalCost = (runs.data ?? []).reduce((s, r) => s + (r.cost_usd ?? 0), 0);
  const successRate =
    totalRuns === 0
      ? 0
      : ((runs.data ?? []).filter((r) => r.status === "completed").length / totalRuns) * 100;

  return (
    <div className="p-8 space-y-8 max-w-5xl mx-auto">
      <PageHeader
        title={a.name}
        description={a.description || "No description provided."}
        actions={
          <>
            <Link href={`/agents/${agentId}/edit`}>
              <Button variant="secondary" size="sm">
                <Pencil size={13} /> Edit spec
              </Button>
            </Link>
          </>
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

      <Card>
        <form onSubmit={onSubmit} className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold tracking-tight">Run now</h2>
            <span className="text-xs text-[--color-fg-muted] font-mono inline-flex items-center gap-1">
              <FileCode2 size={11} /> source: {a.model}
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
                ? "This agent is busy — your run will queue behind the current one."
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
        {runs.data && runs.data.length === 0 ? (
          <Card>
            <p className="text-sm text-[--color-fg-muted]">No runs yet — kick the tires above.</p>
          </Card>
        ) : (
          <div className="space-y-1.5">
            {(runs.data ?? []).map((r) => (
              <Link
                key={r.id}
                href={`/runs/${r.id}`}
                className="surface surface-hover px-4 py-3 flex items-center justify-between text-sm group"
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
    </div>
  );
}
