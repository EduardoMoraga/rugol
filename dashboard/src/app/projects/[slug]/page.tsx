"use client";

import Link from "next/link";
import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Pencil,
  Plus,
  Sparkles,
  Trash2,
  Users,
  Activity,
  DollarSign,
  Brain,
  X,
  FolderOpen,
  ScanSearch,
  Plug,
} from "lucide-react";
import {
  addProjectLesson,
  connectSource,
  deleteProject,
  fetchHealth,
  fetchProject,
  fetchProjectAgents,
  fetchProjectRuns,
  removeProjectLesson,
  screenCvs,
  updateProject,
  type ConnectSourceKind,
  type Lesson,
  type Project,
  type ProjectUpdate,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardSection, PageHeader, Stat } from "@/components/ui/card";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { FieldLabel, Input, Select, Textarea } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { toast } from "@/components/ui/toast";
import { PROJECT_ICONS, projectIcon } from "@/components/projects/project-badge";
import { useI18n } from "@/lib/i18n";

const PALETTE = [
  "#7280a8", "#5b8def", "#7c5cff", "#c44d8c",
  "#e26f3f", "#f5b942", "#3aaf85", "#2c9aaf",
];

export default function ProjectDetail() {
  const { t } = useI18n();
  const params = useParams<{ slug: string }>();
  const slug = params.slug;
  const router = useRouter();
  const qc = useQueryClient();

  // En HRO un proyecto ES una búsqueda: cambiamos los labels (misión → alcance)
  // y mostramos la descripción de cargo.
  const health = useQuery({ queryKey: ["health"], queryFn: fetchHealth });
  const isHro = health.data?.variant === "hro";

  const project = useQuery({
    queryKey: ["project", slug],
    queryFn: () => fetchProject(slug),
    enabled: !!slug,
    refetchInterval: 8000,
  });
  const agents = useQuery({
    queryKey: ["project-agents", slug],
    queryFn: () => fetchProjectAgents(slug),
    enabled: !!slug,
    refetchInterval: 5000,
  });
  const runs = useQuery({
    queryKey: ["project-runs", slug],
    queryFn: () => fetchProjectRuns(slug, 30),
    enabled: !!slug,
    refetchInterval: 5000,
  });

  const remove = useMutation({
    mutationFn: () => deleteProject(slug),
    onSuccess: () => {
      toast({ tone: "success", title: isHro ? t("searchDetail.deleted") : t("projectDetail.deleted") });
      qc.invalidateQueries({ queryKey: ["projects"] });
      router.push("/projects");
    },
    onError: (e: Error) => toast({ tone: "error", title: t("projectDetail.deleteFailed"), body: e.message }),
  });

  if (project.isLoading) {
    return (
      <div className="p-8 text-sm text-[--color-fg-muted]">
        {isHro ? t("searchDetail.loading") : t("projectDetail.loading")}
      </div>
    );
  }
  if (!project.data) {
    return (
      <div className="p-8 space-y-3">
        <Link href="/projects" className="text-xs text-[--color-fg-muted] inline-flex items-center gap-1.5">
          <ArrowLeft size={12} /> {isHro ? t("searches.title") : t("projects.title")}
        </Link>
        <p className="text-sm text-[--color-fg-muted]">
          {isHro ? t("searchDetail.notFound") : t("projectDetail.notFound")}
        </p>
      </div>
    );
  }

  const p = project.data;
  const Icon = projectIcon(p.icon);
  const isWorkspace = p.slug === "workspace";

  return (
    <div className="p-8 space-y-6 max-w-[1400px] mx-auto">
      <Link
        href="/projects"
        className="text-xs text-[--color-fg-muted] hover:text-[--color-fg] inline-flex items-center gap-1.5"
      >
        <ArrowLeft size={12} /> {isHro ? t("searches.title") : t("projects.title")}
      </Link>

      <header className="flex items-start gap-4">
        <div
          className="w-14 h-14 rounded-2xl grid place-items-center shrink-0"
          style={{
            background: `${p.color}22`,
            color: p.color,
            border: `1px solid ${p.color}55`,
          }}
        >
          <Icon size={26} />
        </div>
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight">{p.name}</h1>
          <p className="text-sm text-[--color-fg-muted] mt-1">{p.description || t("projectDetail.noDescription")}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <EditProjectDialog project={p} isHro={isHro} />
          {!isWorkspace && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                const msg = (isHro ? t("searchDetail.deleteConfirm") : t("projectDetail.deleteConfirm")).replace("{name}", p.name);
                if (confirm(msg)) {
                  remove.mutate();
                }
              }}
              disabled={remove.isPending || p.agent_count > 0}
              title={p.agent_count > 0 ? t("projectDetail.moveAgentsFirst") : (isHro ? t("searchDetail.deleteTitle") : t("projectDetail.deleteTitle"))}
            >
              <Trash2 size={13} />
            </Button>
          )}
        </div>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label={t("projectDetail.statAgents")} value={p.agent_count} />
        <Stat label={t("projects.runs24h")} value={p.runs_24h} />
        <Stat label={t("projects.cost24h")} value={`$${p.cost_24h.toFixed(3)}`} />
        <Stat label={t("projectDetail.statStatus")} value={p.status} />
      </div>

      {p.mission && (
        <Card className="space-y-2 border-l-4" style={{ borderLeftColor: p.color }}>
          <p className="text-[10px] uppercase tracking-widest text-[--color-fg-muted] font-medium">
            {isHro ? t("project.scope") : t("projectDetail.mission")}
          </p>
          <p className="text-[14px] leading-relaxed text-[--color-fg]">{p.mission}</p>
        </Card>
      )}

      {isHro && (
        <Card className="space-y-2 border-l-4" style={{ borderLeftColor: p.color }}>
          <p className="text-[10px] uppercase tracking-widest text-[--color-fg-muted] font-medium">
            {t("project.jobDescription")}
          </p>
          {p.job_description ? (
            <p className="text-[14px] leading-relaxed text-[--color-fg] whitespace-pre-wrap">
              {p.job_description}
            </p>
          ) : (
            <p className="text-[13px] text-[--color-fg-muted]">{t("project.noJobDescription")}</p>
          )}
        </Card>
      )}

      {isHro && <CvSourceCard project={p} />}

      <Tabs defaultValue="team">
        <TabsList>
          <TabsTrigger value="team">
            <Users size={12} />
            <span className="ml-1.5">{t("projectDetail.tabTeam")} ({p.agent_count})</span>
          </TabsTrigger>
          <TabsTrigger value="lessons">
            <Brain size={12} />
            <span className="ml-1.5">{t("projectDetail.tabLessons")} ({p.lessons.length})</span>
          </TabsTrigger>
          <TabsTrigger value="runs">
            <Activity size={12} />
            <span className="ml-1.5">{t("projectDetail.tabRuns")}</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="team" className="mt-5">
          <CardSection>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold tracking-tight">
                {isHro ? t("searchDetail.teamHeading") : t("projectDetail.teamHeading")}
              </h2>
              <div className="flex gap-2">
                <Link href={`/architect?project=${p.slug}`}>
                  <Button variant="outline" size="sm">
                    <Sparkles size={12} /> {t("projectDetail.addArchitect")}
                  </Button>
                </Link>
                <Link href={`/agents/new?project=${p.slug}`}>
                  <Button variant="ghost" size="sm">
                    <Plus size={12} /> {t("projectDetail.newAgent")}
                  </Button>
                </Link>
              </div>
            </div>
            {agents.data && agents.data.length === 0 ? (
              <Card className="text-center py-10 space-y-2">
                <p className="text-sm text-[--color-fg-muted]">
                  {isHro ? t("searchDetail.teamEmpty") : t("projectDetail.teamEmpty")}
                </p>
                <p className="text-xs text-[--color-fg-subtle] max-w-md mx-auto">
                  {isHro ? t("searchDetail.teamEmptyHint") : t("projectDetail.teamEmptyHint")}
                </p>
              </Card>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {(agents.data ?? []).map((a) => (
                  <Link
                    key={a.id}
                    href={`/agents/${a.id}`}
                    className="surface surface-hover p-4 flex items-center justify-between gap-3"
                  >
                    <div className="min-w-0">
                      <p className="font-medium truncate">{a.name}</p>
                      <p className="text-xs text-[--color-fg-muted] truncate mt-0.5">
                        {a.description || t("projectDetail.noDescription")}
                      </p>
                      <p className="text-[11px] font-mono text-[--color-fg-subtle] mt-1">
                        {a.model.replace("claude-", "")}
                      </p>
                    </div>
                    <StatusBadge status={a.status} />
                  </Link>
                ))}
              </div>
            )}
          </CardSection>
        </TabsContent>

        <TabsContent value="lessons" className="mt-5">
          <LessonsPane project={p} isHro={isHro} />
        </TabsContent>

        <TabsContent value="runs" className="mt-5">
          <CardSection>
            <h2 className="text-sm font-semibold tracking-tight mb-3">
              {t("projectDetail.runsHeading").replace("{n}", String((runs.data ?? []).length))}
            </h2>
            {runs.data && runs.data.length === 0 ? (
              <Card>
                <p className="text-sm text-[--color-fg-muted]">
                  {isHro ? t("searchDetail.runsEmpty") : t("projectDetail.runsEmpty")}
                </p>
              </Card>
            ) : (
              <div className="space-y-1.5">
                {(runs.data ?? []).map((r) => (
                  <Link
                    key={r.id}
                    href={`/runs/${r.id}`}
                    className="surface surface-hover px-4 py-3 flex items-center justify-between text-sm"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="text-xs font-mono text-[--color-fg-subtle]">#{r.id}</span>
                      <StatusBadge status={r.status} />
                      <span className="text-xs text-[--color-fg]">{r.agent_name}</span>
                      <span className="text-xs text-[--color-fg-muted] truncate hidden md:inline max-w-md">
                        {r.prompt}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-[--color-fg-muted] shrink-0 font-mono tabular-nums">
                      <span>{(r.input_tokens + r.output_tokens).toLocaleString()} tok</span>
                      <span>${r.cost_usd.toFixed(4)}</span>
                      <span>{new Date(r.started_at).toLocaleTimeString()}</span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </CardSection>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function CvSourceCard({ project }: { project: Project }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const folder = project.cv_folder ?? "";

  const connect = useMutation({
    mutationFn: async () => {
      // Selector NATIVO de Electron; fallback a prompt() en el navegador.
      const picked =
        (await window.rugol?.pickFolder?.()) ??
        window.prompt(t("cvSource.prompt")) ??
        null;
      const path = picked?.trim();
      if (!path) return null; // cancelado: no mutamos
      return updateProject(project.slug, { cv_folder: path });
    },
    onSuccess: (res) => {
      if (!res) return; // cancelado
      toast({ tone: "success", title: t("cvSource.connected") });
      qc.invalidateQueries({ queryKey: ["project", project.slug] });
    },
    onError: (e: Error) =>
      toast({ tone: "error", title: t("cvSource.connectError"), body: e.message }),
  });

  const analyze = useMutation({
    mutationFn: () => screenCvs(project.slug),
    onSuccess: () => toast({ tone: "success", title: t("cvSource.analyzeStarted") }),
    onError: (e: Error) =>
      toast({ tone: "error", title: t("cvSource.analyzeError"), body: e.message }),
  });

  return (
    <Card className="space-y-3 border-l-4" style={{ borderLeftColor: project.color }}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="text-[10px] uppercase tracking-widest text-[--color-fg-muted] font-medium inline-flex items-center gap-1.5">
            <FolderOpen size={12} /> {t("cvSource.title")}
          </p>
          {folder ? (
            <p
              className="text-[13px] text-[--color-fg] font-mono break-all"
              title={folder}
            >
              {folder}
            </p>
          ) : (
            <p className="text-[13px] text-[--color-fg-muted]">{t("cvSource.none")}</p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
          <Button
            variant="outline"
            size="sm"
            onClick={() => connect.mutate()}
            disabled={connect.isPending}
          >
            <FolderOpen size={13} />
            {folder ? t("cvSource.change") : t("cvSource.connect")}
          </Button>
          <ConnectSourceDialog project={project} onPickFolder={() => connect.mutate()} />
          <Button
            variant="primary"
            size="sm"
            onClick={() => analyze.mutate()}
            disabled={!folder || analyze.isPending}
            title={!folder ? t("cvSource.needFolder") : undefined}
          >
            <ScanSearch size={13} />
            {analyze.isPending ? t("cvSource.analyzing") : t("cvSource.analyze")}
          </Button>
        </div>
      </div>
      <p className="text-xs text-[--color-fg-muted] leading-relaxed">{t("cvSource.help")}</p>
    </Card>
  );
}

// Diálogo para conectar una fuente EXTERNA de CVs a la búsqueda.
//  - Drive/OneDrive → reutiliza el flujo de pickFolder (setea cv_folder), NO /connect.
//  - API/Pandapé y Web → dispara al agente conector vía POST /connect.
type SourceChoice = "drive" | "api" | "web";

function ConnectSourceDialog({
  project,
  onPickFolder,
}: {
  project: Project;
  onPickFolder: () => void;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [choice, setChoice] = useState<SourceChoice>("api");
  const [goal, setGoal] = useState("");
  const [credentials, setCredentials] = useState("");

  const connect = useMutation({
    mutationFn: () => {
      // Para API/Pandapé y Web sí llamamos al conector. Si el goal menciona
      // pandapé, mandamos kind="pandape"; si no, kind según el tipo elegido.
      const mentionsPandape = /pandap[ée]/i.test(goal);
      const kind: ConnectSourceKind =
        choice === "web" ? "web" : mentionsPandape ? "pandape" : "api";
      return connectSource(project.slug, {
        kind,
        goal: goal.trim(),
        credentials: credentials.trim() || undefined,
      });
    },
    onSuccess: () => {
      toast({ tone: "success", title: t("connect.started") });
      setOpen(false);
      setGoal("");
      setCredentials("");
    },
    onError: (e: Error) =>
      toast({ tone: "error", title: t("connect.error"), body: e.message }),
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!goal.trim()) return;
    connect.mutate();
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Plug size={13} />
          {t("connect.button")}
        </Button>
      </DialogTrigger>
      <DialogContent
        title={t("connect.dialogTitle")}
        description={t("connect.dialogDescription")}
      >
        <div className="space-y-4">
          <div className="space-y-1.5">
            <FieldLabel>{t("connect.typeLabel")}</FieldLabel>
            <Select
              value={choice}
              onChange={(e) => setChoice(e.target.value as SourceChoice)}
            >
              <option value="drive">{t("connect.type.drive")}</option>
              <option value="api">{t("connect.type.api")}</option>
              <option value="web">{t("connect.type.web")}</option>
            </Select>
          </div>

          {choice === "drive" ? (
            <div className="space-y-3">
              <p className="text-[13px] text-[--color-fg-muted] leading-relaxed">
                {t("connect.driveNote")}
              </p>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => {
                  setOpen(false);
                  onPickFolder();
                }}
              >
                <FolderOpen size={13} />
                {t("connect.drivePick")}
              </Button>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-4">
              <div className="space-y-1.5">
                <FieldLabel>{t("connect.goalLabel")}</FieldLabel>
                <Textarea
                  value={goal}
                  onChange={(e) => setGoal(e.target.value)}
                  rows={3}
                  placeholder={t("connect.goalPlaceholder")}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <FieldLabel hint={t("connect.credentialsHint")}>
                  {t("connect.credentialsLabel")}
                </FieldLabel>
                <Textarea
                  value={credentials}
                  onChange={(e) => setCredentials(e.target.value)}
                  rows={2}
                  placeholder={t("connect.credentialsPlaceholder")}
                  spellCheck={false}
                  autoComplete="off"
                  className="[-webkit-text-security:disc]"
                />
                <p className="text-xs text-[--color-fg-subtle] leading-relaxed">
                  {t("connect.credentialsSecurity")}
                </p>
              </div>
              <div className="flex items-center justify-end gap-2 pt-1">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setOpen(false)}
                >
                  {t("connect.cancel")}
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  disabled={connect.isPending || !goal.trim()}
                  title={!goal.trim() ? t("connect.needGoal") : undefined}
                >
                  <Plug size={13} />
                  {connect.isPending
                    ? t("connect.submitting")
                    : t("connect.submit")}
                </Button>
              </div>
            </form>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function LessonsPane({ project, isHro }: { project: Project; isHro: boolean }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [draft, setDraft] = useState("");
  const [kind, setKind] = useState<Lesson["kind"]>("lesson");

  const add = useMutation({
    mutationFn: (body: { text: string; kind: Lesson["kind"] }) =>
      addProjectLesson(project.slug, body),
    onSuccess: () => {
      setDraft("");
      qc.invalidateQueries({ queryKey: ["project", project.slug] });
      toast({ tone: "success", title: t("lessons.saved") });
    },
    onError: (e: Error) =>
      toast({ tone: "error", title: t("lessons.saveFailed"), body: e.message }),
  });

  const remove = useMutation({
    mutationFn: (index: number) => removeProjectLesson(project.slug, index),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["project", project.slug] }),
    onError: (e: Error) =>
      toast({ tone: "error", title: t("lessons.deleteFailed"), body: e.message }),
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.trim() || draft.trim().length < 4) return;
    add.mutate({ text: draft.trim(), kind });
  }

  return (
    <div className="space-y-5">
      <Card className="space-y-3">
        <header>
          <h2 className="text-sm font-semibold tracking-tight inline-flex items-center gap-2">
            <Brain size={13} className="text-[--color-accent-strong]" />
            {isHro ? t("lessons.headingSearch") : t("lessons.heading")}
          </h2>
          <p className="text-xs text-[--color-fg-muted] mt-1 max-w-2xl">
            {t("lessons.description")}
          </p>
        </header>
        <form onSubmit={submit} className="flex items-end gap-2">
          <div className="flex-1 space-y-1.5">
            <FieldLabel hint={t("lessons.newLessonHint")}>
              {t("lessons.newLesson")}
            </FieldLabel>
            <input
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={t("lessons.placeholder")}
              className="w-full px-3 py-2 bg-transparent border border-[--color-border] rounded-md text-sm focus:outline-none focus:border-[--color-accent] transition"
              maxLength={500}
            />
          </div>
          <div className="space-y-1.5">
            <FieldLabel>{t("lessons.type")}</FieldLabel>
            <select
              value={kind}
              onChange={(e) => setKind(e.target.value as Lesson["kind"])}
              className="px-3 py-2 bg-transparent border border-[--color-border] rounded-md text-sm focus:outline-none focus:border-[--color-accent]"
            >
              <option value="lesson">lesson</option>
              <option value="bias">bias</option>
              <option value="fact">fact</option>
            </select>
          </div>
          <Button type="submit" variant="primary" disabled={add.isPending || draft.trim().length < 4}>
            <Plus size={13} /> {t("lessons.add")}
          </Button>
        </form>
      </Card>

      {project.lessons.length === 0 ? (
        <Card className="text-center py-10 space-y-2">
          <p className="text-sm text-[--color-fg-muted]">
            {isHro ? t("lessons.emptySearch") : t("lessons.empty")}
          </p>
          <p className="text-xs text-[--color-fg-subtle] max-w-md mx-auto">
            {t("lessons.emptyHint")}
          </p>
        </Card>
      ) : (
        <ul className="space-y-2">
          {project.lessons.map((l, i) => (
            <li
              key={i}
              className="surface px-4 py-3 flex items-start justify-between gap-3 group"
            >
              <div className="flex items-start gap-3 min-w-0 flex-1">
                <span
                  className={`text-[10px] uppercase tracking-widest font-semibold px-1.5 py-0.5 rounded ${
                    l.kind === "bias"
                      ? "bg-[--color-error]/15 text-[--color-error]"
                      : l.kind === "fact"
                        ? "bg-[--color-accent-soft] text-[--color-accent-strong]"
                        : "bg-[--color-success]/15 text-[--color-success]"
                  }`}
                >
                  {l.kind}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-[--color-fg] leading-relaxed">{l.text}</p>
                  <p className="text-[10px] text-[--color-fg-subtle] mt-1 font-mono">
                    {l.source} · {new Date(l.added_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
              <button
                onClick={() => remove.mutate(i)}
                disabled={remove.isPending}
                title={t("lessons.delete")}
                className="opacity-50 hover:opacity-100 hover:text-[--color-error] transition shrink-0"
              >
                <X size={13} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}


function EditProjectDialog({
  project,
  isHro,
}: {
  project: ReturnType<typeof useQuery<any>>["data"] | any;
  isHro: boolean;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [body, setBody] = useState<ProjectUpdate>({
    name: project.name,
    description: project.description,
    mission: project.mission,
    job_description: project.job_description ?? "",
    color: project.color,
    icon: project.icon,
  });
  const update = useMutation({
    mutationFn: (b: ProjectUpdate) => updateProject(project.slug, b),
    onSuccess: () => {
      toast({ tone: "success", title: isHro ? t("searchDetail.updated") : t("projectDetail.updated") });
      qc.invalidateQueries({ queryKey: ["project", project.slug] });
      qc.invalidateQueries({ queryKey: ["projects"] });
      setOpen(false);
    },
    onError: (e: Error) =>
      toast({ tone: "error", title: t("projectDetail.updateFailed"), body: e.message }),
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    update.mutate(body);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="secondary" size="sm">
          <Pencil size={13} /> {t("projectDetail.edit")}
        </Button>
      </DialogTrigger>
      <DialogContent
        title={t("projectDetail.editTitle").replace("{name}", project.name)}
        description={t("projectDetail.editDescription")}
      >
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-1.5">
            <FieldLabel>{t("projectDetail.fieldName")}</FieldLabel>
            <Input
              value={body.name ?? ""}
              onChange={(e) => setBody({ ...body, name: e.target.value })}
              required
            />
          </div>
          <div className="space-y-1.5">
            <FieldLabel>{t("projectDetail.fieldShortDesc")}</FieldLabel>
            <Input
              value={body.description ?? ""}
              onChange={(e) => setBody({ ...body, description: e.target.value })}
            />
          </div>
          <div className="space-y-1.5">
            <FieldLabel>{isHro ? t("project.scope") : t("projectDetail.mission")}</FieldLabel>
            <Textarea
              value={body.mission ?? ""}
              onChange={(e) => setBody({ ...body, mission: e.target.value })}
              rows={4}
            />
          </div>
          {isHro && (
            <div className="space-y-1.5">
              <FieldLabel hint={t("project.jobDescriptionHint")}>
                {t("project.jobDescription")}
              </FieldLabel>
              <Textarea
                value={body.job_description ?? ""}
                onChange={(e) => setBody({ ...body, job_description: e.target.value })}
                rows={6}
                placeholder={t("project.jobDescriptionPlaceholder")}
              />
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <FieldLabel>{t("projectDetail.fieldIcon")}</FieldLabel>
              <Select
                value={body.icon ?? "briefcase"}
                onChange={(e) => setBody({ ...body, icon: e.target.value })}
              >
                {PROJECT_ICONS.map((i) => (
                  <option key={i} value={i}>{i}</option>
                ))}
              </Select>
            </div>
            <div className="space-y-1.5">
              <FieldLabel>{t("projectDetail.fieldColor")}</FieldLabel>
              <div className="flex flex-wrap gap-1.5">
                {PALETTE.map((c) => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setBody({ ...body, color: c })}
                    className={`w-7 h-7 rounded-md border-2 transition ${
                      body.color === c ? "border-[--color-fg]" : "border-transparent hover:border-[--color-border]"
                    }`}
                    style={{ background: c }}
                    aria-label={c}
                  />
                ))}
              </div>
            </div>
          </div>
          <div className="flex items-center justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" variant="primary" disabled={update.isPending}>
              {update.isPending ? t("projectDetail.saving") : t("common.save")}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
