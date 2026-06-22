"use client";

/**
 * HroCockpit — "Sala de reclutamiento": la pantalla de INICIO de la variante HRO.
 *
 * Reemplaza el bienvenido genérico de Rugol cuando `health.variant === "hro"`.
 * Es 100% frontend y solo lee endpoints ya en vivo:
 *   - GET /api/health           → marca/variante (lo resuelve page.tsx, no acá)
 *   - GET /api/settings/status  → telegram / slack / elevenlabs configurados
 *   - GET /api/voice/status     → Sofía (ElevenLabs) conectada
 *   - GET /api/pipeline?kind=candidate → conteo candidatos / entrevistas hechas
 *   - POST /api/voice/sync      → sincroniza entrevistas (reusa syncVoice)
 *
 * Si un endpoint falla, su tarjeta queda en estado neutro — nunca rompe la página.
 * Estética crema/editorial; el acento violeta de HRO entra por --color-accent
 * (la nav-rail lo inyecta en runtime). Sin colores hardcodeados.
 */

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  UserPlus,
  ScanSearch,
  Mic,
  Trophy,
  Sparkles,
  Bot,
  Copy,
  ExternalLink,
  RefreshCw,
  Users,
  ClipboardCheck,
  Settings as SettingsIcon,
  ArrowRight,
} from "lucide-react";
import {
  fetchSettingsStatus,
  fetchSettings,
  fetchVoiceStatus,
  fetchPipeline,
  fetchAgents,
  syncVoice,
  type PipelineItem,
} from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toast";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/cn";
import { AgentChat } from "@/components/agents/agent-chat";
import { CvSourcesManager } from "@/components/hro/cv-sources";
import { OnboardingWizard } from "@/components/hro/onboarding-wizard";
import { Database } from "lucide-react";

// Landing externa de la entrevista de voz (Sofía). Se comparte con el candidato.
const VOICE_LANDING_URL = "https://hro-entrevista.vercel.app/";

function openExternal(url: string) {
  if (typeof window === "undefined") return;
  if (window.rugol?.openExternal) {
    window.rugol.openExternal(url);
  } else {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}

// Un candidato "tiene entrevista" cuando Sofía dejó su informe en data.interview.
function hasInterview(item: PipelineItem): boolean {
  const raw = (item.data as Record<string, unknown> | undefined)?.interview;
  return !!raw && typeof raw === "object";
}

export function HroCockpit() {
  const { t } = useI18n();
  const qc = useQueryClient();

  // --- Estado de conexiones e indicadores (todos tolerantes a fallo) ---
  const statusQuery = useQuery({
    queryKey: ["settings-status"],
    queryFn: fetchSettingsStatus,
    refetchInterval: 15_000,
    retry: false,
  });
  const voiceQuery = useQuery({
    queryKey: ["voice-status"],
    queryFn: fetchVoiceStatus,
    refetchInterval: 30_000,
    retry: false,
  });
  const candidatesQuery = useQuery({
    queryKey: ["pipeline", "candidate"],
    queryFn: () => fetchPipeline("candidate"),
    refetchInterval: 15_000,
    retry: false,
  });

  // Onboarding: se muestra el wizard en primer arranque (onboarding_done=false).
  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
    retry: false,
  });
  const [wizardDismissed, setWizardDismissed] = useState(false);
  const showWizard =
    !wizardDismissed && settingsQuery.isSuccess && settingsQuery.data?.onboarding_done === false;

  const voiceConfigured = voiceQuery.data?.configured ?? false;
  const telegram = statusQuery.data?.telegram;

  const { totalCandidates, totalInterviews } = useMemo(() => {
    const items = candidatesQuery.data ?? [];
    return {
      totalCandidates: items.length,
      totalInterviews: items.filter(hasInterview).length,
    };
  }, [candidatesQuery.data]);

  // --- Sincronización de entrevistas (mismo patrón que la página interviews) ---
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

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(VOICE_LANDING_URL);
      toast({ tone: "success", title: t("hro.cockpit.link.copied") });
    } catch {
      toast({ tone: "error", title: t("hro.cockpit.link.copyFailed") });
    }
  }

  // --- Embudo: cada paso con el agente que lo hace (legibilidad del flujo) ---
  const steps = [
    { n: "01", icon: UserPlus, title: t("hro.funnel.s1.title"), body: t("hro.funnel.s1.body"), agent: t("hro.funnel.s1.agent") },
    { n: "02", icon: ScanSearch, title: t("hro.funnel.s2.title"), body: t("hro.funnel.s2.body"), agent: t("hro.funnel.s2.agent") },
    { n: "03", icon: SettingsIcon, title: t("hro.funnel.s3.title"), body: t("hro.funnel.s3.body"), agent: t("hro.funnel.s3.agent") },
    { n: "04", icon: Mic, title: t("hro.funnel.s4.title"), body: t("hro.funnel.s4.body"), agent: t("hro.funnel.s4.agent") },
    { n: "05", icon: Trophy, title: t("hro.funnel.s5.title"), body: t("hro.funnel.s5.body"), agent: t("hro.funnel.s5.agent") },
    { n: "06", icon: ClipboardCheck, title: t("hro.funnel.s6.title"), body: t("hro.funnel.s6.body"), agent: t("hro.funnel.s6.agent") },
  ];

  return (
    <div className="p-8 space-y-10 max-w-[1200px] mx-auto">
      {showWizard && <OnboardingWizard onDone={() => setWizardDismissed(true)} />}

      {/* ---- Encabezado ---- */}
      <header className="relative overflow-hidden surface px-8 py-9 md:py-11">
        <div
          className="absolute -top-20 -right-20 w-80 h-80 rounded-full opacity-25 blur-3xl pointer-events-none"
          style={{ background: "radial-gradient(circle, var(--color-accent) 0%, transparent 70%)" }}
        />
        <div className="relative max-w-2xl space-y-3">
          <span className="inline-flex items-center gap-1.5 text-[10.5px] uppercase tracking-widest font-medium text-[--color-accent-strong]">
            <Sparkles size={12} /> {t("hro.cockpit.tag")}
          </span>
          <h1 className="text-3xl md:text-4xl font-semibold tracking-tight leading-[1.1]">
            {t("hro.cockpit.title")}
          </h1>
          <p className="text-[15px] text-[--color-fg-muted] leading-relaxed max-w-xl">
            {t("hro.cockpit.subtitle")}
          </p>

          {/* Mini-estado: candidatos / entrevistas */}
          <div className="flex flex-wrap items-center gap-2 pt-2">
            <span className="pill pill-idle text-[11px] tabular-nums inline-flex items-center gap-1.5">
              <Users size={11} /> {totalCandidates} {t("hro.cockpit.stat.candidates")}
            </span>
            <span className="pill pill-accent text-[11px] tabular-nums inline-flex items-center gap-1.5">
              <ClipboardCheck size={11} /> {totalInterviews} {t("hro.cockpit.stat.interviews")}
            </span>
          </div>
        </div>
      </header>

      {/* ---- Copiloto: el centro de la experiencia ---- */}
      <CopilotPanel />

      {/* ---- Embudo: el equipo que coordina el copiloto (qué hace cada agente) ---- */}
      <section className="space-y-4">
        <div>
          <h2 className="text-sm font-semibold tracking-tight">{t("hro.funnel.heading")}</h2>
          <p className="text-[12.5px] text-[--color-fg-muted] leading-relaxed mt-1 max-w-3xl">
            {t("hro.funnel.note")}
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
          {steps.map(({ n, icon: Icon, title, body, agent }) => (
            <div
              key={n}
              className="surface p-4 flex flex-col gap-2.5 relative overflow-hidden"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] tracking-widest text-[--color-fg-subtle]">
                  {n}
                </span>
                <Icon size={16} className="text-[--color-accent-strong]" />
              </div>
              <h3 className="text-[13.5px] font-semibold tracking-tight leading-tight">
                {title}
              </h3>
              <p className="text-[12px] text-[--color-fg-muted] leading-relaxed flex-1">{body}</p>
              <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider text-[--color-fg-subtle] mt-1">
                <Bot size={10} /> {t("hro.funnel.driver")}: {agent}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* ---- Conexiones ---- */}
      <section className="space-y-4">
        <h2 className="text-sm font-semibold tracking-tight">{t("hro.cockpit.connections.heading")}</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {/* Anthropic — siempre activo (es la suscripción) */}
          <ConnectionCard
            icon={<Bot size={16} />}
            name={t("hro.cockpit.connections.anthropic.name")}
            body={t("hro.cockpit.connections.anthropic.body")}
            badge={<Badge tone="running">{t("hro.cockpit.connections.active")}</Badge>}
          />

          {/* ElevenLabs · Sofía */}
          <ConnectionCard
            icon={<Mic size={16} />}
            name={t("hro.cockpit.connections.elevenlabs.name")}
            body={t("hro.cockpit.connections.elevenlabs.body")}
            badge={
              voiceConfigured ? (
                <Badge tone="running">{t("hro.cockpit.connections.connected")}</Badge>
              ) : (
                <Badge tone="warn">{t("hro.cockpit.connections.missing")}</Badge>
              )
            }
            configureHref={voiceConfigured ? undefined : "/settings"}
            configureLabel={t("hro.cockpit.connections.configure")}
          />

          {/* Telegram */}
          <ConnectionCard
            icon={<SettingsIcon size={16} />}
            name={t("hro.cockpit.connections.telegram.name")}
            body={t("hro.cockpit.connections.telegram.body")}
            badge={
              telegram?.running ? (
                <Badge tone="running">{t("hro.cockpit.connections.connected")}</Badge>
              ) : telegram?.configured ? (
                <Badge tone="warn">{t("hro.cockpit.connections.notRunning")}</Badge>
              ) : (
                <Badge tone="idle">{t("hro.cockpit.connections.notConnected")}</Badge>
              )
            }
            configureHref="/settings"
            configureLabel={t("hro.cockpit.connections.configure")}
          />
        </div>
      </section>

      {/* ---- Fuentes de CV ---- */}
      <section className="space-y-4">
        <div className="flex items-center gap-2">
          <Database size={16} className="text-[--color-accent-strong]" />
          <h2 className="text-sm font-semibold tracking-tight">{t("cvSources.title")}</h2>
        </div>
        <p className="text-[12.5px] text-[--color-fg-muted] leading-relaxed max-w-3xl -mt-2">
          {t("cvSources.subtitle")}
        </p>
        <CvSourcesManager />
      </section>

      {/* ---- Link de entrevista (destacado) ---- */}
      <section>
        <Card className="border-[--color-accent]/40 space-y-4">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-xl grid place-items-center shrink-0 bg-[--color-accent-soft] text-[--color-accent-strong]">
              <Mic size={17} />
            </div>
            <div className="min-w-0">
              <h2 className="text-base font-semibold tracking-tight">
                {t("hro.cockpit.link.heading")}
              </h2>
              <p className="text-sm text-[--color-fg-muted] mt-0.5">
                {t("hro.cockpit.link.body")}
              </p>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
            <code className="flex-1 min-w-0 surface px-3 py-2.5 font-mono text-[13px] text-[--color-fg] truncate">
              {VOICE_LANDING_URL}
            </code>
            <div className="flex items-center gap-2 shrink-0">
              <Button variant="primary" size="md" onClick={copyLink}>
                <Copy size={14} /> {t("hro.cockpit.link.copy")}
              </Button>
              <Button variant="secondary" size="md" onClick={() => openExternal(VOICE_LANDING_URL)}>
                <ExternalLink size={14} /> {t("hro.cockpit.link.open")}
              </Button>
            </div>
          </div>
        </Card>
      </section>

      {/* ---- Acciones rápidas ---- */}
      <section className="space-y-4">
        <h2 className="text-sm font-semibold tracking-tight">{t("hro.cockpit.actions.heading")}</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <ActionCard
            href="/pipeline"
            icon={<Users size={16} />}
            title={t("hro.cockpit.actions.candidates.title")}
            body={t("hro.cockpit.actions.candidates.body")}
          />
          <ActionCard
            href="/interviews"
            icon={<ClipboardCheck size={16} />}
            title={t("hro.cockpit.actions.interviews.title")}
            body={t("hro.cockpit.actions.interviews.body")}
          />
          {/* Sincronizar entrevistas: acción in-place con loading */}
          <button
            type="button"
            onClick={() => sync.mutate()}
            disabled={sync.isPending}
            className="group surface surface-hover p-4 flex flex-col gap-2 text-left transition disabled:opacity-60 disabled:cursor-not-allowed"
          >
            <div className="flex items-center justify-between">
              <span className="w-8 h-8 rounded-lg grid place-items-center bg-[--color-accent-soft] text-[--color-accent-strong]">
                <RefreshCw size={16} className={sync.isPending ? "animate-spin" : undefined} />
              </span>
            </div>
            <h3 className="text-[13.5px] font-semibold tracking-tight leading-tight">
              {sync.isPending ? t("voice.syncing") : t("hro.cockpit.actions.sync.title")}
            </h3>
            <p className="text-[12px] text-[--color-fg-muted] leading-relaxed">
              {t("hro.cockpit.actions.sync.body")}
            </p>
          </button>
          <ActionCard
            href="/agents"
            icon={<Mic size={16} />}
            title={t("hro.cockpit.actions.configureSofia.title")}
            body={t("hro.cockpit.actions.configureSofia.body")}
          />
        </div>
      </section>
    </div>
  );
}

// Copiloto: la cara de HRO. La reclutadora le habla en lenguaje natural y él
// orquesta al equipo (assistant tiene el prompt de orquestación + RAG).
function CopilotPanel() {
  const { t } = useI18n();
  const agentsQ = useQuery({ queryKey: ["agents"], queryFn: () => fetchAgents(), retry: false });
  const assistant = (agentsQ.data ?? []).find((a) => a.name === "assistant");
  const examples = [
    t("hro.copilot.ex1"),
    t("hro.copilot.ex2"),
    t("hro.copilot.ex3"),
    t("hro.copilot.ex4"),
  ];

  return (
    <section className="space-y-3">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-xl grid place-items-center shrink-0 bg-[--color-accent-soft] text-[--color-accent-strong]">
          <Sparkles size={17} />
        </div>
        <div className="min-w-0">
          <h2 className="text-base font-semibold tracking-tight">{t("hro.copilot.title")}</h2>
          <p className="text-sm text-[--color-fg-muted] mt-0.5 max-w-2xl">{t("hro.copilot.subtitle")}</p>
        </div>
      </div>
      {assistant ? (
        <AgentChat
          agentId={assistant.id}
          agentName={t("hro.copilot.name")}
          modelLabel={(assistant.model || "").replace("claude-", "")}
          agentBusy={assistant.status === "running"}
          projectSlug={null}
          examples={examples}
        />
      ) : (
        <Card>
          <p className="text-sm text-[--color-fg-muted]">{t("hro.copilot.unavailable")}</p>
        </Card>
      )}
    </section>
  );
}

function ConnectionCard({
  icon,
  name,
  body,
  badge,
  configureHref,
  configureLabel,
}: {
  icon: React.ReactNode;
  name: string;
  body: string;
  badge: React.ReactNode;
  configureHref?: string;
  configureLabel?: string;
}) {
  return (
    <Card className="flex flex-col gap-3 h-full">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="w-8 h-8 rounded-lg grid place-items-center shrink-0 bg-[--color-accent-soft] text-[--color-accent-strong]">
            {icon}
          </span>
          <h3 className="text-[14px] font-semibold tracking-tight truncate">{name}</h3>
        </div>
        {badge}
      </div>
      <p className="text-[12.5px] text-[--color-fg-muted] leading-relaxed flex-1">{body}</p>
      {configureHref && configureLabel && (
        <Link
          href={configureHref}
          className="text-[12.5px] font-medium text-[--color-accent-strong] hover:underline inline-flex items-center gap-1"
        >
          {configureLabel} <ArrowRight size={12} />
        </Link>
      )}
    </Card>
  );
}

function ActionCard({
  href,
  icon,
  title,
  body,
}: {
  href: string;
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "group surface surface-hover p-4 flex flex-col gap-2 transition",
      )}
    >
      <div className="flex items-center justify-between">
        <span className="w-8 h-8 rounded-lg grid place-items-center bg-[--color-accent-soft] text-[--color-accent-strong]">
          {icon}
        </span>
        <ArrowRight
          size={14}
          className="text-[--color-fg-subtle] group-hover:text-[--color-accent-strong] transition"
        />
      </div>
      <h3 className="text-[13.5px] font-semibold tracking-tight leading-tight">{title}</h3>
      <p className="text-[12px] text-[--color-fg-muted] leading-relaxed">{body}</p>
    </Link>
  );
}
