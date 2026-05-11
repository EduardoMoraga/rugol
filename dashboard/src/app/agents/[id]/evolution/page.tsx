"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  GitBranch,
  History,
  Loader,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Undo2,
} from "lucide-react";

import {
  EvolutionValidation,
  EvolutionVersion,
  acceptEvolution,
  branchEvolution,
  fetchEvolution,
  fetchVersionBody,
  proposeEvolution,
  rejectEvolution,
  rollbackEvolution,
  validateEvolution,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardSection, PageHeader, Stat } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { toast } from "@/components/ui/toast";

function statusTone(status: EvolutionVersion["status"]):
  | "running"
  | "accent"
  | "warn"
  | "idle"
  | "error" {
  switch (status) {
    case "active":
      return "running";
    case "accepted":
      return "accent";
    case "proposed":
      return "warn";
    case "rejected":
      return "error";
    default:
      return "idle";
  }
}

export default function EvolutionPage() {
  const params = useParams<{ id: string }>();
  const agentId = Number(params.id);
  const qc = useQueryClient();

  const lineage = useQuery({
    queryKey: ["evolution", agentId],
    queryFn: () => fetchEvolution(agentId),
    enabled: !Number.isNaN(agentId),
  });

  const [expanded, setExpanded] = useState<string | null>(null);
  const [bodyOpen, setBodyOpen] = useState<string | null>(null);
  const [validationByVersion, setValidationByVersion] = useState<
    Record<string, EvolutionValidation>
  >({});

  const propose = useMutation({
    mutationFn: () => proposeEvolution(agentId, 2),
    onSuccess: (r) => {
      toast({
        tone: r.proposed_version_ids.length ? "info" : "warning",
        title: r.proposed_version_ids.length
          ? `Proposed ${r.proposed_version_ids.join(", ")}`
          : "No proposals — the spec is already strong",
      });
      qc.invalidateQueries({ queryKey: ["evolution", agentId] });
    },
    onError: (e: Error) => toast({ tone: "error", title: e.message }),
  });

  const validate = useMutation({
    mutationFn: (versionId: string) => validateEvolution(agentId, versionId),
    onSuccess: (r, versionId) => {
      setValidationByVersion((m) => ({ ...m, [versionId]: r }));
      toast({
        tone: r.verdict === "improve" ? "info" : r.verdict === "regress" ? "error" : "warning",
        title: `Score ${(r.score * 100).toFixed(0)}% — ${r.verdict}`,
      });
      qc.invalidateQueries({ queryKey: ["evolution", agentId] });
    },
    onError: (e: Error) => toast({ tone: "error", title: e.message }),
  });

  const accept = useMutation({
    mutationFn: (versionId: string) => acceptEvolution(agentId, versionId),
    onSuccess: (_r, v) => {
      toast({ tone: "info", title: `Version ${v} accepted as current` });
      qc.invalidateQueries({ queryKey: ["evolution", agentId] });
    },
    onError: (e: Error) => toast({ tone: "error", title: e.message }),
  });

  const reject = useMutation({
    mutationFn: (versionId: string) => rejectEvolution(agentId, versionId),
    onSuccess: (_r, v) => {
      toast({ tone: "info", title: `Version ${v} rejected` });
      qc.invalidateQueries({ queryKey: ["evolution", agentId] });
    },
    onError: (e: Error) => toast({ tone: "error", title: e.message }),
  });

  const branch = useMutation({
    mutationFn: (versionId: string) => branchEvolution(agentId, versionId),
    onSuccess: (_r, v) => {
      toast({ tone: "info", title: `Branched — running A/B with ${v}` });
      qc.invalidateQueries({ queryKey: ["evolution", agentId] });
    },
    onError: (e: Error) => toast({ tone: "error", title: e.message }),
  });

  const rollback = useMutation({
    mutationFn: (versionId: string) => rollbackEvolution(agentId, versionId),
    onSuccess: (_r, v) => {
      toast({ tone: "info", title: `Rolled back to ${v}` });
      qc.invalidateQueries({ queryKey: ["evolution", agentId] });
    },
    onError: (e: Error) => toast({ tone: "error", title: e.message }),
  });

  if (lineage.isLoading) {
    return (
      <div className="p-8 text-sm text-[--color-fg-muted]">
        Loading evolutionary archive…
      </div>
    );
  }
  if (!lineage.data) {
    return (
      <div className="p-8 text-sm text-[--color-fg-muted]">
        No archive yet. Once an agent has runs and the proposer fires, versions
        will appear here.
      </div>
    );
  }

  const data = lineage.data;
  const versions = [...data.versions].sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
  const proposedCount = versions.filter((v) => v.status === "proposed").length;
  const activeCount = versions.filter((v) => v.status === "active").length;

  return (
    <div className="p-8 space-y-6 max-w-5xl mx-auto">
      <Link
        href={`/agents/${agentId}`}
        className="text-xs text-[--color-fg-muted] hover:text-[--color-fg] inline-flex items-center gap-1.5"
      >
        <ArrowLeft size={12} /> Back to agent
      </Link>

      <PageHeader
        title={`Evolution · ${data.agent_name}`}
        description={`Lineage of ${versions.length} version(s) · current is ${data.current}`}
        actions={
          <Button
            size="sm"
            onClick={() => propose.mutate()}
            disabled={propose.isPending}
          >
            {propose.isPending ? <Loader size={12} className="animate-spin" /> : <Sparkles size={12} />}
            Propose mutations
          </Button>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Total versions" value={String(versions.length)} />
        <Stat label="Active" value={String(activeCount)} />
        <Stat label="Pending review" value={String(proposedCount)} />
        <Stat label="Current" value={data.current} />
      </div>

      <CardSection>
        <h2 className="text-sm font-semibold tracking-tight">Versions</h2>
        <div className="space-y-2">
          {versions.map((v) => {
            const isCurrent = v.id === data.current;
            const validation = validationByVersion[v.id];
            const score =
              v.validation_score ?? validation?.score ?? null;
            const isExpanded = expanded === v.id;
            return (
              <Card key={v.id} className="space-y-3">
                <header className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-mono font-semibold">
                        v{v.id}
                      </span>
                      <Badge tone={statusTone(v.status)}>{v.status}</Badge>
                      {isCurrent && <Badge tone="accent">current</Badge>}
                      {v.parent && (
                        <span className="text-[10px] text-[--color-fg-subtle] font-mono">
                          parent v{v.parent}
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-[--color-fg-muted]">
                      {new Date(v.created_at).toLocaleString()}
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setBodyOpen(v.id)}
                    >
                      View body
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setExpanded(isExpanded ? null : v.id)}
                    >
                      {isExpanded ? "Less" : "Details"}
                    </Button>
                  </div>
                </header>

                {(v.hypothesis || v.rationale) && (
                  <div className="text-xs text-[--color-fg-muted] space-y-1">
                    {v.hypothesis && (
                      <div>
                        <span className="text-[--color-fg-subtle]">Hypothesis:</span>{" "}
                        {v.hypothesis}
                      </div>
                    )}
                    {v.rationale && (
                      <div>
                        <span className="text-[--color-fg-subtle]">Rationale:</span>{" "}
                        {v.rationale}
                      </div>
                    )}
                  </div>
                )}

                {isExpanded && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                    <Stat label="Runs" value={String(v.metrics.runs ?? 0)} />
                    <Stat
                      label="Avg cost"
                      value={`$${(v.metrics.avg_cost_usd ?? 0).toFixed(4)}`}
                    />
                    <Stat
                      label="Avg latency"
                      value={`${(v.metrics.avg_latency_ms ?? 0).toFixed(0)} ms`}
                    />
                    <Stat
                      label="Validation"
                      value={
                        score === null
                          ? "—"
                          : `${(score * 100).toFixed(0)}%`
                      }
                    />
                  </div>
                )}

                <div className="flex items-center gap-1.5 flex-wrap">
                  {v.status === "proposed" && (
                    <>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => validate.mutate(v.id)}
                        disabled={validate.isPending}
                      >
                        Validate
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => accept.mutate(v.id)}
                        disabled={accept.isPending}
                      >
                        <ThumbsUp size={12} /> Accept
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => branch.mutate(v.id)}
                        disabled={branch.isPending}
                      >
                        <GitBranch size={12} /> Branch (A/B)
                      </Button>
                      <Button
                        size="sm"
                        variant="danger"
                        onClick={() => reject.mutate(v.id)}
                        disabled={reject.isPending}
                      >
                        <ThumbsDown size={12} /> Reject
                      </Button>
                    </>
                  )}
                  {(v.status === "archived" || v.status === "accepted") && !isCurrent && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => rollback.mutate(v.id)}
                      disabled={rollback.isPending}
                    >
                      <Undo2 size={12} /> Set as current
                    </Button>
                  )}
                  {v.status === "active" && !isCurrent && (
                    <Button
                      size="sm"
                      onClick={() => rollback.mutate(v.id)}
                      disabled={rollback.isPending}
                    >
                      <History size={12} /> Make current
                    </Button>
                  )}
                </div>

                {validation && (
                  <div className="surface p-3 text-xs space-y-1">
                    <div className="text-[--color-fg-muted]">
                      <span className="text-[--color-fg-subtle]">Verdict:</span>{" "}
                      {validation.verdict} · {(validation.score * 100).toFixed(0)}%
                    </div>
                    {validation.rationale && (
                      <div className="text-[--color-fg-muted]">
                        {validation.rationale}
                      </div>
                    )}
                    {validation.concerns.length > 0 && (
                      <ul className="list-disc list-inside text-[--color-fg-muted]">
                        {validation.concerns.map((c, i) => (
                          <li key={i}>{c}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      </CardSection>

      <Dialog
        open={bodyOpen !== null}
        onOpenChange={(open) => !open && setBodyOpen(null)}
      >
        {bodyOpen !== null && (
          <BodyDialogContent agentId={agentId} versionId={bodyOpen} />
        )}
      </Dialog>
    </div>
  );
}

function BodyDialogContent({
  agentId,
  versionId,
}: {
  agentId: number;
  versionId: string;
}) {
  const body = useQuery({
    queryKey: ["evolution-body", agentId, versionId],
    queryFn: () => fetchVersionBody(agentId, versionId),
  });
  return (
    <DialogContent title={`Version v${versionId} · body`}>
      {body.isLoading ? (
        <div className="text-sm text-[--color-fg-muted]">Loading…</div>
      ) : (
        <pre className="text-xs font-mono whitespace-pre-wrap max-h-[60vh] overflow-y-auto">
          {body.data?.body ?? "(empty)"}
        </pre>
      )}
    </DialogContent>
  );
}
