"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  approveImprovement,
  fetchAgents,
  fetchImprovements,
  rejectImprovement,
  type Agent,
} from "@/lib/api";
import { EmptyState } from "@/components/dashboard/empty-state";
import { DiffView } from "@/components/improvements/diff-view";

const TABS = [
  { key: "proposed", label: "Pending" },
  { key: "approved", label: "Approved" },
  { key: "rejected", label: "Rejected" },
] as const;

export default function ImprovementsPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<typeof TABS[number]["key"]>("proposed");

  const { data, isLoading } = useQuery({
    queryKey: ["improvements", tab],
    queryFn: () => fetchImprovements(tab),
  });
  const agents = useQuery({ queryKey: ["agents"], queryFn: fetchAgents });

  const agentById = useMemo(() => {
    const m = new Map<number, Agent>();
    (agents.data ?? []).forEach((a) => m.set(a.id, a));
    return m;
  }, [agents.data]);

  const approveMut = useMutation({
    mutationFn: approveImprovement,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["improvements"] }),
  });
  const rejectMut = useMutation({
    mutationFn: rejectImprovement,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["improvements"] }),
  });

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Improvements</h1>
        <p className="text-sm text-[--color-fg-muted]">
          Self-proposed edits to agent specs. You decide what gets applied — Rogologo
          never rewrites an agent file without explicit approval.
        </p>
      </header>

      <nav className="flex gap-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`text-sm px-3 py-1.5 rounded border transition ${
              tab === t.key
                ? "border-[--color-fg-muted] bg-[--color-border]"
                : "border-[--color-border] text-[--color-fg-muted] hover:text-[--color-fg] hover:bg-[--color-border]/40"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {isLoading && <p className="text-sm text-[--color-fg-muted]">Loading…</p>}

      {data && data.length === 0 && (
        <EmptyState
          title={
            tab === "proposed"
              ? "No proposals to review"
              : `No ${tab} improvements yet`
          }
          body={
            tab === "proposed"
              ? "When an agent's reflection loop fires (after 3 consecutive failures or every 10 successful runs), proposed diffs land here."
              : "When proposals are reviewed they appear under this tab."
          }
        />
      )}

      {data && data.length > 0 && (
        <div className="space-y-4">
          {data.map((imp) => {
            const agent = agentById.get(imp.agent_id);
            return (
              <article key={imp.id} className="card space-y-3">
                <header className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-mono text-[--color-fg-muted]">
                      #{imp.id} · {agent ? agent.name : `agent ${imp.agent_id}`} · {new Date(imp.created_at).toLocaleString()}
                    </p>
                    <p className="text-sm mt-1">{imp.rationale}</p>
                  </div>
                  {tab === "proposed" && (
                    <div className="flex gap-2 shrink-0">
                      <button
                        onClick={() => approveMut.mutate(imp.id)}
                        disabled={approveMut.isPending}
                        className="text-xs px-3 py-1 rounded border border-[--color-accent]/50 text-[--color-accent] hover:bg-[--color-accent]/10 transition disabled:opacity-50"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => rejectMut.mutate(imp.id)}
                        disabled={rejectMut.isPending}
                        className="text-xs px-3 py-1 rounded border border-[--color-error]/50 text-[--color-error] hover:bg-[--color-error]/10 transition disabled:opacity-50"
                      >
                        Reject
                      </button>
                    </div>
                  )}
                </header>
                <DiffView diff={imp.diff} />
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
