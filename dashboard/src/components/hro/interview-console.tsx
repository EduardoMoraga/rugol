"use client";

/**
 * Consola de entrevista in-app con Sofía (HRO).
 *
 * Reemplaza el viejo link externo a hro-entrevista.vercel.app: la entrevista
 * ocurre DENTRO de la app. Sofía (vía /api/voice/interview-turn) conduce la
 * conversación una pregunta por turno usando la descripción de cargo de la
 * búsqueda; al cerrar, /api/voice/score-text la puntúa con BARS y registra al
 * candidato en el pipeline (misma forma que la sync de ElevenLabs).
 */
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, User, Send, ClipboardCheck, MessageSquarePlus, Link2, Copy } from "lucide-react";
import {
  fetchProjects,
  interviewTurn,
  scoreTextInterview,
  createInterviewLink,
  type InterviewTurnInput,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { FieldLabel, Input, Select } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";
import { useI18n } from "@/lib/i18n";

export function InterviewConsole() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);

  // Setup
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [slug, setSlug] = useState<string>("");
  const [started, setStarted] = useState(false);
  const [turns, setTurns] = useState<InterviewTurnInput[]>([]);
  const [draft, setDraft] = useState("");
  const [linkUrl, setLinkUrl] = useState("");

  const projects = useQuery({ queryKey: ["projects"], queryFn: () => fetchProjects(), enabled: open });
  const scrollRef = useRef<HTMLDivElement>(null);

  function reset() {
    setStarted(false);
    setTurns([]);
    setDraft("");
    setName("");
    setRole("");
    setSlug("");
    setLinkUrl("");
  }

  // Modo ex-ante: genera un link que toma el CANDIDATO.
  const genLink = useMutation({
    mutationFn: () => createInterviewLink({ project_slug: slug || null, candidate_name: name.trim() || null }),
    onSuccess: (res) => {
      const url = `${window.location.origin}${res.path}`;
      setLinkUrl(url);
      navigator.clipboard?.writeText(url).then(
        () => toast({ tone: "success", title: t("interviews.live.linkCopied") }),
        () => {},
      );
    },
    onError: (e: Error) => toast({ tone: "error", title: t("interviews.live.linkError"), body: e.message }),
  });

  useEffect(() => {
    // Auto-scroll al último turno.
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns]);

  // Una vuelta de Sofía: manda los turnos y agrega su respuesta.
  const ask = useMutation({
    mutationFn: (current: InterviewTurnInput[]) => interviewTurn(slug || null, current),
    onSuccess: (res) => {
      setTurns((prev) => [...prev, { role: "sofia", text: res.message }]);
    },
    onError: (e: Error) => toast({ tone: "error", title: t("interviews.live.turnError"), body: e.message }),
  });

  function begin() {
    if (!name.trim()) {
      toast({ tone: "error", title: t("interviews.live.needName") });
      return;
    }
    setStarted(true);
    ask.mutate([]); // Sofía abre con su primera pregunta.
  }

  function sendAnswer() {
    const text = draft.trim();
    if (!text || ask.isPending) return;
    const next: InterviewTurnInput[] = [...turns, { role: "candidate", text }];
    setTurns(next);
    setDraft("");
    ask.mutate(next);
  }

  const candidateTurns = turns.filter((x) => x.role === "candidate");
  const canFinish = candidateTurns.length >= 2 && candidateTurns.reduce((n, x) => n + x.text.length, 0) >= 40;

  const finish = useMutation({
    mutationFn: () =>
      scoreTextInterview({ title: name.trim(), subtitle: role.trim() || null, project_slug: slug || null, turns }),
    onSuccess: (res) => {
      toast({
        tone: "success",
        title: t("interviews.live.scored"),
        body: res.overall != null ? `${res.overall}/100 · ${res.recommendation ?? ""}` : undefined,
      });
      qc.invalidateQueries({ queryKey: ["pipeline", "candidate"] });
      setOpen(false);
      reset();
    },
    onError: (e: Error) => toast({ tone: "error", title: t("interviews.live.scoreError"), body: e.message }),
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button variant="secondary" size="sm">
          <MessageSquarePlus size={13} /> {t("interviews.live.start")}
        </Button>
      </DialogTrigger>
      <DialogContent title={t("interviews.live.title")} description={t("interviews.live.intro")}>
        {!started ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <FieldLabel>{t("interviews.live.candidateName")}</FieldLabel>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={t("interviews.live.candidateNamePlaceholder")}
                  autoFocus
                />
              </div>
              <div className="space-y-1.5">
                <FieldLabel>{t("interviews.live.role")}</FieldLabel>
                <Input
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  placeholder={t("interviews.live.rolePlaceholder")}
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <FieldLabel hint={t("interviews.live.searchHint")}>{t("interviews.live.search")}</FieldLabel>
              <Select value={slug} onChange={(e) => setSlug(e.target.value)}>
                <option value="">{t("interviews.live.noSearch")}</option>
                {(projects.data ?? []).map((p) => (
                  <option key={p.slug} value={p.slug}>
                    {p.name}
                  </option>
                ))}
              </Select>
            </div>
            {/* Link ex-ante generado */}
            {linkUrl && (
              <div className="surface px-3 py-2.5 space-y-2">
                <p className="text-[12px] text-[--color-fg-muted] leading-relaxed">{t("interviews.live.linkReady")}</p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 min-w-0 text-[12px] font-mono text-[--color-fg] truncate">{linkUrl}</code>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() =>
                      navigator.clipboard?.writeText(linkUrl).then(
                        () => toast({ tone: "success", title: t("interviews.live.linkCopied") }),
                        () => {},
                      )
                    }
                  >
                    <Copy size={13} /> {t("interviews.live.copy")}
                  </Button>
                </div>
              </div>
            )}

            <div className="flex items-center justify-between gap-2 pt-1">
              <div className="min-w-0">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => genLink.mutate()}
                  disabled={genLink.isPending}
                  title={t("interviews.live.candidateHint")}
                >
                  <Link2 size={13} />
                  {genLink.isPending ? t("interviews.live.generating") : t("interviews.live.genLink")}
                </Button>
              </div>
              <Button variant="primary" onClick={begin} disabled={!name.trim()}>
                <Bot size={14} /> {t("interviews.live.begin")}
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div
              ref={scrollRef}
              className="max-h-[46vh] overflow-y-auto space-y-3 pr-1"
            >
              {turns.map((turn, i) => (
                <div
                  key={i}
                  className={turn.role === "sofia" ? "flex gap-2" : "flex gap-2 flex-row-reverse"}
                >
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
                      "rounded-2xl px-3.5 py-2 text-[13px] leading-relaxed max-w-[78%] whitespace-pre-wrap " +
                      (turn.role === "sofia"
                        ? "bg-[--color-bg-elev] border border-[--color-border]"
                        : "bg-[--color-accent-soft]")
                    }
                  >
                    <span className="block text-[9px] uppercase tracking-widest text-[--color-fg-subtle] mb-0.5">
                      {turn.role === "sofia" ? t("interviews.live.sofia") : t("interviews.live.you")}
                    </span>
                    {turn.text}
                  </div>
                </div>
              ))}
              {ask.isPending && (
                <div className="flex gap-2 items-center text-[12px] text-[--color-fg-muted]">
                  <div className="w-7 h-7 rounded-full grid place-items-center bg-[--color-accent-soft] text-[--color-accent-strong]">
                    <Bot size={14} />
                  </div>
                  <span className="animate-pulse">{t("interviews.live.thinking")}</span>
                </div>
              )}
            </div>

            <div className="flex items-end gap-2 pt-1 border-t border-[--color-border]">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendAnswer();
                  }
                }}
                rows={2}
                placeholder={t("interviews.live.candidatePlaceholder")}
                className="flex-1 px-3 py-2 bg-transparent border border-[--color-border] rounded-md text-sm focus:outline-none focus:border-[--color-accent] resize-none"
              />
              <Button variant="primary" size="sm" onClick={sendAnswer} disabled={!draft.trim() || ask.isPending}>
                <Send size={13} /> {t("interviews.live.send")}
              </Button>
            </div>

            <div className="flex items-center justify-between pt-1">
              <button
                type="button"
                onClick={reset}
                className="text-[12px] text-[--color-fg-muted] hover:text-[--color-fg]"
              >
                {t("interviews.live.restart")}
              </button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => finish.mutate()}
                disabled={!canFinish || finish.isPending}
                title={!canFinish ? t("interviews.live.minTurns") : undefined}
              >
                <ClipboardCheck size={13} />
                {finish.isPending ? t("interviews.live.finishing") : t("interviews.live.finish")}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
