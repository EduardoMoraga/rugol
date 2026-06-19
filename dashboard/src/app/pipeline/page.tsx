"use client";

/**
 * Pipeline de dominio — vista KANBAN (CRM prospectos / HRO candidatos).
 *
 * La variante (health.variant) decide el dominio:
 *   - crm  → kind=lead      (etiqueta "Prospectos")
 *   - hro  → kind=candidate (etiqueta "Candidatos")
 *   - rugol→ esta vista no aplica (Rugol orquesta agentes, no pipeline de dominio)
 *
 * El backend (core/api/pipeline.py) lo poblan los agentes runtime y el usuario
 * puede operarlo a mano: crear items, moverlos de etapa, agregar notas, borrar.
 *
 * Decisión de UX: mover de etapa con botones ‹ › (sin librerías de drag&drop) —
 * limpio, accesible y sin dependencias nuevas. Refetch tras cada mutación.
 */

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  Plus,
  Target,
  Trash2,
  Bot,
  User,
  KanbanSquare,
  Search,
  Briefcase,
} from "lucide-react";
import {
  createPipelineItem,
  deletePipelineItem,
  fetchHealth,
  fetchPipeline,
  fetchPipelineStages,
  fetchProjects,
  updatePipelineItem,
  type PipelineCreate,
  type PipelineItem,
  type PipelineKind,
  type Project,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, PageHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { FieldLabel, Input, Select, Textarea } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";
import { useI18n } from "@/lib/i18n";

export default function PipelinePage() {
  const { t } = useI18n();
  const health = useQuery({ queryKey: ["health"], queryFn: fetchHealth, refetchInterval: 30_000 });
  const variant = health.data?.variant;

  // Mientras carga la salud no sabemos el dominio: estado neutro.
  if (!health.data) {
    return (
      <div className="p-8 max-w-[1400px] mx-auto">
        <p className="text-sm text-[--color-fg-muted]">{t("pipeline.loading")}</p>
      </div>
    );
  }

  if (variant === "rugol" || variant === undefined) {
    return (
      <div className="p-8 max-w-[1400px] mx-auto">
        <Card className="text-center py-16 space-y-4">
          <KanbanSquare size={36} className="mx-auto text-[--color-fg-subtle]" />
          <div>
            <h2 className="text-lg font-semibold tracking-tight">{t("pipeline.rugolTitle")}</h2>
            <p className="text-sm text-[--color-fg-muted] mt-1 max-w-md mx-auto">
              {t("pipeline.rugolBody")}
            </p>
          </div>
        </Card>
      </div>
    );
  }

  const kind: PipelineKind = variant === "hro" ? "candidate" : "lead";
  return <PipelineBoard kind={kind} />;
}

function PipelineBoard({ kind }: { kind: PipelineKind }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [selected, setSelected] = useState<PipelineItem | null>(null);

  // --- Filtros (barra superior) ---
  const isLead = kind === "lead";
  const [projectFilter, setProjectFilter] = useState<string>(""); // "" = todas
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState(""); // valor con debounce

  // Debounce simple del texto libre (300ms) para no refetchear en cada tecla.
  useEffect(() => {
    const id = setTimeout(() => setSearch(searchInput.trim()), 300);
    return () => clearTimeout(id);
  }, [searchInput]);

  // Lista de búsquedas/proyectos para el filtro y para resolver nombres.
  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => fetchProjects(),
  });
  const projects = projectsQuery.data ?? [];
  const projectName = useMemo(() => {
    const m: Record<string, string> = {};
    for (const p of projects) m[p.slug] = p.name;
    return m;
  }, [projects]);

  const stagesQuery = useQuery({
    queryKey: ["pipeline-stages", kind],
    queryFn: () => fetchPipelineStages(kind),
  });
  const itemsQuery = useQuery({
    queryKey: ["pipeline", kind, projectFilter, search],
    queryFn: () =>
      fetchPipeline(kind, {
        project: projectFilter || undefined,
        q: search || undefined,
      }),
    refetchInterval: 8000,
  });

  const stages = stagesQuery.data?.stages ?? [];
  const items = itemsQuery.data ?? [];

  const byStage = useMemo(() => {
    const map: Record<string, PipelineItem[]> = {};
    for (const s of stages) map[s] = [];
    for (const it of items) {
      (map[it.stage] ??= []).push(it);
    }
    return map;
  }, [items, stages]);

  const title = isLead ? t("pipeline.titleLead") : t("pipeline.titleCandidate");
  const description = isLead ? t("pipeline.descLead") : t("pipeline.descCandidate");
  const emptyMsg = isLead ? t("pipeline.emptyLead") : t("pipeline.emptyCandidate");

  // --- Mutaciones ---
  // Invalida todas las variantes de la query del pipeline para este kind
  // (cualquier combinación de filtros project/q).
  const invalidate = () =>
    qc.invalidateQueries({ queryKey: ["pipeline", kind] });

  const move = useMutation({
    mutationFn: ({ id, stage }: { id: number; stage: string }) =>
      updatePipelineItem(id, { stage }),
    onSuccess: () => {
      toast({ tone: "success", title: t("pipeline.moved") });
      invalidate();
    },
    onError: (e: Error) => toast({ tone: "error", title: t("pipeline.moved"), body: e.message }),
  });

  function moveBy(it: PipelineItem, delta: 1 | -1) {
    const idx = stages.indexOf(it.stage);
    const next = idx + delta;
    if (next < 0 || next >= stages.length) return;
    move.mutate({ id: it.id, stage: stages[next] });
  }

  const hasFilters = projectFilter !== "" || search !== "";
  // El estado vacío "no hay nada todavía" solo aplica sin filtros activos:
  // con filtros, mostramos el tablero (columnas vacías) para que el usuario
  // pueda ajustarlos o limpiarlos.
  const isEmpty = !itemsQuery.isLoading && items.length === 0 && !hasFilters;

  return (
    <div className="p-8 space-y-8 max-w-[1600px] mx-auto">
      <PageHeader
        title={title}
        description={description}
        actions={
          <AddItemDialog
            kind={kind}
            stages={stages}
            projects={projects}
            onCreated={invalidate}
          />
        }
      />

      {/* Barra de filtros */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <Briefcase size={14} className="text-[--color-fg-muted]" />
          <Select
            value={projectFilter}
            onChange={(e) => setProjectFilter(e.target.value)}
            className="h-9 w-[220px]"
            aria-label={isLead ? t("candidates.filter.project") : t("candidates.filter.search")}
          >
            <option value="">
              {isLead ? t("candidates.filter.allProjects") : t("candidates.filter.allSearches")}
            </option>
            {projects.map((p) => (
              <option key={p.slug} value={p.slug}>
                {p.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-[--color-fg-muted] pointer-events-none"
          />
          <Input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder={
              isLead
                ? t("candidates.filter.searchLeadPlaceholder")
                : t("candidates.filter.searchPlaceholder")
            }
            className="pl-9"
          />
        </div>
      </div>

      {itemsQuery.isLoading && (
        <p className="text-sm text-[--color-fg-muted]">{t("pipeline.loading")}</p>
      )}

      {isEmpty && (
        <Card className="text-center py-16 space-y-4">
          <Target size={36} className="mx-auto text-[--color-fg-subtle]" />
          <div>
            <p className="text-sm text-[--color-fg-muted] max-w-md mx-auto">{emptyMsg}</p>
          </div>
          <div className="flex items-center justify-center pt-2">
            <AddItemDialog
              kind={kind}
              stages={stages}
              projects={projects}
              onCreated={invalidate}
            />
          </div>
        </Card>
      )}

      {!isEmpty && stages.length > 0 && (
        <div className="flex gap-4 overflow-x-auto pb-4">
          {stages.map((stage, stageIdx) => {
            const colItems = byStage[stage] ?? [];
            return (
              <div key={stage} className="w-[280px] shrink-0 flex flex-col">
                <div className="flex items-center justify-between px-1 pb-2 sticky top-0">
                  <h2 className="text-[13px] font-semibold tracking-tight">{stage}</h2>
                  <span className="pill pill-idle text-[10px] tabular-nums">{colItems.length}</span>
                </div>
                <div className="space-y-2 min-h-[60px]">
                  {colItems.length === 0 && (
                    <div className="surface border-dashed text-center py-6 text-[11px] text-[--color-fg-subtle]">
                      {t("pipeline.colEmpty")}
                    </div>
                  )}
                  {colItems.map((it) => (
                    <KanbanCard
                      key={it.id}
                      item={it}
                      projectName={
                        it.project_slug ? projectName[it.project_slug] ?? null : null
                      }
                      canBack={stageIdx > 0}
                      canForward={stageIdx < stages.length - 1}
                      onBack={() => moveBy(it, -1)}
                      onForward={() => moveBy(it, 1)}
                      onOpen={() => setSelected(it)}
                      busy={move.isPending}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {selected && (
        <DetailDialog
          item={items.find((i) => i.id === selected.id) ?? selected}
          kind={kind}
          onClose={() => setSelected(null)}
          onChanged={invalidate}
        />
      )}
    </div>
  );
}

function scoreTone(score: number): "accent" | "running" | "warn" | "idle" {
  if (score >= 4) return "running";
  if (score >= 3) return "accent";
  if (score >= 2) return "warn";
  return "idle";
}

function KanbanCard({
  item,
  projectName,
  canBack,
  canForward,
  onBack,
  onForward,
  onOpen,
  busy,
}: {
  item: PipelineItem;
  projectName: string | null;
  canBack: boolean;
  canForward: boolean;
  onBack: () => void;
  onForward: () => void;
  onOpen: () => void;
  busy: boolean;
}) {
  const { t } = useI18n();
  return (
    <div className="surface surface-hover p-3 space-y-2 group">
      <button
        type="button"
        onClick={onOpen}
        className="block w-full text-left space-y-1"
      >
        <div className="flex items-start justify-between gap-2">
          <p className="text-[13px] font-medium leading-tight">{item.title}</p>
          {item.score != null && (
            <Badge tone={scoreTone(item.score)} className="shrink-0 text-[10px]">
              {item.score}/5
            </Badge>
          )}
        </div>
        {item.subtitle && (
          <p className="text-[11px] text-[--color-fg-muted] line-clamp-2">{item.subtitle}</p>
        )}
        {projectName && (
          <div className="pt-0.5">
            <Badge tone="idle" className="text-[10px] inline-flex items-center gap-1 max-w-full">
              <Briefcase size={9} className="shrink-0" />
              <span className="truncate">{projectName}</span>
            </Badge>
          </div>
        )}
        <div className="flex items-center gap-1.5 text-[10px] text-[--color-fg-subtle] font-mono pt-0.5">
          <Bot size={10} />
          <span className="truncate">{item.source_agent || t("pipeline.manual")}</span>
        </div>
      </button>
      <div className="flex items-center justify-between pt-1 border-t border-[--color-border]/60">
        <button
          type="button"
          onClick={onBack}
          disabled={!canBack || busy}
          aria-label={t("pipeline.moveBack")}
          title={t("pipeline.moveBack")}
          className="h-6 w-6 grid place-items-center rounded text-[--color-fg-muted] hover:text-[--color-fg] hover:bg-[--color-bg-elev] disabled:opacity-30 disabled:cursor-not-allowed transition"
        >
          <ChevronLeft size={14} />
        </button>
        <button
          type="button"
          onClick={onForward}
          disabled={!canForward || busy}
          aria-label={t("pipeline.moveForward")}
          title={t("pipeline.moveForward")}
          className="h-6 w-6 grid place-items-center rounded text-[--color-fg-muted] hover:text-[--color-accent-strong] hover:bg-[--color-accent-soft] disabled:opacity-30 disabled:cursor-not-allowed transition"
        >
          <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}

function DetailDialog({
  item,
  kind,
  onClose,
  onChanged,
}: {
  item: PipelineItem;
  kind: PipelineKind;
  onClose: () => void;
  onChanged: () => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [note, setNote] = useState("");

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["pipeline", kind] });
    onChanged();
  };

  const addNote = useMutation({
    mutationFn: (text: string) =>
      updatePipelineItem(item.id, { note: text, note_agent: t("pipeline.manual") }),
    onSuccess: () => {
      toast({ tone: "success", title: t("pipeline.noteAdded") });
      setNote("");
      refresh();
    },
    onError: (e: Error) => toast({ tone: "error", title: t("pipeline.addNote"), body: e.message }),
  });

  const remove = useMutation({
    mutationFn: () => deletePipelineItem(item.id),
    onSuccess: () => {
      toast({ tone: "success", title: t("pipeline.deleted") });
      refresh();
      onClose();
    },
    onError: (e: Error) => toast({ tone: "error", title: t("pipeline.delete"), body: e.message }),
  });

  const dataEntries = Object.entries(item.data ?? {});
  const notes = [...(item.notes ?? [])];

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={item.title} description={item.subtitle || undefined}>
        <div className="space-y-5 max-h-[70vh] overflow-y-auto pr-1">
          {/* Meta */}
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            <Badge tone="accent">{item.stage}</Badge>
            {item.score != null ? (
              <Badge tone={scoreTone(item.score)}>
                {t("pipeline.score")} {item.score}/5
              </Badge>
            ) : (
              <Badge tone="idle">{t("pipeline.noScore")}</Badge>
            )}
            <span className="inline-flex items-center gap-1.5 text-[--color-fg-muted] font-mono">
              <Bot size={11} /> {item.source_agent || t("pipeline.manual")}
            </span>
          </div>

          {/* Data key/values */}
          <section className="space-y-2">
            <h3 className="text-[11px] uppercase tracking-wider text-[--color-fg-muted] font-medium">
              {t("pipeline.data")}
            </h3>
            {dataEntries.length === 0 ? (
              <p className="text-xs text-[--color-fg-subtle]">{t("pipeline.noData")}</p>
            ) : (
              <dl className="surface p-3 space-y-1.5">
                {dataEntries.map(([k, v]) => (
                  <div key={k} className="flex items-start justify-between gap-3 text-xs">
                    <dt className="text-[--color-fg-muted] font-mono shrink-0">{k}</dt>
                    <dd className="text-[--color-fg] text-right break-words min-w-0">
                      {typeof v === "object" ? JSON.stringify(v) : String(v)}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
          </section>

          {/* Historial de notas */}
          <section className="space-y-2">
            <h3 className="text-[11px] uppercase tracking-wider text-[--color-fg-muted] font-medium">
              {t("pipeline.history")}
            </h3>
            {notes.length === 0 ? (
              <p className="text-xs text-[--color-fg-subtle]">{t("pipeline.noNotes")}</p>
            ) : (
              <ol className="space-y-2">
                {notes.map((n, i) => (
                  <li key={i} className="surface p-3 space-y-1">
                    <div className="flex items-center gap-1.5 text-[10px] text-[--color-fg-subtle] font-mono">
                      {n.agent ? <Bot size={10} /> : <User size={10} />}
                      <span>{n.agent || t("pipeline.manual")}</span>
                      {n.at && <span>· {new Date(n.at).toLocaleString()}</span>}
                    </div>
                    <p className="text-[13px] leading-relaxed whitespace-pre-wrap">{n.text}</p>
                  </li>
                ))}
              </ol>
            )}
          </section>

          {/* Agregar nota */}
          <section className="space-y-2">
            <FieldLabel>{t("pipeline.addNote")}</FieldLabel>
            <Textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              placeholder={t("pipeline.notePlaceholder")}
            />
            <div className="flex items-center justify-between gap-2">
              <Button
                variant="danger"
                size="sm"
                onClick={() => {
                  if (window.confirm(t("pipeline.deleteConfirm"))) remove.mutate();
                }}
                disabled={remove.isPending}
              >
                <Trash2 size={13} /> {t("pipeline.delete")}
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => note.trim() && addNote.mutate(note.trim())}
                disabled={addNote.isPending || !note.trim()}
              >
                {addNote.isPending ? t("pipeline.savingNote") : t("pipeline.saveNote")}
              </Button>
            </div>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function AddItemDialog({
  kind,
  stages,
  projects,
  onCreated,
}: {
  kind: PipelineKind;
  stages: string[];
  projects: Project[];
  onCreated: () => void;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const isLead = kind === "lead";
  const empty: PipelineCreate = {
    kind,
    title: "",
    subtitle: "",
    stage: stages[0] ?? null,
    source_agent: null,
    project_slug: null,
  };
  const [body, setBody] = useState<PipelineCreate>(empty);

  const create = useMutation({
    mutationFn: (b: PipelineCreate) => createPipelineItem(b),
    onSuccess: (it) => {
      toast({ tone: "success", title: `${t("pipeline.created")}: ${it.title}` });
      onCreated();
      setOpen(false);
      setBody({ ...empty, stage: stages[0] ?? null });
    },
    onError: (e: Error) => toast({ tone: "error", title: t("pipeline.create"), body: e.message }),
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!body.title.trim()) return;
    create.mutate({
      ...body,
      title: body.title.trim(),
      subtitle: body.subtitle?.trim() || null,
      stage: body.stage || stages[0] || null,
      project_slug: body.project_slug || null,
    });
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (o) setBody({ ...empty, stage: stages[0] ?? null });
      }}
    >
      <DialogTrigger asChild>
        <Button variant="primary">
          <Plus size={14} /> {isLead ? t("pipeline.addLead") : t("pipeline.addCandidate")}
        </Button>
      </DialogTrigger>
      <DialogContent
        title={isLead ? t("pipeline.addLead") : t("pipeline.addCandidate")}
        className="max-w-lg"
      >
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-1.5">
            <FieldLabel>{t("pipeline.title")}</FieldLabel>
            <Input
              value={body.title}
              onChange={(e) => setBody({ ...body, title: e.target.value })}
              placeholder={t("pipeline.titlePlaceholder")}
              required
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <FieldLabel>{t("pipeline.subtitle")}</FieldLabel>
            <Input
              value={body.subtitle ?? ""}
              onChange={(e) => setBody({ ...body, subtitle: e.target.value })}
              placeholder={t("pipeline.subtitlePlaceholder")}
            />
          </div>
          <div className="space-y-1.5">
            <FieldLabel>{t("pipeline.stage")}</FieldLabel>
            <Select
              value={body.stage ?? stages[0] ?? ""}
              onChange={(e) => setBody({ ...body, stage: e.target.value })}
            >
              {stages.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <FieldLabel hint={t("candidates.field.searchHint")}>
              {isLead ? t("candidates.field.project") : t("candidates.field.search")}
            </FieldLabel>
            <Select
              value={body.project_slug ?? ""}
              onChange={(e) =>
                setBody({ ...body, project_slug: e.target.value || null })
              }
            >
              <option value="">{t("candidates.field.none")}</option>
              {projects.map((p) => (
                <option key={p.slug} value={p.slug}>
                  {p.name}
                </option>
              ))}
            </Select>
          </div>
          {create.isError && (
            <p className="text-xs text-[--color-error] bg-[--color-error]/10 border border-[--color-error]/30 rounded-md px-3 py-2">
              {(create.error as Error).message}
            </p>
          )}
          <div className="flex items-center justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setOpen(false)}
              disabled={create.isPending}
            >
              {t("pipeline.cancel")}
            </Button>
            <Button type="submit" variant="primary" disabled={create.isPending || !body.title.trim()}>
              {create.isPending ? t("pipeline.creating") : t("pipeline.create")}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
