"use client";

/**
 * CvSourcesManager — gestiona las fuentes de CV de HRO (Pandapé, Chiletrabajo,
 * Computrabajo, LinkedIn, Drive, carpeta…). Reusable en el onboarding y en
 * Ajustes. La reclutadora elige un tipo, pega el token si hace falta, y listo;
 * el agente `connector` usa esta lista para traer candidatos al pipeline.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Database, KeyRound } from "lucide-react";
import {
  fetchCvSources,
  addCvSource,
  deleteCvSource,
  type CvSourceType,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { FieldLabel, Input, Select } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";
import { useI18n } from "@/lib/i18n";

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
                      {s.credentials_set && (
                        <span className="ml-1.5 inline-flex items-center gap-0.5">
                          <KeyRound size={9} /> {s.credentials_hint}
                        </span>
                      )}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => remove.mutate(s.id)}
                  disabled={remove.isPending}
                  title={t("cvSources.remove")}
                  className="opacity-60 hover:opacity-100 hover:text-[--color-error] transition shrink-0"
                >
                  <Trash2 size={14} />
                </button>
              </li>
            );
          })}
        </ul>
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
