"use client";

import { FormEvent, useEffect, useState } from "react";
import { Save, Send, MessageSquare, FolderOpen, Cpu, RefreshCw, Plug, Trash2, AlertTriangle, Mic } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createChannelBinding,
  deleteChannelBinding,
  fetchAgents,
  fetchChannelBindings,
  fetchEngines,
  fetchHealth,
  fetchSettings,
  fetchSettingsStatus,
  fetchVoiceStatus,
  resetInstall,
  saveSettings,
  updateSettings,
  type SettingsUpdate,
} from "@/lib/api";
import { ProjectBadge } from "@/components/projects/project-badge";
import { useI18n } from "@/lib/i18n";
import { withCurrent } from "@/lib/models";
import { Button } from "@/components/ui/button";
import { Card, CardSection, PageHeader } from "@/components/ui/card";
import { FieldLabel, Input, Select } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/toast";

export default function SettingsPage() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: fetchSettings });
  const status = useQuery({
    queryKey: ["settings-status"],
    queryFn: fetchSettingsStatus,
    refetchInterval: 4000,
  });
  const health = useQuery({ queryKey: ["health"], queryFn: fetchHealth });
  const isHro = health.data?.variant === "hro";

  return (
    <div className="p-8 space-y-8 max-w-4xl mx-auto">
      <PageHeader
        title={t("settings.title")}
        description={t("settings.description")}
        actions={
          <Button
            variant="ghost"
            size="sm"
            onClick={() => qc.invalidateQueries({ queryKey: ["settings-status"] })}
          >
            <RefreshCw size={13} /> {t("settings.refreshStatus")}
          </Button>
        }
      />

      {settings.isLoading && <p className="text-sm text-[--color-fg-muted]">{t("common.loading")}</p>}

      <EnginesSection />

      {settings.data && status.data && (
        <>
          <TelegramSection settings={settings.data} status={status.data.telegram} qc={qc} />
          <SlackSection settings={settings.data} status={status.data.slack} qc={qc} />
          {isHro && (
            <VoiceSection
              configured={
                status.data.elevenlabs?.configured ?? false
              }
              qc={qc}
            />
          )}
          <ChannelsSection />
          <RegistrySection settings={settings.data} status={status.data.watcher} qc={qc} />
          <ModelSection settings={settings.data} qc={qc} />
          <DangerZone />
        </>
      )}
    </div>
  );
}



function EnginesSection() {
  const { t } = useI18n();
  const qc = useQueryClient();
  // Los dos motores en una sola tarjeta. Antes sólo se veía Claude, y Codex
  // existía únicamente en el frontmatter de un archivo .md — invisible.
  const engines = useQuery({
    queryKey: ["engines"],
    queryFn: () => fetchEngines(),
    refetchInterval: 60_000,
    retry: false,
  });

  // La comprobación REAL: una llamada mínima al API. El chequeo de arriba sólo
  // dice qué está configurado — un token revocado aparece como conectado.
  const verify = useMutation({
    mutationFn: () => fetchEngines(true),
    onSuccess: (data) => {
      qc.setQueryData(["engines"], data);
      const claude = data.engines.find((e) => e.name === "claude");
      toast({
        tone: claude?.verified ? "success" : "error",
        title: claude?.verified
          ? t("settings.claude.verified")
          : t("settings.claude.rejected"),
        body: claude?.verified ? claude.account : claude?.error || "",
      });
    },
    onError: (e: Error) => toast({ tone: "error", title: t("common.error"), body: e.message }),
  });

  const list = engines.data?.engines ?? [];
  const anyBroken = list.some((e) => !e.connected);

  return (
    <Card className={anyBroken ? "border-[--color-warn]/40" : undefined}>
      <SectionHeader
        icon={<Cpu size={14} />}
        title={t("settings.engines.title")}
        body={t("settings.engines.body")}
        status={
          engines.isLoading || verify.isPending ? (
            <Badge tone="idle">{t("settings.claude.checking")}</Badge>
          ) : list.length === 0 ? null : (
            <Badge tone={anyBroken ? "warn" : "running"}>
              {list.filter((e) => e.connected).length}/{list.length}{" "}
              {t("settings.engines.connected")}
            </Badge>
          )
        }
      />

      <div className="space-y-3 mt-1">
        {list.map((e) => (
          <div
            key={e.name}
            className="rounded-md border border-[--color-border] p-3 space-y-2"
          >
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <p className="font-medium inline-flex items-center gap-2">
                {e.label}
                {e.default && (
                  <span className="text-[10px] uppercase tracking-wider text-[--color-fg-subtle]">
                    {t("settings.engines.default")}
                  </span>
                )}
              </p>
              {!e.installed ? (
                <Badge tone="error">{t("settings.engines.notInstalled")}</Badge>
              ) : e.verified === false ? (
                <Badge tone="error">{t("settings.claude.rejected")}</Badge>
              ) : e.connected ? (
                <Badge tone="running">
                  {e.verified ? t("settings.claude.verified") : t("settings.engines.ready")}
                </Badge>
              ) : (
                <Badge tone="warn">{t("settings.engines.notConnected")}</Badge>
              )}
            </div>

            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-[13px]">
              {e.account && <Row label={t("settings.claude.account")} value={e.account} />}
              {e.plan && <Row label={t("settings.claude.plan")} value={e.plan} />}
              {e.method && <Row label={t("settings.claude.method")} value={e.method} />}
              {e.cli_version && <Row label={t("settings.claude.cli")} value={e.cli_version} />}
            </dl>

            {/* Lo único que el usuario necesita accionar: el comando exacto. */}
            {(!e.installed || !e.connected || e.verified === false) && (
              <div className="rounded bg-[--color-bg-elev-2] p-2.5 space-y-1.5">
                {e.error && <p className="text-[12.5px] text-[--color-fg]">{e.error}</p>}
                <p className="text-[12.5px] text-[--color-fg-muted]">
                  {t("settings.engines.runThis")}{" "}
                  <code className="px-1 py-0.5 rounded bg-[--color-bg] font-mono">
                    {e.install_command || e.connect_command}
                  </code>
                </p>
              </div>
            )}

            {!e.supports_memory && (
              <p className="text-[12px] text-[--color-warn]">
                {t("settings.engines.noMemory")}
              </p>
            )}
          </div>
        ))}

        <div className="flex items-center justify-between gap-4">
          <p className="text-xs text-[--color-fg-subtle]">{t("settings.claude.verifyCost")}</p>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => verify.mutate()}
            disabled={verify.isPending}
          >
            <RefreshCw size={13} />
            {verify.isPending ? t("settings.claude.checking") : t("settings.claude.verifyButton")}
          </Button>
        </div>
      </div>
    </Card>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-2 min-w-0">
      <dt className="text-[--color-fg-subtle] shrink-0">{label}</dt>
      <dd className="truncate font-medium">{value}</dd>
    </div>
  );
}

function DangerZone() {
  const { t } = useI18n();
  const reset = useMutation({
    mutationFn: () => resetInstall(),
    onSuccess: (data) => {
      toast({
        tone: "success",
        title: t("settings.resetButton"),
        body: `${data.deleted.length} ${t("common.delete").toLowerCase()}.`,
      });
    },
    onError: (e: Error) =>
      toast({ tone: "error", title: t("common.error"), body: e.message }),
  });

  function handleReset() {
    const phrase = "BORRAR TODO";
    const typed = window.prompt(
      `${t("settings.dangerZoneDescription")}\n\nEscribe: ${phrase}`,
    );
    if (typed === phrase) {
      reset.mutate();
    } else if (typed !== null) {
      toast({ tone: "info", title: "—" });
    }
  }

  return (
    <Card className="border-[--color-error]/40">
      <SectionHeader
        icon={<AlertTriangle size={14} />}
        title={t("settings.dangerZone")}
        body={t("settings.dangerZoneDescription")}
      />
      <Button variant="danger" onClick={handleReset} disabled={reset.isPending}>
        <Trash2 size={13} /> {reset.isPending ? t("settings.resetting") : t("settings.resetButton")}
      </Button>
    </Card>
  );
}

interface SectionProps<S, ST> {
  settings: S;
  status: ST;
  qc: ReturnType<typeof useQueryClient>;
}

function useUpdate(qc: ReturnType<typeof useQueryClient>, label: string) {
  return useMutation({
    mutationFn: (u: SettingsUpdate) => updateSettings(u),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      qc.invalidateQueries({ queryKey: ["settings-status"] });
      const fails = Object.entries(data.restarted).filter(([, v]) => v !== "ok");
      if (fails.length === 0) {
        toast({ tone: "success", title: `${label} saved`, body: "Adapters restarted cleanly." });
      } else {
        toast({
          tone: "error",
          title: `${label} saved with errors`,
          body: fails.map(([k, v]) => `${k}: ${v}`).join(" · "),
        });
      }
    },
    onError: (e: Error) => toast({ tone: "error", title: `Could not save ${label}`, body: e.message }),
  });
}

function TelegramSection({ settings, status, qc }: SectionProps<any, any>) {
  const { t } = useI18n();
  const [token, setToken] = useState("");
  const update = useUpdate(qc, "Telegram");

  function submit(e: FormEvent) {
    e.preventDefault();
    const upd: SettingsUpdate = {};
    if (token) upd.telegram_bot_token = token;
    update.mutate(upd);
    setToken("");
  }

  return (
    <Card>
      <SectionHeader
        icon={<Send size={14} />}
        title={t("settings.telegram.title")}
        body={t("settings.telegram.body")}
        status={
          status.running ? (
            <Badge tone="running">{t("settings.telegram.connected")}</Badge>
          ) : status.configured ? (
            <Badge tone="warn">{t("settings.telegram.configuredNotRunning")}</Badge>
          ) : (
            <Badge tone="idle">{t("settings.telegram.notConfigured")}</Badge>
          )
        }
      />
      <form onSubmit={submit} className="space-y-3 mt-1">
        <div className="space-y-1.5">
          <FieldLabel
            hint={
              settings.telegram_bot_token_set
                ? t("settings.telegram.tokenHintCurrent").replace("{hint}", settings.telegram_bot_token_hint ?? "")
                : t("settings.telegram.tokenHintNone")
            }
          >
            {t("settings.telegram.tokenLabel")}
          </FieldLabel>
          <Input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder={
              settings.telegram_bot_token_set
                ? t("settings.telegram.tokenPlaceholderSet")
                : "1234567:ABC-DEF…"
            }
            autoComplete="new-password"
          />
        </div>
        <div className="flex justify-end">
          <Button type="submit" variant="primary" disabled={update.isPending}>
            <Save size={13} /> {update.isPending ? t("settings.telegram.saving") : t("settings.telegram.save")}
          </Button>
        </div>
      </form>
    </Card>
  );
}

function SlackSection({ settings, status, qc }: SectionProps<any, any>) {
  const [bot, setBot] = useState("");
  const [signing, setSigning] = useState("");
  const [appT, setAppT] = useState("");
  const update = useUpdate(qc, "Slack");

  function submit(e: FormEvent) {
    e.preventDefault();
    const upd: SettingsUpdate = {};
    if (bot) upd.slack_bot_token = bot;
    if (signing) upd.slack_signing_secret = signing;
    if (appT) upd.slack_app_token = appT;
    if (Object.keys(upd).length === 0) {
      toast({ tone: "info", title: "Nothing to save" });
      return;
    }
    update.mutate(upd);
    setBot("");
    setSigning("");
    setAppT("");
  }

  return (
    <Card>
      <SectionHeader
        icon={<MessageSquare size={14} />}
        title="Slack"
        body="Bolt for Python in socket mode — no public webhook needed. Provide the bot token (xoxb-…), the app-level token (xapp-…), and the signing secret."
        status={
          status.running ? (
            <Badge tone="running">connected</Badge>
          ) : status.configured ? (
            <Badge tone="warn">configured · not running</Badge>
          ) : (
            <Badge tone="idle">not configured</Badge>
          )
        }
      />
      <form onSubmit={submit} className="space-y-3 mt-1">
        <div className="space-y-1.5">
          <FieldLabel
            hint={
              settings.slack_bot_token_set ? `current ${settings.slack_bot_token_hint}` : "no token saved"
            }
          >
            Bot token (xoxb-)
          </FieldLabel>
          <Input
            type="password"
            value={bot}
            onChange={(e) => setBot(e.target.value)}
            placeholder={settings.slack_bot_token_set ? "(leave blank to keep current)" : "xoxb-…"}
            autoComplete="new-password"
          />
        </div>
        <div className="space-y-1.5">
          <FieldLabel
            hint={
              settings.slack_app_token_set ? `current ${settings.slack_app_token_hint}` : "no token saved"
            }
          >
            App-level token (xapp-)
          </FieldLabel>
          <Input
            type="password"
            value={appT}
            onChange={(e) => setAppT(e.target.value)}
            placeholder={settings.slack_app_token_set ? "(leave blank to keep current)" : "xapp-…"}
            autoComplete="new-password"
          />
        </div>
        <div className="space-y-1.5">
          <FieldLabel hint={settings.slack_signing_secret_set ? "saved" : "no secret saved"}>
            Signing secret
          </FieldLabel>
          <Input
            type="password"
            value={signing}
            onChange={(e) => setSigning(e.target.value)}
            placeholder={settings.slack_signing_secret_set ? "(leave blank to keep current)" : "32-char secret"}
            autoComplete="new-password"
          />
        </div>
        <div className="flex justify-end">
          <Button type="submit" variant="primary" disabled={update.isPending}>
            <Save size={13} /> {update.isPending ? "Saving…" : "Save & restart"}
          </Button>
        </div>
      </form>
    </Card>
  );
}

function RegistrySection({ settings, status, qc }: SectionProps<any, any>) {
  const [agentsDir, setAgentsDir] = useState(settings.agents_dir || "");
  const [skillsDir, setSkillsDir] = useState(settings.skills_dir || "");
  const update = useUpdate(qc, "Registry");

  useEffect(() => setAgentsDir(settings.agents_dir || ""), [settings.agents_dir]);
  useEffect(() => setSkillsDir(settings.skills_dir || ""), [settings.skills_dir]);

  function submit(e: FormEvent) {
    e.preventDefault();
    update.mutate({ agents_dir: agentsDir, skills_dir: skillsDir });
  }

  return (
    <Card>
      <SectionHeader
        icon={<FolderOpen size={14} />}
        title="Agents folder"
        body="Point Rugol at any folder of .md files. The watcher hot-reloads on save. Default is the bundled agents-templates."
        status={
          <Badge tone={status.running ? "running" : "warn"}>
            {status.running ? "watching" : "not watching"}
          </Badge>
        }
      />
      <form onSubmit={submit} className="space-y-3 mt-1">
        <div className="space-y-1.5">
          <FieldLabel hint={`active: ${status.agents_dir}`}>Agents directory</FieldLabel>
          <Input
            value={agentsDir}
            onChange={(e) => setAgentsDir(e.target.value)}
            placeholder="C:\Moragent\.claude\agents"
            spellCheck={false}
            className="font-mono text-[12px]"
          />
        </div>
        <div className="space-y-1.5">
          <FieldLabel hint={`active: ${status.skills_dir}`}>Skills directory</FieldLabel>
          <Input
            value={skillsDir}
            onChange={(e) => setSkillsDir(e.target.value)}
            placeholder="C:\Moragent\.claude\skills"
            spellCheck={false}
            className="font-mono text-[12px]"
          />
        </div>
        <p className="text-xs text-[--color-fg-muted]">
          Tip: leave blank to revert to the bundled templates. Saving rescans the folder and restarts the watcher.
        </p>
        <div className="flex justify-end">
          <Button type="submit" variant="primary" disabled={update.isPending}>
            <Save size={13} /> {update.isPending ? "Applying…" : "Save & rescan"}
          </Button>
        </div>
      </form>
    </Card>
  );
}

function ChannelsSection() {
  const qc = useQueryClient();
  const bindings = useQuery({
    queryKey: ["channel-bindings"],
    queryFn: () => fetchChannelBindings(),
  });
  const agents = useQuery({ queryKey: ["agents"], queryFn: () => fetchAgents() });

  const [type, setType] = useState<"telegram" | "slack">("telegram");
  const [externalId, setExternalId] = useState("");
  const [agentId, setAgentId] = useState<number | null>(null);
  const [label, setLabel] = useState("");

  const create = useMutation({
    mutationFn: () =>
      createChannelBinding({
        channel_type: type,
        external_id: externalId.trim(),
        agent_id: agentId as number,
        label: label.trim() || null,
      }),
    onSuccess: () => {
      toast({ tone: "success", title: "Channel binding guardado" });
      qc.invalidateQueries({ queryKey: ["channel-bindings"] });
      setExternalId("");
      setLabel("");
    },
    onError: (e: Error) =>
      toast({ tone: "error", title: "No se pudo bindear", body: e.message }),
  });

  const remove = useMutation({
    mutationFn: (id: number) => deleteChannelBinding(id),
    onSuccess: () => {
      toast({ tone: "info", title: "Binding borrado" });
      qc.invalidateQueries({ queryKey: ["channel-bindings"] });
    },
    onError: (e: Error) =>
      toast({ tone: "error", title: "No se pudo borrar", body: e.message }),
  });

  return (
    <Card>
      <SectionHeader
        icon={<Plug size={14} />}
        title="Channel bindings"
        body="Cada chat de Telegram / canal de Slack se asocia a un agente. Sin binding, el bot responde con un mensaje de ayuda en vez de despachar al agente equivocado."
        status={
          <Badge tone="idle">{bindings.data?.length ?? 0} bindings</Badge>
        }
      />

      {/* Existing bindings */}
      {bindings.data && bindings.data.length > 0 && (
        <ul className="space-y-1.5 mb-4">
          {bindings.data.map((b) => (
            <li
              key={b.id}
              className="surface px-3 py-2 flex items-center justify-between text-sm gap-3"
            >
              <div className="flex items-center gap-2 min-w-0 flex-1">
                <Badge tone={b.channel_type === "telegram" ? "running" : "accent"}>
                  {b.channel_type}
                </Badge>
                <span className="font-mono text-xs text-[--color-fg-muted] truncate">
                  {b.external_id}
                </span>
                {b.label && (
                  <span className="text-xs text-[--color-fg-subtle] truncate">
                    {b.label}
                  </span>
                )}
                <span className="text-xs text-[--color-fg-subtle] mx-1">→</span>
                <span className="text-sm text-[--color-fg]">{b.agent_name}</span>
                {b.project_slug && (
                  <ProjectBadge
                    slug={b.project_slug}
                    name={b.project_name}
                    color={null}
                    icon={null}
                    asLink={false}
                  />
                )}
              </div>
              <button
                onClick={() => remove.mutate(b.id)}
                disabled={remove.isPending}
                className="text-[--color-fg-subtle] hover:text-[--color-error] transition shrink-0"
                title="Borrar binding"
              >
                <Trash2 size={13} />
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* Add new binding */}
      <div className="space-y-3">
        <p className="text-[10.5px] uppercase tracking-widest text-[--color-fg-muted] font-medium">
          Nuevo binding
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="space-y-1.5">
            <FieldLabel>Canal</FieldLabel>
            <Select value={type} onChange={(e) => setType(e.target.value as "telegram" | "slack")}>
              <option value="telegram">Telegram</option>
              <option value="slack">Slack</option>
            </Select>
          </div>
          <div className="space-y-1.5">
            <FieldLabel hint={type === "telegram" ? "chat_id (envía /whoami al bot)" : "channel id (e.g. C0ABC123)"}>
              External ID
            </FieldLabel>
            <Input
              value={externalId}
              onChange={(e) => setExternalId(e.target.value)}
              placeholder={type === "telegram" ? "123456789" : "C0ABC123"}
              className="font-mono"
            />
          </div>
          <div className="space-y-1.5">
            <FieldLabel>Agente</FieldLabel>
            <Select
              value={agentId ?? ""}
              onChange={(e) => setAgentId(e.target.value ? parseInt(e.target.value, 10) : null)}
            >
              <option value="">— elegir —</option>
              {(agents.data ?? []).map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                  {a.project_name ? ` · ${a.project_name}` : ""}
                </option>
              ))}
            </Select>
          </div>
        </div>
        <div className="space-y-1.5">
          <FieldLabel hint="opcional · ej. 'Edu DM' o '#sales'">Label</FieldLabel>
          <Input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Edu DM"
          />
        </div>
        <div className="flex justify-end">
          <Button
            variant="primary"
            onClick={() => create.mutate()}
            disabled={create.isPending || !externalId.trim() || !agentId}
          >
            <Plug size={13} /> Bindear
          </Button>
        </div>
        <p className="text-[10.5px] text-[--color-fg-subtle]">
          Tip Telegram: el usuario manda <code className="font-mono">/whoami</code> al bot
          y le devuelve su <code className="font-mono">chat_id</code>. También funciona{" "}
          <code className="font-mono">/bind &lt;agente&gt;</code> directo desde el chat.
        </p>
      </div>
    </Card>
  );
}


function ModelSection({ settings, qc }: { settings: any; qc: ReturnType<typeof useQueryClient> }) {
  const [model, setModel] = useState(settings.default_model || "");
  const update = useUpdate(qc, "Default model");

  useEffect(() => setModel(settings.default_model || ""), [settings.default_model]);

  function submit(e: FormEvent) {
    e.preventDefault();
    update.mutate({ default_model: model });
  }

  return (
    <Card>
      <SectionHeader
        icon={<Cpu size={14} />}
        title="Default model"
        body="Used when an agent's frontmatter does not specify a model."
      />
      <form onSubmit={submit} className="space-y-3 mt-1">
        <div className="space-y-1.5">
          <FieldLabel>Model</FieldLabel>
          <Select value={model} onChange={(e) => setModel(e.target.value)}>
            <option value="">(use config default)</option>
            {withCurrent(settings.default_model).map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="flex justify-end">
          <Button type="submit" variant="primary" disabled={update.isPending}>
            <Save size={13} /> Save
          </Button>
        </div>
      </form>
    </Card>
  );
}

function VoiceSection({
  configured,
  qc,
}: {
  configured: boolean;
  qc: ReturnType<typeof useQueryClient>;
}) {
  const { t } = useI18n();
  const [apiKey, setApiKey] = useState("");
  const [agentId, setAgentId] = useState("");

  // Fuente secundaria de "configurado": /api/voice/status (más específico que
  // /api/settings/status). Si una está true, lo damos por configurado.
  const voice = useQuery({
    queryKey: ["voice-status"],
    queryFn: fetchVoiceStatus,
    refetchInterval: 30_000,
    retry: false,
  });
  const isConfigured = configured || (voice.data?.configured ?? false);

  const save = useMutation({
    mutationFn: (body: SettingsUpdate) => saveSettings(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      qc.invalidateQueries({ queryKey: ["settings-status"] });
      qc.invalidateQueries({ queryKey: ["voice-status"] });
      toast({ tone: "success", title: t("settings.elevenlabs.saved") });
      setApiKey("");
    },
    onError: (e: Error) =>
      toast({ tone: "error", title: t("common.error"), body: e.message }),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    const upd: SettingsUpdate = {};
    if (apiKey) upd.elevenlabs_api_key = apiKey;
    if (agentId) upd.elevenlabs_agent_id = agentId;
    if (Object.keys(upd).length === 0) {
      toast({ tone: "info", title: "—" });
      return;
    }
    save.mutate(upd);
  }

  return (
    <Card>
      <SectionHeader
        icon={<Mic size={14} />}
        title={t("settings.elevenlabs.title")}
        body={t("settings.elevenlabs.body")}
        status={
          <Badge tone={isConfigured ? "running" : "idle"}>
            {isConfigured
              ? t("settings.elevenlabs.configured")
              : t("settings.elevenlabs.notConfigured")}
          </Badge>
        }
      />
      <form onSubmit={submit} className="space-y-3 mt-1">
        <div className="space-y-1.5">
          <FieldLabel hint={t("settings.elevenlabs.apiKeyHint")}>
            {t("settings.elevenlabs.apiKey")}
          </FieldLabel>
          <Input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk_..."
            autoComplete="new-password"
            className="font-mono text-[12px]"
          />
        </div>
        <div className="space-y-1.5">
          <FieldLabel>{t("settings.elevenlabs.agentId")}</FieldLabel>
          <Input
            value={agentId}
            onChange={(e) => setAgentId(e.target.value)}
            placeholder="agent_..."
            spellCheck={false}
            className="font-mono text-[12px]"
          />
        </div>
        <div className="flex justify-end">
          <Button type="submit" variant="primary" disabled={save.isPending}>
            <Save size={13} /> {save.isPending ? t("pipeline.creating") : t("common.save")}
          </Button>
        </div>
      </form>
    </Card>
  );
}

function SectionHeader({
  icon,
  title,
  body,
  status,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
  status?: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 mb-4">
      <div>
        <h2 className="text-base font-semibold tracking-tight inline-flex items-center gap-2">
          <span className="text-[--color-accent-strong]">{icon}</span>
          {title}
        </h2>
        <p className="text-sm text-[--color-fg-muted] mt-1 max-w-xl">{body}</p>
      </div>
      {status}
    </div>
  );
}
