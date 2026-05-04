"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Plus, Search, Sparkles, Wand2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { fetchAgents, type Agent } from "@/lib/api";
import { AgentCard } from "@/components/dashboard/agent-card";
import { PageHeader } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export default function AgentsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["agents"],
    queryFn: () => fetchAgents(),
    refetchInterval: 5000,
  });

  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (data ?? []).filter((a: Agent) => {
      if (statusFilter !== "all" && a.status !== statusFilter) return false;
      if (!q) return true;
      return (
        a.name.toLowerCase().includes(q) ||
        a.description.toLowerCase().includes(q) ||
        a.model.toLowerCase().includes(q)
      );
    });
  }, [data, query, statusFilter]);

  const total = data?.length ?? 0;

  return (
    <div className="p-8 space-y-6 max-w-6xl mx-auto">
      <PageHeader
        title="Agents"
        description={`${total} registered · ${filtered.length} shown`}
        actions={
          <>
            <Link href="/architect">
              <Button variant="primary">
                <Wand2 size={13} /> Design a team
              </Button>
            </Link>
            <Link href="/agents/new">
              <Button variant="secondary">
                <Plus size={13} /> Add one
              </Button>
            </Link>
          </>
        }
      />

      {total > 0 && (
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[280px] max-w-md">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-[--color-fg-muted] pointer-events-none"
            />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by name, description, or model…"
              className="pl-9"
            />
          </div>
          <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="w-44">
            <option value="all">All statuses</option>
            <option value="idle">Idle</option>
            <option value="running">Running</option>
            <option value="error">Error</option>
            <option value="offline">Offline</option>
          </Select>
        </div>
      )}

      {isLoading && <p className="text-sm text-[--color-fg-muted]">Loading…</p>}
      {error && <p className="text-sm text-[--color-error]">Failed to load agents.</p>}

      {data && data.length === 0 && (
        <div className="surface p-10 text-center space-y-4">
          <Sparkles size={28} className="mx-auto text-[--color-accent-strong]" />
          <div>
            <h2 className="text-lg font-semibold">Aún no hay agentes</h2>
            <p className="text-sm text-[--color-fg-muted] mt-1 max-w-md mx-auto">
              Los agentes viven dentro de un proyecto. La forma más rápida:
              ir a Proyectos y clonar uno de los 5 templates curados — el equipo
              de agentes se arma solo. O describe tu idea con Architect.
            </p>
          </div>
          <div className="flex items-center justify-center gap-2">
            <Link href="/projects">
              <Button variant="primary">
                <Sparkles size={13} /> Ver templates
              </Button>
            </Link>
            <Link href="/architect">
              <Button variant="secondary">
                <Wand2 size={13} /> Diseñar con Architect
              </Button>
            </Link>
            <Link href="/agents/new">
              <Button variant="ghost">
                <Plus size={13} /> Crear manual
              </Button>
            </Link>
          </div>
        </div>
      )}

      {data && data.length > 0 && filtered.length === 0 && (
        <div className="surface p-8 text-center text-sm text-[--color-fg-muted]">
          Sin coincidencias para tu búsqueda.
        </div>
      )}

      {filtered.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((a) => (
            <AgentCard key={a.id} agent={a} />
          ))}
        </div>
      )}
    </div>
  );
}
