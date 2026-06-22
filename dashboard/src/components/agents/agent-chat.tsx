"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowUp, RotateCcw, Square, ExternalLink, User, Bot, Zap, Brain, Scale, BookmarkPlus } from "lucide-react";
import { addProjectLesson, cancelRun, fetchRun, runAgentNow, type RunDetail, type RunNowOptions } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
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
  taskType?: TaskType;
  /** Devil's advocate critique attached to this turn (Capa 4). */
  advocate?: {
    runId?: number;
    text: string;
    status: Turn["status"];
    cost?: number;
  };
}

type TaskType = "fast" | "think" | "deep";

const TASK_TYPES: { id: TaskType; labelKey: string; hintKey: string; icon: typeof Zap }[] = [
  { id: "fast", labelKey: "chat.fast", hintKey: "chat.fastHint", icon: Zap },
  { id: "think", labelKey: "chat.think", hintKey: "chat.thinkHint", icon: Brain },
  { id: "deep", labelKey: "chat.deep", hintKey: "chat.deepHint", icon: Scale },
];

interface Props {
  agentId: number;
  agentName: string;
  modelLabel: string;
  agentBusy: boolean;
  /** Capa 7: when set, the chat exposes a "Promote to lesson" button that
   * appends bubble text to this project's living lesson list. */
  projectSlug: string | null;
  /** Used in the context banner so the user can see what the agent has been
   * told before each run — the project's mission and lesson count. */
  projectName?: string | null;
  projectMission?: string | null;
  projectLessonCount?: number;
  /** Ejemplos clicables que se muestran cuando el chat está vacío (copiloto). */
  examples?: string[];
}

/**
 * Multi-turn chat with a single agent (Capa 2).
 *
 * Each turn POSTs `/api/agents/:id/run` with the previous turn's
 * `session_id`, so the agent keeps its memory across the conversation.
 * Live output streams in via the SSE bus filtered by run_id, and lands
 * persisted as `final_text` on the run row when the LLM finishes.
 */
export function AgentChat({
  agentId,
  agentName,
  modelLabel,
  agentBusy,
  projectSlug,
  projectName,
  projectMission,
  projectLessonCount = 0,
  examples,
}: Props) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [taskType, setTaskType] = useState<TaskType>("think");
  const [seekAdvocate, setSeekAdvocate] = useState(false);
  const tailRef = useRef<HTMLDivElement>(null);
  const liveTurnIdRef = useRef<string | null>(null);
  // Map advocate runId → parent turn id, so when SSE events arrive for the
  // critique run we can attach them to the right bubble.
  const advocateRunToTurnRef = useRef<Map<number, string>>(new Map());

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
        taskType,
      };
      liveTurnIdRef.current = local.id;
      setTurns((t) => [...t, local]);
      const opts: RunNowOptions = {
        session_id: lastSessionId,
        task_type: taskType,
        seek_devils_advocate: seekAdvocate,
      };
      const res = await runAgentNow(agentId, prompt, opts);
      setTurns((t) =>
        t.map((x) =>
          x.id === local.id ? { ...x, runId: res.run_id, status: "streaming" } : x,
        ),
      );
      return { localId: local.id, runId: res.run_id };
    },
    onError: (e: Error) => {
      toast({ tone: "error", title: t("common.error"), body: e.message });
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
  // Also listens for devil's advocate runs (source=devils-advocate, with
  // advocate_for_run_id pointing at a parent run) and routes their text
  // into the parent turn's `advocate` field.
  useStream(
    "run:*",
    (e) => {
      const rid = e.data?.run_id;
      if (typeof rid !== "number") return;

      // First: register a new advocate run when it starts so we can track
      // its deltas afterwards. The bus emits run:started with both the
      // advocate's run_id AND the parent's advocate_for_run_id.
      if (e.topic === "run:started" && typeof e.data?.advocate_for_run_id === "number") {
        const parentRunId = e.data.advocate_for_run_id;
        setTurns((prev) => {
          const parent = prev.find((t) => t.runId === parentRunId);
          if (!parent) return prev;
          advocateRunToTurnRef.current.set(rid, parent.id);
          return prev.map((t) =>
            t.id === parent.id
              ? { ...t, advocate: { runId: rid, text: "", status: "streaming" as const } }
              : t,
          );
        });
        return;
      }

      // Second: route this event to either a primary turn OR an advocate.
      const advocateParentTurnId = advocateRunToTurnRef.current.get(rid);
      setTurns((prev) => {
        let touched = false;
        const next = prev.map((t) => {
          // -------- Advocate path --------
          if (advocateParentTurnId && t.id === advocateParentTurnId && t.advocate) {
            touched = true;
            const adv = t.advocate;
            if (e.topic === "run:message" && e.data?.kind === "text" && e.data?.delta) {
              return {
                ...t,
                advocate: { ...adv, text: adv.text + e.data.delta, status: "streaming" as const },
              };
            }
            if (e.topic === "run:completed") {
              return { ...t, advocate: { ...adv, status: "completed" as const } };
            }
            if (e.topic === "run:failed") {
              return { ...t, advocate: { ...adv, status: "failed" as const } };
            }
            if (e.topic === "run:cancelled") {
              return { ...t, advocate: { ...adv, status: "cancelled" as const } };
            }
            return t;
          }
          // -------- Primary turn path --------
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

        // After primary completion: hydrate session + cost.
        if (touched && (e.topic === "run:completed" || e.topic === "run:failed") && !advocateParentTurnId) {
          const liveId = liveTurnIdRef.current;
          if (liveId) {
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

        // After advocate completion: hydrate cost.
        if (touched && advocateParentTurnId && (e.topic === "run:completed" || e.topic === "run:failed")) {
          fetchRun(rid)
            .then((r: RunDetail) => {
              setTurns((p) =>
                p.map((x) =>
                  x.id === advocateParentTurnId && x.advocate
                    ? {
                        ...x,
                        advocate: {
                          ...x.advocate,
                          cost: r.cost_usd,
                          text: x.advocate.text || r.final_text || "",
                        },
                      }
                    : x,
                ),
              );
            })
            .catch(() => {});
        }

        return next;
      });
    },
  );

  useEffect(() => {
    tailRef.current?.scrollTo({ top: tailRef.current.scrollHeight, behavior: "smooth" });
  }, [turns]);

  // Polling safety net (Capa 14): if a turn or its advocate is still in
  // "queued" / "streaming" state, every 4s we hit /api/runs/{id}. If the
  // backend reports completed/failed/cancelled, we hydrate locally — this
  // covers SSE disconnects (e.g. backend restart) where the run finishes
  // but the completion event never reaches us. Without this, the UI can
  // sit at "streaming" forever even though the run finished minutes ago.
  useEffect(() => {
    const inflight = turns.filter(
      (t) => t.runId && (t.status === "queued" || t.status === "streaming"),
    );
    const inflightAdvocates = turns.filter(
      (t) => t.advocate?.runId && (t.advocate.status === "queued" || t.advocate.status === "streaming"),
    );
    if (inflight.length === 0 && inflightAdvocates.length === 0) return;

    let cancelled = false;
    const interval = window.setInterval(async () => {
      // Re-read latest turns inside the interval via setTurns(prev → prev).
      // (prev gives us the freshest state without re-running the effect.)
      let snapshot: Turn[] = [];
      setTurns((prev) => {
        snapshot = prev;
        return prev;
      });

      for (const t of snapshot) {
        if (cancelled) return;
        // Primary turn check.
        if (t.runId && (t.status === "queued" || t.status === "streaming")) {
          try {
            const r = await fetchRun(t.runId);
            if (cancelled) return;
            if (r.status === "completed" || r.status === "failed" || r.status === "cancelled") {
              setTurns((prev) =>
                prev.map((x) =>
                  x.id === t.id
                    ? {
                        ...x,
                        status: r.status as Turn["status"],
                        sessionId: r.session_id ?? x.sessionId,
                        cost: r.cost_usd,
                        // Prefer persisted final_text over (possibly empty) live deltas.
                        assistant: r.final_text || x.assistant || "",
                      }
                    : x,
                ),
              );
              if (liveTurnIdRef.current === t.id) liveTurnIdRef.current = null;
              qc.invalidateQueries({ queryKey: ["agent-runs", agentId] });
            }
          } catch {
            // Network blip; next tick retries.
          }
        }
        // Advocate turn check.
        if (
          t.advocate?.runId &&
          (t.advocate.status === "queued" || t.advocate.status === "streaming")
        ) {
          try {
            const r = await fetchRun(t.advocate.runId);
            if (cancelled) return;
            if (r.status === "completed" || r.status === "failed" || r.status === "cancelled") {
              setTurns((prev) =>
                prev.map((x) =>
                  x.id === t.id && x.advocate
                    ? {
                        ...x,
                        advocate: {
                          ...x.advocate,
                          status: r.status as Turn["status"],
                          cost: r.cost_usd,
                          text: r.final_text || x.advocate.text || "",
                        },
                      }
                    : x,
                ),
              );
            }
          } catch {
            // ignore
          }
        }
      }
    }, 4000);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [turns.map((t) => `${t.runId}:${t.status}:${t.advocate?.runId}:${t.advocate?.status}`).join("|")]);

  function submit(e: FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || send.isPending) return;
    setDraft("");
    send.mutate(text);
  }

  function reset() {
    if (turns.length > 0 && !confirm(t("chat.restart") + " — " + t("chat.firstMessage"))) return;
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
            {t("chat.title")} {agentName}
            {lastSessionId && (
              <span className="ml-2 text-[10px] font-mono text-[--color-fg-subtle]">
                · {t("chat.session")} {lastSessionId.slice(0, 8)}
              </span>
            )}
          </p>
          <p className="text-[11px] text-[--color-fg-muted]">
            {modelLabel}
            {agentBusy && !liveTurn && (
              <span className="ml-2 text-[--color-warn]">· {t("chat.busy")}</span>
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
              <Square size={11} /> {t("chat.cancel")}
            </Button>
          )}
          {turns.length > 0 && (
            <Button variant="ghost" size="sm" onClick={reset} disabled={!!liveTurn}>
              <RotateCcw size={11} /> {t("chat.restart")}
            </Button>
          )}
        </div>
      </header>

      <div ref={tailRef} className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
        {turns.length === 0 ? (
          <EmptyChat
            agentName={agentName}
            projectName={projectName}
            projectMission={projectMission}
            projectLessonCount={projectLessonCount}
            examples={examples}
            onPickExample={(s) => setDraft(s)}
          />
        ) : (
          turns.map((t) => <TurnView key={t.id} turn={t} projectSlug={projectSlug} />)
        )}
      </div>

      <form onSubmit={submit} className="border-t border-[--color-border] p-3 space-y-2">
        <div className="flex items-center justify-between gap-2 text-[11px]">
          <div className="inline-flex items-center gap-1 surface px-1 py-1">
            {TASK_TYPES.map((tt) => {
              const Icon = tt.icon;
              const active = taskType === tt.id;
              return (
                <button
                  key={tt.id}
                  type="button"
                  onClick={() => setTaskType(tt.id)}
                  disabled={!!liveTurn}
                  title={t(tt.hintKey)}
                  className={`px-2 py-1 rounded-md inline-flex items-center gap-1 transition ${
                    active
                      ? "bg-[--color-accent-soft] text-[--color-accent-strong] font-medium"
                      : "text-[--color-fg-muted] hover:text-[--color-fg]"
                  }`}
                >
                  <Icon size={11} /> {t(tt.labelKey)}
                </button>
              );
            })}
          </div>
          <label
            className={`inline-flex items-center gap-1.5 cursor-pointer transition ${
              seekAdvocate ? "text-[--color-accent-strong]" : "text-[--color-fg-muted] hover:text-[--color-fg]"
            }`}
            title={t("chat.devilsAdvocateHint")}
          >
            <input
              type="checkbox"
              checked={seekAdvocate}
              onChange={(e) => setSeekAdvocate(e.target.checked)}
              disabled={!!liveTurn}
              className="accent-[--color-accent-strong]"
            />
            <Scale size={11} /> {t("chat.devilsAdvocate")}
          </label>
        </div>
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
                ? t("chat.placeholderBusy")
                : `${t("chat.placeholder")} ${agentName}… ${t("chat.placeholderHint")}`
            }
            disabled={!!liveTurn}
            className="resize-none"
          />
          <Button type="submit" variant="primary" disabled={submitDisabled} size="md">
            <ArrowUp size={14} />
          </Button>
        </div>
        {lastSessionId ? (
          <p className="text-[10.5px] text-[--color-fg-subtle]">{t("chat.sessionContinues")}</p>
        ) : (
          <p className="text-[10.5px] text-[--color-fg-subtle]">{t("chat.firstMessage")}</p>
        )}
      </form>
    </div>
  );
}

function EmptyChat({
  agentName,
  projectName,
  projectMission,
  projectLessonCount = 0,
  examples,
  onPickExample,
}: {
  agentName: string;
  projectName?: string | null;
  projectMission?: string | null;
  projectLessonCount?: number;
  examples?: string[];
  onPickExample?: (s: string) => void;
}) {
  const { t } = useI18n();
  return (
    <div className="text-center text-sm text-[--color-fg-muted] py-8 space-y-4">
      <Bot size={28} className="mx-auto text-[--color-fg-subtle]" />
      <p>
        {t("chat.empty")} <span className="text-[--color-fg]">{agentName}</span>.
      </p>
      {examples && examples.length > 0 && (
        <div className="flex flex-wrap justify-center gap-2 max-w-2xl mx-auto pt-1">
          {examples.map((ex, i) => (
            <button
              key={i}
              type="button"
              onClick={() => onPickExample?.(ex)}
              className="text-left text-[12.5px] px-3 py-1.5 rounded-full border border-[--color-border] bg-[--color-bg-elev] text-[--color-fg] hover:border-[--color-accent] hover:text-[--color-accent-strong] transition"
            >
              {ex}
            </button>
          ))}
        </div>
      )}
      {(projectMission || projectLessonCount > 0) && (
        <div className="surface text-left max-w-lg mx-auto px-4 py-3 space-y-2">
          <p className="text-[10px] uppercase tracking-widest text-[--color-fg-muted] font-medium">
            {t("chat.knownContext")}
          </p>
          {projectMission && (
            <div>
              <p className="text-[10px] text-[--color-fg-subtle] uppercase tracking-wider">
                {t("chat.mission")} {projectName ? `· ${projectName}` : ""}
              </p>
              <p className="text-[12.5px] text-[--color-fg] leading-relaxed mt-0.5">
                {projectMission}
              </p>
            </div>
          )}
          {projectLessonCount > 0 && (
            <p className="text-[11px] text-[--color-fg-muted]">
              + {projectLessonCount}{" "}
              {projectLessonCount === 1 ? t("chat.lesson") : t("chat.lessons")}
            </p>
          )}
        </div>
      )}
      <p className="text-[11.5px] text-[--color-fg-subtle] max-w-md mx-auto">
        {t("chat.eachTurn")}
      </p>
    </div>
  );
}

function PromoteToLessonButton({
  projectSlug,
  text,
  defaultKind = "lesson",
  label = "Promover a lección",
}: {
  projectSlug: string | null;
  text: string;
  defaultKind?: "lesson" | "bias" | "fact";
  label?: string;
}) {
  const [done, setDone] = useState(false);
  const promote = useMutation({
    mutationFn: () =>
      addProjectLesson(projectSlug as string, {
        text: text.slice(0, 480),
        kind: defaultKind,
      }),
    onSuccess: () => {
      setDone(true);
      toast({
        tone: "success",
        title: "Guardada como lección del proyecto",
        body: "Todos los agentes del equipo van a leerla antes de cada run.",
      });
    },
    onError: (e: Error) =>
      toast({ tone: "error", title: "No se pudo guardar", body: e.message }),
  });
  if (!projectSlug || !text.trim()) return null;
  return (
    <button
      type="button"
      onClick={() => promote.mutate()}
      disabled={promote.isPending || done}
      title="Agregar al banco de lecciones del proyecto"
      className={`text-[10px] inline-flex items-center gap-1 px-1.5 py-0.5 rounded transition ${
        done
          ? "text-[--color-success] cursor-default"
          : "text-[--color-fg-muted] hover:text-[--color-accent-strong] hover:bg-[--color-bg-elev]"
      }`}
    >
      <BookmarkPlus size={10} /> {done ? "guardada" : promote.isPending ? "…" : label}
    </button>
  );
}

function TurnView({ turn, projectSlug }: { turn: Turn; projectSlug: string | null }) {
  const { t } = useI18n();
  const tt = TASK_TYPES.find((x) => x.id === turn.taskType);
  return (
    <div className="space-y-3">
      <div className="flex items-start gap-3">
        <div className="w-7 h-7 rounded-full grid place-items-center bg-[--color-bg-elev-2] border border-[--color-border] shrink-0">
          <User size={13} className="text-[--color-fg-muted]" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[10px] text-[--color-fg-subtle] uppercase tracking-wider mb-1">
            {t("chat.you")}
            {tt && (
              <span className="ml-2 text-[--color-fg-muted]">
                · {t(tt.labelKey).toLowerCase()}
              </span>
            )}
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
              {t("chat.agent")}
              {turn.status === "queued" && ` · ${t("chat.queued")}`}
              {turn.status === "streaming" && ` · ${t("chat.streaming")}`}
              {turn.status === "completed" && ` · ${t("chat.ok")}`}
              {turn.status === "failed" && (
                <span className="text-[--color-error]"> · {t("chat.failed")}</span>
              )}
              {turn.status === "cancelled" && (
                <span className="text-[--color-warn]"> · {t("chat.cancelled")}</span>
              )}
            </p>
            <div className="flex items-center gap-1">
              {turn.status === "completed" && turn.assistant && (
                <PromoteToLessonButton
                  projectSlug={projectSlug}
                  text={turn.assistant}
                  defaultKind="lesson"
                />
              )}
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
          </div>
          {turn.assistant ? (
            <MarkdownView>{turn.assistant}</MarkdownView>
          ) : turn.status === "queued" ? (
            <p className="text-[12.5px] text-[--color-fg-subtle]">{t("chat.waiting")}</p>
          ) : (
            <p className="text-[12.5px] text-[--color-fg-subtle]">
              <span className="inline-block w-2 h-3.5 bg-[--color-accent-strong] align-middle animate-[pulse-soft_1s_ease-in-out_infinite]" />
            </p>
          )}
        </div>
      </div>

      {turn.advocate && (
        <div className="flex items-start gap-3 pl-7 border-l-2 border-[--color-warn]/40 ml-3">
          <div className="w-7 h-7 rounded-full grid place-items-center bg-[--color-warn]/15 border border-[--color-warn]/40 shrink-0">
            <Scale size={13} className="text-[--color-warn]" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-1">
              <p className="text-[10px] text-[--color-warn] uppercase tracking-wider font-medium">
                {t("chat.advocate")}
                {turn.advocate.status === "streaming" && ` · ${t("chat.streaming")}`}
                {turn.advocate.status === "completed" && ` · ${t("chat.ok")}`}
                {turn.advocate.status === "failed" && ` · ${t("chat.failed")}`}
              </p>
              <div className="flex items-center gap-1">
                {turn.advocate.status === "completed" && turn.advocate.text && (
                  <PromoteToLessonButton
                    projectSlug={projectSlug}
                    text={turn.advocate.text}
                    defaultKind="bias"
                    label="Promover crítica a lección"
                  />
                )}
                {turn.advocate.runId && (
                  <Link
                    href={`/runs/${turn.advocate.runId}`}
                    className="text-[10px] text-[--color-fg-muted] hover:text-[--color-fg] inline-flex items-center gap-1"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    run #{turn.advocate.runId} <ExternalLink size={9} />
                    {turn.advocate.cost !== undefined && (
                      <span className="font-mono ml-1">${turn.advocate.cost.toFixed(4)}</span>
                    )}
                  </Link>
                )}
              </div>
            </div>
            {turn.advocate.text ? (
              <MarkdownView>{turn.advocate.text}</MarkdownView>
            ) : (
              <p className="text-[12.5px] text-[--color-fg-subtle]">
                <span className="inline-block w-2 h-3.5 bg-[--color-warn] align-middle animate-[pulse-soft_1s_ease-in-out_infinite]" />
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
