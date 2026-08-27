"use client";

import { useQuery } from "@tanstack/react-query";
import { Gauge, TrendingDown, TrendingUp } from "lucide-react";
import { fetchProcedures, type Procedure } from "@/lib/api";
import { Card, PageHeader } from "@/components/ui/card";
import { useI18n } from "@/lib/i18n";

/**
 * Los métodos que los agentes compilaron solos — y si de verdad están
 * abaratando el trabajo.
 *
 * Esta pantalla existe para hacer FALSABLE la tesis del producto. "Mi agente
 * aprende y se vuelve más rápido" es una frase que nadie puede contradecir, y
 * por eso no significa nada. Lo que sí significa algo es: esta familia de tarea
 * costaba 18.000 tokens y cuesta 6.000, sobre 23 corridas. Si el número no
 * baja, el bucle no funciona — y hay que poder verlo.
 */
export default function ProceduresPage() {
  const { t } = useI18n();
  const { data, isLoading } = useQuery({
    queryKey: ["procedures"],
    queryFn: fetchProcedures,
    refetchInterval: 30_000,
  });

  const total = data?.length ?? 0;
  // El titular es el SALTO, no la pendiente. La pendiente responde "¿se
  // abarató con el uso?"; el salto responde la pregunta del producto:
  // "¿esto costaba deliberar y ahora no?".
  const conSalto = (data ?? []).filter((p) => p.leap?.tokens_delta_pct != null);
  const mejoraMedia =
    conSalto.length > 0
      ? conSalto.reduce((a, p) => a + (p.leap!.tokens_delta_pct ?? 0), 0) / conSalto.length
      : null;

  return (
    <div className="p-8 space-y-6 max-w-5xl mx-auto">
      <PageHeader
        title={t("procedures.title")}
        description={t("procedures.desc")}
        actions={
          <span className="text-xs text-[--color-fg-muted]">
            {t("procedures.count").replace("{n}", String(total))}
          </span>
        }
      />

      {isLoading && <p className="text-sm text-[--color-fg-muted]">{t("common.loading")}</p>}

      {data && data.length === 0 && (
        <Card className="text-center py-10 space-y-3">
          <Gauge size={28} className="mx-auto text-[--color-accent-strong]" />
          <h2 className="text-lg font-semibold">{t("procedures.emptyTitle")}</h2>
          <p className="text-sm text-[--color-fg-muted] max-w-lg mx-auto">
            {t("procedures.emptyBody")}
          </p>
        </Card>
      )}

      {mejoraMedia != null && (
        <Card className="flex items-center gap-4">
          {mejoraMedia < 0 ? (
            <TrendingDown size={26} className="text-[--color-success] shrink-0" />
          ) : (
            <TrendingUp size={26} className="text-[--color-warn] shrink-0" />
          )}
          <div>
            <p className="text-2xl font-semibold tabular-nums tracking-tight">
              {mejoraMedia > 0 ? "+" : ""}
              {mejoraMedia.toFixed(1)}%
            </p>
            <p className="text-xs text-[--color-fg-muted]">
              {t(
                conSalto.length === 1 ? "procedures.headlineOne" : "procedures.headline",
              ).replace("{n}", String(conSalto.length))}
            </p>
          </div>
        </Card>
      )}

      {data && data.length > 0 && (
        <div className="space-y-3">
          {data.map((p) => (
            <ProcedureCard key={`${p.agent}/${p.name}`} p={p} />
          ))}
        </div>
      )}
    </div>
  );
}

function ProcedureCard({ p }: { p: Procedure }) {
  const { t } = useI18n();
  // El salto manda; la pendiente es el complemento.
  const delta = p.leap?.tokens_delta_pct ?? null;
  const mejora = delta != null && delta < 0;

  return (
    <Card className="space-y-3">
      <header className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="font-mono text-sm font-semibold tracking-tight">{p.name}</h3>
          <p className="text-xs text-[--color-fg-muted] mt-1">{p.description}</p>
        </div>
        <div className="text-right shrink-0">
          <p className="text-sm font-semibold tabular-nums">{p.applied_runs}</p>
          <p className="text-[10px] uppercase tracking-wider text-[--color-fg-subtle]">
            {t("procedures.applied")}
          </p>
        </div>
      </header>

      <p className="text-[11px] text-[--color-fg-subtle] font-mono">{p.agent}</p>

      {p.leap ? (
        <div className="grid grid-cols-3 gap-3 pt-1 border-t border-[--color-border]">
          <Metric
            label={t("procedures.tokens")}
            before={p.leap.discovering.tokens}
            after={p.leap.applying.tokens}
          />
          <Metric
            label={t("procedures.seconds")}
            before={p.leap.discovering.seconds}
            after={p.leap.applying.seconds}
          />
          <div className="pt-2">
            <p className="text-[10px] uppercase tracking-wider text-[--color-fg-subtle]">
              {t("procedures.change")}
            </p>
            <p
              className={`text-lg font-semibold tabular-nums ${
                mejora ? "text-[--color-success]" : "text-[--color-warn]"
              }`}
            >
              {delta != null ? `${delta > 0 ? "+" : ""}${delta.toFixed(1)}%` : "—"}
            </p>
          </div>
        </div>
      ) : (
        // Sin la corrida que lo descubrió no hay "antes", y estimarlo sería
        // inventarlo. Antes esta pantalla comparaba el primer tercio contra el
        // último de las aplicaciones y lo presentaba como si fuera el salto:
        // medía la pendiente DESPUÉS del salto.
        <p className="text-xs text-[--color-fg-subtle] pt-1 border-t border-[--color-border]">
          {t("procedures.noSample")}
        </p>
      )}

      {p.trend?.tokens_delta_pct != null && (
        <p className="text-[11px] text-[--color-fg-subtle]">
          {t("procedures.slope").replace(
            "{pct}",
            `${p.trend.tokens_delta_pct > 0 ? "+" : ""}${p.trend.tokens_delta_pct.toFixed(1)}%`,
          )}
        </p>
      )}
    </Card>
  );
}

function Metric({ label, before, after }: { label: string; before: number; after: number }) {
  return (
    <div className="pt-2">
      <p className="text-[10px] uppercase tracking-wider text-[--color-fg-subtle]">{label}</p>
      <p className="text-sm tabular-nums">
        <span className="text-[--color-fg-muted]">{Math.round(before).toLocaleString()}</span>
        <span className="mx-1.5 text-[--color-fg-subtle]">→</span>
        <span className="font-semibold">{Math.round(after).toLocaleString()}</span>
      </p>
    </div>
  );
}
