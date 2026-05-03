"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Sparkles,
  Users,
  Activity,
  DollarSign,
  Briefcase,
} from "lucide-react";
import {
  createProject,
  fetchProjects,
  type ProjectCreate,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, PageHeader, Stat } from "@/components/ui/card";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { FieldLabel, Input, Select, Textarea } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";
import { PROJECT_ICONS, projectIcon } from "@/components/projects/project-badge";
import { TemplateCatalog } from "@/components/projects/template-catalog";

const PALETTE = [
  "#7280a8", "#5b8def", "#7c5cff", "#c44d8c",
  "#e26f3f", "#f5b942", "#3aaf85", "#2c9aaf",
];

export default function ProjectsHome() {
  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: () => fetchProjects(false),
    refetchInterval: 8000,
  });

  const totalProjects = projects.data?.length ?? 0;
  const totalAgents = (projects.data ?? []).reduce((s, p) => s + p.agent_count, 0);
  const totalRuns24h = (projects.data ?? []).reduce((s, p) => s + p.runs_24h, 0);
  const totalCost24h = (projects.data ?? []).reduce((s, p) => s + p.cost_24h, 0);

  return (
    <div className="p-8 space-y-8 max-w-[1400px] mx-auto">
      <PageHeader
        title="Proyectos"
        description="Cada proyecto es un departamento con misión propia y un equipo de agentes que trabaja en él. Vos sos el CEO; ellos ejecutan."
        actions={
          <div className="flex items-center gap-2">
            <Link href="/architect">
              <Button variant="primary">
                <Sparkles size={14} /> Diseñar con Architect
              </Button>
            </Link>
            <NewProjectDialog />
          </div>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Proyectos activos" value={totalProjects} />
        <Stat label="Agentes en plantilla" value={totalAgents} />
        <Stat label="Runs · 24h" value={totalRuns24h} />
        <Stat label="Costo · 24h" value={`$${totalCost24h.toFixed(3)}`} />
      </div>

      {projects.isLoading && (
        <p className="text-sm text-[--color-fg-muted]">Cargando proyectos…</p>
      )}

      <TemplateCatalog />

      {projects.data && projects.data.length === 0 && <EmptyState />}

      {projects.data && projects.data.length > 0 && (
        <h2 className="text-sm font-semibold tracking-tight pt-2">
          Tus proyectos
        </h2>
      )}

      {projects.data && projects.data.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.data.map((p) => {
            const Icon = projectIcon(p.icon);
            return (
              <Link
                key={p.id}
                href={`/projects/${p.slug}`}
                className="group surface surface-hover p-5 flex flex-col gap-4 transition relative overflow-hidden"
              >
                <div
                  className="absolute -top-12 -right-12 w-40 h-40 rounded-full opacity-20 blur-2xl"
                  style={{ background: p.color }}
                />
                <header className="flex items-start gap-3 relative">
                  <div
                    className="w-10 h-10 rounded-xl grid place-items-center shrink-0"
                    style={{
                      background: `${p.color}22`,
                      color: p.color,
                      border: `1px solid ${p.color}44`,
                    }}
                  >
                    <Icon size={18} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="text-base font-semibold tracking-tight truncate">
                      {p.name}
                    </h3>
                    <p className="text-xs text-[--color-fg-muted] truncate">
                      {p.description || "(sin descripción)"}
                    </p>
                  </div>
                </header>

                {p.mission && (
                  <p className="text-[12.5px] text-[--color-fg-muted] line-clamp-3 leading-relaxed">
                    {p.mission}
                  </p>
                )}

                <footer className="flex items-center justify-between text-[11px] text-[--color-fg-muted] font-mono pt-2 border-t border-[--color-border]/60">
                  <span className="inline-flex items-center gap-1.5">
                    <Users size={11} /> {p.agent_count}
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <Activity size={11} /> {p.runs_24h} · 24h
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <DollarSign size={11} /> {p.cost_24h.toFixed(3)}
                  </span>
                </footer>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <Card className="text-center py-16 space-y-4">
      <Briefcase size={36} className="mx-auto text-[--color-fg-subtle]" />
      <div>
        <h2 className="text-lg font-semibold tracking-tight">
          Todavía no tenés proyectos
        </h2>
        <p className="text-sm text-[--color-fg-muted] mt-1 max-w-md mx-auto">
          Empezá describiendo una idea — Architect propone el equipo, las skills
          y los rituales — o creá un proyecto manualmente.
        </p>
      </div>
      <div className="flex items-center justify-center gap-2 pt-2">
        <Link href="/architect">
          <Button variant="primary">
            <Sparkles size={14} /> Diseñar con Architect
          </Button>
        </Link>
        <NewProjectDialog />
      </div>
    </Card>
  );
}

function NewProjectDialog() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [body, setBody] = useState<ProjectCreate>({
    name: "",
    description: "",
    mission: "",
    color: PALETTE[0],
    icon: "briefcase",
  });
  const create = useMutation({
    mutationFn: (b: ProjectCreate) => createProject(b),
    onSuccess: (p) => {
      toast({ tone: "success", title: `Proyecto creado: ${p.name}` });
      qc.invalidateQueries({ queryKey: ["projects"] });
      setOpen(false);
      setBody({
        name: "",
        description: "",
        mission: "",
        color: PALETTE[0],
        icon: "briefcase",
      });
    },
    onError: (e: Error) =>
      toast({ tone: "error", title: "No se pudo crear el proyecto", body: e.message }),
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!body.name.trim()) return;
    create.mutate(body);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="secondary">
          <Plus size={14} /> Nuevo proyecto
        </Button>
      </DialogTrigger>
      <DialogContent
        title="Nuevo proyecto"
        description="Definí una misión clara — los agentes la van a leer antes de cada run para mantenerse anclados."
      >
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-1.5">
            <FieldLabel>Nombre</FieldLabel>
            <Input
              value={body.name}
              onChange={(e) => setBody({ ...body, name: e.target.value })}
              placeholder="Marca personal"
              required
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <FieldLabel hint="una sola línea para la tarjeta">
              Descripción corta
            </FieldLabel>
            <Input
              value={body.description}
              onChange={(e) => setBody({ ...body, description: e.target.value })}
              placeholder="Equipo que cuida mi voz pública en LinkedIn y X."
            />
          </div>
          <div className="space-y-1.5">
            <FieldLabel hint="el porqué que el equipo lee antes de cada tarea">
              Misión
            </FieldLabel>
            <Textarea
              value={body.mission}
              onChange={(e) => setBody({ ...body, mission: e.target.value })}
              rows={4}
              placeholder="Construir credibilidad técnica honesta. Publicar 3 piezas por semana centradas en lo que aprendí en producción. Nunca hype."
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <FieldLabel>Ícono</FieldLabel>
              <Select
                value={body.icon}
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
                      body.color === c
                        ? "border-[--color-fg]"
                        : "border-transparent hover:border-[--color-border]"
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
            <Button type="submit" variant="primary" disabled={create.isPending || !body.name.trim()}>
              {create.isPending ? "Creando…" : "Crear proyecto"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
