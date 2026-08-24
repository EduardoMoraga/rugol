"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Save, Sparkles } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Card, PageHeader } from "@/components/ui/card";
import { FieldLabel, Input, Select, Textarea } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";
import { type AgentSpec, type Agent } from "@/lib/api";
import {
  AGENT_NAME_MAX,
  AGENT_NAME_MIN,
  AGENT_NAME_PATTERN,
  slugifyAgentName,
} from "@/lib/agent-name";
import { DEFAULT_MODEL, withCurrent } from "@/lib/models";
import { fetchEngines } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";


const STARTER_BODY = `You are a focused agent. Describe in 1-2 sentences who you are.

## When you are invoked

Describe the trigger (a schedule, a Telegram message, a dashboard click).

## What you do, step by step

1. First do this.
2. Then this.
3. Always finish with this.

## Output format

Be specific about what the response should look like. Markdown is fine.

## Constraints

- What you must not do
- What you should always do
`;

interface Props {
  mode: "create" | "edit";
  initial?: AgentSpec;
  onSubmit: (spec: AgentSpec) => Promise<Agent>;
  /** Header title shown on the page. */
  title: string;
  /** Header description shown on the page. */
  description: string;
  /** Where to redirect after success. Receives the resulting Agent.id. */
  redirectTo: (id: number) => string;
}

export function AgentForm({ mode, initial, onSubmit, title, description, redirectTo }: Props) {
  const router = useRouter();
  const [name, setName] = useState(initial?.name ?? "");
  // Lo que se guarda es el slug, no lo que la persona tipeó. Nadie debería
  // aprender las reglas de un slug para crear un agente: mostramos el
  // resultado mientras escribe y mandamos eso.
  const slug = slugifyAgentName(name);
  const slugDiffers = mode === "create" && slug !== name.trim() && name.trim() !== "";
  const slugTooShort = mode === "create" && name.trim() !== "" && slug.length < AGENT_NAME_MIN;
  const [model, setModel] = useState(initial?.model ?? DEFAULT_MODEL);
  const [engine, setEngine] = useState(initial?.engine ?? "claude");
  // El estado real de cada motor: si el CLI no está instalado o la cuenta no
  // está conectada, hay que decirlo ACÁ — no al fallar la primera corrida.
  const engines = useQuery({
    queryKey: ["engines"],
    queryFn: () => fetchEngines(),
    staleTime: 60_000,
    retry: false,
  });
  const engineInfo = engines.data?.engines.find((e) => e.name === engine);
  // El modelo del agente puede ser de una generación anterior: lo mantenemos
  // en la lista para no cambiárselo por debajo al editar otro campo.
  // Los modelos los manda el backend por motor: si elegís Codex ves Sol/Terra/
  // Luna, si elegís Claude ves Opus/Sonnet/Haiku. Mantener la lista acá era
  // ofrecer modelos que el otro motor rechaza.
  const engineModels = engineInfo?.models?.length
    ? engineInfo.models
    : withCurrent(initial?.model);
  const modelOptions =
    initial?.model && !engineModels.some((m) => m.value === initial.model)
      ? [...engineModels, { value: initial.model, label: `${initial.model} — actual` }]
      : engineModels;
  const [desc, setDesc] = useState(initial?.description ?? "");
  const [body, setBody] = useState(initial?.body ?? STARTER_BODY);
  const [submitting, setSubmitting] = useState(false);

  async function handle(e: FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    try {
      const a = await onSubmit({
        name: mode === "create" ? slug : name.trim(),
        model,
        engine,
        description: desc.trim(),
        body,
      });
      toast({
        tone: "success",
        title: mode === "create" ? `Created ${a.name}` : `Updated ${a.name}`,
      });
      router.push(redirectTo(a.id));
    } catch (err) {
      toast({
        tone: "error",
        title: mode === "create" ? "Could not create agent" : "Could not update agent",
        body: (err as Error).message,
      });
      setSubmitting(false);
    }
  }

  return (
    <div className="p-8 space-y-6 max-w-4xl mx-auto">
      <PageHeader
        title={title}
        description={description}
        actions={
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="ghost" size="sm">
                <Sparkles size={13} /> Scaffold with Moragent
              </Button>
            </DialogTrigger>
            <DialogContent
              title="Scaffold with Moragent"
              description="Moragent is the Claude Code skill that designs rich agents from a one-line idea."
            >
              <ol className="space-y-2 text-sm text-[--color-fg-muted] list-decimal pl-5">
                <li>
                  In your Claude Code session run:{" "}
                  <code className="text-[--color-accent-strong] font-mono">/moragent nuevo proyecto idea</code>
                </li>
                <li>
                  Pick the agent specs Moragent generates (name, model, prompt body) and paste them into
                  the fields below — name on top, the long markdown into the body.
                </li>
                <li>
                  Save here. Rugol writes the <code className="font-mono">.md</code> into your{" "}
                  <code className="font-mono">AGENTS_DIR</code>, the watcher picks it up, and the new agent
                  shows up across the dashboard.
                </li>
              </ol>
              <p className="text-xs text-[--color-fg-subtle] mt-4">
                Long term we'll wire the skill directly to this dialog. For now copy-paste keeps the
                two systems honestly decoupled.
              </p>
            </DialogContent>
          </Dialog>
        }
      />

      <form onSubmit={handle} className="space-y-5">
        <Card>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <FieldLabel
                hint={mode === "edit" ? "renames not supported here" : "spaces and accents are fine"}
              >
                Name
              </FieldLabel>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Brand architect"
                required
                disabled={mode === "edit"}
                // El guion va ESCAPADO: los navegadores compilan el `pattern`
                // con el flag `v`, y un guion literal suelto en una clase de
                // caracteres no compila bajo `v`. Cuando no compila, el
                // navegador ignora el pattern en silencio — que es como
                // "Analista BI" llegaba al servidor y volvía como 400.
                pattern={mode === "create" ? undefined : AGENT_NAME_PATTERN}
                maxLength={AGENT_NAME_MAX * 2}
              />
              {mode === "create" && (slugDiffers || slugTooShort) && (
                <p
                  className={
                    slugTooShort
                      ? "text-xs text-[--color-danger]"
                      : "text-xs text-[--color-fg-muted]"
                  }
                >
                  {slugTooShort ? (
                    <>Needs at least {AGENT_NAME_MIN} letters or digits.</>
                  ) : (
                    <>
                      Saved as <code className="font-mono text-[--color-accent-strong]">{slug}</code>
                    </>
                  )}
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <FieldLabel>Model</FieldLabel>
              <Select value={model} onChange={(e) => setModel(e.target.value)}>
                {modelOptions.map((m) => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </Select>
            </div>
          </div>

          {/* Motor: con qué CLI corre este agente. Vivía sólo en el frontmatter
              del .md, así que desde la interfaz era invisible. */}
          <div className="space-y-1.5 mt-4">
            <FieldLabel hint="qué CLI ejecuta este agente">Motor</FieldLabel>
            <Select
              value={engine}
              onChange={(e) => {
                const next = e.target.value;
                setEngine(next);
                // El modelo tiene que seguir al motor: dejar uno de la otra
                // familia hacía fallar la corrida con "issue with the selected
                // model". El backend igual lo traduce por nivel, pero la UI no
                // debe mostrar algo que no es lo que va a correr.
                const info = engines.data?.engines.find((x) => x.name === next);
                if (info?.default_model) setModel(info.default_model);
              }}
            >
              {(engines.data?.engines ?? [{ name: "claude", label: "Claude (Anthropic)" }]).map(
                (e) => (
                  <option key={e.name} value={e.name}>
                    {e.label}
                  </option>
                ),
              )}
            </Select>

            {engineInfo && !engineInfo.installed && (
              <p className="text-[12.5px] text-[--color-error]">
                El CLI no está instalado. En la terminal:{" "}
                <code className="px-1 py-0.5 rounded bg-[--color-bg-elev-2] font-mono">
                  {engineInfo.install_command}
                </code>
              </p>
            )}
            {engineInfo?.installed && !engineInfo.connected && (
              <p className="text-[12.5px] text-[--color-error]">
                La cuenta no está conectada. En la terminal:{" "}
                <code className="px-1 py-0.5 rounded bg-[--color-bg-elev-2] font-mono">
                  {engineInfo.connect_command}
                </code>
              </p>
            )}
            {engineInfo?.connected && (
              <p className="text-[12.5px] text-[--color-fg-muted]">
                Conectado{engineInfo.account ? ` · ${engineInfo.account}` : ""}
                {engineInfo.cli_version ? ` · ${engineInfo.cli_version}` : ""}
              </p>
            )}
            {engineInfo?.supports_memory && (
              <p className="text-[12.5px] text-[--color-fg-muted]">
                La memoria de Rugol funciona en este motor: vive en el core, no en el CLI.
              </p>
            )}
            {engineInfo?.missing?.length ? (
              <p className="text-[12.5px] text-[--color-warn]">
                No disponible en este motor: {engineInfo.missing.join(" · ")}.
              </p>
            ) : null}
            {engine !== "claude" && (
              <p className="text-[12.5px] text-[--color-fg-subtle]">
                El modelo de arriba se ignora si es de Claude: este motor usa el suyo.
              </p>
            )}
          </div>
          <div className="space-y-1.5 mt-4">
            <FieldLabel hint="one sentence shown on the card">Description</FieldLabel>
            <Input
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              placeholder="Strategic personal-brand agent. Posts every Monday with curated takes."
              maxLength={240}
            />
          </div>
        </Card>

        <Card>
          <div className="space-y-1.5">
            <FieldLabel hint="markdown · this is the full agent prompt">Spec body</FieldLabel>
            <Textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={20}
              required
              spellCheck={false}
              className="text-[12px]"
            />
          </div>
        </Card>

        <div className="flex items-center justify-end gap-3">
          <Button
            type="button"
            variant="ghost"
            onClick={() => router.back()}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            disabled={submitting || (mode === "create" && slug.length < AGENT_NAME_MIN)}
          >
            <Save size={13} /> {submitting ? "Saving…" : mode === "create" ? "Create agent" : "Save changes"}
          </Button>
        </div>
      </form>
    </div>
  );
}
