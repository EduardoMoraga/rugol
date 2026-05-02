"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAgent, fetchAgentRuns } from "@/lib/api";
import { StatusBadge } from "@/components/dashboard/status-badge";

export default function AgentDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const agentId = Number(id);

  const agent = useQuery({ queryKey: ["agent", agentId], queryFn: () => fetchAgent(agentId) });
  const runs = useQuery({ queryKey: ["agent-runs", agentId], queryFn: () => fetchAgentRuns(agentId) });

  if (agent.isLoading) return <p className="p-6">Loading…</p>;
  if (!agent.data) return <p className="p-6">Not found.</p>;

  return (
    <div className="p-6 space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">{agent.data.name}</h1>
            <StatusBadge status={agent.data.status} />
          </div>
          <p className="text-sm text-[--color-fg-muted] mt-1">{agent.data.description}</p>
          <p className="text-xs text-[--color-fg-muted] mt-1 font-mono">model: {agent.data.model}</p>
        </div>
        <button className="card hover:bg-[--color-border] transition px-4 py-2 text-sm">
          Run now
        </button>
      </header>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[--color-fg-muted] mb-3">
          Recent runs
        </h2>
        {runs.data && runs.data.length === 0 && (
          <p className="text-sm text-[--color-fg-muted]">No runs yet.</p>
        )}
        {runs.data && runs.data.length > 0 && (
          <div className="space-y-2">
            {runs.data.map((r) => (
              <div key={r.id} className="card flex items-center justify-between text-sm">
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono text-[--color-fg-muted]">#{r.id}</span>
                  <StatusBadge status={r.status} />
                  <span className="text-xs text-[--color-fg-muted]">{r.source}</span>
                </div>
                <div className="flex items-center gap-4 text-xs text-[--color-fg-muted]">
                  <span>{r.input_tokens + r.output_tokens} tokens</span>
                  <span>${r.cost_usd.toFixed(4)}</span>
                  <span>{new Date(r.started_at).toLocaleString()}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
