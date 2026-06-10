"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useI18n } from "@/lib/i18n";
import { fetchMemoryGraph, type MemoryGraphNode } from "@/lib/api";
import { Card, PageHeader } from "@/components/ui/card";
import { MemoryGraphCanvas } from "@/components/memory/memory-graph";

const KIND_DOTS: { key: string; color: string }[] = [
  { key: "agent", color: "#a78bfa" },
  { key: "user", color: "#60a5fa" },
  { key: "feedback", color: "#f59e0b" },
  { key: "project", color: "#34d399" },
  { key: "reference", color: "#22d3ee" },
  { key: "note", color: "#94a3b8" },
  { key: "concept", color: "#64748b" },
];

export default function MemoryGraphPage() {
  const { t } = useI18n();
  const [agentFilter, setAgentFilter] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<MemoryGraphNode | null>(null);

  // refetch every 20s: the network grows live as agents save memories.
  const graph = useQuery({
    queryKey: ["memory-graph"],
    queryFn: fetchMemoryGraph,
    refetchInterval: 20_000,
  });

  const agents = useMemo(
    () => (graph.data?.nodes ?? []).filter((n) => n.type === "agent").map((n) => n.label).sort(),
    [graph.data],
  );
  const stats = graph.data?.stats;
  const isEmpty = !graph.isLoading && (graph.data?.nodes.length ?? 0) === 0;

  return (
    <div className="p-8 space-y-4 max-w-[1500px] mx-auto h-full flex flex-col">
      <PageHeader title={t("memgraph.title")} description={t("memgraph.desc")} />

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("memgraph.search")}
          className="px-3 py-1.5 rounded-lg bg-[--color-bg-subtle] border border-[--color-border] focus:outline-none focus:border-[--color-accent] w-56"
        />
        <select
          value={agentFilter ?? ""}
          onChange={(e) => { setAgentFilter(e.target.value || null); setSelected(null); }}
          className="px-3 py-1.5 rounded-lg bg-[--color-bg-subtle] border border-[--color-border]"
        >
          <option value="">{t("memgraph.allAgents")}</option>
          {agents.map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
        {stats && (
          <span className="text-[--color-fg-muted]">
            {stats.agents} {t("memgraph.agents")} · {stats.memories} {t("memgraph.memories")} ·{" "}
            {stats.concepts} {t("memgraph.concepts")} · {stats.links} {t("memgraph.links")}
          </span>
        )}
        <span className="ml-auto flex items-center gap-3 text-xs text-[--color-fg-muted]">
          {KIND_DOTS.map((k) => (
            <span key={k.key} className="flex items-center gap-1">
              <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: k.color }} />
              {t(`memgraph.kind.${k.key}`)}
            </span>
          ))}
        </span>
      </div>

      {/* Graph + detail panel */}
      {isEmpty ? (
        <Card className="text-center py-12 space-y-3">
          <h2 className="text-lg font-semibold">{t("memgraph.emptyTitle")}</h2>
          <p className="text-sm text-[--color-fg-muted] max-w-md mx-auto">{t("memgraph.emptyBody")}</p>
        </Card>
      ) : (
        <div className="flex gap-4 flex-1 min-h-[560px]">
          <div className="flex-1 rounded-xl overflow-hidden border border-[--color-border]">
            {graph.data && (
              <MemoryGraphCanvas
                data={graph.data}
                agentFilter={agentFilter}
                search={search}
                selectedId={selected?.id ?? null}
                onSelect={setSelected}
              />
            )}
          </div>
          {selected && (
            <Card className="w-[340px] shrink-0 space-y-3 overflow-y-auto max-h-[72vh]">
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-semibold leading-tight break-words">{selected.label}</h3>
                <button
                  onClick={() => setSelected(null)}
                  className="text-[--color-fg-muted] hover:text-[--color-fg] text-sm"
                  aria-label="close"
                >
                  ✕
                </button>
              </div>
              <p className="text-xs text-[--color-fg-muted]">
                {selected.type === "agent" && t("memgraph.panel.agent")}
                {selected.type === "concept" && t("memgraph.panel.concept")}
                {selected.type === "memory" && (
                  <>
                    <span className="uppercase tracking-wide">{selected.kind}</span>
                    {" · "}{selected.agent}
                    {selected.created_at ? <>{" · "}{selected.created_at.slice(0, 10)}</> : null}
                  </>
                )}
              </p>
              {selected.description && (
                <p className="text-sm text-[--color-fg-muted]">{selected.description}</p>
              )}
              {selected.body && (
                <pre className="text-xs whitespace-pre-wrap font-sans bg-[--color-bg-subtle] rounded-lg p-3 border border-[--color-border]">
                  {selected.body}
                </pre>
              )}
              <p className="text-xs text-[--color-fg-muted]">
                {t("memgraph.panel.degree")}: {selected.degree}
              </p>
            </Card>
          )}
        </div>
      )}
      <p className="text-xs text-[--color-fg-muted]">{t("memgraph.hint")}</p>
    </div>
  );
}
