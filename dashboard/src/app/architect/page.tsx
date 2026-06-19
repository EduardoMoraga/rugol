"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Sparkles,
  Wand2,
  ArrowRight,
  Trash2,
  Bot,
  Wrench,
  Clock,
  Network,
  CheckCircle2,
  Plus,
  RefreshCw,
  Briefcase,
} from "lucide-react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  deployProposal,
  fetchInstallDirs,
  proposeArchitecture,
  type DeployResult,
  type Proposal,
  type ProposalAgent,
  type ProposalProject,
  type ProposalSchedule,
  type ProposalSkill,
  type ProposalTriple,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, PageHeader } from "@/components/ui/card";
import { FieldLabel, Input, Select, Textarea } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/toast";
import { PROJECT_ICONS, projectIcon } from "@/components/projects/project-badge";
import { PromptGuide } from "@/components/architect/prompt-guide";
import { useI18n } from "@/lib/i18n";

type Stage = "idea" | "review" | "deploying" | "done";

const MODELS = [
  "claude-opus-4-7",
  "claude-sonnet-4-6",
  "claude-haiku-4-5-20251001",
];

const EXAMPLE_IDEAS = [
  "An assistant that drafts three LinkedIn posts every Monday from what I shipped the previous week.",
  "A support triage system that classifies inbound emails into bug / sales / spam and drafts a first reply.",
  "A weekly research team that scans 5 RSS feeds for AI news, picks the top 3, and writes a 5-minute brief.",
];

export default function ArchitectPage() {
  const { t } = useI18n();
  const [stage, setStage] = useState<Stage>("idea");
  const [idea, setIdea] = useState("");
  const [constraints, setConstraints] = useState("");
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [deployResult, setDeployResult] = useState<DeployResult | null>(null);
  const router = useRouter();

  const [proposeError, setProposeError] = useState<string | null>(null);
  const proposeMut = useMutation({
    mutationFn: ({ i, c }: { i: string; c: string }) => proposeArchitecture(i, c),
    onMutate: () => setProposeError(null),
    onSuccess: (p) => {
      setProposal(p);
      setStage("review");
    },
    onError: (e: Error) => {
      setProposeError(e.message);
      toast({
        tone: "error",
        title: "Architect failed",
        body: e.message.slice(0, 200),
      });
    },
  });

  const [installAgentsDir, setInstallAgentsDir] = useState("");
  const [installSkillsDir, setInstallSkillsDir] = useState("");
  const installDirs = useQuery({
    queryKey: ["install-dirs"],
    queryFn: fetchInstallDirs,
  });

  const deployMut = useMutation({
    mutationFn: (p: Proposal) =>
      deployProposal(
        p,
        installAgentsDir.trim() || undefined,
        installSkillsDir.trim() || undefined,
      ),
    onSuccess: (r) => {
      setDeployResult(r);
      setStage("done");
    },
    onError: (e: Error) =>
      toast({ tone: "error", title: "Deploy failed", body: e.message.slice(0, 200) }),
  });

  function submitIdea(e: FormEvent) {
    e.preventDefault();
    if (idea.trim().length < 10) {
      toast({ tone: "info", title: "Tell me a bit more about the idea." });
      return;
    }
    setStage("idea"); // visual
    proposeMut.mutate({ i: idea.trim(), c: constraints.trim() });
  }

  function reset() {
    setIdea("");
    setConstraints("");
    setProposal(null);
    setDeployResult(null);
    setStage("idea");
  }

  return (
    <div className="p-8 space-y-6 max-w-5xl mx-auto">
      <PageHeader
        title={t("architect.title")}
        description={t("architect.description")}
        actions={
          stage !== "idea" ? (
            <Button variant="ghost" size="sm" onClick={reset}>
              <RefreshCw size={13} /> {t("architect.startOver")}
            </Button>
          ) : null
        }
      />

      <Stepper stage={stage} />

      {stage === "idea" && (
        <>
          <PromptGuide
            onCopyExample={(ex) => {
              setIdea(ex.idea);
              setConstraints(ex.constraints);
              toast({
                tone: "success",
                title: "Plantilla copiada",
                body: "Edita lo que quieras y pulsa Proponer.",
              });
            }}
          />
          <IdeaStage
            idea={idea}
            setIdea={setIdea}
            constraints={constraints}
            setConstraints={setConstraints}
            onSubmit={submitIdea}
            loading={proposeMut.isPending}
          />
          {proposeError && (
            <div className="surface border-[--color-error]/40 p-5 space-y-2">
              <h3 className="text-sm font-semibold text-[--color-error]">
                Architect could not produce a usable proposal
              </h3>
              <pre className="text-xs whitespace-pre-wrap font-mono text-[--color-fg-muted] max-h-[420px] overflow-y-auto">
                {proposeError}
              </pre>
              <p className="text-xs text-[--color-fg-muted]">
                Tip: tighten the idea to one sentence about an outcome (what should the team produce?).
                Long constraints are fine; the model usually fails on a vague goal, not on too much context.
              </p>
            </div>
          )}
        </>
      )}

      {stage === "review" && proposal && (
        <ReviewStage
          proposal={proposal}
          setProposal={setProposal}
          onDeploy={() => {
            setStage("deploying");
            deployMut.mutate(proposal);
          }}
          deploying={deployMut.isPending}
          installAgentsDir={installAgentsDir}
          installSkillsDir={installSkillsDir}
          defaultAgentsDir={installDirs.data?.agents_dir ?? ""}
          defaultSkillsDir={installDirs.data?.skills_dir ?? ""}
          onInstallAgentsDirChange={setInstallAgentsDir}
          onInstallSkillsDirChange={setInstallSkillsDir}
        />
      )}

      {stage === "deploying" && (
        <Card className="text-center py-12 space-y-3">
          <Wand2 className="mx-auto text-[--color-accent-strong] animate-pulse" size={28} />
          <p className="text-base font-medium">Deploying your stack…</p>
          <p className="text-sm text-[--color-fg-muted]">
            Writing markdown files, registering schedules, seeding the ontology.
          </p>
        </Card>
      )}

      {stage === "done" && deployResult && (
        <DoneStage result={deployResult} onView={() => router.push("/agents")} onReset={reset} />
      )}
    </div>
  );
}

function Stepper({ stage }: { stage: Stage }) {
  const steps: { key: Stage | "deploying-or-done"; label: string }[] = [
    { key: "idea", label: "1 · Describe the idea" },
    { key: "review", label: "2 · Review the proposal" },
    { key: "deploying-or-done", label: "3 · Deploy" },
  ];
  const currentIndex =
    stage === "idea" ? 0 : stage === "review" ? 1 : 2;
  return (
    <div className="surface px-4 py-3 flex items-center gap-3 text-sm">
      {steps.map((s, i) => (
        <span key={s.label} className="flex items-center gap-2">
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              i <= currentIndex ? "bg-[--color-accent-strong]" : "bg-[--color-fg-subtle]"
            }`}
          />
          <span className={i === currentIndex ? "text-[--color-fg]" : "text-[--color-fg-muted]"}>
            {s.label}
          </span>
          {i < steps.length - 1 && <span className="text-[--color-fg-subtle] mx-1">→</span>}
        </span>
      ))}
    </div>
  );
}

// ---------- Stage 1: idea ----------

function IdeaStage({
  idea,
  setIdea,
  constraints,
  setConstraints,
  onSubmit,
  loading,
}: {
  idea: string;
  setIdea: (s: string) => void;
  constraints: string;
  setConstraints: (s: string) => void;
  onSubmit: (e: FormEvent) => void;
  loading: boolean;
}) {
  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <Card>
        <div className="space-y-1.5">
          <FieldLabel hint="one or two sentences in plain language">Your idea</FieldLabel>
          <Textarea
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
            rows={4}
            required
            placeholder="An assistant that drafts three LinkedIn posts every Monday from what I shipped the previous week."
            disabled={loading}
          />
        </div>
        <div className="flex flex-wrap gap-2 mt-3">
          {EXAMPLE_IDEAS.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => setIdea(ex)}
              disabled={loading}
              className="text-xs px-3 py-1 rounded-full border border-[--color-border] text-[--color-fg-muted] hover:text-[--color-fg] hover:border-[--color-border-strong] transition disabled:opacity-50"
            >
              {ex.slice(0, 60)}…
            </button>
          ))}
        </div>
      </Card>

      <Card>
        <div className="space-y-1.5">
          <FieldLabel hint="optional · cadence, channels, what NOT to include">
            Constraints
          </FieldLabel>
          <Textarea
            value={constraints}
            onChange={(e) => setConstraints(e.target.value)}
            rows={3}
            placeholder="Use only Sonnet. No Slack agent — I only use Telegram. Keep the team to 2 agents max."
            disabled={loading}
          />
        </div>
      </Card>

      <div className="flex items-center justify-between">
        <p className="text-xs text-[--color-fg-muted] max-w-md">
          Architect calls Claude Sonnet 4.6 to design your stack. Typical response is 15-40 seconds.
        </p>
        <Button type="submit" variant="primary" size="lg" disabled={loading || !idea.trim()}>
          <Sparkles size={14} />
          {loading ? "Designing…" : "Propose architecture"}
          {!loading && <ArrowRight size={14} />}
        </Button>
      </div>
    </form>
  );
}

// ---------- Stage 2: review ----------

function ReviewStage({
  proposal,
  setProposal,
  onDeploy,
  deploying,
  installAgentsDir,
  installSkillsDir,
  defaultAgentsDir,
  defaultSkillsDir,
  onInstallAgentsDirChange,
  onInstallSkillsDirChange,
}: {
  proposal: Proposal;
  setProposal: (p: Proposal) => void;
  onDeploy: () => void;
  deploying: boolean;
  installAgentsDir: string;
  installSkillsDir: string;
  defaultAgentsDir: string;
  defaultSkillsDir: string;
  onInstallAgentsDirChange: (s: string) => void;
  onInstallSkillsDirChange: (s: string) => void;
}) {
  function update<K extends keyof Proposal>(key: K, value: Proposal[K]) {
    setProposal({ ...proposal, [key]: value });
  }

  function addAgent() {
    update("agents", [
      ...proposal.agents,
      {
        name: `agent-${proposal.agents.length + 1}`,
        model: "claude-sonnet-4-6",
        description: "",
        body: "",
      },
    ]);
  }

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex items-start gap-3">
          <Sparkles size={18} className="text-[--color-accent-strong] mt-0.5 shrink-0" />
          <div>
            <h2 className="text-base font-semibold">Architect's proposal</h2>
            <p className="text-sm text-[--color-fg-muted] mt-1">{proposal.summary}</p>
            {proposal.rationale && (
              <details className="mt-3">
                <summary className="text-xs text-[--color-fg-muted] hover:text-[--color-fg] cursor-pointer">
                  Read the rationale
                </summary>
                <p className="text-sm text-[--color-fg-muted] mt-2 whitespace-pre-wrap leading-relaxed">
                  {proposal.rationale}
                </p>
              </details>
            )}
          </div>
        </div>
      </Card>

      <Section
        icon={<Briefcase size={14} />}
        title="Project"
        description="Every team belongs to a project. The mission anchors decisions for every agent in the team."
      >
        <ProjectEditor
          project={proposal.project ?? {
            name: "",
            slug: "",
            description: "",
            mission: "",
            color: "#7280a8",
            icon: "briefcase",
          }}
          onChange={(next) => update("project", next)}
        />
      </Section>

      <Section
        icon={<Bot size={14} />}
        title={`Agents (${proposal.agents.length})`}
        description="Each agent gets its own .md file in your AGENTS_DIR. Edit anything inline."
        action={
          <Button variant="outline" size="sm" onClick={addAgent}>
            <Plus size={12} /> Add agent
          </Button>
        }
      >
        {proposal.agents.length === 0 ? (
          <Card>
            <p className="text-sm text-[--color-fg-muted]">
              The Architect did not propose any agents. Add one above or restart with a different idea.
            </p>
          </Card>
        ) : (
          <div className="space-y-3">
            {proposal.agents.map((a, i) => (
              <AgentEditor
                key={i}
                agent={a}
                onChange={(next) =>
                  update("agents", proposal.agents.map((x, j) => (i === j ? next : x)))
                }
                onRemove={() =>
                  update("agents", proposal.agents.filter((_, j) => i !== j))
                }
              />
            ))}
          </div>
        )}
      </Section>

      {proposal.skills.length > 0 && (
        <Section
          icon={<Wrench size={14} />}
          title={`Skills (${proposal.skills.length})`}
          description="Reusable capabilities written to your SKILLS_DIR."
        >
          <div className="space-y-3">
            {proposal.skills.map((s, i) => (
              <SkillEditor
                key={i}
                skill={s}
                onChange={(next) =>
                  update("skills", proposal.skills.map((x, j) => (i === j ? next : x)))
                }
                onRemove={() =>
                  update("skills", proposal.skills.filter((_, j) => i !== j))
                }
              />
            ))}
          </div>
        </Section>
      )}

      {proposal.schedules.length > 0 && (
        <Section
          icon={<Clock size={14} />}
          title={`Schedules (${proposal.schedules.length})`}
          description="Cron triggers that fire the agents on cadence."
        >
          <div className="space-y-3">
            {proposal.schedules.map((s, i) => (
              <ScheduleEditor
                key={i}
                schedule={s}
                agents={proposal.agents}
                onChange={(next) =>
                  update("schedules", proposal.schedules.map((x, j) => (i === j ? next : x)))
                }
                onRemove={() =>
                  update("schedules", proposal.schedules.filter((_, j) => i !== j))
                }
              />
            ))}
          </div>
        </Section>
      )}

      {proposal.ontology_seeds.length > 0 && (
        <Section
          icon={<Network size={14} />}
          title={`Ontology seeds (${proposal.ontology_seeds.length})`}
          description="Initial facts the team starts with."
        >
          <div className="space-y-2">
            {proposal.ontology_seeds.map((t, i) => (
              <TripleEditor
                key={i}
                triple={t}
                onChange={(next) =>
                  update(
                    "ontology_seeds",
                    proposal.ontology_seeds.map((x, j) => (i === j ? next : x)),
                  )
                }
                onRemove={() =>
                  update(
                    "ontology_seeds",
                    proposal.ontology_seeds.filter((_, j) => i !== j),
                  )
                }
              />
            ))}
          </div>
        </Section>
      )}

      <Section
        icon={<Wrench size={14} />}
        title="Dónde se instala"
        description="Por defecto los .md aterrizan en las carpetas globales (Settings). Sobrescribe solo para esta deploy."
      >
        <Card className="space-y-3">
          <div className="space-y-1.5">
            <FieldLabel hint={defaultAgentsDir ? `default: ${defaultAgentsDir}` : "cargando default…"}>
              Carpeta de agentes
            </FieldLabel>
            <Input
              value={installAgentsDir}
              onChange={(e) => onInstallAgentsDirChange(e.target.value)}
              placeholder={defaultAgentsDir || "C:\\Moragent\\04-LAB\\rugol\\agents-templates"}
              className="font-mono text-[12px]"
              spellCheck={false}
            />
          </div>
          <div className="space-y-1.5">
            <FieldLabel hint={defaultSkillsDir ? `default: ${defaultSkillsDir}` : "cargando default…"}>
              Carpeta de skills
            </FieldLabel>
            <Input
              value={installSkillsDir}
              onChange={(e) => onInstallSkillsDirChange(e.target.value)}
              placeholder={defaultSkillsDir || "C:\\Moragent\\04-LAB\\rugol\\skills-templates"}
              className="font-mono text-[12px]"
              spellCheck={false}
            />
          </div>
          <p className="text-[11px] text-[--color-fg-subtle]">
            Path absoluto. Se crea si no existe. Si dejas vacío usa el default.
            Para cambiar el default global ve a Settings.
          </p>
        </Card>
      </Section>

      <div className="flex items-center justify-between">
        <p className="text-xs text-[--color-fg-muted]">
          Files that already exist will be skipped (no overwrites).
        </p>
        <Button
          variant="primary"
          size="lg"
          onClick={onDeploy}
          disabled={deploying || proposal.agents.length === 0}
        >
          <Wand2 size={14} /> Deploy {proposal.agents.length} agent
          {proposal.agents.length === 1 ? "" : "s"}
        </Button>
      </div>
    </div>
  );
}

function Section({
  icon,
  title,
  description,
  action,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-end justify-between">
        <div>
          <h3 className="text-sm font-semibold tracking-tight inline-flex items-center gap-2">
            <span className="text-[--color-accent-strong]">{icon}</span>
            {title}
          </h3>
          <p className="text-xs text-[--color-fg-muted] mt-0.5">{description}</p>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

const PALETTE = [
  "#7280a8", "#5b8def", "#7c5cff", "#c44d8c",
  "#e26f3f", "#f5b942", "#3aaf85", "#2c9aaf",
];

function slugify(name: string) {
  return name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "").slice(0, 80);
}

function ProjectEditor({
  project,
  onChange,
}: {
  project: ProposalProject;
  onChange: (p: ProposalProject) => void;
}) {
  const Icon = projectIcon(project.icon);
  const tone = project.color || "#7280a8";
  return (
    <Card className="space-y-3">
      <header className="flex items-start gap-3">
        <div
          className="w-12 h-12 rounded-xl grid place-items-center shrink-0"
          style={{
            background: `${tone}22`,
            color: tone,
            border: `1px solid ${tone}55`,
          }}
        >
          <Icon size={20} />
        </div>
        <div className="flex-1 min-w-0 space-y-2">
          <Input
            value={project.name}
            onChange={(e) => {
              const name = e.target.value;
              const auto = slugify(name);
              onChange({
                ...project,
                name,
                slug: !project.slug || project.slug === slugify(project.name) ? auto : project.slug,
              });
            }}
            placeholder="Marca personal"
            className="text-base"
          />
          <Input
            value={project.slug || ""}
            onChange={(e) => onChange({ ...project, slug: e.target.value.toLowerCase() })}
            placeholder="slug-url-safe"
            className="font-mono text-xs"
          />
        </div>
      </header>
      <Input
        value={project.description || ""}
        onChange={(e) => onChange({ ...project, description: e.target.value })}
        placeholder="Una sola línea para la tarjeta del proyecto"
      />
      <Textarea
        value={project.mission || ""}
        onChange={(e) => onChange({ ...project, mission: e.target.value })}
        rows={4}
        placeholder="Misión: el porqué que el equipo lee antes de cada run"
      />
      <div className="grid grid-cols-2 gap-3">
        <Select
          value={project.icon || "briefcase"}
          onChange={(e) => onChange({ ...project, icon: e.target.value })}
        >
          {PROJECT_ICONS.map((i) => (
            <option key={i} value={i}>{i}</option>
          ))}
        </Select>
        <div className="flex flex-wrap gap-1.5">
          {PALETTE.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => onChange({ ...project, color: c })}
              className={`w-7 h-7 rounded-md border-2 transition ${
                project.color === c ? "border-[--color-fg]" : "border-transparent hover:border-[--color-border]"
              }`}
              style={{ background: c }}
              aria-label={c}
            />
          ))}
        </div>
      </div>
    </Card>
  );
}

function AgentEditor({
  agent,
  onChange,
  onRemove,
}: {
  agent: ProposalAgent;
  onChange: (a: ProposalAgent) => void;
  onRemove: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Card className="space-y-3">
      <header className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0 space-y-2">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <Input
              value={agent.name}
              onChange={(e) => onChange({ ...agent, name: e.target.value })}
              placeholder="agent-name"
              className="font-mono text-sm"
            />
            <Select value={agent.model} onChange={(e) => onChange({ ...agent, model: e.target.value })}>
              {MODELS.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </Select>
          </div>
          <Input
            value={agent.description}
            onChange={(e) => onChange({ ...agent, description: e.target.value })}
            placeholder="One-sentence description"
          />
        </div>
        <Button variant="ghost" size="icon" onClick={onRemove} title="Remove">
          <Trash2 size={13} />
        </Button>
      </header>
      <div>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="text-xs text-[--color-fg-muted] hover:text-[--color-fg] inline-flex items-center gap-1"
        >
          {open ? "Hide" : "Show"} prompt body ({agent.body.length} chars)
        </button>
        {open && (
          <Textarea
            value={agent.body}
            onChange={(e) => onChange({ ...agent, body: e.target.value })}
            rows={14}
            className="mt-2 text-[12px]"
            spellCheck={false}
          />
        )}
      </div>
    </Card>
  );
}

function SkillEditor({
  skill,
  onChange,
  onRemove,
}: {
  skill: ProposalSkill;
  onChange: (s: ProposalSkill) => void;
  onRemove: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Card className="space-y-2">
      <header className="flex items-start justify-between gap-3">
        <div className="flex-1 space-y-2 min-w-0">
          <Input
            value={skill.name}
            onChange={(e) => onChange({ ...skill, name: e.target.value })}
            className="font-mono text-sm"
          />
          <Input
            value={skill.description}
            onChange={(e) => onChange({ ...skill, description: e.target.value })}
            placeholder="One-sentence description"
          />
        </div>
        <Button variant="ghost" size="icon" onClick={onRemove} title="Remove">
          <Trash2 size={13} />
        </Button>
      </header>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="text-xs text-[--color-fg-muted] hover:text-[--color-fg] inline-flex items-center gap-1"
      >
        {open ? "Hide" : "Show"} body ({skill.body.length} chars)
      </button>
      {open && (
        <Textarea
          value={skill.body}
          onChange={(e) => onChange({ ...skill, body: e.target.value })}
          rows={10}
          className="text-[12px]"
          spellCheck={false}
        />
      )}
    </Card>
  );
}

function ScheduleEditor({
  schedule,
  agents,
  onChange,
  onRemove,
}: {
  schedule: ProposalSchedule;
  agents: ProposalAgent[];
  onChange: (s: ProposalSchedule) => void;
  onRemove: () => void;
}) {
  return (
    <Card className="space-y-2">
      <header className="flex items-start justify-between gap-3">
        <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-2 min-w-0">
          <Select
            value={schedule.agent_name}
            onChange={(e) => onChange({ ...schedule, agent_name: e.target.value })}
          >
            <option value="">— pick agent —</option>
            {agents.map((a) => (
              <option key={a.name} value={a.name}>{a.name}</option>
            ))}
          </Select>
          <Input
            value={schedule.cron_expr}
            onChange={(e) => onChange({ ...schedule, cron_expr: e.target.value })}
            placeholder="0 9 * * 1"
            className="font-mono"
          />
        </div>
        <Button variant="ghost" size="icon" onClick={onRemove} title="Remove">
          <Trash2 size={13} />
        </Button>
      </header>
      <Textarea
        value={schedule.prompt}
        onChange={(e) => onChange({ ...schedule, prompt: e.target.value })}
        rows={2}
        placeholder="What to send each tick"
      />
    </Card>
  );
}

function TripleEditor({
  triple,
  onChange,
  onRemove,
}: {
  triple: ProposalTriple;
  onChange: (t: ProposalTriple) => void;
  onRemove: () => void;
}) {
  return (
    <div className="surface px-4 py-2.5 flex items-center gap-2 text-sm">
      <Input
        value={triple.src}
        onChange={(e) => onChange({ ...triple, src: e.target.value })}
        className="font-mono flex-1"
      />
      <Input
        value={triple.predicate}
        onChange={(e) => onChange({ ...triple, predicate: e.target.value })}
        className="font-mono flex-1 text-[--color-accent-strong]"
      />
      <Input
        value={triple.dst}
        onChange={(e) => onChange({ ...triple, dst: e.target.value })}
        className="font-mono flex-1"
      />
      <Button variant="ghost" size="icon" onClick={onRemove} title="Remove">
        <Trash2 size={13} />
      </Button>
    </div>
  );
}

// ---------- Stage 3: done ----------

function DoneStage({
  result,
  onView,
  onReset,
}: {
  result: DeployResult;
  onView: () => void;
  onReset: () => void;
}) {
  const total =
    result.agents_created.length +
    result.skills_created.length +
    result.schedules_created.length +
    result.ontology_edges_created;

  return (
    <Card className="space-y-5 py-8 text-center">
      <CheckCircle2 className="mx-auto text-[--color-success]" size={36} />
      <div>
        <h2 className="text-xl font-semibold tracking-tight">Stack deployed</h2>
        <p className="text-sm text-[--color-fg-muted] mt-1">
          {total} thing{total === 1 ? "" : "s"} written to disk and registered.
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-left max-w-2xl mx-auto">
        <ResultRow
          label="Agents"
          created={result.agents_created}
          skipped={result.agents_skipped.map((s) => `${s.name} — ${s.reason}`)}
        />
        <ResultRow
          label="Skills"
          created={result.skills_created}
          skipped={result.skills_skipped.map((s) => `${s.name} — ${s.reason}`)}
        />
        <ResultRow
          label="Schedules"
          created={result.schedules_created.map((id) => `#${id}`)}
          skipped={result.schedules_skipped.map((s) => `${s.agent_name} — ${s.reason}`)}
        />
        <ResultRow
          label="Ontology edges"
          created={Array.from({ length: result.ontology_edges_created }, (_, i) => `edge ${i + 1}`)}
          skipped={[]}
        />
      </div>
      <div className="flex items-center justify-center gap-2 pt-4">
        <Button variant="primary" onClick={onView}>
          See agents
        </Button>
        <Button variant="ghost" onClick={onReset}>
          Design another
        </Button>
      </div>
    </Card>
  );
}

function ResultRow({
  label,
  created,
  skipped,
}: {
  label: string;
  created: string[];
  skipped: string[];
}) {
  if (created.length === 0 && skipped.length === 0) return null;
  return (
    <div className="surface p-4 space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wider text-[--color-fg-muted] font-medium">
          {label}
        </p>
        {created.length > 0 && <Badge tone="running">{created.length} created</Badge>}
      </div>
      {created.length > 0 && (
        <ul className="text-xs space-y-0.5 font-mono">
          {created.map((c, i) => (
            <li key={i} className="text-[--color-fg-muted]">+ {c}</li>
          ))}
        </ul>
      )}
      {skipped.length > 0 && (
        <ul className="text-xs space-y-0.5 font-mono">
          {skipped.map((s, i) => (
            <li key={i} className="text-[--color-warn]">! {s}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
