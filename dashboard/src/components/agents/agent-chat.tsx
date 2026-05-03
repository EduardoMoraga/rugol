"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowUp, RotateCcw, Square, ExternalLink, User, Bot } from "lucide-react";
import { cancelRun, fetchRun, runAgentNow, type RunDetail } from "@/lib/api";
import { useStream } from "@/lib/use-stream";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { MarkdownView } from "@/components/ui/markdown";
import { toast } from "@/components/ui/toast";

interface Turn {
  /** local turn id (UI only). */
  id: string;
  user: string;
  /** run id once the backend assigned one. */
  runId?: number;
  /** assistant text accumulated from SSE deltas. */
  assistant: string;
  /** session id returned by the run for chaining the next turn. */
  sessionId?: string | null;
  status: "queued" | "streaming" | "completed" | "failed" | "cancelled";
  startedAt: number;
  cost?: number;
}

interface Props {
  agentId: number;
  agentName: string;
  modelLabel: string;
  agentBusy: boolean;
}

/**
 * Multi-turn chat with a single agent (Capa 2).
 *
 * Each turn POSTs `/api/agents/:id/run` with the previous turn's
 * `session_id`, so the agent keeps its memory across the conversation.
 * Live output streams in via the SSE bus filtered by run_id, and lands
 * persisted as `final_text` on the run row when the LLM finishes.
 */
export function AgentChat({ agentId, agentName, modelLabel, agentBusy }: Props) {
  const qc = useQueryClient();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const tailRef = useRef<HTMLDivElement>(null);
  const liveTurnIdRef = useRef<string | null>(null);

  const lastSessionId = (() => {
    for (let i = turns.length - 1; i >= 0; i--) {
      const sid = turns[i].sessionId;
      if (sid) return sid;
    }
    return null;
  })();

  const send = useMutation({
    mutationFn: async (prompt: string) => {
      const local: Turn = {
        id: `t-${Date.now()}`,
        user: prompt,
        assistant: "",
        status: "queued",
        startedAt: Date.now(),
        sessionId: lastSessionId,
      };
      liveTurnIdRef.current = local.id;
      setTurns((t) => [...t, local]);
      const res = await runAgentNow(agentId, prompt);
      setTurns((t) =>
        t.map((x) =>
          x.id === local.id ? { ...x, runId: res.run_id, status: "streaming" } : x,
        ),
      );
      return { localId: local.id, runId: res.run_id };
    },
    onError: (e: Error) => {
      toast({ tone: "error", title: "No se pudo enviar", body: e.message });
      const id = liveTurnIdRef.current;
      if (id) {
        setTurns((t) =>
          t.map((x) => (x.id === id ? { ...x, status: "failed", assistant: e.message } : x)),
        );
      }
    },
  });

  const cancel = useMutation({
    mutationFn: (runId: number) => cancelRun(runId),
    onSuccess: () =>
      toast({ tone: "info", title: "Cancelación solicitada" }),
  });

  // Stream consumer: deltas + completion finalize the matching turn.
  useStream(
    "run:*",
    (e) => {
      const rid = e.data?.run_id;
      if (typeof rid !== "number") return;
      setTurns((prev) => {
        let touched = false;
        const next = prev.map((t) => {
          if (t.runId !== rid) return t;
          touched = true;
          if (e.topic === "run:message" && e.data?.kind === "text" && e.data?.delta) {
            return { ...t, assistant: t.assistant + e.data.delta, status: "streaming" as const };
          }
          if (e.topic === "run:completed") {
            return { ...t, status: "completed" as const };
          }
          if (e.topic === "run:failed") {
            return { ...t, status: "failed" as const };
          }
          if (e.topic === "run:cancelled") {
            return { ...t, status: "cancelled" as const };
          }
          return t;
        });
        if (touched && (e.topic === "run:completed" || e.topic === "run:failed")) {
          const liveId = liveTurnIdRef.current;
          if (liveId) {
            // Hydrate session_id + cost asynchronously after the run is final.
            const target = next.find((x) => x.id === liveId);
            if (target?.runId) {
              fetchRun(target.runId)
                .then((r: RunDetail) => {
                  setTurns((p) =>
                    p.map((x) =>
                      x.id === liveId
                        ? {
                            ...x,
                            sessionId: r.session_id ?? x.sessionId,
                            cost: r.cost_usd,
                            // Prefer the persisted final_text if SSE missed any deltas.
                            assistant: x.assistant || r.final_text || "",
                          }
                        : x,
                    ),
                  );
                })
                .catch(() => {});
            }
            liveTurnIdRef.current = null;
            qc.invalidateQueries({ queryKey: ["agent-runs", agentId] });
            qc.invalidateQueries({ queryKey: ["agent", agentId] });
          }
        }
        return next;
      });
    },
  );

  useEffect(() => {
    tailRef.current?.scrollTo({ top: tailRef.current.scrollHeight, behavior: "smooth" });
  }, [turns]);

  function submit(e: FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || send.isPending) return;
    setDraft("");
    send.mutate(text);
  }

  function reset() {
    if (turns.length > 0 && !confirm("Esto reinicia la conversación (pierde el contexto local). ¿Seguir?")) return;
    setTurns([]);
    liveTurnIdRef.current = null;
  }

  const liveTurn = turns.find((t) => t.status === "queued" || t.status === "streaming");
  const submitDisabled = send.isPending || !draft.trim() || !!liveTurn;

  return (
    <div className="surface flex flex-col h-[640px]">
      <header className="px-5 py-3 border-b border-[--color-border] flex items-center justify-between">
        <div className="min-w-0">
          <p className="text-sm font-medium tracking-tight">
            Chat con {agentName}
            {lastSessionId && (
              <span className="ml-2 text-[10px] font-mono text-[--color-fg-subtle]">
                · sesión {lastSessionId.slice(0, 8)}
              </span>
            )}
          </p>
          <p className="text-[11px] text-[--color-fg-muted]">
            {modelLabel}
            {agentBusy && !liveTurn && (
              <span className="ml-2 text-[--color-warn]">· el agente está ocupado en otra fuente</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {liveTurn?.runId && (liveTurn.status === "streaming" || liveTurn.status === "queued") && (
            <Button
              variant="danger"
              size="sm"
              onClick={() => cancel.mutate(liveTurn.runId!)}
              disabled={cancel.isPending}
            >
              <Square size={11} /> Cancelar
            </Button>
          )}
          {turns.length > 0 && (
            <Button variant="ghost" size="sm" onClick={reset} disabled={!!liveTurn}>
              <RotateCcw size={11} /> Reiniciar
            </Button>
          )}
        </div>
      </header>

      <div ref={tailRef} className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
        {turns.length === 0 ? (
          <EmptyChat agentName={agentName} />
        ) : (
          turns.map((t) => <TurnView key={t.id} turn={t} />)
        )}
      </div>

      <form onSubmit={submit} className="border-t border-[--color-border] p-3">
        <div className="flex items-end gap-2">
          <Textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                submit(e as unknown as FormEvent);
              }
            }}
            rows={2}
            placeholder={
              liveTurn
                ? "El agente está respondiendo… esperá que termine"
                : `Pedile algo a ${agentName}… (Ctrl+Enter para enviar)`
            }
            disabled={!!liveTurn}
            className="resize-none"
          />
          <Button type="submit" variant="primary" disabled={submitDisabled} size="md">
            <ArrowUp size={14} />
          </Button>
        </div>
        {lastSessionId ? (
          <p className="text-[10.5px] text-[--color-fg-subtle] mt-1.5">
            Cada mensaje continúa la sesión anterior — el agente recuerda el contexto.
            Reiniciá para empezar de cero.
          </p>
        ) : (
          <p className="text-[10.5px] text-[--color-fg-subtle] mt-1.5">
            El primer mensaje crea una sesión nueva.
          </p>
        )}
      </form>
    </div>
  );
}

function EmptyChat({ agentName }: { agentName: string }) {
  return (
    <div className="text-center text-sm text-[--color-fg-muted] py-12 space-y-2">
      <Bot size={28} className="mx-auto text-[--color-fg-subtle]" />
      <p>
        Empezá la conversación con <span className="text-[--color-fg]">{agentName}</span>.
      </p>
      <p className="text-[12px] text-[--color-fg-subtle] max-w-md mx-auto">
        Cada turno se ejecuta como un run real — vas a ver tokens, costo y poder
        abrir cualquier respuesta en su página de detalle para inspeccionarla.
      </p>
    </div>
  );
}

function TurnView({ turn }: { turn: Turn }) {
  return (
    <div className="space-y-3">
      <div className="flex items-start gap-3">
        <div className="w-7 h-7 rounded-full grid place-items-center bg-[--color-bg-elev-2] border border-[--color-border] shrink-0">
          <User size={13} className="text-[--color-fg-muted]" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[10px] text-[--color-fg-subtle] uppercase tracking-wider mb-1">
            vos
          </p>
          <pre className="text-[13.5px] whitespace-pre-wrap font-sans text-[--color-fg] leading-relaxed">
            {turn.user}
          </pre>
        </div>
      </div>

      <div className="flex items-start gap-3">
        <div className="w-7 h-7 rounded-full grid place-items-center bg-[--color-accent-soft] border border-[--color-accent]/30 shrink-0">
          <Bot size={13} className="text-[--color-accent-strong]" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <p className="text-[10px] text-[--color-fg-subtle] uppercase tracking-wider">
              agente
              {turn.status === "queued" && " · queued"}
              {turn.status === "streaming" && " · streaming"}
              {turn.status === "completed" && " · ok"}
              {turn.status === "failed" && (
                <span className="text-[--color-error]"> · failed</span>
              )}
              {turn.status === "cancelled" && (
                <span className="text-[--color-warn]"> · cancelled</span>
              )}
            </p>
            {turn.runId && (
              <Link
                href={`/runs/${turn.runId}`}
                className="text-[10px] text-[--color-fg-muted] hover:text-[--color-fg] inline-flex items-center gap-1"
                target="_blank"
                rel="noopener noreferrer"
              >
                run #{turn.runId} <ExternalLink size={9} />
                {turn.cost !== undefined && (
                  <span className="font-mono ml-1">${turn.cost.toFixed(4)}</span>
                )}
              </Link>
            )}
          </div>
          {turn.assistant ? (
            <MarkdownView>{turn.assistant}</MarkdownView>
          ) : turn.status === "queued" ? (
            <p className="text-[12.5px] text-[--color-fg-subtle]">esperando…</p>
          ) : (
            <p className="text-[12.5px] text-[--color-fg-subtle]">
              <span className="inline-block w-2 h-3.5 bg-[--color-accent-strong] align-middle animate-[pulse-soft_1s_ease-in-out_infinite]" />
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
