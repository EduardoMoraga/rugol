"use client";

import { useEffect, useRef } from "react";

export interface StreamEvent {
  topic: string;
  data: Record<string, any>;
  ts: number;
}

/** Subscribe to SSE topics. Reconnects with exponential backoff on error. */
export function useStream(topics: string, onEvent: (evt: StreamEvent) => void) {
  const handlerRef = useRef(onEvent);
  handlerRef.current = onEvent;

  useEffect(() => {
    let es: EventSource | null = null;
    let backoff = 500;
    let cancelled = false;

    function connect() {
      if (cancelled) return;
      const url = `/api/stream?topics=${encodeURIComponent(topics)}`;
      es = new EventSource(url);
      es.addEventListener("message", (e) => {
        try {
          const data = JSON.parse((e as MessageEvent).data);
          handlerRef.current(data as StreamEvent);
          backoff = 500;
        } catch (err) {
          // ignore malformed events
        }
      });
      es.addEventListener("error", () => {
        es?.close();
        if (!cancelled) {
          setTimeout(connect, backoff);
          backoff = Math.min(backoff * 2, 15_000);
        }
      });
    }

    connect();
    return () => {
      cancelled = true;
      es?.close();
    };
  }, [topics]);
}
