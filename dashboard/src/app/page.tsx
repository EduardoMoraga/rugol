"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Plus, Rocket, Settings, Sparkles, Zap } from "lucide-react";
import { fetchAgents, fetchHealth, fetchRecentRuns } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Stat } from "@/components/ui/card";
import { ActivityFeed } from "@/components/dashboard/activity-feed";
import { StatusBadge } from "@/components/dashboard/status-badge";

export default function OperationsPage() {
  const agents = useQuery({ queryKey: ["agents"], queryFn: fetchAgents, refetchInterval: 5000 });
  const runs = useQuery({ queryKey: ["recent-runs"], queryFn: fetchRecentRuns, refetchInterval: 5000 });
  const health = useQuery({ queryKey: ["health"], queryFn: fetchHealth, refetchInterval: 5000 });

  const totalAgents = agents.data?.length ?? 0;
  const activeAgents = (agents.data ?? []).filter((a) => a.status === "running").length;
  const last24h = (runs.data ?? []).filter(
    (r) => Date.now() - new Date(r.started_at).getTime() < 86_400_000,
  );
  const cost24h = last24h.reduce((s, r) => s + (Number(r.cost_usd) || 0), 0);
  const tokens24h = last24h.reduce(
    (s, r) => s + (Number(r.input_tokens) || 0) + (Number(r.output_tokens) || 0),
    0,
  );
  const liveRuns = (runs.data ?? []).filter((r) => r.status === "running").slice(0, 5);

  return (
    <div className="p-8 space-y-8 max-w-[1400px] mx-auto">
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-[--color-border] pb-6">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-semibold tracking-tight">Operations</h1>
            <span
              className={`pill ${
                health.data?.status === "ok" ? "pill-running" : "pill-error"
              }`}
            >
              {health.data ? `core ${health.data.status} · v${health.data.version}` : "connecting…"}
            </span>
          </div>
          <p className="text-sm text-[--color-fg-muted]">
            Live status across every registered agent. Drop a markdown file in your agents folder, paste a
            Telegram token, and you're operating.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/architect">
            <Button variant="primary">
              <Sparkles size={14} /> Design with Architect
            </Button>
          </Link>
          <Link href="/agents/new">
            <Button variant="secondary">
              <Plus size={14} /> New agent
            </Button>
          </Link>
          <Link href="/settings">
            <Button variant="ghost">
              <Settings size={14} /> Settings
            </Button>
          </Link>
        </div>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat
          label="Agents"
          value={totalAgents}
          hint={activeAgents ? `${activeAgents} running` : "all idle"}
          accent={activeAgents > 0}
        />
        <Stat label="Runs · 24h" value={last24h.length} />
        <Stat
          label="Tokens · 24h"
          value={tokens24h >= 1000 ? `${(tokens24h / 1000).toFixed(1)}k` : tokens24h}
        />
        <Stat label="Cost · 24h" value={`$${cost24h.toFixed(3)}`} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <section className="lg:col-span-2 space-y-6">
          <div>
            <div className="flex items-baseline justify-between mb-3">
              <h2 className="text-sm font-semibold tracking-tight">Live runs</h2>
              <Link href="/agents" className="text-xs text-[--color-fg-muted] hover:text-[--color-fg]">
                All agents →
              </Link>
            </div>
            {liveRuns.length === 0 ? (
              <div className="surface p-8 text-center space-y-3">
                <Zap size={24} className="mx-auto text-[--color-fg-subtle]" />
                <div>
                  <p className="text-sm font-medium">Nothing running right now</p>
                  <p className="text-xs text-[--color-fg-muted] mt-1">
                    Click <span className="text-[--color-accent-strong]">Run</span> on any agent or wait
                    for a schedule to fire.
                  </p>
                </div>
              </div>
            ) : (
              <div className="space-y-1.5">
                {liveRuns.map((r) => (
                  <Link
                    key={r.id}
                    href={`/runs/${r.id}`}
                    className="surface surface-hover px-4 py-3 flex items-center justify-between text-sm group"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="text-xs font-mono text-[--color-fg-subtle]">#{r.id}</span>
                      <StatusBadge status={r.status} />
                      <span className="text-xs text-[--color-fg-muted]">{r.source}</span>
                    </div>
                    <span className="text-xs text-[--color-fg-muted] font-mono">
                      started {new Date(r.started_at).toLocaleTimeString()}
                    </span>
                  </Link>
                ))}
              </div>
            )}
          </div>

          <div>
            <div className="flex items-baseline justify-between mb-3">
              <h2 className="text-sm font-semibold tracking-tight">Agents</h2>
              <Link href="/agents" className="text-xs text-[--color-fg-muted] hover:text-[--color-fg]">
                Manage →
              </Link>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {(agents.data ?? []).slice(0, 6).map((a) => (
                <Link
                  key={a.id}
                  href={`/agents/${a.id}`}
                  className="surface surface-hover px-4 py-3 flex items-center justify-between text-sm"
                >
                  <div className="min-w-0">
                    <p className="font-medium truncate">{a.name}</p>
                    <p className="text-[11px] font-mono text-[--color-fg-subtle] mt-0.5">
                      {a.model.replace("claude-", "")}
                    </p>
                  </div>
                  <StatusBadge status={a.status} />
                </Link>
              ))}
              {(agents.data ?? []).length === 0 && (
                <Link
                  href="/architect"
                  className="surface surface-hover px-5 py-6 col-span-full text-center group border-[--color-accent]/30 bg-[--color-accent-soft]/40"
                >
                  <Sparkles size={22} className="mx-auto text-[--color-accent-strong]" />
                  <p className="text-sm font-medium mt-2">Start with Architect</p>
                  <p className="text-xs text-[--color-fg-muted] mt-1 max-w-md mx-auto">
                    Describe your idea in one line — Architect proposes the agents, skills,
                    schedules, and ontology seeds you'd otherwise sketch on a napkin.
                  </p>
                </Link>
              )}
            </div>
          </div>
        </section>

        <aside className="lg:row-span-2 h-[640px]">
          <ActivityFeed limit={40} />
        </aside>
      </div>
    </div>
  );
}
