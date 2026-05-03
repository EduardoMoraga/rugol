"use client";

import { Sparkles } from "lucide-react";

/**
 * Emotional first-touch for users who land on /projects with nothing real
 * yet (only Workspace, no named projects). Disappears the moment they
 * clone a template or create their first project — Capa 10.
 *
 * Pure copywriting + a CTA that scrolls to the template catalog further
 * down the page. No backend dependencies.
 */
export function OnboardingHero() {
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
          <Sparkles size={12} /> Bienvenida a Rogologo
        </span>
        <h1 className="text-3xl md:text-4xl font-semibold tracking-tight leading-[1.1]">
          La vida es la sumatoria de proyectos.
          <br />
          <span className="text-[--color-fg-muted]">Tú eres el CEO; ellos ejecutan.</span>
        </h1>
        <p className="text-[15px] text-[--color-fg-muted] leading-relaxed max-w-2xl">
          Rogologo es tu sala de control de agentes. No piensas "qué agente creo" —
          piensas "qué proyecto necesito": tu marca, tu día a día, ayudar a tu hija a
          estudiar, tu pipeline comercial. El equipo de agentes se arma alrededor de eso.
        </p>
        <p className="text-[14px] text-[--color-fg] leading-relaxed">
          ¿Por dónde te gustaría empezar?
        </p>
        <div className="flex flex-wrap items-center gap-3 pt-1">
          <button
            type="button"
            onClick={scrollToTemplates}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-md bg-[--color-accent] hover:bg-[--color-accent-strong] text-[--color-accent-fg] text-sm font-medium transition shadow-lg shadow-[--color-accent]/30"
          >
            <Sparkles size={14} /> Ver los 5 templates
          </button>
          <a
            href="/architect"
            className="text-sm text-[--color-fg-muted] hover:text-[--color-fg] inline-flex items-center gap-1.5 px-3 py-2"
          >
            o describilo en una línea con Architect →
          </a>
        </div>
        <ul className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-1.5 text-[12.5px] text-[--color-fg-muted] pt-4 max-w-2xl border-t border-[--color-border]/60 mt-4">
          <li className="pt-3">
            <strong className="text-[--color-fg]">Local-first.</strong> Todo corre en tu
            PC. Tus datos no salen.
          </li>
          <li className="pt-3">
            <strong className="text-[--color-fg]">Misión por proyecto.</strong> Cada
            equipo lee su porqué antes de cada tarea.
          </li>
          <li className="pt-3">
            <strong className="text-[--color-fg]">Lecciones vivas.</strong> Lo que el
            equipo aprende queda como anclaje permanente.
          </li>
          <li className="pt-3">
            <strong className="text-[--color-fg]">Abogado del diablo.</strong> Para las
            decisiones que importan, dos perspectivas.
          </li>
        </ul>
      </div>
    </section>
  );
}
