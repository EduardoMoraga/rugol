"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { type Agent } from "@/lib/api";
import { StatusBadge } from "./status-badge";

export function AgentCard({ agent }: { agent: Agent }) {
  return (
    <Link
      href={`/agents/${agent.id}`}
      className="card hover:border-[--color-fg-muted]/40 transition group block"
    >
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold truncate">{agent.name}</h3>
          <p className="text-xs text-[--color-fg-muted] font-mono">{agent.model}</p>
        </div>
        <StatusBadge status={agent.status} />
      </header>

      {agent.description && (
        <p className="text-sm text-[--color-fg-muted] mt-3 line-clamp-2">{agent.description}</p>
      )}

      <footer className="flex items-center justify-between mt-4">
        <span className="text-xs text-[--color-fg-muted]">
          {agent.last_run_at
            ? `last run ${new Date(agent.last_run_at).toLocaleString()}`
            : "never run"}
        </span>
        <span className="text-xs text-[--color-fg-muted] group-hover:text-[--color-fg] inline-flex items-center gap-0.5 transition">
          Open <ChevronRight size={12} />
        </span>
      </footer>
    </Link>
  );
}
