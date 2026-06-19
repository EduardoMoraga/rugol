"use client";

/**
 * Config Assistant — paste-and-go config from arbitrary input.
 *
 * Flow:
 *   1. User pastes anything (JSON dump, .env, free text with credentials).
 *   2. We send it to the backend which uses claude-agent-sdk + a meta-prompt
 *      to detect what the input contains.
 *   3. Backend returns a plan with token-masked actions.
 *   4. User picks which actions to apply (checkboxes).
 *   5. We send selected ids back; backend uses the cached raw plan to apply.
 *
 * Tokens never leave the client→backend pipe in plain after the first paste:
 * the masked plan that comes back never includes raw values.
 */
import { FormEvent, useState } from "react";
import { Wand2, ShieldCheck, AlertTriangle, Check, X, RefreshCw } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import {
  configAssistantApply,
  configAssistantParse,
  type ConfigAssistantApplyResult,
  type ConfigAssistantParseResponse,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, PageHeader } from "@/components/ui/card";
import { toast } from "@/components/ui/toast";

export default function ConfigAssistantPage() {
  const [text, setText] = useState("");
  const [parsed, setParsed] = useState<ConfigAssistantParseResponse | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [applyResult, setApplyResult] = useState<ConfigAssistantApplyResult | null>(null);

  const parseMut = useMutation({
    mutationFn: (input: string) => configAssistantParse(input),
    onSuccess: (resp) => {
      setParsed(resp);
      // Pre-select all actions by default — user opts out, not in.
      setSelected(new Set(resp.plan.actions.map((a) => a.id)));
      setApplyResult(null);
    },
    onError: (e: Error) => {
      toast({
        tone: "error",
        title: "El asistente no pudo parsear",
        body: e.message.slice(0, 240),
      });
    },
  });

  const applyMut = useMutation({
    mutationFn: () =>
      configAssistantApply(parsed!.plan_token, Array.from(selected)),
    onSuccess: (r) => {
      setApplyResult(r);
      const okCount = r.results.filter((x) => x.ok).length;
      const errCount = r.results.length - okCount;
      toast({
        tone: errCount === 0 ? "success" : "warning",
        title: `Aplicado: ${okCount} OK${errCount ? `, ${errCount} con error` : ""}`,
      });
    },
    onError: (e: Error) =>
      toast({ tone: "error", title: "Aplicar falló", body: e.message.slice(0, 240) }),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    parseMut.mutate(text.trim());
  }

  function reset() {
    setText("");
    setParsed(null);
    setSelected(new Set());
    setApplyResult(null);
  }

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="p-8 space-y-6 max-w-4xl mx-auto">
      <PageHeader
        title="Asistente de configuración"
        description="Pega un JSON, un .env, o cualquier texto con credenciales. El asistente detecta qué hay y propone configuraciones aplicables. Los tokens nunca se muestran completos en pantalla."
        actions={
          parsed ? (
            <Button variant="ghost" size="sm" onClick={reset}>
              <RefreshCw size={13} /> Empezar de nuevo
            </Button>
          ) : null
        }
      />

      {!parsed && (
        <Card className="space-y-4">
          <form onSubmit={submit} className="space-y-3">
            <label className="block">
              <span className="text-xs uppercase tracking-widest text-[--color-fg-muted] font-medium">
                Pega tu input
              </span>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={14}
                spellCheck={false}
                placeholder={`Ejemplos de qué pegar:\n• Un JSON de OpenClaw o cualquier herramienta agéntica\n• El contenido de un .env\n• Texto libre con tokens y URLs\n• Output de "vercel env pull"\n• Tus notas privadas con credenciales`}
                className="mt-2 w-full px-3 py-2 bg-transparent border border-[--color-border] rounded-md text-sm font-mono focus:outline-none focus:border-[--color-accent]"
              />
            </label>
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <p className="text-[11px] text-[--color-fg-muted] flex items-start gap-1.5">
                <ShieldCheck size={12} className="mt-0.5 text-emerald-400 shrink-0" />
                Lo que pegues se manda a Claude para parsear. Los valores con apariencia de
                secreto se guardan en memoria del backend por 10 minutos y NO se devuelven
                en claro al frontend. Después de aplicar, se borran.
              </p>
              <Button
                type="submit"
                variant="primary"
                disabled={parseMut.isPending || !text.trim()}
              >
                <Wand2 size={14} />
                {parseMut.isPending ? "Analizando…" : "Analizar"}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {parsed && (
        <>
          <Card className="space-y-3">
            <header className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold tracking-tight">Plan propuesto</h2>
                <p className="text-xs text-[--color-fg-muted] mt-0.5">
                  {parsed.plan.actions.length} acción
                  {parsed.plan.actions.length === 1 ? "" : "es"} detectada
                  {parsed.plan.actions.length === 1 ? "" : "s"}. Marca las que quieres
                  aplicar.
                </p>
              </div>
              <Button
                variant="primary"
                size="sm"
                onClick={() => applyMut.mutate()}
                disabled={applyMut.isPending || selected.size === 0}
              >
                {applyMut.isPending
                  ? "Aplicando…"
                  : `Aplicar ${selected.size === 0 ? "" : `(${selected.size})`}`}
              </Button>
            </header>

            {parsed.plan.actions.length === 0 ? (
              <p className="text-sm text-[--color-fg-muted] py-6 text-center">
                El asistente no detectó nada accionable. Prueba con un input distinto.
              </p>
            ) : (
              <ul className="space-y-2">
                {parsed.plan.actions.map((a) => {
                  const isSelected = selected.has(a.id);
                  return (
                    <li
                      key={a.id}
                      className={`surface px-3 py-2.5 cursor-pointer transition ${
                        isSelected
                          ? "border-[--color-accent]/40 bg-[--color-accent]/5"
                          : ""
                      }`}
                      onClick={() => toggle(a.id)}
                    >
                      <div className="flex items-start gap-3">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggle(a.id)}
                          className="mt-1 shrink-0"
                        />
                        <div className="min-w-0 flex-1 space-y-1">
                          <div className="flex items-baseline gap-2 flex-wrap">
                            <code className="text-[10.5px] uppercase tracking-widest text-[--color-fg-muted]">
                              {a.type}
                            </code>
                            <p className="text-sm text-[--color-fg]">
                              {a.description || "(sin descripción)"}
                            </p>
                          </div>
                          <ActionDetail action={a} />
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}

            {parsed.plan.unsure.length > 0 && (
              <div className="rounded border border-yellow-500/30 bg-yellow-500/5 p-3 space-y-1">
                <p className="text-[11px] text-yellow-400 font-medium flex items-center gap-1.5">
                  <AlertTriangle size={11} /> El asistente vio cosas que no clasificó:
                </p>
                <ul className="text-[11.5px] text-[--color-fg-muted] list-disc pl-5 space-y-0.5">
                  {parsed.plan.unsure.map((u, i) => (
                    <li key={i}>{u}</li>
                  ))}
                </ul>
              </div>
            )}
          </Card>

          {applyResult && (
            <Card className="space-y-2">
              <h3 className="text-sm font-semibold">Resultado</h3>
              <ul className="space-y-1.5">
                {applyResult.results.map((r) => (
                  <li
                    key={r.id}
                    className="text-[12.5px] flex items-start gap-2"
                  >
                    {r.ok ? (
                      <Check size={14} className="text-emerald-400 mt-0.5 shrink-0" />
                    ) : (
                      <X size={14} className="text-red-400 mt-0.5 shrink-0" />
                    )}
                    <span className={r.ok ? "text-[--color-fg]" : "text-red-400"}>
                      <span className="font-mono text-[10.5px] mr-2">{r.id}</span>
                      {r.ok ? r.outcome : r.error}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="text-[11px] text-[--color-fg-muted] pt-2 border-t border-[--color-border]">
                Recordá: si configuraste tokens de Telegram o Slack, reiniciá el backend
                (Ctrl+C en uvicorn + relanzar) o usa el botón Restart en Settings para que
                los adapters arranquen con los tokens nuevos.
              </p>
            </Card>
          )}
        </>
      )}
    </div>
  );
}


function ActionDetail({
  action,
}: {
  action: { [key: string]: any };
}) {
  // Render type-specific extra info, with masked secret values (already
  // masked server-side).
  const skip = new Set(["type", "id", "description"]);
  const entries = Object.entries(action).filter(([k]) => !skip.has(k));
  if (entries.length === 0) return null;
  return (
    <div className="text-[11px] font-mono text-[--color-fg-muted] space-y-0.5 pt-1">
      {entries.map(([k, v]) => {
        if (v === null || v === undefined) return null;
        if (typeof v === "object") {
          return (
            <div key={k}>
              {k}:
              <ul className="pl-3">
                {Object.entries(v as Record<string, any>).map(([kk, vv]) => (
                  <li key={kk}>
                    {kk}={String(vv)}
                  </li>
                ))}
              </ul>
            </div>
          );
        }
        return (
          <div key={k} className="break-all">
            {k}={String(v)}
          </div>
        );
      })}
    </div>
  );
}
