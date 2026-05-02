"use client";

import { use, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Square } from "lucide-react";
import { cancelRun, fetchRun } from "@/lib/api";
import { useStream } from "@/lib/use-stream";
import { StatusBadge } from "@/components/dashboard/status-badge";

interface ToolCall { ts: number; tool: string; }

export default function RunDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const runId = Number(id);
  const qc = useQueryClient();

  const run = useQuery({
    queryKey: ["run", runId],
    queryFn: () => fetchRun(runId),
    refetchInterval: (q) => (q.state.data?.status === "running" ? 3000 : false),
  });

  const cancel = useMutation({
    mutationFn: () => cancelRun(runId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["run", runId] }),
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
      } else if (e.topic === "run:completed" || e.topic === "run:failed" || e.topic === "run:cancelled") {
        setTerminal(e.topic.split(":")[1]);
        qc.invalidateQueries({ queryKey: ["run", runId] });
      }
    },
    { runId },
  );

  useEffect(() => {
    tailRef.current?.scrollTo({ top: tailRef.current.scrollHeight });
  }, [liveText]);

  const isLive = run.data?.status === "running" && terminal === null;
  const finalText = run.data?.final_text || "";
  const display = useMemo(() => (isLive ? liveText : finalText || liveText), [isLive, liveText, finalText]);

  if (run.isLoading) return <p className="p-6 text-sm text-[--color-fg-muted]">Loading run…</p>;
  if (!run.data) return <p className="p-6 text-sm text-[--color-fg-muted]">Run not found.</p>;

  const r = run.data;
  const totalTokens = r.input_tokens + r.output_tokens;
  const elapsed = r.ended_at
    ? (new Date(r.ended_at).getTime() - new Date(r.started_at).getTime()) / 1000
    : null;

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <div className="flex items-center gap-2 text-sm text-[--color-fg-muted]">
        <Link href={`/agents/${r.agent_id}`} className="hover:text-[--color-fg] inline-flex items-center gap-1">
          <ArrowLeft size={14} /> Back to agent
        </Link>
      </div>

      <header className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">Run #{r.id}</h1>
            <StatusBadge status={r.status} />
            <span className="badge badge-idle">{r.source}</span>
          </div>
          <p className="text-xs text-[--color-fg-muted] font-mono mt-2">
            started {new Date(r.started_at).toLocaleString()}
            {elapsed !== null && <> · {elapsed.toFixed(1)}s</>}
            {r.session_id && <> · session {r.session_id.slice(0, 8)}</>}
          </p>
        </div>
        {isLive && (
          <button
            onClick={() => cancel.mutate()}
            disabled={cancel.isPending}
            className="text-sm flex items-center gap-1 px-3 py-1.5 rounded border border-[--color-border] hover:bg-[--color-border] transition disabled:opacity-50"
          >
            <Square size={12} /> Cancel
          </button>
        )}
      </header>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Input tokens" value={r.input_tokens.toLocaleString()} />
        <Stat label="Output tokens" value={r.output_tokens.toLocaleString()} />
        <Stat label="Total tokens" value={totalTokens.toLocaleString()} />
        <Stat label="Cost" value={`$${r.cost_usd.toFixed(4)}`} />
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[--color-fg-muted]">Prompt</h2>
        <div className="card whitespace-pre-wrap text-sm font-mono">{r.prompt}</div>
      </section>

      <section className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[--color-fg-muted]">
            {isLive ? "Live output" : "Output"}
          </h2>
          {isLive && <span className="badge badge-running">streaming</span>}
        </div>
        <div
          ref={tailRef}
          className="card whitespace-pre-wrap text-sm font-mono max-h-[480px] overflow-y-auto"
        >
          {display || <span className="text-[--color-fg-muted]">(waiting for output…)</span>}
          {isLive && display && <span className="inline-block w-2 h-4 bg-[--color-accent] animate-pulse ml-0.5 align-middle" />}
        </div>
      </section>

      {tools.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[--color-fg-muted]">
            Tool calls ({tools.length})
          </h2>
          <ul className="space-y-1 text-xs font-mono">
            {tools.map((t, i) => (
              <li key={i} className="flex items-center gap-3">
                <span className="text-[--color-fg-muted]">{new Date(t.ts * 1000).toLocaleTimeString()}</span>
                <span className="text-[--color-accent]">{t.tool}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {r.error_message && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[--color-error]">Error</h2>
          <pre className="card text-sm whitespace-pre-wrap border-[--color-error]/40">{r.error_message}</pre>
        </section>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="card">
      <p className="text-xs uppercase tracking-wide text-[--color-fg-muted]">{label}</p>
      <p className="text-lg font-semibold mt-1 font-mono">{value}</p>
    </div>
  );
}
