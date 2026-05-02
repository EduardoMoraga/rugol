"use client";

import { useEffect, useState } from "react";
import { useStream, type StreamEvent } from "@/lib/use-stream";

export function LiveFeed() {
  const [events, setEvents] = useState<StreamEvent[]>([]);

  useStream("run:*,agent:*,improvement:*", (e) => {
    setEvents((prev) => [e, ...prev].slice(0, 50));
  });

  return (
    <div className="card h-full flex flex-col">
      <header className="flex items-center justify-between mb-3">
        <h3 className="font-semibold">Live feed</h3>
        <span className="badge badge-running">SSE</span>
      </header>

      {events.length === 0 ? (
        <p className="text-sm text-[--color-fg-muted]">Waiting for events…</p>
      ) : (
        <ul className="space-y-2 overflow-y-auto flex-1 text-sm">
          {events.map((e, i) => (
            <li key={i} className="flex items-start gap-2 font-mono text-xs">
              <span className="text-[--color-fg-muted] shrink-0">
                {new Date(e.ts * 1000).toLocaleTimeString()}
              </span>
              <span className="text-[--color-accent] shrink-0">{e.topic}</span>
              <span className="text-[--color-fg-muted] truncate">
                {JSON.stringify(e.data).slice(0, 80)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
