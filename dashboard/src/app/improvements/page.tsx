"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookmarkPlus } from "lucide-react";
import {
  addProjectLesson,
  approveImprovement,
  fetchAgents,
  fetchImprovements,
  rejectImprovement,
  type Agent,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, PageHeader } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { DiffView } from "@/components/improvements/diff-view";
import { ProjectBadge } from "@/components/projects/project-badge";
import { toast } from "@/components/ui/toast";

const TABS = [
  { key: "proposed", label: "Pending" },
  { key: "approved", label: "Approved" },
  { key: "rejected", label: "Rejected" },
] as const;

export default function ImprovementsPage() {
  const qc = useQueryClient();

  const agents = useQuery({ queryKey: ["agents"], queryFn: () => fetchAgents() });
  const agentById = useMemo(() => {
    const m = new Map<number, Agent>();
    (agents.data ?? []).forEach((a) => m.set(a.id, a));
    return m;
  }, [agents.data]);

  return (
    <div className="p-8 space-y-6 max-w-5xl mx-auto">
      <PageHeader
        title="Improvements"
        description="Self-proposed edits to agent specs. Rogologo never rewrites an agent file without explicit approval."
      />

      <Tabs defaultValue="proposed">
        <TabsList>
          {TABS.map((t) => (
            <TabsTrigger key={t.key} value={t.key}>
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>
        {TABS.map((t) => (
          <TabsContent key={t.key} value={t.key} className="mt-5">
            <Panel
              status={t.key}
              agentById={agentById}
              onAction={() => qc.invalidateQueries({ queryKey: ["improvements"] })}
            />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}

function PromoteRationaleButton({
  projectSlug,
  text,
}: {
  projectSlug: string;
  text: string;
}) {
  const [done, setDone] = useState(false);
  const promote = useMutation({
    mutationFn: () =>
      addProjectLesson(projectSlug, { text: text.slice(0, 480), kind: "lesson" }),
    onSuccess: () => {
      setDone(true);
      toast({
        tone: "success",
        title: "Guardada como lección",
        body: "Todos los agentes del proyecto la van a leer antes de cada run.",
      });
    },
    onError: (e: Error) =>
      toast({ tone: "error", title: "No se pudo guardar", body: e.message }),
  });
  return (
    <button
      type="button"
      onClick={() => promote.mutate()}
      disabled={promote.isPending || done}
      className={`text-[11px] inline-flex items-center gap-1 px-2 py-1 rounded-md border transition ${
        done
          ? "border-[--color-success]/40 text-[--color-success] cursor-default"
          : "border-[--color-border] text-[--color-fg-muted] hover:text-[--color-accent-strong] hover:border-[--color-accent]/40"
      }`}
    >
      <BookmarkPlus size={11} />
      {done ? "Guardada en el proyecto" : promote.isPending ? "Guardando…" : "Promover rationale a lección del proyecto"}
    </button>
  );
}


function Panel({
  status,
  agentById,
  onAction,
}: {
  status: string;
  agentById: Map<number, Agent>;
  onAction: () => void;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["improvements", status],
    queryFn: () => fetchImprovements(status),
  });

  const approveMut = useMutation({
    mutationFn: approveImprovement,
    onSuccess: () => {
      onAction();
      toast({ tone: "success", title: "Improvement approved" });
    },
  });
  const rejectMut = useMutation({
    mutationFn: rejectImprovement,
    onSuccess: () => {
      onAction();
      toast({ tone: "info", title: "Improvement rejected" });
    },
  });

  if (isLoading) return <p className="text-sm text-[--color-fg-muted]">Loading…</p>;

  if (!data || data.length === 0) {
    return (
      <Card>
        <p className="text-sm text-[--color-fg-muted]">
          {status === "proposed"
            ? "No proposals to review. Reflection fires after 3 consecutive failures or every 10 successful runs."
            : `No ${status} improvements yet.`}
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {data.map((imp) => {
        const agent = agentById.get(imp.agent_id);
        return (
          <Card key={imp.id} className="space-y-4">
            <header className="flex items-start justify-between gap-3">
              <div className="min-w-0 space-y-1.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-[11px] font-mono text-[--color-fg-subtle]">
                    #{imp.id} · {agent ? agent.name : `agent ${imp.agent_id}`} ·{" "}
                    {new Date(imp.created_at).toLocaleString()}
                  </p>
                  {agent?.project_slug && (
                    <ProjectBadge
                      slug={agent.project_slug}
                      name={agent.project_name}
                      color={agent.project_color}
                      icon={agent.project_icon}
                    />
                  )}
                </div>
                <p className="text-sm">{imp.rationale}</p>
                {agent?.project_slug && imp.rationale && (
                  <PromoteRationaleButton
                    projectSlug={agent.project_slug}
                    text={imp.rationale}
                  />
                )}
              </div>
              {status === "proposed" && (
                <div className="flex gap-2 shrink-0">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => approveMut.mutate(imp.id)}
                    disabled={approveMut.isPending}
                  >
                    Approve
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => rejectMut.mutate(imp.id)}
                    disabled={rejectMut.isPending}
                  >
                    Reject
                  </Button>
                </div>
              )}
            </header>
            <DiffView diff={imp.diff} />
          </Card>
        );
      })}
    </div>
  );
}
