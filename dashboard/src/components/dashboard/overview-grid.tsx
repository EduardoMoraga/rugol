"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchAgents, fetchHealth, fetchRecentRuns } from "@/lib/api";

function StatCard({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="card">
      <p className="text-xs uppercase tracking-wide text-[--color-fg-muted]">{label}</p>
      <p className="text-2xl font-semibold mt-1 font-mono">{value}</p>
      {hint && <p className="text-xs text-[--color-fg-muted] mt-1">{hint}</p>}
    </div>
  );
}

export function OverviewGrid() {
  const agents = useQuery({ queryKey: ["agents"], queryFn: fetchAgents, refetchInterval: 5000 });
  const runs = useQuery({ queryKey: ["recent-runs"], queryFn: fetchRecentRuns, refetchInterval: 5000 });
  const health = useQuery({ queryKey: ["health"], queryFn: fetchHealth, refetchInterval: 5000 });

  const totalAgents = agents.data?.length ?? 0;
  const activeAgents = agents.data?.filter((a) => a.status === "running").length ?? 0;
  const last24h = runs.data?.filter((r) => Date.now() - new Date(r.started_at).getTime() < 86_400_000).length ?? 0;
  const cost24h = runs.data
    ?.filter((r) => Date.now() - new Date(r.started_at).getTime() < 86_400_000)
    .reduce((s, r) => s + (r.cost_usd || 0), 0) ?? 0;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <StatCard label="Agents" value={totalAgents} hint={`${activeAgents} active`} />
      <StatCard label="Runs · 24h" value={last24h} />
      <StatCard label="Cost · 24h" value={`$${cost24h.toFixed(3)}`} />
      <StatCard
        label="Core"
        value={health.data?.status ?? "—"}
        hint={health.data?.version ? `v${health.data.version}` : undefined}
      />
    </div>
  );
}
