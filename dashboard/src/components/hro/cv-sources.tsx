"use client";

/**
 * CvSourcesManager — gestiona las fuentes de CV de HRO (Pandapé, Chiletrabajo,
 * Computrabajo, LinkedIn, Drive, carpeta…). Reusable en el onboarding y en
 * Ajustes. La reclutadora elige un tipo, pega el token si hace falta, y listo;
 * el agente `connector` usa esta lista para traer candidatos al pipeline.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Database, KeyRound, Cloud, Link2 } from "lucide-react";
import {
  fetchCvSources,
  addCvSource,
  deleteCvSource,
  type CvSourceType,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FieldLabel, Input, Select } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";
import { useI18n } from "@/lib/i18n";

// Estado de una fuente → tono del badge.
const STATUS_TONE: Record<string, "running" | "accent" | "warn" | "idle"> = {
  conectada: "running",
  detectada: "accent",
  falta_ruta: "warn",
  falta_credencial: "warn",
  pendiente: "idle",
  configurada: "idle",
};

export function CvSourcesManager({ compact = false }: { compact?: boolean }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["cv-sources"], queryFn: fetchCvSources, retry: false });

  const types: CvSourceType[] = q.data?.types ?? [];
  const sources = q.data?.sources ?? [];

  const [type, setType] = useState("");
  const [name, setName] = useState("");
  const [credentials, setCredentials] = useState("");

  const selectedType = types.find((x) => x.id === type);
  const needsCreds = selectedType?.needs_credentials ?? false;

  const add = useMutation({
    mutationFn: () => addCvSource({ type, name: name.trim() || undefined, credentials: credentials.trim() || undefined }),
    onSuccess: (res) => {
      qc.setQueryData(["cv-sources"], res);
      setType("");
      setName("");
      setCredentials("");
      toast({ tone: "success", title: t("cvSources.added") });
    },
    onError: (e: Error) => toast({ tone: "error", title: t("cvSources.addError"), body: e.message }),
  });

  const remove = useMutation({
    mutationFn: (id: string) => deleteCvSource(id),
    onSuccess: (res) => {
      qc.setQueryData(["cv-sources"], res);
      toast({ tone: "success", title: t("cvSources.removed") });
    },
    onError: (e: Error) => toast({ tone: "error", title: t("cvSources.removeError"), body: e.message }),
  });

  // Conectar en un clic una carpeta de nube detectada en el equipo.
  const connectDetected = useMutation({
    mutationFn: (d: { name: string; path: string }) =>
      addCvSource({ type: "drive", name: d.name, path: d.path }),
    onSuccess: (res) => {
      qc.setQueryData(["cv-sources"], res);
      toast({ tone: "success", title: t("cvSources.added") });
    },
    onError: (e: Error) => toast({ tone: "error", title: t("cvSources.addError"), body: e.message }),
  });

  const detected = q.data?.detected ?? [];

  return (
    <div className="space-y-4">
      {/* Lista de fuentes */}
      {sources.length === 0 ? (
        <p className="text-[13px] text-[--color-fg-muted]">{t("cvSources.empty")}</p>
      ) : (
        <ul className="space-y-2">
          {sources.map((s) => {
            const label = types.find((x) => x.id === s.type)?.label ?? s.type;
            return (
              <li
                key={s.id}
                className="surface px-3 py-2.5 flex items-center justify-between gap-3"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className="w-7 h-7 rounded-lg grid place-items-center shrink-0 bg-[--color-accent-soft] text-[--color-accent-strong]">
                    <Database size={14} />
                  </span>
                  <div className="min-w-0">
                    <p className="text-[13px] font-medium truncate">{s.name}</p>
                    <p className="text-[11px] text-[--color-fg-subtle] truncate">
                      {label}
                      {s.path && <span className="ml-1.5 font-mono">{s.path}</span>}
                      {s.credentials_set && (
                        <span className="ml-1.5 inline-flex items-center gap-0.5">
                          <KeyRound size={9} /> {s.credentials_hint}
                        </span>
                      )}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Badge tone={STATUS_TONE[s.status] ?? "idle"} className="text-[10px]">
                    {t(`cvSources.status.${s.status}`)}
                  </Badge>
                  <button
                    type="button"
                    onClick={() => remove.mutate(s.id)}
                    disabled={remove.isPending}
                    title={t("cvSources.remove")}
                    className="opacity-60 hover:opacity-100 hover:text-[--color-error] transition"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {/* Detectadas en tu equipo (carpetas de nube montadas) */}
      {detected.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-1.5">
            <Cloud size={13} className="text-[--color-accent-strong]" />
            <p className="text-[12px] font-semibold tracking-tight">{t("cvSources.detected")}</p>
          </div>
          <p className="text-[11px] text-[--color-fg-subtle] -mt-1">{t("cvSources.detectedHint")}</p>
          <ul className="space-y-1.5">
            {detected.map((d) => (
              <li key={d.path} className="surface px-3 py-2 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[12.5px] font-medium truncate">{d.name}</p>
                  <p className="text-[10.5px] text-[--color-fg-subtle] font-mono truncate">{d.path}</p>
                </div>
                {d.added ? (
                  <Badge tone="running" className="text-[10px] shrink-0">{t("cvSources.alreadyAdded")}</Badge>
                ) : (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => connectDetected.mutate({ name: d.name, path: d.path })}
                    disabled={connectDetected.isPending}
                    className="shrink-0"
                  >
                    <Link2 size={12} /> {t("cvSources.connectOne")}
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Agregar fuente */}
      <div className={compact ? "space-y-3" : "surface p-4 space-y-3"}>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <FieldLabel>{t("cvSources.type")}</FieldLabel>
            <Select value={type} onChange={(e) => setType(e.target.value)}>
              <option value="">—</option>
              {types.map((x) => (
                <option key={x.id} value={x.id}>{x.label}</option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <FieldLabel>{t("cvSources.name")}</FieldLabel>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("cvSources.namePlaceholder")}
            />
          </div>
        </div>
        {needsCreds && (
          <div className="space-y-1.5">
            <FieldLabel hint={t("cvSources.credentialsOptional")}>{t("cvSources.credentials")}</FieldLabel>
            <Input
              type="password"
              value={credentials}
              onChange={(e) => setCredentials(e.target.value)}
              placeholder={t("cvSources.credentialsPlaceholder")}
              autoComplete="new-password"
            />
            {selectedType?.hint && (
              <p className="text-[11px] text-[--color-fg-subtle]">{selectedType.hint}</p>
            )}
            <p className="text-[11px] text-[--color-fg-subtle]">{t("cvSources.secure")}</p>
          </div>
        )}
        <div className="flex justify-end">
          <Button
            variant="primary"
            size="sm"
            onClick={() => add.mutate()}
            disabled={!type || add.isPending}
          >
            <Plus size={13} /> {add.isPending ? t("cvSources.adding") : t("cvSources.add")}
          </Button>
        </div>
      </div>
    </div>
  );
}
