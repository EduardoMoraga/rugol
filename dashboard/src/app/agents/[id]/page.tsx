"use client";

import { FormEvent, use, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { fetchAgent, fetchAgentRuns, runAgentNow } from "@/lib/api";
import { StatusBadge } from "@/components/dashboard/status-badge";

export default function AgentDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const agentId = Number(id);
  const router = useRouter();
  const qc = useQueryClient();

  const agent = useQuery({
    queryKey: ["agent", agentId],
    queryFn: () => fetchAgent(agentId),
    refetchInterval: (q) => (q.state.data?.status === "running" ? 3000 : false),
  });
  const runs = useQuery({
    queryKey: ["agent-runs", agentId],
    queryFn: () => fetchAgentRuns(agentId),
    refetchInterval: 5000,
  });

  const [prompt, setPrompt] = useState("");
  const run = useMutation({
    mutationFn: (p: string) => runAgentNow(agentId, p),
    onSuccess: ({ run_id }) => {
      qc.invalidateQueries({ queryKey: ["agent-runs", agentId] });
      qc.invalidateQueries({ queryKey: ["agent", agentId] });
      setPrompt("");
      router.push(`/runs/${run_id}`);
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!prompt.trim()) return;
    run.mutate(prompt.trim());
  }

  if (agent.isLoading) return <p className="p-6 text-sm text-[--color-fg-muted]">Loading…</p>;
  if (!agent.data) return <p className="p-6 text-sm text-[--color-fg-muted]">Not found.</p>;

  const a = agent.data;
  const totalRuns = runs.data?.length ?? 0;
  const running = a.status === "running";

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <header className="space-y-2">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">{a.name}</h1>
          <StatusBadge status={a.status} />
        </div>
        {a.description && (
          <p className="text-sm text-[--color-fg-muted] max-w-2xl">{a.description}</p>
        )}
        <p className="text-xs text-[--color-fg-muted] font-mono">model: {a.model}</p>
      </header>

      <form onSubmit={onSubmit} className="card space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[--color-fg-muted]">
          Run now
        </h2>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          placeholder={`Ask ${a.name} to do something…`}
          className="w-full bg-[--color-bg] border border-[--color-border] rounded px-3 py-2 text-sm"
        />
        <div className="flex items-center justify-between">
          <span className="text-xs text-[--color-fg-muted]">
            {running
              ? "This agent is currently running another task — your run will queue."
              : "You'll be redirected to the live run view."}
          </span>
          <button
            type="submit"
            disabled={run.isPending || !prompt.trim()}
            className="text-sm flex items-center gap-1 px-4 py-1.5 rounded border border-[--color-border] hover:bg-[--color-border] transition disabled:opacity-50"
          >
            <Play size={12} /> {run.isPending ? "Queueing…" : "Run"}
          </button>
        </div>
        {run.isError && (
          <p className="text-xs text-[--color-error]">Failed to queue — is the backend up?</p>
        )}
      </form>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[--color-fg-muted]">
          Recent runs ({totalRuns})
        </h2>
        {runs.data && runs.data.length === 0 && (
          <p className="text-sm text-[--color-fg-muted]">No runs yet — kick the tires above.</p>
        )}
        {runs.data && runs.data.length > 0 && (
          <div className="space-y-2">
            {runs.data.map((r) => (
              <Link
                key={r.id}
                href={`/runs/${r.id}`}
                className="card flex items-center justify-between text-sm hover:border-[--color-fg-muted]/40 transition"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="text-xs font-mono text-[--color-fg-muted]">#{r.id}</span>
                  <StatusBadge status={r.status} />
                  <span className="text-xs text-[--color-fg-muted]">{r.source}</span>
                  <span className="text-xs text-[--color-fg-muted] truncate hidden md:inline">
                    {r.prompt}
                  </span>
                </div>
                <div className="flex items-center gap-4 text-xs text-[--color-fg-muted] shrink-0">
                  <span>{(r.input_tokens + r.output_tokens).toLocaleString()} tok</span>
                  <span>${r.cost_usd.toFixed(4)}</span>
                  <span>{new Date(r.started_at).toLocaleString()}</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
