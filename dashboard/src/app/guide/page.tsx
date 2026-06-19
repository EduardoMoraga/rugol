"use client";

/**
 * /guide — "Cómo funciona" DENTRO de la app (no un HTML aparte).
 *
 * Lee /api/health (variant) y muestra el flujo según la variante:
 *   - hro → flujo de reclutamiento (5 pasos), tabla de configuración, link de
 *           entrevista y "dónde ves cada cosa".
 *   - crm → flujo de prospección (5 pasos) equivalente.
 *   - rugol / default → texto breve genérico.
 *
 * 100% frontend. Estética crema/editorial; el acento entra por --color-accent
 * (lo inyecta la nav-rail en runtime). Sin colores hardcodeados.
 */

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  UserPlus,
  ScanSearch,
  Mic,
  KanbanSquare,
  Trophy,
  Sparkles,
  Target,
  Search,
  PenLine,
  ClipboardCheck,
  Users,
  Briefcase,
  Bot,
  Copy,
  ExternalLink,
  Map as MapIcon,
} from "lucide-react";
import { fetchHealth } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toast";
import { useI18n } from "@/lib/i18n";

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

type Step = { n: string; icon: typeof UserPlus; title: string; body: string };

export default function GuidePage() {
  const health = useQuery({ queryKey: ["health"], queryFn: fetchHealth });
  const variant = health.data?.variant;

  if (variant === "hro") return <HroGuide />;
  if (variant === "crm") return <CrmGuide />;
  return <RugolGuide />;
}

// ---------------------------------------------------------------------------
// Bloques compartidos
// ---------------------------------------------------------------------------

function GuideHeader({ title, subtitle }: { title: string; subtitle: string }) {
  const { t } = useI18n();
  return (
    <header className="relative overflow-hidden surface px-8 py-9 md:py-11">
      <div
        className="absolute -top-20 -right-20 w-80 h-80 rounded-full opacity-25 blur-3xl pointer-events-none"
        style={{ background: "radial-gradient(circle, var(--color-accent) 0%, transparent 70%)" }}
      />
      <div className="relative max-w-2xl space-y-3">
        <span className="inline-flex items-center gap-1.5 text-[10.5px] uppercase tracking-widest font-medium text-[--color-accent-strong]">
          <MapIcon size={12} /> {t("nav.guide")}
        </span>
        <h1 className="text-3xl md:text-4xl font-semibold tracking-tight leading-[1.1]">
          {title}
        </h1>
        <p className="text-[15px] text-[--color-fg-muted] leading-relaxed max-w-xl">
          {subtitle}
        </p>
      </div>
    </header>
  );
}

function FlowSteps({ steps }: { steps: Step[] }) {
  const { t } = useI18n();
  return (
    <section className="space-y-4">
      <h2 className="text-sm font-semibold tracking-tight">{t("guide.flowHeading")}</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        {steps.map(({ n, icon: Icon, title, body }) => (
          <div key={n} className="surface p-4 flex flex-col gap-2.5 relative overflow-hidden">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[11px] tracking-widest text-[--color-fg-subtle]">
                {n}
              </span>
              <Icon size={16} className="text-[--color-accent-strong]" />
            </div>
            <h3 className="text-[13.5px] font-semibold tracking-tight leading-tight">{title}</h3>
            <p className="text-[12px] text-[--color-fg-muted] leading-relaxed">{body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function SeeCard({
  href,
  icon: Icon,
  title,
  body,
}: {
  href: string;
  icon: typeof Users;
  title: string;
  body: string;
}) {
  return (
    <Link
      href={href}
      className="group surface surface-hover p-4 flex flex-col gap-2 transition"
    >
      <span className="w-8 h-8 rounded-lg grid place-items-center bg-[--color-accent-soft] text-[--color-accent-strong]">
        <Icon size={16} />
      </span>
      <h3 className="text-[13.5px] font-semibold tracking-tight leading-tight">{title}</h3>
      <p className="text-[12px] text-[--color-fg-muted] leading-relaxed">{body}</p>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// HRO
// ---------------------------------------------------------------------------

function HroGuide() {
  const { t } = useI18n();

  const steps: Step[] = [
    { n: "01", icon: UserPlus, title: t("guide.hro.s1.title"), body: t("guide.hro.s1.body") },
    { n: "02", icon: ScanSearch, title: t("guide.hro.s2.title"), body: t("guide.hro.s2.body") },
    { n: "03", icon: Mic, title: t("guide.hro.s3.title"), body: t("guide.hro.s3.body") },
    { n: "04", icon: KanbanSquare, title: t("guide.hro.s4.title"), body: t("guide.hro.s4.body") },
    { n: "05", icon: Trophy, title: t("guide.hro.s5.title"), body: t("guide.hro.s5.body") },
  ];

  const configRows = [
    { thing: t("guide.config.anthropic.thing"), where: t("guide.config.anthropic.where") },
    { thing: t("guide.config.elevenlabs.thing"), where: t("guide.config.elevenlabs.where") },
    { thing: t("guide.config.telegram.thing"), where: t("guide.config.telegram.where") },
    { thing: t("guide.config.tools.thing"), where: t("guide.config.tools.where") },
  ];

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(VOICE_LANDING_URL);
      toast({ tone: "success", title: t("guide.link.copied") });
    } catch {
      toast({ tone: "error", title: t("guide.link.copyFailed") });
    }
  }

  return (
    <div className="p-8 space-y-10 max-w-[1200px] mx-auto">
      <GuideHeader title={t("guide.hro.title")} subtitle={t("guide.hro.subtitle")} />

      <FlowSteps steps={steps} />

      {/* Tabla: dónde se configura cada cosa */}
      <section className="space-y-4">
        <h2 className="text-sm font-semibold tracking-tight">{t("guide.config.heading")}</h2>
        <Card className="p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[--color-border] text-[10px] uppercase tracking-widest text-[--color-fg-muted]">
                  <th className="text-left font-medium px-5 py-3">{t("guide.config.thing")}</th>
                  <th className="text-left font-medium px-5 py-3">{t("guide.config.where")}</th>
                </tr>
              </thead>
              <tbody>
                {configRows.map((row) => (
                  <tr
                    key={row.thing}
                    className="border-b border-[--color-border]/60 last:border-0"
                  >
                    <td className="px-5 py-3 font-medium text-[--color-fg]">{row.thing}</td>
                    <td className="px-5 py-3 text-[--color-fg-muted]">{row.where}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </section>

      {/* Link de entrevista */}
      <section>
        <Card className="border-[--color-accent]/40 space-y-4">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-xl grid place-items-center shrink-0 bg-[--color-accent-soft] text-[--color-accent-strong]">
              <Mic size={17} />
            </div>
            <div className="min-w-0">
              <h2 className="text-base font-semibold tracking-tight">{t("guide.link.heading")}</h2>
              <p className="text-sm text-[--color-fg-muted] mt-0.5">{t("guide.link.body")}</p>
            </div>
          </div>
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
            <code className="flex-1 min-w-0 surface px-3 py-2.5 font-mono text-[13px] text-[--color-fg] truncate">
              {VOICE_LANDING_URL}
            </code>
            <div className="flex items-center gap-2 shrink-0">
              <Button variant="primary" size="md" onClick={copyLink}>
                <Copy size={14} /> {t("guide.link.copy")}
              </Button>
              <Button variant="secondary" size="md" onClick={() => openExternal(VOICE_LANDING_URL)}>
                <ExternalLink size={14} /> {t("guide.link.open")}
              </Button>
            </div>
          </div>
        </Card>
      </section>

      {/* Dónde ves cada cosa */}
      <section className="space-y-4">
        <h2 className="text-sm font-semibold tracking-tight">{t("guide.see.heading")}</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <SeeCard
            href="/pipeline"
            icon={Users}
            title={t("guide.see.candidates.title")}
            body={t("guide.see.candidates.body")}
          />
          <SeeCard
            href="/interviews"
            icon={ClipboardCheck}
            title={t("guide.see.interviews.title")}
            body={t("guide.see.interviews.body")}
          />
          <SeeCard
            href="/projects"
            icon={Briefcase}
            title={t("guide.see.searches.title")}
            body={t("guide.see.searches.body")}
          />
          <SeeCard
            href="/agents"
            icon={Bot}
            title={t("guide.see.agents.title")}
            body={t("guide.see.agents.body")}
          />
        </div>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CRM
// ---------------------------------------------------------------------------

function CrmGuide() {
  const { t } = useI18n();

  const steps: Step[] = [
    { n: "01", icon: Target, title: t("guide.crm.s1.title"), body: t("guide.crm.s1.body") },
    { n: "02", icon: Search, title: t("guide.crm.s2.title"), body: t("guide.crm.s2.body") },
    { n: "03", icon: ScanSearch, title: t("guide.crm.s3.title"), body: t("guide.crm.s3.body") },
    { n: "04", icon: PenLine, title: t("guide.crm.s4.title"), body: t("guide.crm.s4.body") },
    { n: "05", icon: Trophy, title: t("guide.crm.s5.title"), body: t("guide.crm.s5.body") },
  ];

  return (
    <div className="p-8 space-y-10 max-w-[1200px] mx-auto">
      <GuideHeader title={t("guide.crm.title")} subtitle={t("guide.crm.subtitle")} />

      <FlowSteps steps={steps} />

      {/* Dónde ves cada cosa */}
      <section className="space-y-4">
        <h2 className="text-sm font-semibold tracking-tight">{t("guide.see.heading")}</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          <SeeCard
            href="/pipeline"
            icon={Users}
            title={t("guide.see.prospects.title")}
            body={t("guide.see.prospects.body")}
          />
          <SeeCard
            href="/projects"
            icon={Briefcase}
            title={t("guide.see.projects.title")}
            body={t("guide.see.projects.body")}
          />
          <SeeCard
            href="/agents"
            icon={Bot}
            title={t("guide.see.agents.title")}
            body={t("guide.see.agents.body")}
          />
        </div>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Rugol (genérico)
// ---------------------------------------------------------------------------

function RugolGuide() {
  const { t } = useI18n();
  return (
    <div className="p-8 space-y-8 max-w-[900px] mx-auto">
      <GuideHeader title={t("guide.rugol.title")} subtitle={t("onboarding.headline")} />
      <Card className="space-y-3">
        <span className="inline-flex items-center gap-1.5 text-[10.5px] uppercase tracking-widest font-medium text-[--color-accent-strong]">
          <Sparkles size={12} /> Rugol
        </span>
        <p className="text-[15px] text-[--color-fg] leading-relaxed">{t("guide.rugol.body")}</p>
        <div className="flex items-center gap-2 pt-2">
          <Link href="/projects">
            <Button variant="primary">
              <Briefcase size={14} /> {t("nav.projects")}
            </Button>
          </Link>
          <Link href="/architect">
            <Button variant="secondary">
              <Sparkles size={14} /> {t("nav.architect")}
            </Button>
          </Link>
        </div>
      </Card>
    </div>
  );
}
