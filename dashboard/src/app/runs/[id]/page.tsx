"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Square } from "lucide-react";
import { cancelRun, fetchRun } from "@/lib/api";
import { useStream } from "@/lib/use-stream";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardSection, PageHeader, Stat } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/toast";
import { MarkdownView } from "@/components/ui/markdown";

interface ToolCall { ts: number; tool: string; }

export default function RunDetail() {
  const params = useParams<{ id: string }>();
  const runId = Number(params.id);
  const qc = useQueryClient();

  const run = useQuery({
    queryKey: ["run", runId],
    queryFn: () => fetchRun(runId),
    refetchInterval: (q) => (q.state.data?.status === "running" ? 3000 : false),
    enabled: !Number.isNaN(runId),
  });

  const cancel = useMutation({
    mutationFn: () => cancelRun(runId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["run", runId] });
      toast({ tone: "info", title: `Run #${runId} cancellation requested` });
    },
  });

  const [liveText, setLiveText] = useState("");
  const [tools, setTools] = useState<ToolCall[]>([]);
  const [terminal, setTerminal] = useState<string | null>(null);
  const tailRef = useRef<HTMLDivElement>(null);

  useStream(
    "run:*",
    (e) => {
      if (e.data?.run_id !== runId) return;
      if (e.topic === "run:message" && e.data?.kind === "text" && e.data?.delta) {
        setLiveText((t) => t + e.data.delta);
      } else if (e.topic === "run:tool" && e.data?.tool) {
        setTools((prev) => [...prev, { ts: e.ts, tool: e.data.tool }]);
      } else if (
        e.topic === "run:completed" ||
        e.topic === "run:failed" ||
        e.topic === "run:cancelled"
      ) {
        setTerminal(e.topic.split(":")[1]);
        qc.invalidateQueries({ queryKey: ["run", runId] });
      }
    },
    { runId },
  );

  useEffect(() => {
    tailRef.current?.scrollTo({ top: tailRef.current.scrollHeight });
  }, [liveText]);

  const r = run.data;
  const isLive = r?.status === "running" && terminal === null;
  const finalText = r?.final_text || "";
  const display = useMemo(
    () => (isLive ? liveText : finalText || liveText),
    [isLive, liveText, finalText],
  );

  if (run.isLoading) return <div className="p-8 text-sm text-[--color-fg-muted]">Loading run…</div>;
  if (!r) return <div className="p-8 text-sm text-[--color-fg-muted]">Run not found.</div>;

  const totalTokens = r.input_tokens + r.output_tokens;
  const elapsed = r.ended_at
    ? (new Date(r.ended_at).getTime() - new Date(r.started_at).getTime()) / 1000
    : null;

  return (
    <div className="p-8 space-y-6 max-w-5xl mx-auto">
      <Link
        href={`/agents/${r.agent_id}`}
        className="text-xs text-[--color-fg-muted] hover:text-[--color-fg] inline-flex items-center gap-1.5"
      >
        <ArrowLeft size={12} /> Back to agent
      </Link>

      <PageHeader
        title={`Run #${r.id}`}
        description={`Source: ${r.source}${
          elapsed !== null ? ` · ${elapsed.toFixed(1)}s elapsed` : ""
        }${r.session_id ? ` · session ${r.session_id.slice(0, 8)}` : ""}${
          r.agent_version_id ? ` · version ${r.agent_version_id}` : ""
        }`}
        actions={
          <>
            <StatusBadge status={r.status} />
            {r.track && (
              <Badge
                tone={r.track === "s1" ? "idle" : "accent"}
                title={
                  r.classifier_rationale
                    ? `${r.track.toUpperCase()} (${(
                        (r.classifier_confidence ?? 0) * 100
                      ).toFixed(0)}%) — ${r.classifier_rationale}`
                    : r.track.toUpperCase()
                }
              >
                {r.track === "s1" ? "S1 · fast" : "S2 · deliberate"}
              </Badge>
            )}
            {isLive && (
              <Button variant="danger" size="sm" onClick={() => cancel.mutate()} disabled={cancel.isPending}>
                <Square size={12} /> Cancel
              </Button>
            )}
          </>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Input tokens" value={r.input_tokens.toLocaleString()} />
        <Stat label="Output tokens" value={r.output_tokens.toLocaleString()} />
        <Stat label="Total tokens" value={totalTokens.toLocaleString()} />
        <Stat label="Cost" value={`$${r.cost_usd.toFixed(4)}`} />
      </div>

      <CardSection>
        <h2 className="text-sm font-semibold tracking-tight">Prompt</h2>
        <Card>
          <pre className="text-sm whitespace-pre-wrap font-mono text-[--color-fg-muted]">
            {r.prompt}
          </pre>
        </Card>
      </CardSection>

      <CardSection>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold tracking-tight">
            {isLive ? "Live output" : "Output"}
          </h2>
          {isLive && <Badge tone="running">streaming</Badge>}
        </div>
        <div
          ref={tailRef}
          className="surface p-5 max-h-[640px] overflow-y-auto"
        >
          {display ? (
            <>
              <MarkdownView>{display}</MarkdownView>
              {isLive && (
                <span className="inline-block w-2 h-4 bg-[--color-accent-strong] align-middle animate-[pulse-soft_1s_ease-in-out_infinite] ml-0.5" />
              )}
            </>
          ) : (
            <span className="text-[--color-fg-subtle] text-sm">
              (esperando salida…)
            </span>
          )}
        </div>
      </CardSection>

      {tools.length > 0 && (
        <CardSection>
          <h2 className="text-sm font-semibold tracking-tight">Tool calls ({tools.length})</h2>
          <Card>
            <ul className="space-y-1.5 text-xs font-mono">
              {tools.map((t, i) => (
                <li key={i} className="flex items-center gap-3">
                  <span className="text-[--color-fg-subtle]">
                    {new Date(t.ts * 1000).toLocaleTimeString()}
                  </span>
                  <span className="text-[--color-accent-strong]">{t.tool}</span>
                </li>
              ))}
            </ul>
          </Card>
        </CardSection>
      )}

      {r.error_message && (
        <CardSection>
          <h2 className="text-sm font-semibold tracking-tight text-[--color-error]">Error</h2>
          <Card className="border-[--color-error]/40">
            <pre className="text-sm whitespace-pre-wrap font-mono text-[--color-error]">
              {r.error_message}
            </pre>
          </Card>
        </CardSection>
      )}
    </div>
  );
}
