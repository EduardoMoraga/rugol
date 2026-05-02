"use client";

import { useQuery } from "@tanstack/react-query";
import { AgentCard } from "@/components/dashboard/agent-card";
import { EmptyState } from "@/components/dashboard/empty-state";
import { fetchAgents, type Agent } from "@/lib/api";

export default function AgentsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["agents"],
    queryFn: fetchAgents,
  });

  return (
    <div className="p-6 space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Agents</h1>
        <p className="text-sm text-[--color-fg-muted]">
          {data?.length ?? 0} agent{data?.length === 1 ? "" : "s"} registered
        </p>
      </header>

      {isLoading && <p className="text-sm text-[--color-fg-muted]">Loading…</p>}
      {error && <p className="text-sm text-[--color-error]">Failed to load agents.</p>}

      {data && data.length === 0 && (
        <EmptyState
          title="No agents yet"
          body="Drop a markdown file under agents/ and it'll appear here within seconds."
          ctaLabel="See examples"
          ctaHref="https://github.com/eduardomoraga/rogologo/tree/main/agents-templates"
        />
      )}

      {data && data.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {data.map((a: Agent) => <AgentCard key={a.id} agent={a} />)}
        </div>
      )}
    </div>
  );
}
