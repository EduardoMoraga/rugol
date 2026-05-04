"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { type Agent } from "@/lib/api";
import { StatusBadge } from "./status-badge";
import { ProjectBadge } from "@/components/projects/project-badge";
import { useI18n } from "@/lib/i18n";

export function AgentCard({ agent }: { agent: Agent }) {
  const { t } = useI18n();
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

      {agent.project_slug && (
        <div className="mb-3">
          {/* asLink=false: AgentCard already wraps the whole tile in <Link>;
              nesting another <a> here triggers React's "<a> inside <a>"
              hydration error. */}
          <ProjectBadge
            slug={agent.project_slug}
            name={agent.project_name}
            color={agent.project_color}
            icon={agent.project_icon}
            asLink={false}
          />
        </div>
      )}

      {agent.description && (
        <p className="text-sm text-[--color-fg-muted] line-clamp-2 leading-relaxed">
          {agent.description}
        </p>
      )}

      <footer className="flex items-center justify-between mt-4 pt-4 border-t border-[--color-border]">
        <span className="text-[11px] text-[--color-fg-subtle]">
          {agent.last_run_at
            ? `${t("agentCard.lastRun")} ${new Date(agent.last_run_at).toLocaleString()}`
            : t("agentCard.neverRun")}
        </span>
        <span className="text-[11px] text-[--color-fg-muted] group-hover:text-[--color-accent-strong] inline-flex items-center gap-0.5 transition-colors">
          {t("agentCard.open")} <ChevronRight size={11} />
        </span>
      </footer>
    </Link>
  );
}
