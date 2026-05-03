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
} from "lucide-react";
import {
  addProjectLesson,
  deleteProject,
  fetchProject,
  fetchProjectAgents,
  fetchProjectRuns,
  removeProjectLesson,
  updateProject,
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

const PALETTE = [
  "#7280a8", "#5b8def", "#7c5cff", "#c44d8c",
  "#e26f3f", "#f5b942", "#3aaf85", "#2c9aaf",
];

export default function ProjectDetail() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;
  const router = useRouter();
  const qc = useQueryClient();

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
      toast({ tone: "success", title: "Proyecto eliminado" });
      qc.invalidateQueries({ queryKey: ["projects"] });
      router.push("/projects");
    },
    onError: (e: Error) => toast({ tone: "error", title: "No se pudo eliminar", body: e.message }),
  });

  if (project.isLoading) {
    return <div className="p-8 text-sm text-[--color-fg-muted]">Cargando proyecto…</div>;
  }
  if (!project.data) {
    return (
      <div className="p-8 space-y-3">
        <Link href="/projects" className="text-xs text-[--color-fg-muted] inline-flex items-center gap-1.5">
          <ArrowLeft size={12} /> Proyectos
        </Link>
        <p className="text-sm text-[--color-fg-muted]">Proyecto no encontrado.</p>
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
        <ArrowLeft size={12} /> Proyectos
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
          <p className="text-sm text-[--color-fg-muted] mt-1">{p.description || "(sin descripción)"}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <EditProjectDialog project={p} />
          {!isWorkspace && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                if (confirm(`Eliminar el proyecto "${p.name}"? Solo es posible si no tiene agentes.`)) {
                  remove.mutate();
                }
              }}
              disabled={remove.isPending || p.agent_count > 0}
              title={p.agent_count > 0 ? "Movéte los agentes primero" : "Eliminar proyecto"}
            >
              <Trash2 size={13} />
            </Button>
          )}
        </div>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Agentes" value={p.agent_count} />
        <Stat label="Runs · 24h" value={p.runs_24h} />
        <Stat label="Costo · 24h" value={`$${p.cost_24h.toFixed(3)}`} />
        <Stat label="Estado" value={p.status} />
      </div>

      {p.mission && (
        <Card className="space-y-2 border-l-4" style={{ borderLeftColor: p.color }}>
          <p className="text-[10px] uppercase tracking-widest text-[--color-fg-muted] font-medium">
            Misión
          </p>
          <p className="text-[14px] leading-relaxed text-[--color-fg]">{p.mission}</p>
        </Card>
      )}

      <Tabs defaultValue="team">
        <TabsList>
          <TabsTrigger value="team">
            <Users size={12} />
            <span className="ml-1.5">Equipo ({p.agent_count})</span>
          </TabsTrigger>
          <TabsTrigger value="lessons">
            <Brain size={12} />
            <span className="ml-1.5">Lecciones ({p.lessons.length})</span>
          </TabsTrigger>
          <TabsTrigger value="runs">
            <Activity size={12} />
            <span className="ml-1.5">Runs recientes</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="team" className="mt-5">
          <CardSection>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold tracking-tight">Plantilla del proyecto</h2>
              <div className="flex gap-2">
                <Link href={`/architect?project=${p.slug}`}>
                  <Button variant="outline" size="sm">
                    <Sparkles size={12} /> Sumar con Architect
                  </Button>
                </Link>
                <Link href={`/agents/new?project=${p.slug}`}>
                  <Button variant="ghost" size="sm">
                    <Plus size={12} /> Nuevo agente
                  </Button>
                </Link>
              </div>
            </div>
            {agents.data && agents.data.length === 0 ? (
              <Card className="text-center py-10 space-y-2">
                <p className="text-sm text-[--color-fg-muted]">
                  Este proyecto todavía no tiene agentes asignados.
                </p>
                <p className="text-xs text-[--color-fg-subtle] max-w-md mx-auto">
                  Usa Architect para diseñar el equipo a partir de una idea, o crea uno
                  manualmente y elige este proyecto.
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
                        {a.description || "(sin descripción)"}
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
          <LessonsPane project={p} />
        </TabsContent>

        <TabsContent value="runs" className="mt-5">
          <CardSection>
            <h2 className="text-sm font-semibold tracking-tight mb-3">Últimos {(runs.data ?? []).length} runs</h2>
            {runs.data && runs.data.length === 0 ? (
              <Card>
                <p className="text-sm text-[--color-fg-muted]">
                  Todavía no hay runs en este proyecto.
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

function LessonsPane({ project }: { project: Project }) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState("");
  const [kind, setKind] = useState<Lesson["kind"]>("lesson");

  const add = useMutation({
    mutationFn: (body: { text: string; kind: Lesson["kind"] }) =>
      addProjectLesson(project.slug, body),
    onSuccess: () => {
      setDraft("");
      qc.invalidateQueries({ queryKey: ["project", project.slug] });
      toast({ tone: "success", title: "Lección guardada" });
    },
    onError: (e: Error) =>
      toast({ tone: "error", title: "No se pudo guardar", body: e.message }),
  });

  const remove = useMutation({
    mutationFn: (index: number) => removeProjectLesson(project.slug, index),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["project", project.slug] }),
    onError: (e: Error) =>
      toast({ tone: "error", title: "No se pudo borrar", body: e.message }),
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
            Lecciones vivas del proyecto
          </h2>
          <p className="text-xs text-[--color-fg-muted] mt-1 max-w-2xl">
            Cada agente del equipo lee esta lista <strong>antes</strong> de cada
            run. Funciona como anclaje: lo que el equipo aprendió de la mala,
            las decisiones tomadas, los sesgos detectados. Pensalo como las
            "reglas de la casa" — no más de 10-15 ítems o pierde foco.
          </p>
        </header>
        <form onSubmit={submit} className="flex items-end gap-2">
          <div className="flex-1 space-y-1.5">
            <FieldLabel hint="qué tipo de aprendizaje es">
              Nueva lección
            </FieldLabel>
            <input
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder='ej: "El cliente Acme prefiere correos cortos sin asunto en mayúsculas"'
              className="w-full px-3 py-2 bg-transparent border border-[--color-border] rounded-md text-sm focus:outline-none focus:border-[--color-accent] transition"
              maxLength={500}
            />
          </div>
          <div className="space-y-1.5">
            <FieldLabel>Tipo</FieldLabel>
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
            <Plus size={13} /> Agregar
          </Button>
        </form>
      </Card>

      {project.lessons.length === 0 ? (
        <Card className="text-center py-10 space-y-2">
          <p className="text-sm text-[--color-fg-muted]">
            Todavía no hay lecciones registradas para este proyecto.
          </p>
          <p className="text-xs text-[--color-fg-subtle] max-w-md mx-auto">
            Empezá con 2-3 reglas que el equipo nunca debería romper. Las
            siguientes van a aparecer cuando aprueves propuestas de mejora
            (Improvements) y las promueves a lección.
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
                title="Borrar"
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


function EditProjectDialog({ project }: { project: ReturnType<typeof useQuery<any>>["data"] | any }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [body, setBody] = useState<ProjectUpdate>({
    name: project.name,
    description: project.description,
    mission: project.mission,
    color: project.color,
    icon: project.icon,
  });
  const update = useMutation({
    mutationFn: (b: ProjectUpdate) => updateProject(project.slug, b),
    onSuccess: () => {
      toast({ tone: "success", title: "Proyecto actualizado" });
      qc.invalidateQueries({ queryKey: ["project", project.slug] });
      qc.invalidateQueries({ queryKey: ["projects"] });
      setOpen(false);
    },
    onError: (e: Error) =>
      toast({ tone: "error", title: "No se pudo actualizar", body: e.message }),
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    update.mutate(body);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="secondary" size="sm">
          <Pencil size={13} /> Editar
        </Button>
      </DialogTrigger>
      <DialogContent
        title={`Editar ${project.name}`}
        description="Cambios se guardan en la DB. El slug es inmutable."
      >
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-1.5">
            <FieldLabel>Nombre</FieldLabel>
            <Input
              value={body.name ?? ""}
              onChange={(e) => setBody({ ...body, name: e.target.value })}
              required
            />
          </div>
          <div className="space-y-1.5">
            <FieldLabel>Descripción corta</FieldLabel>
            <Input
              value={body.description ?? ""}
              onChange={(e) => setBody({ ...body, description: e.target.value })}
            />
          </div>
          <div className="space-y-1.5">
            <FieldLabel>Misión</FieldLabel>
            <Textarea
              value={body.mission ?? ""}
              onChange={(e) => setBody({ ...body, mission: e.target.value })}
              rows={4}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <FieldLabel>Ícono</FieldLabel>
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
              <FieldLabel>Color</FieldLabel>
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
              Cancelar
            </Button>
            <Button type="submit" variant="primary" disabled={update.isPending}>
              {update.isPending ? "Guardando…" : "Guardar"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
