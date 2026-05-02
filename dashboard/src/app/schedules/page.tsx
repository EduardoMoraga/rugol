"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchSchedules } from "@/lib/api";
import { EmptyState } from "@/components/dashboard/empty-state";

export default function SchedulesPage() {
  const { data, isLoading } = useQuery({ queryKey: ["schedules"], queryFn: fetchSchedules });

  return (
    <div className="p-6 space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Schedules</h1>
        <p className="text-sm text-[--color-fg-muted]">Recurring jobs registered in APScheduler.</p>
      </header>

      {isLoading && <p className="text-sm text-[--color-fg-muted]">Loading…</p>}

      {data && data.length === 0 && (
        <EmptyState
          title="No schedules yet"
          body="Pick an agent and create a schedule from its detail page."
          ctaLabel="See agents"
          ctaHref="/agents"
        />
      )}

      {data && data.length > 0 && (
        <div className="space-y-2">
          {data.map((s) => (
            <div key={s.id} className="card flex items-center justify-between text-sm">
              <div className="flex items-center gap-3">
                <span className="font-mono text-xs">#{s.id}</span>
                <span className="badge badge-idle">agent {s.agent_id}</span>
                <code className="text-xs">{s.cron_expr}</code>
              </div>
              <span className="text-xs text-[--color-fg-muted]">
                {s.next_run_at ? `next ${new Date(s.next_run_at).toLocaleString()}` : "—"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
