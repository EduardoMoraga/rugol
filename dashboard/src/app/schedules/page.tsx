"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Plus, Trash2, Clock, Code2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createSchedule,
  deleteSchedule,
  fetchAgents,
  fetchSchedules,
  type Agent,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardSection, PageHeader } from "@/components/ui/card";
import { FieldLabel, Input, Select, Textarea } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/toast";

// ---------------------------------------------------------------------------
// Cron builder helpers — convert local-time + frequency to a 5-field cron in UTC.
//
// Why we convert: APScheduler runs cron expressions in UTC. A Chilean user
// who wants "all days at 6 AM" needs `0 9 * * *` (UTC-3 standard) — but
// nobody should have to do that math by hand. Browsers expose
// Intl.DateTimeFormat().resolvedOptions().timeZone, which is enough for us
// to compute the offset reliably for whole-hour offsets.
// ---------------------------------------------------------------------------

type FreqMode = "daily" | "weekdays" | "weekend" | "weekly" | "interval" | "advanced";

const WEEKDAY_LABELS = [
  { value: 1, es: "Lunes", en: "Mon" },
  { value: 2, es: "Martes", en: "Tue" },
  { value: 3, es: "Miércoles", en: "Wed" },
  { value: 4, es: "Jueves", en: "Thu" },
  { value: 5, es: "Viernes", en: "Fri" },
  { value: 6, es: "Sábado", en: "Sat" },
  { value: 0, es: "Domingo", en: "Sun" },
];

function detectTz(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

/**
 * Returns the offset in MINUTES between UTC and the given IANA timezone at
 * the current instant. Positive when tz is behind UTC (e.g. America/Santiago
 * = +180 in standard time). The trick: render now() once with the tz and
 * once with UTC, parse both back, take the difference.
 */
function tzOffsetMinutes(tz: string): number {
  const now = new Date();
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone: tz,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
  const parts = formatter.formatToParts(now);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "0";
  const localMs = Date.UTC(
    Number(get("year")),
    Number(get("month")) - 1,
    Number(get("day")),
    Number(get("hour")) === 24 ? 0 : Number(get("hour")),
    Number(get("minute")),
    Number(get("second")),
  );
  return Math.round((now.getTime() - localMs) / 60000);
}

function localToUtcHourMinute(
  localHour: number,
  localMinute: number,
  tz: string,
): { hour: number; minute: number } {
  const offsetMin = tzOffsetMinutes(tz);
  const totalMin = localHour * 60 + localMinute + offsetMin;
  const wrapped = ((totalMin % 1440) + 1440) % 1440;
  return { hour: Math.floor(wrapped / 60), minute: wrapped % 60 };
}

function utcHourMinuteToLocal(
  utcHour: number,
  utcMinute: number,
  tz: string,
): { hour: number; minute: number } {
  const offsetMin = tzOffsetMinutes(tz);
  const totalMin = utcHour * 60 + utcMinute - offsetMin;
  const wrapped = ((totalMin % 1440) + 1440) % 1440;
  return { hour: Math.floor(wrapped / 60), minute: wrapped % 60 };
}

function pad2(n: number): string {
  return n.toString().padStart(2, "0");
}

function buildCron(
  mode: FreqMode,
  hhmm: string,
  weekday: number,
  intervalMin: number,
  _tz: string,
): string {
  if (mode === "interval") {
    const m = Math.max(1, Math.min(59, intervalMin));
    return `*/${m} * * * *`;
  }
  // v0.7.1: the backend scheduler is configured in America/Santiago by
  // default (settings.SCHEDULER_TIMEZONE). The cron expression is now
  // interpreted in THAT zone, so we no longer convert to UTC here —
  // we pass the user's chosen wall-clock hour straight through. If the
  // user runs the backend in a non-Chile timezone they should set
  // SCHEDULER_TIMEZONE in their .env accordingly.
  const [hStr, mStr] = (hhmm || "09:00").split(":");
  const t = `${Number(mStr)} ${Number(hStr)}`;
  if (mode === "daily") return `${t} * * *`;
  if (mode === "weekdays") return `${t} * * 1-5`;
  if (mode === "weekend") return `${t} * * 0,6`;
  if (mode === "weekly") return `${t} * * ${weekday}`;
  return "";
}

/**
 * Try to interpret a cron expression as a friendly local-time description.
 * Returns null when the expression doesn't match any of our supported shapes.
 */
function describeCronInLocal(cronExpr: string, _tz: string): string | null {
  const parts = cronExpr.trim().split(/\s+/);
  if (parts.length !== 5) return null;
  const [m, h, dom, mon, dow] = parts;
  // Interval (every N minutes): "*/N * * * *"
  if (m.startsWith("*/") && h === "*" && dom === "*" && mon === "*" && dow === "*") {
    return `cada ${m.slice(2)} min`;
  }
  // Hourly at minute M: "M * * * *"
  if (/^\d+$/.test(m) && h === "*" && dom === "*" && mon === "*" && dow === "*") {
    return `cada hora al minuto ${m}`;
  }
  // Daily / weekly / etc — needs concrete h, m
  if (!/^\d+$/.test(m) || !/^\d+$/.test(h)) return null;
  if (dom !== "*" || mon !== "*") return null;
  // v0.7.1: cron is interpreted in the backend's SCHEDULER_TIMEZONE
  // (default America/Santiago), not in the browser's tz. We display the
  // hour exactly as stored — the backend zone takes care of firing it.
  const tStr = `${pad2(Number(h))}:${pad2(Number(m))}`;
  const tzNote = " hora del servidor";
  if (dow === "*") return `todos los días a las ${tStr}${tzNote}`;
  if (dow === "1-5") return `lunes a viernes a las ${tStr}${tzNote}`;
  if (dow === "0,6" || dow === "6,0") return `sábado y domingo a las ${tStr}${tzNote}`;
  if (/^\d$/.test(dow)) {
    const wd = WEEKDAY_LABELS.find((w) => w.value === Number(dow));
    if (wd) return `cada ${wd.es.toLowerCase()} a las ${tStr}${tzNote}`;
  }
  return null;
}

const FREQ_OPTIONS: { id: FreqMode; label: string; needsTime: boolean; needsWeekday?: boolean; needsInterval?: boolean }[] = [
  { id: "daily", label: "Todos los días", needsTime: true },
  { id: "weekdays", label: "Lunes a viernes", needsTime: true },
  { id: "weekend", label: "Sábado y domingo", needsTime: true },
  { id: "weekly", label: "Un día por semana", needsTime: true, needsWeekday: true },
  { id: "interval", label: "Cada N minutos", needsTime: false, needsInterval: true },
  { id: "advanced", label: "Cron avanzado (escribir a mano)", needsTime: false },
];

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function SchedulesPage() {
  const qc = useQueryClient();
  const schedules = useQuery({ queryKey: ["schedules"], queryFn: fetchSchedules, refetchInterval: 5000 });
  const agents = useQuery({ queryKey: ["agents"], queryFn: () => fetchAgents() });

  const agentById = useMemo(() => {
    const m = new Map<number, Agent>();
    (agents.data ?? []).forEach((a) => m.set(a.id, a));
    return m;
  }, [agents.data]);

  const create = useMutation({
    mutationFn: ({ agent_id, cron_expr, prompt, enabled }: any) =>
      createSchedule(agent_id, cron_expr, prompt, enabled),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["schedules"] });
      toast({ tone: "success", title: "Schedule creado" });
    },
    onError: (e: Error) => toast({ tone: "error", title: "No se pudo crear", body: e.message }),
  });

  const remove = useMutation({
    mutationFn: deleteSchedule,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["schedules"] });
      toast({ tone: "info", title: "Schedule borrado" });
    },
  });

  const tz = useMemo(detectTz, []);
  const [agentId, setAgentId] = useState<string>("");
  const [freq, setFreq] = useState<FreqMode>("daily");
  const [time, setTime] = useState("09:00");
  const [weekday, setWeekday] = useState<number>(1);
  const [intervalMin, setIntervalMin] = useState<number>(60);
  const [cronExpr, setCronExpr] = useState("0 12 * * *");
  const [prompt, setPrompt] = useState("");
  const [enabled, setEnabled] = useState(true);

  // Auto-update cronExpr from the visual builder when not in advanced mode.
  useEffect(() => {
    if (freq === "advanced") return;
    const next = buildCron(freq, time, weekday, intervalMin, tz);
    if (next) setCronExpr(next);
  }, [freq, time, weekday, intervalMin, tz]);

  const cronDescription = useMemo(
    () => describeCronInLocal(cronExpr, tz),
    [cronExpr, tz],
  );

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!agentId || !cronExpr.trim() || !prompt.trim()) return;
    create.mutate(
      { agent_id: Number(agentId), cron_expr: cronExpr.trim(), prompt: prompt.trim(), enabled },
      { onSuccess: () => setPrompt("") },
    );
  }

  const currentFreq = FREQ_OPTIONS.find((f) => f.id === freq)!;

  return (
    <div className="p-8 space-y-6 max-w-4xl mx-auto">
      <PageHeader
        title="Programación de tareas"
        description="Tareas que disparan agentes automáticamente. Persisten entre reinicios. Tu zona horaria detectada es: "
        actions={
          <Badge tone="accent">
            <Clock size={11} /> {tz}
          </Badge>
        }
      />

      <Card>
        <h2 className="text-sm font-semibold tracking-tight inline-flex items-center gap-2 mb-4">
          <Plus size={14} className="text-[--color-accent-strong]" />
          Nueva tarea programada
        </h2>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <FieldLabel>Agente</FieldLabel>
            <Select required value={agentId} onChange={(e) => setAgentId(e.target.value)}>
              <option value="">— elige un agente —</option>
              {(agents.data ?? []).map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </Select>
          </div>

          <div className="space-y-1.5">
            <FieldLabel>Frecuencia</FieldLabel>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-1.5">
              {FREQ_OPTIONS.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => setFreq(opt.id)}
                  className={`text-left px-3 py-2 rounded-md border text-[12.5px] transition ${
                    freq === opt.id
                      ? "border-[--color-accent] bg-[--color-accent-soft] text-[--color-accent-strong]"
                      : "border-[--color-border] text-[--color-fg-muted] hover:text-[--color-fg] hover:border-[--color-fg-muted]"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {currentFreq.needsTime && (
              <div className="space-y-1.5">
                <FieldLabel hint={`hora local en ${tz}`}>Hora</FieldLabel>
                <Input
                  type="time"
                  value={time}
                  onChange={(e) => setTime(e.target.value)}
                  className="font-mono"
                />
              </div>
            )}
            {currentFreq.needsWeekday && (
              <div className="space-y-1.5">
                <FieldLabel>Día de la semana</FieldLabel>
                <Select
                  value={String(weekday)}
                  onChange={(e) => setWeekday(Number(e.target.value))}
                >
                  {WEEKDAY_LABELS.map((w) => (
                    <option key={w.value} value={w.value}>
                      {w.es}
                    </option>
                  ))}
                </Select>
              </div>
            )}
            {currentFreq.needsInterval && (
              <div className="space-y-1.5">
                <FieldLabel hint="entre 1 y 59 minutos">Cada N minutos</FieldLabel>
                <Input
                  type="number"
                  min={1}
                  max={59}
                  value={intervalMin}
                  onChange={(e) => setIntervalMin(Number(e.target.value || 1))}
                />
              </div>
            )}
          </div>

          <div className="space-y-1.5">
            <FieldLabel hint="cron en UTC, 5 campos">
              Cron resultante
              {freq !== "advanced" && (
                <span className="ml-2 text-[10px] uppercase tracking-widest text-[--color-fg-muted]">
                  (auto-generado)
                </span>
              )}
            </FieldLabel>
            <Input
              required
              value={cronExpr}
              onChange={(e) => setCronExpr(e.target.value)}
              placeholder="0 12 * * *"
              className="font-mono"
              readOnly={freq !== "advanced"}
            />
            {cronDescription && (
              <p className="text-[11px] text-emerald-400 flex items-center gap-1.5">
                <Clock size={10} /> {cronDescription}
              </p>
            )}
            {!cronDescription && cronExpr && (
              <p className="text-[11px] text-[--color-fg-subtle] flex items-center gap-1.5">
                <Code2 size={10} /> expresión cron custom (no la pude traducir a tu zona horaria automáticamente)
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <FieldLabel>Qué tiene que hacer el agente cada vez que se dispare</FieldLabel>
            <Textarea
              required
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={3}
              placeholder="Ej: trae los 5 videos más recientes de IA del canal X y mándamelos por Telegram"
            />
          </div>

          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2 text-xs text-[--color-fg-muted] cursor-pointer">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                className="accent-[--color-accent]"
              />
              Activar inmediatamente
            </label>
            <Button
              type="submit"
              variant="primary"
              disabled={create.isPending || !agentId || !cronExpr.trim() || !prompt.trim()}
            >
              {create.isPending ? "Creando…" : "Crear tarea"}
            </Button>
          </div>
        </form>
      </Card>

      <CardSection>
        <div className="flex items-baseline justify-between">
          <h2 className="text-sm font-semibold tracking-tight">Activas</h2>
          <span className="text-xs text-[--color-fg-muted]">
            {schedules.data?.length ?? 0} tarea{schedules.data?.length === 1 ? "" : "s"}
          </span>
        </div>

        {schedules.isLoading && <p className="text-sm text-[--color-fg-muted]">Cargando…</p>}

        {schedules.data && schedules.data.length === 0 && (
          <Card>
            <p className="text-sm text-[--color-fg-muted]">No hay tareas todavía — creá una arriba.</p>
          </Card>
        )}

        {schedules.data && schedules.data.length > 0 && (
          <div className="space-y-2">
            {schedules.data.map((s) => {
              const agent = agentById.get(s.agent_id);
              const desc = describeCronInLocal(s.cron_expr, tz);
              return (
                <div key={s.id} className="surface p-4 space-y-2">
                  <header className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3 min-w-0 flex-wrap">
                      <span className="font-mono text-xs text-[--color-fg-subtle]">#{s.id}</span>
                      {agent ? (
                        <Link
                          href={`/agents/${agent.id}`}
                          className="font-semibold truncate hover:text-[--color-accent-strong] transition-colors"
                        >
                          {agent.name}
                        </Link>
                      ) : (
                        <Badge tone="warn">agent {s.agent_id}</Badge>
                      )}
                      <code className="text-xs px-2 py-0.5 rounded bg-[--color-bg] border border-[--color-border] font-mono">
                        {s.cron_expr}
                      </code>
                      {desc && (
                        <span className="text-[11px] text-emerald-400">= {desc}</span>
                      )}
                      {!s.enabled && <Badge tone="warn">pausada</Badge>}
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        if (confirm(`¿Borrar la tarea #${s.id}?`)) remove.mutate(s.id);
                      }}
                    >
                      <Trash2 size={12} /> Borrar
                    </Button>
                  </header>
                  <p className="text-[12.5px] text-[--color-fg-muted] leading-relaxed">
                    {s.prompt}
                  </p>
                  <p className="text-[10.5px] text-[--color-fg-subtle]">
                    {s.next_run_at ? `Próxima corrida: ${new Date(s.next_run_at).toLocaleString()}` : "next run pending"}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </CardSection>
    </div>
  );
}
