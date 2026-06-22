"use client";

/**
 * OnboardingWizard — primer arranque "Instalar → Configurar → Enjoy".
 *
 * Cuatro pasos simples para una reclutadora no técnica: Anthropic (ya viene),
 * Telegram (opcional), ElevenLabs/Sofía (opcional) y al menos una fuente de CV.
 * Al terminar marca onboarding_done=true (persistido) y desaparece. El padre
 * (HroCockpit) decide cuándo mostrarlo leyendo settings.onboarding_done.
 */
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Sparkles, Bot, Send, Mic, Database, Check, ArrowRight, ArrowLeft } from "lucide-react";
import { updateSettings } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { FieldLabel, Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";
import { useI18n } from "@/lib/i18n";
import { CvSourcesManager } from "@/components/hro/cv-sources";

export function OnboardingWizard({ onDone }: { onDone: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [step, setStep] = useState(0);
  const [telegram, setTelegram] = useState("");
  const [elevenKey, setElevenKey] = useState("");
  const [elevenAgent, setElevenAgent] = useState("");

  const steps = [
    { icon: Bot, title: t("onboarding.anthropic.title") },
    { icon: Send, title: t("onboarding.telegram.title") },
    { icon: Mic, title: t("onboarding.eleven.title") },
    { icon: Database, title: t("onboarding.sources.title") },
  ];
  const last = steps.length - 1;

  const finish = useMutation({
    mutationFn: () => {
      const upd: Record<string, unknown> = { onboarding_done: true };
      if (telegram.trim()) upd.telegram_bot_token = telegram.trim();
      if (elevenKey.trim()) upd.elevenlabs_api_key = elevenKey.trim();
      if (elevenAgent.trim()) upd.elevenlabs_agent_id = elevenAgent.trim();
      return updateSettings(upd);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      qc.invalidateQueries({ queryKey: ["settings-status"] });
      qc.invalidateQueries({ queryKey: ["voice-status"] });
      toast({ tone: "success", title: t("onboarding.wizard.done") });
      onDone();
    },
    onError: (e: Error) => toast({ tone: "error", title: t("common.error"), body: e.message }),
  });

  const StepIcon = steps[step].icon;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="w-full max-w-xl surface rounded-2xl border border-[--color-accent]/40 shadow-xl overflow-hidden">
        {/* Cabecera */}
        <div className="px-6 pt-6 pb-4 border-b border-[--color-border]">
          <span className="inline-flex items-center gap-1.5 text-[10.5px] uppercase tracking-widest font-medium text-[--color-accent-strong]">
            <Sparkles size={12} /> {t("onboarding.wizard.tag")}
          </span>
          <h2 className="text-xl font-semibold tracking-tight mt-1">{t("onboarding.wizard.title")}</h2>
          <p className="text-[13px] text-[--color-fg-muted] mt-0.5">{t("onboarding.wizard.subtitle")}</p>
          {/* Progreso */}
          <div className="flex items-center gap-1.5 mt-3">
            {steps.map((_, i) => (
              <span
                key={i}
                className={
                  "h-1.5 flex-1 rounded-full transition-colors " +
                  (i <= step ? "bg-[--color-accent]" : "bg-[--color-border-strong]")
                }
              />
            ))}
          </div>
        </div>

        {/* Cuerpo del paso */}
        <div className="px-6 py-5 min-h-[230px]">
          <div className="flex items-center gap-2.5 mb-3">
            <span className="w-9 h-9 rounded-xl grid place-items-center shrink-0 bg-[--color-accent-soft] text-[--color-accent-strong]">
              <StepIcon size={17} />
            </span>
            <h3 className="text-[15px] font-semibold tracking-tight">{steps[step].title}</h3>
          </div>

          {step === 0 && (
            <div className="space-y-3">
              <p className="text-[13.5px] text-[--color-fg-muted] leading-relaxed">{t("onboarding.anthropic.body")}</p>
              <div className="surface px-3 py-2.5 inline-flex items-center gap-2 text-[13px] text-[--color-success]">
                <Check size={14} /> {t("onboarding.anthropic.ok")}
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="space-y-3">
              <p className="text-[13.5px] text-[--color-fg-muted] leading-relaxed">{t("onboarding.telegram.body")}</p>
              <div className="space-y-1.5">
                <FieldLabel>Token</FieldLabel>
                <Input
                  type="password"
                  value={telegram}
                  onChange={(e) => setTelegram(e.target.value)}
                  placeholder="1234567:ABC-DEF…"
                  autoComplete="new-password"
                />
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-3">
              <p className="text-[13.5px] text-[--color-fg-muted] leading-relaxed">{t("onboarding.eleven.body")}</p>
              <div className="space-y-1.5">
                <FieldLabel>{t("onboarding.eleven.key")}</FieldLabel>
                <Input
                  type="password"
                  value={elevenKey}
                  onChange={(e) => setElevenKey(e.target.value)}
                  placeholder="sk_…"
                  autoComplete="new-password"
                />
              </div>
              <div className="space-y-1.5">
                <FieldLabel>{t("onboarding.eleven.agent")}</FieldLabel>
                <Input value={elevenAgent} onChange={(e) => setElevenAgent(e.target.value)} placeholder="agent_…" />
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-3">
              <p className="text-[13.5px] text-[--color-fg-muted] leading-relaxed">{t("onboarding.sources.body")}</p>
              <CvSourcesManager compact />
            </div>
          )}
        </div>

        {/* Pie */}
        <div className="px-6 py-4 border-t border-[--color-border] flex items-center justify-between">
          <button
            type="button"
            onClick={() => finish.mutate()}
            className="text-[12.5px] text-[--color-fg-muted] hover:text-[--color-fg]"
            disabled={finish.isPending}
          >
            {t("onboarding.wizard.skip")}
          </button>
          <div className="flex items-center gap-2">
            {step > 0 && (
              <Button variant="ghost" size="sm" onClick={() => setStep((s) => s - 1)} disabled={finish.isPending}>
                <ArrowLeft size={13} /> {t("onboarding.wizard.back")}
              </Button>
            )}
            {step < last ? (
              <Button variant="primary" size="sm" onClick={() => setStep((s) => s + 1)}>
                {t("onboarding.wizard.next")} <ArrowRight size={13} />
              </Button>
            ) : (
              <Button variant="primary" size="sm" onClick={() => finish.mutate()} disabled={finish.isPending}>
                {finish.isPending ? t("onboarding.wizard.finishing") : t("onboarding.wizard.finish")}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
