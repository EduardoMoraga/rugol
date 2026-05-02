"use client";

import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { AgentCard } from "@/components/dashboard/agent-card";
import { EmptyState } from "@/components/dashboard/empty-state";
import { fetchAgents, type Agent } from "@/lib/api";

export default function AgentsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["agents"],
    queryFn: fetchAgents,
    refetchInterval: 5000,
  });

  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (data ?? []).filter((a: Agent) => {
      if (statusFilter !== "all" && a.status !== statusFilter) return false;
      if (!q) return true;
      return (
        a.name.toLowerCase().includes(q) ||
        a.description.toLowerCase().includes(q) ||
        a.model.toLowerCase().includes(q)
      );
    });
  }, [data, query, statusFilter]);

  const totalAgents = data?.length ?? 0;

  return (
    <div className="p-6 space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Agents</h1>
        <p className="text-sm text-[--color-fg-muted]">
          {totalAgents} registered · {filtered.length} shown
        </p>
      </header>

      {totalAgents > 0 && (
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[240px] max-w-md">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[--color-fg-muted]" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by name, description, or model…"
              className="w-full bg-[--color-bg] border border-[--color-border] rounded pl-8 pr-3 py-2 text-sm"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-[--color-bg] border border-[--color-border] rounded px-3 py-2 text-sm"
          >
            <option value="all">All statuses</option>
            <option value="idle">Idle</option>
            <option value="running">Running</option>
            <option value="error">Error</option>
            <option value="offline">Offline</option>
          </select>
        </div>
      )}

      {isLoading && <p className="text-sm text-[--color-fg-muted]">Loading…</p>}
      {error && <p className="text-sm text-[--color-error]">Failed to load agents.</p>}

      {data && data.length === 0 && (
        <EmptyState
          title="No agents yet"
          body="Drop a markdown file under agents-templates/ (or your AGENTS_DIR) and it'll appear here within seconds."
          ctaLabel="See examples"
          ctaHref="https://github.com/eduardomoraga/rogologo/tree/main/agents-templates"
        />
      )}

      {data && data.length > 0 && filtered.length === 0 && (
        <EmptyState
          title="Nothing matches"
          body="No agent matches your search and status filter."
        />
      )}

      {filtered.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((a: Agent) => <AgentCard key={a.id} agent={a} />)}
        </div>
      )}
    </div>
  );
}
