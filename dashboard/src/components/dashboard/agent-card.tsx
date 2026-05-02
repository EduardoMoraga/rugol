"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { type Agent } from "@/lib/api";
import { StatusBadge } from "./status-badge";

export function AgentCard({ agent }: { agent: Agent }) {
  return (
    <Link
      href={`/agents/${agent.id}`}
      className="surface surface-hover p-5 group block"
    >
      <header className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <h3 className="font-semibold tracking-tight truncate">{agent.name}</h3>
          <p className="text-[11px] text-[--color-fg-subtle] font-mono mt-0.5">
            {agent.model.replace("claude-", "")}
          </p>
        </div>
        <StatusBadge status={agent.status} />
      </header>

      {agent.description && (
        <p className="text-sm text-[--color-fg-muted] line-clamp-2 leading-relaxed">
          {agent.description}
        </p>
      )}

      <footer className="flex items-center justify-between mt-4 pt-4 border-t border-[--color-border]">
        <span className="text-[11px] text-[--color-fg-subtle]">
          {agent.last_run_at
            ? `last run ${new Date(agent.last_run_at).toLocaleString()}`
            : "never run"}
        </span>
        <span className="text-[11px] text-[--color-fg-muted] group-hover:text-[--color-accent-strong] inline-flex items-center gap-0.5 transition-colors">
          Open <ChevronRight size={11} />
        </span>
      </footer>
    </Link>
  );
}
