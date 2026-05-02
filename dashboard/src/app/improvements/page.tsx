"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { approveImprovement, fetchImprovements, rejectImprovement } from "@/lib/api";
import { EmptyState } from "@/components/dashboard/empty-state";

export default function ImprovementsPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["improvements"],
    queryFn: () => fetchImprovements("proposed"),
  });

  const approveMut = useMutation({
    mutationFn: approveImprovement,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["improvements"] }),
  });
  const rejectMut = useMutation({
    mutationFn: rejectImprovement,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["improvements"] }),
  });

  return (
    <div className="p-6 space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Improvements</h1>
        <p className="text-sm text-[--color-fg-muted]">
          Self-proposed edits to agent specs. You decide what gets applied.
        </p>
      </header>

      {isLoading && <p className="text-sm text-[--color-fg-muted]">Loading…</p>}

      {data && data.length === 0 && (
        <EmptyState
          title="No proposals to review"
          body="When an agent's reflection loop fires, you'll see proposed diffs here."
          ctaLabel="Read about reflection"
          ctaHref="/docs/adrs/ADR-004-ontology-and-self-improving"
        />
      )}

      {data && data.length > 0 && (
        <div className="space-y-4">
          {data.map((imp) => (
            <article key={imp.id} className="card space-y-3">
              <header className="flex items-start justify-between">
                <div>
                  <p className="text-xs font-mono text-[--color-fg-muted]">#{imp.id} · agent {imp.agent_id}</p>
                  <p className="text-sm mt-1">{imp.rationale}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => approveMut.mutate(imp.id)}
                    className="badge badge-running cursor-pointer"
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => rejectMut.mutate(imp.id)}
                    className="badge badge-error cursor-pointer"
                  >
                    Reject
                  </button>
                </div>
              </header>
              <pre className="text-xs bg-black/40 p-3 rounded overflow-x-auto whitespace-pre-wrap">
                {imp.diff}
              </pre>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
