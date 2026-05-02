"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Activity, Pause, Play } from "lucide-react";
import { useStream, type StreamEvent } from "@/lib/use-stream";
import { Badge } from "@/components/ui/badge";

interface FeedItem extends StreamEvent {
  id: string;
}

const TOPIC_LABEL: Record<string, { label: string; tone: "running" | "error" | "warn" | "idle" | "accent" }> = {
  "run:started": { label: "Run started", tone: "running" },
  "run:completed": { label: "Run completed", tone: "running" },
  "run:failed": { label: "Run failed", tone: "error" },
  "run:cancelled": { label: "Run cancelled", tone: "warn" },
  "run:tool": { label: "Tool used", tone: "idle" },
  "run:message": { label: "Message", tone: "idle" },
  "agent:registered": { label: "Agent registered", tone: "accent" },
  "agent:updated": { label: "Agent updated", tone: "accent" },
  "skill:registered": { label: "Skill registered", tone: "accent" },
  "improvement:proposed": { label: "Improvement proposed", tone: "warn" },
};

export function ActivityFeed({
  limit = 30,
  showHeader = true,
  filter,
}: {
  limit?: number;
  showHeader?: boolean;
  filter?: (e: StreamEvent) => boolean;
}) {
  const [items, setItems] = useState<FeedItem[]>([]);
  const [paused, setPaused] = useState(false);

  useStream("run:*,agent:*,skill:*,improvement:*", (e) => {
    if (paused) return;
    if (e.topic === "run:message") return; // too noisy for the feed
    if (filter && !filter(e)) return;
    setItems((prev) => [{ ...e, id: `${e.ts}-${e.topic}-${Math.random()}` }, ...prev].slice(0, limit));
  });

  // Empty placeholder hint while we wait for first event.
  const [waited, setWaited] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setWaited(true), 1500);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="surface flex flex-col h-full overflow-hidden">
      {showHeader && (
        <header className="flex items-center justify-between px-4 py-3 border-b border-[--color-border]">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Activity size={14} className="text-[--color-accent-strong]" />
            Activity
            {!paused && <span className="pill pill-running">live</span>}
          </div>
          <button
            onClick={() => setPaused((p) => !p)}
            className="text-xs text-[--color-fg-muted] hover:text-[--color-fg] inline-flex items-center gap-1"
            title={paused ? "Resume" : "Pause"}
          >
            {paused ? <Play size={12} /> : <Pause size={12} />}
            {paused ? "resume" : "pause"}
          </button>
        </header>
      )}
      <div className="flex-1 overflow-y-auto">
        {items.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-[--color-fg-muted]">
            {waited
              ? "No activity yet. Trigger a run from any agent and it lands here."
              : "Connecting to event stream…"}
          </div>
        ) : (
          <ul className="divide-y divide-[--color-border]">
            {items.map((it) => (
              <FeedRow key={it.id} item={it} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function FeedRow({ item }: { item: FeedItem }) {
  const meta = TOPIC_LABEL[item.topic] ?? { label: item.topic, tone: "idle" as const };
  const agent = item.data?.agent ?? "";
  const runId = item.data?.run_id;
  const subject = runId ? `run #${runId}${agent ? ` · ${agent}` : ""}` : agent;

  const detail = (() => {
    if (item.topic === "run:completed") {
      const tokens = (item.data?.input_tokens ?? 0) + (item.data?.output_tokens ?? 0);
      const cost = item.data?.cost_usd ?? 0;
      return `${tokens.toLocaleString()} tok · $${Number(cost).toFixed(4)}`;
    }
    if (item.topic === "run:failed" || item.topic === "run:cancelled") {
      return item.data?.error || "";
    }
    if (item.topic === "run:tool") {
      return item.data?.tool;
    }
    return "";
  })();

  const Inner = (
    <div className="px-4 py-2.5 flex items-start justify-between gap-3 hover:bg-[--color-bg-elev-2]/50 transition-colors">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge tone={meta.tone}>{meta.label}</Badge>
          {subject && <span className="text-xs font-mono text-[--color-fg-muted] truncate">{subject}</span>}
        </div>
        {detail && (
          <p className="text-[11px] text-[--color-fg-subtle] mt-1 truncate font-mono">{detail}</p>
        )}
      </div>
      <span className="text-[10px] text-[--color-fg-subtle] font-mono shrink-0 mt-0.5">
        {new Date(item.ts * 1000).toLocaleTimeString()}
      </span>
    </div>
  );

  return runId ? <Link href={`/runs/${runId}`} className="block">{Inner}</Link> : <li>{Inner}</li>;
}
