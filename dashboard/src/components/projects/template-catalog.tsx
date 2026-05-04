"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  Sparkles,
  Users,
  Clock,
  ChevronRight,
  Wand2,
  X,
} from "lucide-react";
import {
  cloneTemplate,
  fetchTemplates,
  type TemplateCard,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { FieldLabel, Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";
import { projectIcon } from "./project-badge";
import { useI18n } from "@/lib/i18n";

/**
 * Renders the curated template catalog as a horizontal-feeling grid above
 * the project list. Clicking a card opens a preview modal that summarizes
 * the team and lets the user clone it (with optional slug override).
 */
export function TemplateCatalog({ open = true }: { open?: boolean }) {
  const { t } = useI18n();
  const templates = useQuery({
    queryKey: ["templates"],
    queryFn: fetchTemplates,
    staleTime: 60_000,
  });

  if (!open) return null;
  if (templates.isLoading) {
    return <p className="text-sm text-[--color-fg-muted]">{t("common.loading")}</p>;
  }
  if (!templates.data || templates.data.length === 0) return null;

  return (
    <section className="space-y-3">
      <header className="flex items-end justify-between">
        <div>
          <h2 className="text-sm font-semibold tracking-tight inline-flex items-center gap-2">
            <Sparkles size={13} className="text-[--color-accent-strong]" />
            {t("templates.title")}
          </h2>
          <p className="text-xs text-[--color-fg-muted] mt-0.5 max-w-2xl">
            {t("templates.description")}
          </p>
        </div>
      </header>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {templates.data.map((tpl) => (
          <TemplatePreview key={tpl.id} template={tpl} />
        ))}
      </div>
    </section>
  );
}

function TemplatePreview({ template }: { template: TemplateCard }) {
  const { t } = useI18n();
  const Icon = projectIcon(template.project?.icon);
  const tone = template.project?.color || "#7280a8";
  const audienceLabel = template.audience === "casual"
    ? t("templates.audienceCasual")
    : t("templates.audiencePro");
  const agentsWord = template.agent_count === 1 ? t("templates.agent") : t("templates.agents");
  const schedulesWord = template.schedule_count === 1 ? t("templates.schedule") : t("templates.schedules");
  return (
    <Dialog>
      <DialogTrigger asChild>
        <button
          type="button"
          className="surface surface-hover p-4 text-left flex flex-col gap-3 transition relative overflow-hidden group"
        >
          <div
            className="absolute -top-10 -right-10 w-32 h-32 rounded-full opacity-20 blur-2xl pointer-events-none"
            style={{ background: tone }}
          />
          <header className="flex items-start gap-3 relative">
            <div
              className="w-9 h-9 rounded-xl grid place-items-center shrink-0"
              style={{
                background: `${tone}22`,
                color: tone,
                border: `1px solid ${tone}44`,
              }}
            >
              <Icon size={16} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[10px] uppercase tracking-widest text-[--color-fg-subtle]">
                {audienceLabel}
              </p>
              <h3 className="text-sm font-semibold tracking-tight truncate">
                {template.title}
              </h3>
            </div>
          </header>
          <p className="text-[12.5px] text-[--color-fg-muted] line-clamp-2 leading-relaxed">
            {template.pitch}
          </p>
          <footer className="flex items-center justify-between text-[10.5px] text-[--color-fg-subtle] font-mono pt-1 border-t border-[--color-border]/60">
            <span className="inline-flex items-center gap-1.5">
              <Users size={10} /> {template.agent_count} {agentsWord}
            </span>
            {template.schedule_count > 0 && (
              <span className="inline-flex items-center gap-1.5">
                <Clock size={10} /> {template.schedule_count} {schedulesWord}
              </span>
            )}
            <span className="inline-flex items-center gap-0.5 group-hover:text-[--color-accent-strong] transition-colors">
              {t("templates.see")} <ChevronRight size={10} />
            </span>
          </footer>
        </button>
      </DialogTrigger>
      <DialogContent
        title={template.title}
        description={template.story}
      >
        <CloneTemplateContent template={template} />
      </DialogContent>
    </Dialog>
  );
}

function CloneTemplateContent({ template }: { template: TemplateCard }) {
  const router = useRouter();
  const qc = useQueryClient();
  const detail = useQuery({
    queryKey: ["template", template.id],
    queryFn: () => import("@/lib/api").then((m) => m.fetchTemplate(template.id)),
  });
  const [slugOverride, setSlugOverride] = useState("");
  const [conflictMode, setConflictMode] = useState(false);

  const clone = useMutation({
    mutationFn: (body: { slug_override?: string }) => cloneTemplate(template.id, body),
    onSuccess: (res) => {
      toast({
        tone: "success",
        title: `Proyecto creado: ${res.project_slug}`,
        body: `${res.agents_created.length} agentes deployados.`,
      });
      qc.invalidateQueries({ queryKey: ["projects"] });
      qc.invalidateQueries({ queryKey: ["agents"] });
      if (res.project_slug) router.push(`/projects/${res.project_slug}`);
    },
    onError: (e: Error) => {
      const msg = e.message || "";
      if (msg.toLowerCase().includes("ya existe un proyecto")) {
        setConflictMode(true);
        if (template.project) setSlugOverride(`${template.project.slug}-2`);
        toast({
          tone: "info",
          title: "Slug ya usado",
          body: "Elegí un slug alternativo abajo y volvé a clonar.",
        });
      } else {
        toast({ tone: "error", title: "No se pudo clonar", body: msg.slice(0, 200) });
      }
    },
  });

  function submit() {
    clone.mutate(slugOverride.trim() ? { slug_override: slugOverride.trim().toLowerCase() } : {});
  }

  return (
    <div className="space-y-4">
      {detail.data?.project?.mission && (
        <div className="surface px-4 py-3 border-l-4" style={{ borderLeftColor: detail.data.project.color }}>
          <p className="text-[10px] uppercase tracking-widest text-[--color-fg-muted] font-medium mb-1">
            Misión
          </p>
          <p className="text-sm text-[--color-fg] leading-relaxed">{detail.data.project.mission}</p>
        </div>
      )}

      {detail.data?.proposal?.agents && (
        <div className="space-y-2">
          <p className="text-xs text-[--color-fg-muted] uppercase tracking-widest font-medium">
            Equipo ({detail.data.proposal.agents.length})
          </p>
          <ul className="space-y-1.5">
            {detail.data.proposal.agents.map((a) => (
              <li key={a.name} className="text-[12.5px] flex items-start gap-2">
                <code className="font-mono text-[--color-accent-strong] shrink-0">{a.name}</code>
                <span className="text-[--color-fg-muted]">— {a.description}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {detail.data?.proposal?.schedules && detail.data.proposal.schedules.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-[--color-fg-muted] uppercase tracking-widest font-medium">
            Schedules
          </p>
          <ul className="space-y-1 text-[12px] font-mono">
            {detail.data.proposal.schedules.map((s, i) => (
              <li key={i} className="flex items-center gap-2">
                <span className="text-[--color-accent-strong]">{s.cron_expr}</span>
                <span className="text-[--color-fg-subtle]">→</span>
                <span className="text-[--color-fg-muted]">{s.agent_name}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {conflictMode && (
        <div className="space-y-1.5">
          <FieldLabel hint="lowercase, dashes ok">
            Slug alternativo
          </FieldLabel>
          <Input
            value={slugOverride}
            onChange={(e) => setSlugOverride(e.target.value.toLowerCase())}
            placeholder={template.project ? `${template.project.slug}-2` : ""}
            className="font-mono"
          />
        </div>
      )}

      <div className="flex items-center justify-end gap-2 pt-2">
        <Button
          variant="primary"
          onClick={submit}
          disabled={clone.isPending || (conflictMode && !slugOverride.trim())}
        >
          <Wand2 size={13} />
          {clone.isPending ? "Clonando…" : "Clonar este template"}
        </Button>
      </div>

      <p className="text-[11px] text-[--color-fg-subtle]">
        Vas a tener una copia editable: cambiá el nombre del proyecto, mové
        agentes, ajustá el spec de cada uno. El template original queda intacto
        para clonarlo otra vez.
      </p>
    </div>
  );
}
