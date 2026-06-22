"use client";

/**
 * Página pública de entrevista del CANDIDATO (ex-ante).
 *
 * El reclutador genera un link (/interview/<token>); el candidato lo abre,
 * conversa con Sofía respondiendo él mismo, y al terminar la entrevista se
 * puntúa (BARS) y entra al pipeline. Es full-screen (overlay fijo) para no
 * mostrar la nav del dashboard — es la experiencia del candidato, no del
 * reclutador.
 *
 * Nota: la app es local-first; este link funciona en la misma máquina/LAN
 * (kiosko) o donde el dashboard esté accesible.
 */
import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Bot, User, Send, Sparkles, ClipboardCheck, CheckCircle2 } from "lucide-react";
import {
  fetchInterviewLink,
  interviewTurn,
  scoreTextInterview,
  type InterviewTurnInput,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { FieldLabel, Input } from "@/components/ui/input";
import { useI18n } from "@/lib/i18n";

export default function CandidateInterviewPage() {
  const { t } = useI18n();
  const params = useParams<{ token: string }>();
  const token = params.token;

  const linkQ = useQuery({
    queryKey: ["interview-link", token],
    queryFn: () => fetchInterviewLink(token),
    enabled: !!token,
    retry: false,
  });

  const [phase, setPhase] = useState<"welcome" | "chat" | "done">("welcome");
  const [name, setName] = useState("");
  const [turns, setTurns] = useState<InterviewTurnInput[]>([]);
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (linkQ.data?.candidate_name && !name) setName(linkQ.data.candidate_name);
  }, [linkQ.data, name]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns]);

  const slug = linkQ.data?.project_slug ?? null;

  const ask = useMutation({
    mutationFn: (current: InterviewTurnInput[]) => interviewTurn(slug, current),
    onSuccess: (res) => setTurns((prev) => [...prev, { role: "sofia", text: res.message }]),
  });

  const finish = useMutation({
    mutationFn: () =>
      scoreTextInterview({ title: name.trim(), project_slug: slug, turns, token }),
    onSuccess: () => setPhase("done"),
  });

  function start() {
    if (!name.trim()) return;
    setPhase("chat");
    ask.mutate([]);
  }
  function send() {
    const text = draft.trim();
    if (!text || ask.isPending) return;
    const next: InterviewTurnInput[] = [...turns, { role: "candidate", text }];
    setTurns(next);
    setDraft("");
    ask.mutate(next);
  }

  const candidateTurns = turns.filter((x) => x.role === "candidate");
  const canFinish = candidateTurns.length >= 2 && candidateTurns.reduce((n, x) => n + x.text.length, 0) >= 40;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-[--color-bg]">
      <div className="min-h-full grid place-items-center p-4">
        <div className="w-full max-w-xl">
          {/* Estados de carga / error */}
          {linkQ.isLoading && (
            <p className="text-center text-sm text-[--color-fg-muted] py-20">{t("cand.loading")}</p>
          )}
          {linkQ.isError && (
            <div className="surface p-8 text-center space-y-2">
              <p className="text-sm text-[--color-fg]">{t("cand.notFound")}</p>
            </div>
          )}

          {linkQ.isSuccess && phase === "welcome" && (
            <div className="surface p-8 space-y-5">
              <div className="space-y-2">
                <span className="inline-flex items-center gap-1.5 text-[10.5px] uppercase tracking-widest font-medium text-[--color-accent-strong]">
                  <Sparkles size={12} /> {t("cand.welcomeTag")}
                </span>
                <h1 className="text-2xl font-semibold tracking-tight">{t("cand.welcomeTitle")}</h1>
                <p className="text-[14px] text-[--color-fg-muted] leading-relaxed">{t("cand.welcomeBody")}</p>
              </div>
              {linkQ.data?.used && (
                <p className="text-[12.5px] text-[--color-warn]">{t("cand.usedNote")}</p>
              )}
              <div className="space-y-1.5">
                <FieldLabel>{t("cand.namePrompt")}</FieldLabel>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={t("cand.namePlaceholder")}
                  autoFocus
                />
              </div>
              <Button variant="primary" onClick={start} disabled={!name.trim()}>
                <Bot size={15} /> {t("cand.start")}
              </Button>
              <p className="text-[10.5px] text-[--color-fg-subtle] text-center pt-2">{t("cand.poweredBy")}</p>
            </div>
          )}

          {phase === "chat" && (
            <div className="surface flex flex-col h-[80vh] max-h-[760px] overflow-hidden">
              <header className="px-5 py-3 border-b border-[--color-border] flex items-center gap-2">
                <span className="w-7 h-7 rounded-full grid place-items-center bg-[--color-accent-soft] text-[--color-accent-strong]">
                  <Bot size={15} />
                </span>
                <span className="text-sm font-medium tracking-tight">Sofía</span>
              </header>

              <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
                {turns.map((turn, i) => (
                  <div key={i} className={turn.role === "sofia" ? "flex gap-2" : "flex gap-2 flex-row-reverse"}>
                    <div
                      className={
                        "w-7 h-7 rounded-full grid place-items-center shrink-0 " +
                        (turn.role === "sofia"
                          ? "bg-[--color-accent-soft] text-[--color-accent-strong]"
                          : "bg-[--color-bg-elev] text-[--color-fg-muted]")
                      }
                    >
                      {turn.role === "sofia" ? <Bot size={14} /> : <User size={14} />}
                    </div>
                    <div
                      className={
                        "rounded-2xl px-3.5 py-2 text-[13.5px] leading-relaxed max-w-[80%] whitespace-pre-wrap " +
                        (turn.role === "sofia"
                          ? "bg-[--color-bg-elev] border border-[--color-border]"
                          : "bg-[--color-accent-soft]")
                      }
                    >
                      {turn.text}
                    </div>
                  </div>
                ))}
                {ask.isPending && (
                  <div className="flex gap-2 items-center text-[12px] text-[--color-fg-muted]">
                    <div className="w-7 h-7 rounded-full grid place-items-center bg-[--color-accent-soft] text-[--color-accent-strong]">
                      <Bot size={14} />
                    </div>
                    <span className="animate-pulse">{t("cand.thinking")}</span>
                  </div>
                )}
              </div>

              <div className="border-t border-[--color-border] p-3 space-y-2">
                <div className="flex items-end gap-2">
                  <textarea
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        send();
                      }
                    }}
                    rows={2}
                    placeholder={t("cand.yourAnswer")}
                    className="flex-1 px-3 py-2 bg-transparent border border-[--color-border] rounded-md text-sm focus:outline-none focus:border-[--color-accent] resize-none"
                  />
                  <Button variant="primary" size="sm" onClick={send} disabled={!draft.trim() || ask.isPending}>
                    <Send size={13} /> {t("cand.send")}
                  </Button>
                </div>
                <div className="flex justify-end">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => finish.mutate()}
                    disabled={!canFinish || finish.isPending}
                    title={!canFinish ? t("cand.minTurns") : undefined}
                  >
                    <ClipboardCheck size={13} /> {finish.isPending ? t("cand.finishing") : t("cand.finish")}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {phase === "done" && (
            <div className="surface p-10 text-center space-y-3">
              <CheckCircle2 size={40} className="mx-auto text-[--color-success]" />
              <h1 className="text-xl font-semibold tracking-tight">{t("cand.thanksTitle")}</h1>
              <p className="text-[14px] text-[--color-fg-muted] leading-relaxed max-w-sm mx-auto">
                {t("cand.thanksBody")}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
