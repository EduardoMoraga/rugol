"use client";

import dynamic from "next/dynamic";
import { useQuery } from "@tanstack/react-query";
import { fetchOntologyEdges, fetchOntologyNodes } from "@/lib/api";
import { EmptyState } from "@/components/dashboard/empty-state";

const OntologyGraph = dynamic(
  () => import("@/components/ontology/ontology-graph").then((m) => m.OntologyGraph),
  {
    ssr: false,
    loading: () => <p className="text-sm text-[--color-fg-muted]">Loading the graph…</p>,
  },
);

export default function OntologyPage() {
  const nodes = useQuery({ queryKey: ["onto-nodes"], queryFn: fetchOntologyNodes });
  const edges = useQuery({ queryKey: ["onto-edges"], queryFn: fetchOntologyEdges });

  const isEmpty = !nodes.data?.length && !edges.data?.length;

  const types = new Map<string, number>();
  (nodes.data ?? []).forEach((n) => types.set(n.type, (types.get(n.type) ?? 0) + 1));

  return (
    <div className="p-6 space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Ontology</h1>
        <p className="text-sm text-[--color-fg-muted]">
          Shared memory graph — facts agents have written. Each node is a concept,
          entity, or event; edges carry the predicate that connects them.
        </p>
      </header>

      {isEmpty ? (
        <EmptyState
          title="The graph is empty"
          body="Agents will populate this as they learn. You can also seed it manually with POST /api/ontology/triples."
          ctaLabel="See API"
          ctaHref="http://localhost:8000/docs"
        />
      ) : (
        <>
          <div className="flex flex-wrap gap-3 text-xs text-[--color-fg-muted]">
            <span>{nodes.data?.length ?? 0} nodes</span>
            <span>·</span>
            <span>{edges.data?.length ?? 0} edges</span>
            {Array.from(types.entries()).map(([t, n]) => (
              <span key={t}>
                · {n} {t}
                {n === 1 ? "" : "s"}
              </span>
            ))}
          </div>
          <OntologyGraph nodes={nodes.data ?? []} edges={edges.data ?? []} />
        </>
      )}
    </div>
  );
}
