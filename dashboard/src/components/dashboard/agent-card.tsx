"use client";

import Link from "next/link";
import { useMutation } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { runAgentNow, type Agent } from "@/lib/api";
import { StatusBadge } from "./status-badge";

export function AgentCard({ agent }: { agent: Agent }) {
  const run = useMutation({
    mutationFn: () => runAgentNow(agent.id, "Tick — auto-triggered from dashboard."),
  });

  return (
    <article className="card hover:border-[--color-fg-muted]/40 transition group">
      <header className="flex items-start justify-between gap-3">
        <Link href={`/agents/${agent.id}`} className="min-w-0">
          <h3 className="font-semibold truncate">{agent.name}</h3>
          <p className="text-xs text-[--color-fg-muted] font-mono">{agent.model}</p>
        </Link>
        <StatusBadge status={agent.status} />
      </header>

      {agent.description && (
        <p className="text-sm text-[--color-fg-muted] mt-3 line-clamp-2">{agent.description}</p>
      )}

      <footer className="flex items-center justify-between mt-4">
        <span className="text-xs text-[--color-fg-muted]">
          {agent.last_run_at
            ? `last run ${new Date(agent.last_run_at).toLocaleTimeString()}`
            : "never run"}
        </span>
        <button
          onClick={() => run.mutate()}
          disabled={run.isPending}
          className="text-xs flex items-center gap-1 px-2 py-1 rounded border border-[--color-border] hover:bg-[--color-border] transition disabled:opacity-50"
        >
          <Play size={12} /> {run.isPending ? "Queued" : "Run"}
        </button>
      </footer>
    </article>
  );
}
