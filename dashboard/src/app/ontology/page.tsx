"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchOntologyEdges, fetchOntologyNodes } from "@/lib/api";
import { EmptyState } from "@/components/dashboard/empty-state";

export default function OntologyPage() {
  const nodes = useQuery({ queryKey: ["onto-nodes"], queryFn: fetchOntologyNodes });
  const edges = useQuery({ queryKey: ["onto-edges"], queryFn: fetchOntologyEdges });

  const isEmpty = nodes.data?.length === 0 && edges.data?.length === 0;

  return (
    <div className="p-6 space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Ontology</h1>
        <p className="text-sm text-[--color-fg-muted]">Shared memory graph — facts agents have written.</p>
      </header>

      {isEmpty && (
        <EmptyState
          title="The graph is empty"
          body="Agents will populate this as they learn. You can also seed it manually via the API."
          ctaLabel="See API"
          ctaHref="/api/docs"
        />
      )}

      {!isEmpty && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-[--color-fg-muted] mb-2">
              Nodes ({nodes.data?.length ?? 0})
            </h2>
            <div className="space-y-1">
              {nodes.data?.slice(0, 20).map((n) => (
                <div key={n.id} className="card text-sm">
                  <span className="badge badge-idle mr-2">{n.type}</span>
                  {n.label}
                </div>
              ))}
            </div>
          </div>
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-[--color-fg-muted] mb-2">
              Edges ({edges.data?.length ?? 0})
            </h2>
            <div className="space-y-1">
              {edges.data?.slice(0, 20).map((e) => (
                <div key={e.id} className="card text-sm font-mono">
                  {e.src} → <span className="text-[--color-accent]">{e.predicate}</span> → {e.dst}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
