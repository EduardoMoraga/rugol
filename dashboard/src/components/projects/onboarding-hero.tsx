"use client";

import { Sparkles } from "lucide-react";
import { useI18n } from "@/lib/i18n";

/**
 * Emotional first-touch for users who land on /projects with nothing real
 * yet (only Workspace, no named projects). Disappears the moment they
 * clone a template or create their first project — Capa 10.
 *
 * Pure copywriting + a CTA that scrolls to the template catalog further
 * down the page. No backend dependencies. Bilingual (Capa 15).
 */
export function OnboardingHero() {
  const { t } = useI18n();
  function scrollToTemplates() {
    const el = document.getElementById("template-catalog");
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <section className="relative overflow-hidden surface px-8 py-10 md:py-14">
      <div
        className="absolute -top-24 -right-24 w-96 h-96 rounded-full opacity-30 blur-3xl pointer-events-none"
        style={{ background: "radial-gradient(circle, #7c5cff 0%, transparent 70%)" }}
      />
      <div
        className="absolute -bottom-24 -left-24 w-80 h-80 rounded-full opacity-20 blur-3xl pointer-events-none"
        style={{ background: "radial-gradient(circle, #3aaf85 0%, transparent 70%)" }}
      />
      <div className="relative max-w-3xl space-y-5">
        <span className="inline-flex items-center gap-1.5 text-[10.5px] uppercase tracking-widest font-medium text-[--color-accent-strong]">
          <Sparkles size={12} /> {t("onboarding.tag")}
        </span>
        <h1 className="text-3xl md:text-4xl font-semibold tracking-tight leading-[1.1]">
          {t("onboarding.headline")}
          <br />
          <span className="text-[--color-fg-muted]">{t("onboarding.headlineHighlight")}</span>
        </h1>
        <p className="text-[15px] text-[--color-fg-muted] leading-relaxed max-w-2xl">
          {t("onboarding.pitch")}
        </p>
        <p className="text-[14px] text-[--color-fg] leading-relaxed">
          {t("onboarding.question")}
        </p>
        <div className="flex flex-wrap items-center gap-3 pt-1">
          <button
            type="button"
            onClick={scrollToTemplates}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-md bg-[--color-accent] hover:bg-[--color-accent-strong] text-[--color-accent-fg] text-sm font-medium transition shadow-lg shadow-[--color-accent]/30"
          >
            <Sparkles size={14} /> {t("onboarding.seeTemplates")}
          </button>
          <a
            href="/architect"
            className="text-sm text-[--color-fg-muted] hover:text-[--color-fg] inline-flex items-center gap-1.5 px-3 py-2"
          >
            {t("onboarding.orArchitect")}
          </a>
        </div>
        <ul className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-1.5 text-[12.5px] text-[--color-fg-muted] pt-4 max-w-2xl border-t border-[--color-border]/60 mt-4">
          <li className="pt-3">
            <strong className="text-[--color-fg]">{t("onboarding.localFirst")}</strong>{" "}
            {t("onboarding.localFirstDesc")}
          </li>
          <li className="pt-3">
            <strong className="text-[--color-fg]">{t("onboarding.mission")}</strong>{" "}
            {t("onboarding.missionDesc")}
          </li>
          <li className="pt-3">
            <strong className="text-[--color-fg]">{t("onboarding.lessons")}</strong>{" "}
            {t("onboarding.lessonsDesc")}
          </li>
          <li className="pt-3">
            <strong className="text-[--color-fg]">{t("onboarding.advocate")}</strong>{" "}
            {t("onboarding.advocateDesc")}
          </li>
        </ul>
      </div>
    </section>
  );
}
