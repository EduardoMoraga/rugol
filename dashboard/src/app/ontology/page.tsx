"use client";

import dynamic from "next/dynamic";
import { useQuery } from "@tanstack/react-query";
import { fetchOntologyEdges, fetchOntologyNodes } from "@/lib/api";
import { Card, PageHeader } from "@/components/ui/card";

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
    <div className="p-8 space-y-6 max-w-6xl mx-auto">
      <PageHeader
        title="Ontology"
        description="Shared memory graph — facts agents have written. Each node is a concept, entity, or event; edges carry the predicate that connects them."
      />

      {isEmpty ? (
        <Card className="text-center py-10 space-y-3">
          <h2 className="text-lg font-semibold">The graph is empty</h2>
          <p className="text-sm text-[--color-fg-muted] max-w-md mx-auto">
            Agents will populate this as they learn. To seed it manually, post triples to
            <code className="font-mono ml-1 text-[--color-accent-strong]">/api/ontology/triples</code>.
          </p>
        </Card>
      ) : (
        <>
          <div className="flex flex-wrap gap-3 text-xs text-[--color-fg-muted]">
            <span className="font-mono">{nodes.data?.length ?? 0} nodes</span>
            <span>·</span>
            <span className="font-mono">{edges.data?.length ?? 0} edges</span>
            {Array.from(types.entries()).map(([t, n]) => (
              <span key={t} className="font-mono">
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
