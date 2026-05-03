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
} from "lucide-react";
import {
  deleteProject,
  fetchProject,
  fetchProjectAgents,
  fetchProjectRuns,
  updateProject,
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
                  Usá Architect para diseñar el equipo a partir de una idea, o creá uno
                  manualmente y elegí este proyecto.
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
