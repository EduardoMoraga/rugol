"use client";

/**
 * Entrevistas (Sofía) — vista de informes de entrevista para la variante HRO.
 *
 * Sofía (agente hro-sofia) registra su informe DENTRO del item del candidato,
 * en `data.interview`:
 *   data.interview = {
 *     competencies: [{ name, score (1-5 | null), evidence }],
 *     verdict: "avanzar" | "dudoso" | "descartar",
 *     confidence: "alta" | "media" | "baja",
 *     risks: string[],
 *   }
 *
 * Reusa `fetchPipeline("candidate")` (ya existente) y filtra los candidatos que
 * tengan `data.interview`. Solo aplica a la variante HRO; en Rugol/CRM muestra
 * un estado informativo. Estética OSCURA, hereda `--color-accent`.
 */

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ClipboardCheck,
  Bot,
  User,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";
import {
  fetchHealth,
  fetchPipeline,
  fetchVoiceStatus,
  syncVoice,
  type PipelineItem,
} from "@/lib/api";
import { Card, PageHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toast";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/cn";
import { InterviewConsole } from "@/components/hro/interview-console";

// --- Forma del informe de Sofía (cast suave: data es Record<string, unknown>) ---
type Verdict = "avanzar" | "dudoso" | "descartar";
type Confidence = "alta" | "media" | "baja";
interface Competency {
  name: string;
  score: number | null; // 1-5 o null
  evidence?: string | null;
}
interface InterviewReport {
  competencies?: Competency[];
  verdict?: Verdict | string;
  confidence?: Confidence | string;
  risks?: string[];
}

function getInterview(item: PipelineItem): InterviewReport | null {
  const raw = (item.data as Record<string, unknown> | undefined)?.interview;
  if (!raw || typeof raw !== "object") return null;
  return raw as InterviewReport;
}

const verdictTone: Record<Verdict, "running" | "warn" | "error"> = {
  avanzar: "running",
  dudoso: "warn",
  descartar: "error",
};

function scoreTone(score: number): "running" | "accent" | "warn" | "idle" {
  if (score >= 4) return "running";
  if (score >= 3) return "accent";
  if (score >= 2) return "warn";
  return "idle";
}

// Las competencias BARS las genera el scorer en español. Para el toggle EN las
// mapeamos por keyword (robusto ante variantes del nombre) con fallback al
// nombre original — así el contenido también es bilingüe, no solo la UI.
const BARS_EN: { match: RegExp; en: string }[] = [
  { match: /confiab|responsab/i, en: "Reliability & accountability" },
  { match: /norma|procedimien|cumplimien/i, en: "Compliance with rules & procedures" },
  { match: /honest|dilema/i, en: "Honesty under dilemmas" },
  { match: /cliente|comunicaci/i, en: "Customer orientation & communication" },
  { match: /ejecuci|punto de venta|supervis/i, en: "In-store execution under remote supervision" },
  { match: /presi[oó]n|estabil/i, en: "Stability under pressure" },
];
function localizeCompetency(name: string, locale: string): string {
  if (locale !== "en" || !name) return name;
  const hit = BARS_EN.find((b) => b.match.test(name));
  return hit ? hit.en : name;
}

export default function InterviewsPage() {
  const { t } = useI18n();
  const health = useQuery({ queryKey: ["health"], queryFn: fetchHealth, refetchInterval: 30_000 });
  const variant = health.data?.variant;

  // Mientras carga la salud no sabemos el dominio: estado neutro.
  if (!health.data) {
    return (
      <div className="p-8 max-w-[1400px] mx-auto">
        <p className="text-sm text-[--color-fg-muted]">{t("interviews.loading")}</p>
      </div>
    );
  }

  if (variant !== "hro") {
    return (
      <div className="p-8 max-w-[1400px] mx-auto">
        <Card className="text-center py-16 space-y-4">
          <ClipboardCheck size={36} className="mx-auto text-[--color-fg-subtle]" />
          <div>
            <h2 className="text-lg font-semibold tracking-tight">{t("interviews.notHroTitle")}</h2>
            <p className="text-sm text-[--color-fg-muted] mt-1 max-w-md mx-auto">
              {t("interviews.notHroBody")}
            </p>
          </div>
        </Card>
      </div>
    );
  }

  return <InterviewsBoard />;
}

function InterviewsBoard() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const itemsQuery = useQuery({
    queryKey: ["pipeline", "candidate"],
    queryFn: () => fetchPipeline("candidate"),
    refetchInterval: 8000,
  });

  // Estado de la integración de voz (ElevenLabs). Si falla (p. ej. variante sin
  // soporte), lo tratamos como no-configurado y no rompemos la vista.
  const voiceQuery = useQuery({
    queryKey: ["voice-status"],
    queryFn: fetchVoiceStatus,
    refetchInterval: 30_000,
    retry: false,
  });
  const voiceConfigured = voiceQuery.data?.configured ?? false;

  // Sincronización: puede tardar 30-60s por entrevista. react-query no aborta
  // por su cuenta; el botón muestra spinner mientras corre.
  const sync = useMutation({
    mutationFn: syncVoice,
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["pipeline", "candidate"] });
      qc.invalidateQueries({ queryKey: ["voice-status"] });
      if (res.created > 0) {
        toast({
          tone: "success",
          title: t("voice.syncDone").replace("{n}", String(res.created)),
        });
      } else {
        toast({ tone: "info", title: t("voice.syncNone") });
      }
      if (res.errors && res.errors.length > 0) {
        toast({
          tone: "warning",
          title: t("voice.syncError"),
          body: res.errors.slice(0, 3).join(" · "),
        });
      }
    },
    onError: (e: Error) =>
      toast({ tone: "error", title: t("voice.syncError"), body: e.message }),
  });

  const interviews = useMemo(() => {
    const items = itemsQuery.data ?? [];
    return items
      .map((item) => ({ item, report: getInterview(item) }))
      .filter((x): x is { item: PipelineItem; report: InterviewReport } => x.report !== null);
  }, [itemsQuery.data]);

  const isEmpty = !itemsQuery.isLoading && interviews.length === 0;

  return (
    <div className="p-8 space-y-8 max-w-[1100px] mx-auto">
      <PageHeader
        title={t("interviews.title")}
        description={t("interviews.desc")}
        actions={
          <>
            {interviews.length > 0 && (
              <span className="pill pill-idle text-[11px] tabular-nums">
                {interviews.length} {t("interviews.count")}
              </span>
            )}
            <InterviewConsole />
            <Button
              variant="primary"
              size="sm"
              onClick={() => sync.mutate()}
              disabled={sync.isPending}
            >
              <RefreshCw size={13} className={sync.isPending ? "animate-spin" : undefined} />
              {sync.isPending ? t("voice.syncing") : t("voice.sync")}
            </Button>
          </>
        }
      />

      {/* Aviso si ElevenLabs no está conectado todavía. */}
      {voiceQuery.isSuccess && !voiceConfigured && (
        <Card className="flex items-start justify-between gap-4 border-[--color-accent]/30">
          <p className="text-sm text-[--color-fg-muted]">{t("voice.notConfigured")}</p>
          <Link
            href="/settings"
            className="shrink-0 text-sm font-medium text-[--color-accent-strong] hover:underline whitespace-nowrap"
          >
            {t("voice.goToSettings")} →
          </Link>
        </Card>
      )}

      {itemsQuery.isLoading && (
        <p className="text-sm text-[--color-fg-muted]">{t("interviews.loading")}</p>
      )}

      {isEmpty && (
        <Card className="text-center py-16 space-y-4">
          <ClipboardCheck size={36} className="mx-auto text-[--color-fg-subtle]" />
          <p className="text-sm text-[--color-fg-muted] max-w-md mx-auto">{t("interviews.empty")}</p>
        </Card>
      )}

      {!isEmpty && (
        <div className="space-y-4">
          {interviews.map(({ item, report }) => (
            <InterviewCard key={item.id} item={item} report={report} />
          ))}
        </div>
      )}
    </div>
  );
}

function InterviewCard({ item, report }: { item: PipelineItem; report: InterviewReport }) {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState(false);

  const competencies = report.competencies ?? [];
  const risks = report.risks ?? [];
  const notes = item.notes ?? [];
  const verdict = report.verdict as Verdict | undefined;
  const confidence = report.confidence as Confidence | undefined;

  const verdictLabel = verdict ? t(`interviews.verdict.${verdict}`) : null;
  const tone = verdict && verdict in verdictTone ? verdictTone[verdict] : "idle";
  const confidenceLabel = confidence
    ? t(`interviews.confidence.${confidence}`)
    : null;

  return (
    <Card className="space-y-4">
      {/* Cabecera: nombre, rol, veredicto, confianza */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 space-y-0.5">
          <h2 className="text-[15px] font-semibold tracking-tight leading-tight">{item.title}</h2>
          {item.subtitle && (
            <p className="text-[12px] text-[--color-fg-muted]">{item.subtitle}</p>
          )}
          <div className="flex items-center gap-1.5 text-[10px] text-[--color-fg-subtle] font-mono pt-1">
            <Bot size={10} />
            <span className="truncate">{item.source_agent || t("interviews.manual")}</span>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5 shrink-0">
          {verdictLabel && (
            <Badge tone={tone} className="text-[11px]">
              {verdictLabel}
            </Badge>
          )}
          {confidenceLabel && (
            <span className="text-[10px] text-[--color-fg-muted] uppercase tracking-wider">
              {t("interviews.confidence")}: {confidenceLabel}
            </span>
          )}
        </div>
      </div>

      {/* Las 6 competencias con score y evidencia (preview) */}
      {competencies.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-[11px] uppercase tracking-wider text-[--color-fg-muted] font-medium">
            {t("interviews.competencies")}
          </h3>
          <div className="space-y-2">
            {competencies.map((c, i) => (
              <CompetencyRow key={`${c.name}-${i}`} competency={c} expanded={expanded} />
            ))}
          </div>
        </section>
      )}

      {/* Detalle expandible: riesgos + historial de notas */}
      {expanded && (
        <div className="space-y-4 pt-1">
          <section className="space-y-2">
            <h3 className="text-[11px] uppercase tracking-wider text-[--color-fg-muted] font-medium flex items-center gap-1.5">
              <AlertTriangle size={12} /> {t("interviews.risks")}
            </h3>
            {risks.length === 0 ? (
              <p className="text-xs text-[--color-fg-subtle]">{t("interviews.noRisks")}</p>
            ) : (
              <ul className="space-y-1.5">
                {risks.map((r, i) => (
                  <li
                    key={i}
                    className="surface px-3 py-2 text-[13px] leading-relaxed flex items-start gap-2"
                  >
                    <span className="text-[--color-warn] mt-0.5 shrink-0">•</span>
                    <span className="whitespace-pre-wrap">{r}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="space-y-2">
            <h3 className="text-[11px] uppercase tracking-wider text-[--color-fg-muted] font-medium">
              {t("interviews.history")}
            </h3>
            {notes.length === 0 ? (
              <p className="text-xs text-[--color-fg-subtle]">{t("interviews.noNotes")}</p>
            ) : (
              <ol className="space-y-2">
                {notes.map((n, i) => (
                  <li key={i} className="surface p-3 space-y-1">
                    <div className="flex items-center gap-1.5 text-[10px] text-[--color-fg-subtle] font-mono">
                      {n.agent ? <Bot size={10} /> : <User size={10} />}
                      <span>{n.agent || t("interviews.manual")}</span>
                      {n.at && <span>· {new Date(n.at).toLocaleString()}</span>}
                    </div>
                    <p className="text-[13px] leading-relaxed whitespace-pre-wrap">{n.text}</p>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>
      )}

      {/* Toggle */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="flex items-center gap-1.5 text-[12px] text-[--color-fg-muted] hover:text-[--color-accent-strong] transition pt-1"
      >
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        {expanded ? t("interviews.collapse") : t("interviews.expand")}
      </button>
    </Card>
  );
}

function CompetencyRow({
  competency,
  expanded,
}: {
  competency: Competency;
  expanded: boolean;
}) {
  const { t, locale } = useI18n();
  const { name, score, evidence } = competency;
  const hasScore = typeof score === "number";

  return (
    <div className="surface px-3 py-2.5 space-y-2">
      <div className="flex items-center justify-between gap-3">
        <span className="text-[13px] font-medium leading-tight min-w-0">{localizeCompetency(name, locale)}</span>
        {hasScore ? (
          <Badge tone={scoreTone(score as number)} className="shrink-0 text-[10px] tabular-nums">
            {score}/5
          </Badge>
        ) : (
          <Badge tone="idle" className="shrink-0 text-[10px]">
            {t("interviews.noScore")}
          </Badge>
        )}
      </div>

      {/* Barra de score 1-5, tonalizada por el mismo criterio del badge */}
      {hasScore && (
        <div className="flex gap-1" aria-hidden>
          {[1, 2, 3, 4, 5].map((n) => (
            <span
              key={n}
              className={cn(
                "h-1.5 flex-1 rounded-full transition-colors",
                n <= (score as number)
                  ? scoreTone(score as number) === "running"
                    ? "bg-[--color-success]"
                    : scoreTone(score as number) === "accent"
                      ? "bg-[--color-accent-strong]"
                      : scoreTone(score as number) === "warn"
                        ? "bg-[--color-warn]"
                        : "bg-[--color-fg-subtle]"
                  : "bg-[--color-border-strong]",
              )}
            />
          ))}
        </div>
      )}

      {/* Evidencia citada: preview cuando está colapsado, completa al expandir */}
      {evidence ? (
        <p
          className={cn(
            "text-[12px] text-[--color-fg-muted] leading-relaxed whitespace-pre-wrap",
            !expanded && "line-clamp-2",
          )}
        >
          <span className="text-[--color-fg-subtle] font-mono text-[10px] uppercase tracking-wider mr-1.5">
            {t("interviews.evidence")}:
          </span>
          {evidence}
        </p>
      ) : (
        <p className="text-[11px] text-[--color-fg-subtle] italic">{t("interviews.noEvidence")}</p>
      )}
    </div>
  );
}
