"use client";

import { FormEvent, useMemo, useState } from "react";
import Link from "next/link";
import { Plus, Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createSchedule,
  deleteSchedule,
  fetchAgents,
  fetchSchedules,
  type Agent,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardSection, PageHeader } from "@/components/ui/card";
import { FieldLabel, Input, Select, Textarea } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/toast";

const CRON_PRESETS = [
  { label: "Every 5 min", expr: "*/5 * * * *" },
  { label: "Hourly", expr: "0 * * * *" },
  { label: "Daily 9 AM", expr: "0 9 * * *" },
  { label: "Weekdays 9 AM", expr: "0 9 * * 1-5" },
  { label: "Mon 9 AM", expr: "0 9 * * 1" },
];

export default function SchedulesPage() {
  const qc = useQueryClient();
  const schedules = useQuery({ queryKey: ["schedules"], queryFn: fetchSchedules, refetchInterval: 5000 });
  const agents = useQuery({ queryKey: ["agents"], queryFn: () => fetchAgents() });

  const agentById = useMemo(() => {
    const m = new Map<number, Agent>();
    (agents.data ?? []).forEach((a) => m.set(a.id, a));
    return m;
  }, [agents.data]);

  const create = useMutation({
    mutationFn: ({ agent_id, cron_expr, prompt, enabled }: any) =>
      createSchedule(agent_id, cron_expr, prompt, enabled),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["schedules"] });
      toast({ tone: "success", title: "Schedule created" });
    },
    onError: (e: Error) => toast({ tone: "error", title: "Failed to create", body: e.message }),
  });

  const remove = useMutation({
    mutationFn: deleteSchedule,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["schedules"] });
      toast({ tone: "info", title: "Schedule deleted" });
    },
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
      { onSuccess: () => setPrompt("") },
    );
  }

  return (
    <div className="p-8 space-y-6 max-w-4xl mx-auto">
      <PageHeader
        title="Schedules"
        description="Recurring jobs registered in APScheduler. Survive restarts via SQLite jobstore."
      />

      <Card>
        <h2 className="text-sm font-semibold tracking-tight inline-flex items-center gap-2 mb-4">
          <Plus size={14} className="text-[--color-accent-strong]" />
          New schedule
        </h2>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <FieldLabel>Agent</FieldLabel>
              <Select required value={agentId} onChange={(e) => setAgentId(e.target.value)}>
                <option value="">— pick an agent —</option>
                {(agents.data ?? []).map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </Select>
            </div>
            <div className="space-y-1.5">
              <FieldLabel hint="cron in UTC">Expression</FieldLabel>
              <Input
                required
                value={cronExpr}
                onChange={(e) => setCronExpr(e.target.value)}
                placeholder="0 9 * * 1-5"
                className="font-mono"
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-1.5">
            {CRON_PRESETS.map((p) => (
              <Button
                key={p.expr}
                type="button"
                variant={cronExpr === p.expr ? "primary" : "outline"}
                size="sm"
                onClick={() => setCronExpr(p.expr)}
              >
                {p.label}
              </Button>
            ))}
          </div>

          <div className="space-y-1.5">
            <FieldLabel>Prompt sent on each tick</FieldLabel>
            <Textarea
              required
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={3}
              placeholder="What should this agent do every time it fires?"
            />
          </div>

          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2 text-xs text-[--color-fg-muted] cursor-pointer">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                className="accent-[--color-accent]"
              />
              Enabled (start firing immediately)
            </label>
            <Button
              type="submit"
              variant="primary"
              disabled={create.isPending || !agentId || !cronExpr.trim() || !prompt.trim()}
            >
              {create.isPending ? "Creating…" : "Create schedule"}
            </Button>
          </div>
        </form>
      </Card>

      <CardSection>
        <div className="flex items-baseline justify-between">
          <h2 className="text-sm font-semibold tracking-tight">Active</h2>
          <span className="text-xs text-[--color-fg-muted]">
            {schedules.data?.length ?? 0} schedule{schedules.data?.length === 1 ? "" : "s"}
          </span>
        </div>

        {schedules.isLoading && <p className="text-sm text-[--color-fg-muted]">Loading…</p>}

        {schedules.data && schedules.data.length === 0 && (
          <Card>
            <p className="text-sm text-[--color-fg-muted]">No schedules yet — create one above.</p>
          </Card>
        )}

        {schedules.data && schedules.data.length > 0 && (
          <div className="space-y-2">
            {schedules.data.map((s) => {
              const agent = agentById.get(s.agent_id);
              return (
                <div key={s.id} className="surface p-4 space-y-2">
                  <header className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="font-mono text-xs text-[--color-fg-subtle]">#{s.id}</span>
                      {agent ? (
                        <Link
                          href={`/agents/${agent.id}`}
                          className="font-semibold truncate hover:text-[--color-accent-strong] transition-colors"
                        >
                          {agent.name}
                        </Link>
                      ) : (
                        <Badge tone="warn">agent {s.agent_id}</Badge>
                      )}
                      <code className="text-xs px-2 py-0.5 rounded bg-[--color-bg] border border-[--color-border] font-mono">
                        {s.cron_expr}
                      </code>
                      {!s.enabled && <Badge tone="warn">paused</Badge>}
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        if (confirm(`Delete schedule #${s.id}?`)) remove.mutate(s.id);
                      }}
                    >
                      <Trash2 size={12} /> Delete
                    </Button>
                  </header>
                  <p className="text-xs text-[--color-fg-muted] truncate">{s.prompt}</p>
                  <p className="text-xs text-[--color-fg-subtle] font-mono">
                    {s.next_run_at ? `next ${new Date(s.next_run_at).toLocaleString()}` : "next run pending"}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </CardSection>
    </div>
  );
}
