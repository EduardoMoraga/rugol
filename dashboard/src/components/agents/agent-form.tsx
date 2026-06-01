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

const MODELS = [
  { value: "claude-opus-4-7", label: "Opus 4.7 — heavy reasoning, expensive" },
  { value: "claude-sonnet-4-6", label: "Sonnet 4.6 — balanced (recommended)" },
  { value: "claude-haiku-4-5-20251001", label: "Haiku 4.5 — fast & cheap" },
];

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
  const [model, setModel] = useState(initial?.model ?? "claude-sonnet-4-6");
  const [desc, setDesc] = useState(initial?.description ?? "");
  const [body, setBody] = useState(initial?.body ?? STARTER_BODY);
  const [submitting, setSubmitting] = useState(false);

  async function handle(e: FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    try {
      const a = await onSubmit({ name: name.trim(), model, description: desc.trim(), body });
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
              <FieldLabel hint={mode === "edit" ? "renames not supported here" : "lowercase, dashes ok"}>
                Name
              </FieldLabel>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="brand-architect"
                required
                disabled={mode === "edit"}
                pattern="[a-z0-9][a-z0-9-]+[a-z0-9]"
                minLength={3}
                maxLength={64}
              />
            </div>
            <div className="space-y-1.5">
              <FieldLabel>Model</FieldLabel>
              <Select value={model} onChange={(e) => setModel(e.target.value)}>
                {MODELS.map((m) => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </Select>
            </div>
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
          <Button type="submit" variant="primary" disabled={submitting}>
            <Save size={13} /> {submitting ? "Saving…" : mode === "create" ? "Create agent" : "Save changes"}
          </Button>
        </div>
      </form>
    </div>
  );
}
