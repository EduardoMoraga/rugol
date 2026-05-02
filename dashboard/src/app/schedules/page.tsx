"use client";

import { FormEvent, useMemo, useState } from "react";
import Link from "next/link";
import { Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createSchedule,
  deleteSchedule,
  fetchAgents,
  fetchSchedules,
  type Agent,
} from "@/lib/api";
import { EmptyState } from "@/components/dashboard/empty-state";

const CRON_PRESETS = [
  { label: "Every 5 minutes", expr: "*/5 * * * *" },
  { label: "Hourly (top of hour)", expr: "0 * * * *" },
  { label: "Daily at 9 AM", expr: "0 9 * * *" },
  { label: "Weekdays at 9 AM", expr: "0 9 * * 1-5" },
  { label: "Weekly Mon 9 AM", expr: "0 9 * * 1" },
];

export default function SchedulesPage() {
  const qc = useQueryClient();
  const schedules = useQuery({ queryKey: ["schedules"], queryFn: fetchSchedules });
  const agents = useQuery({ queryKey: ["agents"], queryFn: fetchAgents });

  const agentById = useMemo(() => {
    const m = new Map<number, Agent>();
    (agents.data ?? []).forEach((a) => m.set(a.id, a));
    return m;
  }, [agents.data]);

  const create = useMutation({
    mutationFn: ({ agent_id, cron_expr, prompt, enabled }: {
      agent_id: number; cron_expr: string; prompt: string; enabled: boolean;
    }) => createSchedule(agent_id, cron_expr, prompt, enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedules"] }),
  });

  const remove = useMutation({
    mutationFn: deleteSchedule,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedules"] }),
  });

  const [agentId, setAgentId] = useState<string>("");
  const [cronExpr, setCronExpr] = useState("0 9 * * *");
  const [prompt, setPrompt] = useState("");
  const [enabled, setEnabled] = useState(true);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!agentId || !cronExpr.trim() || !prompt.trim()) return;
    create.mutate(
      { agent_id: Number(agentId), cron_expr: cronExpr.trim(), prompt: prompt.trim(), enabled },
      {
        onSuccess: () => {
          setPrompt("");
        },
      },
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Schedules</h1>
        <p className="text-sm text-[--color-fg-muted]">Recurring jobs registered in APScheduler.</p>
      </header>

      <form onSubmit={onSubmit} className="card space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[--color-fg-muted]">
          New schedule
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label className="text-xs space-y-1">
            <span className="text-[--color-fg-muted]">Agent</span>
            <select
              required
              value={agentId}
              onChange={(e) => setAgentId(e.target.value)}
              className="w-full bg-[--color-bg] border border-[--color-border] rounded px-3 py-2 text-sm"
            >
              <option value="">— pick an agent —</option>
              {(agents.data ?? []).map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </label>

          <label className="text-xs space-y-1">
            <span className="text-[--color-fg-muted]">Cron expression (UTC)</span>
            <input
              required
              value={cronExpr}
              onChange={(e) => setCronExpr(e.target.value)}
              placeholder="0 9 * * 1-5"
              className="w-full bg-[--color-bg] border border-[--color-border] rounded px-3 py-2 text-sm font-mono"
            />
          </label>
        </div>

        <div className="flex flex-wrap gap-2">
          {CRON_PRESETS.map((p) => (
            <button
              key={p.expr}
              type="button"
              onClick={() => setCronExpr(p.expr)}
              className="text-xs px-2 py-1 rounded border border-[--color-border] hover:bg-[--color-border] transition"
            >
              {p.label}
            </button>
          ))}
        </div>

        <label className="text-xs space-y-1 block">
          <span className="text-[--color-fg-muted]">Prompt sent on each tick</span>
          <textarea
            required
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={3}
            placeholder="What should this agent do every time it fires?"
            className="w-full bg-[--color-bg] border border-[--color-border] rounded px-3 py-2 text-sm"
          />
        </label>

        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 text-xs text-[--color-fg-muted]">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="accent-[--color-accent]"
            />
            Enabled (start firing immediately)
          </label>
          <button
            type="submit"
            disabled={create.isPending || !agentId || !cronExpr.trim() || !prompt.trim()}
            className="text-sm px-4 py-1.5 rounded border border-[--color-border] hover:bg-[--color-border] transition disabled:opacity-50"
          >
            {create.isPending ? "Creating…" : "Create schedule"}
          </button>
        </div>

        {create.isError && (
          <p className="text-xs text-[--color-error]">
            Failed to create — check the cron expression and that the agent exists.
          </p>
        )}
      </form>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[--color-fg-muted]">
          Active ({schedules.data?.length ?? 0})
        </h2>

        {schedules.isLoading && <p className="text-sm text-[--color-fg-muted]">Loading…</p>}

        {schedules.data && schedules.data.length === 0 && (
          <EmptyState
            title="No schedules yet"
            body="Create one above. Recurring jobs persist in APScheduler's SQLite jobstore so they survive restarts."
          />
        )}

        {schedules.data && schedules.data.length > 0 && (
          <div className="space-y-2">
            {schedules.data.map((s) => {
              const agent = agentById.get(s.agent_id);
              return (
                <div key={s.id} className="card space-y-2">
                  <header className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="font-mono text-xs text-[--color-fg-muted]">#{s.id}</span>
                      {agent ? (
                        <Link href={`/agents/${agent.id}`} className="font-semibold truncate hover:underline">
                          {agent.name}
                        </Link>
                      ) : (
                        <span className="badge badge-warn">agent {s.agent_id}</span>
                      )}
                      <code className="text-xs">{s.cron_expr}</code>
                      {!s.enabled && <span className="badge badge-warn">paused</span>}
                    </div>
                    <button
                      onClick={() => {
                        if (confirm(`Delete schedule #${s.id}?`)) remove.mutate(s.id);
                      }}
                      className="text-xs flex items-center gap-1 px-2 py-1 rounded border border-[--color-border] hover:bg-[--color-error]/20 transition"
                    >
                      <Trash2 size={12} /> Delete
                    </button>
                  </header>
                  <p className="text-xs text-[--color-fg-muted] truncate">{s.prompt}</p>
                  <p className="text-xs text-[--color-fg-muted]">
                    {s.next_run_at ? `next ${new Date(s.next_run_at).toLocaleString()}` : "next run pending"}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
