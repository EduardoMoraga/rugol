"use client";

import Link from "next/link";
import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  LayoutDashboard,
  Users,
  CalendarClock,
  Hexagon,
  Network,
  GitBranch,
  Settings,
  ChevronRight,
  Sparkles,
  Wrench,
  Briefcase,
  Languages,
  Wand2,
  Brain,
  Target,
  Mic,
  Home,
  BookOpen,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { useI18n } from "@/lib/i18n";
import { fetchHealth } from "@/lib/api";

type NavItem = {
  href: string;
  labelKey: string;
  icon: typeof Briefcase;
  primary?: boolean;
  accent?: boolean;
};

// Sección de navegación con encabezado (variantes de dominio HRO / CRM).
type NavSection = {
  titleKey: string;
  items: NavItem[];
};

// Navegación PLANA (Rugol y default) — se conserva tal cual.
const items: NavItem[] = [
  { href: "/projects", labelKey: "nav.projects", icon: Briefcase, accent: true },
  { href: "/architect", labelKey: "nav.architect", icon: Sparkles, primary: true },
  { href: "/config-assistant", labelKey: "nav.configAssistant", icon: Wand2 },
  { href: "/agents", labelKey: "nav.agents", icon: Users },
  { href: "/skills", labelKey: "nav.skills", icon: Wrench },
  { href: "/schedules", labelKey: "nav.schedules", icon: CalendarClock },
  { href: "/operations", labelKey: "nav.operations", icon: LayoutDashboard },
  { href: "/memory-graph", labelKey: "nav.memoryGraph", icon: Brain },
  { href: "/ant-farm", labelKey: "nav.antFarm", icon: Hexagon },
  { href: "/ontology", labelKey: "nav.ontology", icon: Network },
  { href: "/improvements", labelKey: "nav.improvements", icon: GitBranch },
  { href: "/settings", labelKey: "nav.settings", icon: Settings },
];

// "Cerebro del agente": las vistas que ya existían, ahora agrupadas (no se borra
// ninguna). Compartidas por HRO y CRM.
const AGENT_BRAIN_ITEMS: NavItem[] = [
  { href: "/agents", labelKey: "nav.agents", icon: Users },
  { href: "/memory-graph", labelKey: "nav.memoryGraph", icon: Brain },
  { href: "/ontology", labelKey: "nav.ontology", icon: Network },
  { href: "/improvements", labelKey: "nav.improvements", icon: GitBranch },
  { href: "/ant-farm", labelKey: "nav.antFarm", icon: Hexagon },
  { href: "/skills", labelKey: "nav.skills", icon: Wrench },
  { href: "/schedules", labelKey: "nav.schedules", icon: CalendarClock },
  { href: "/operations", labelKey: "nav.operations", icon: LayoutDashboard },
];

// "Configuración": compartida por HRO y CRM.
const CONFIG_ITEMS: NavItem[] = [
  { href: "/config-assistant", labelKey: "nav.configAssistant", icon: Wand2 },
  { href: "/settings", labelKey: "nav.settings", icon: Settings },
];

// HRO — reclutamiento al frente; el cerebro del agente queda agrupado aparte.
const HRO_SECTIONS: NavSection[] = [
  {
    titleKey: "nav.section.recruitment",
    items: [
      { href: "/", labelKey: "nav.home", icon: Home },
      { href: "/projects", labelKey: "nav.searches", icon: Briefcase, accent: true },
      { href: "/pipeline", labelKey: "nav.pipelineCandidate", icon: Target, accent: true },
      { href: "/interviews", labelKey: "nav.interviews", icon: Mic },
      { href: "/guide", labelKey: "nav.guide", icon: BookOpen },
    ],
  },
  { titleKey: "nav.section.agentBrain", items: AGENT_BRAIN_ITEMS },
  { titleKey: "nav.section.configuration", items: CONFIG_ITEMS },
];

// CRM — prospección al frente; el cerebro del agente queda agrupado aparte.
const CRM_SECTIONS: NavSection[] = [
  {
    titleKey: "nav.section.prospecting",
    items: [
      { href: "/", labelKey: "nav.home", icon: Home },
      { href: "/pipeline", labelKey: "nav.pipelineLead", icon: Target, accent: true },
      { href: "/projects", labelKey: "nav.projects", icon: Briefcase, accent: true },
      { href: "/guide", labelKey: "nav.guide", icon: BookOpen },
    ],
  },
  { titleKey: "nav.section.agentBrain", items: AGENT_BRAIN_ITEMS },
  { titleKey: "nav.section.configuration", items: CONFIG_ITEMS },
];

export function NavRail() {
  const path = usePathname();
  const { t, locale, setLocale } = useI18n();
  // Pull the live backend version so the sidebar always reflects what
  // is actually deployed. Refreshes every 30s.
  const health = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  });
  const versionLabel = health.data?.version
    ? `v${health.data.version}`
    : "alpha";
  const brand = health.data?.brand || "Rugol";
  // Navegación por variante:
  //  - hro / crm → agrupada en secciones (reclutamiento/prospección al frente,
  //    cerebro del agente y configuración aparte). No se borra ninguna vista.
  //  - rugol / default → navegación PLANA, igual que siempre.
  const variant = health.data?.variant;
  const sections: NavSection[] | null =
    variant === "hro" ? HRO_SECTIONS : variant === "crm" ? CRM_SECTIONS : null;
  // Aplica marca por variante en runtime (un solo build sirve a Rugol/CRM/HRO).
  useEffect(() => {
    if (!health.data) return;
    const h = health.data;
    document.title = `${brand} — Agent Operations Center`;
    const root = document.documentElement;
    if (h.accent) { root.style.setProperty("--color-accent", h.accent); root.style.setProperty("--color-accent-soft", h.accent + "26"); }
    if (h.accent_strong) root.style.setProperty("--color-accent-strong", h.accent_strong);
  }, [health.data, brand]);
  return (
    <nav className="w-60 shrink-0 border-r border-[--color-border] flex flex-col p-3 bg-gradient-to-b from-[--color-bg-elev] to-[--color-bg]">
      <Link href="/" className="px-3 py-3 mb-2 group block">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[--color-accent] to-[--color-accent-strong] grid place-items-center text-white text-xs font-bold shadow-lg shadow-[--color-accent]/30">
            R
          </div>
          <div>
            <div className="text-base font-semibold tracking-tight">{brand}</div>
            <div className="text-[10px] text-[--color-accent-strong] uppercase tracking-widest font-medium">
              {health.data?.tagline || versionLabel}
            </div>
          </div>
        </div>
      </Link>

      <div className="space-y-0.5 flex-1 overflow-y-auto">
        {sections
          ? sections.map((section) => (
              <div key={section.titleKey}>
                <p className="px-3 mt-3 mb-1 text-[10px] uppercase tracking-widest text-[--color-fg-muted] font-medium">
                  {t(section.titleKey)}
                </p>
                {section.items.map((item) => (
                  <NavLink key={item.href} item={item} path={path} t={t} />
                ))}
              </div>
            ))
          : items.map((item) => (
              <NavLink key={item.href} item={item} path={path} t={t} />
            ))}
      </div>

      {/* Language toggle (Capa 15). Persiste en localStorage; hot-swap. */}
      <div className="mt-2 mb-1">
        <div
          className="flex items-center gap-1 px-1 py-1 surface text-[11px] font-medium"
          role="group"
          aria-label="Language"
        >
          <Languages size={12} className="ml-1.5 mr-0.5 text-[--color-fg-muted]" />
          {(["es", "en"] as const).map((l) => (
            <button
              key={l}
              type="button"
              onClick={() => setLocale(l)}
              className={cn(
                "px-2 py-1 rounded-md uppercase tracking-wider transition flex-1",
                locale === l
                  ? "bg-[--color-accent-soft] text-[--color-accent-strong]"
                  : "text-[--color-fg-muted] hover:text-[--color-fg]",
              )}
              aria-pressed={locale === l}
            >
              {l}
            </button>
          ))}
        </div>
      </div>

      <div className="px-3 py-2 text-[10px] text-[--color-fg-subtle]">
        Local · {process.env.NEXT_PUBLIC_API_URL ?? "127.0.0.1:8000"}
      </div>
    </nav>
  );
}

// Un ítem de navegación. Conserva el estilo de activo/primary/accent original.
// La raíz "/" se resalta solo en coincidencia exacta (de lo contrario haría
// match con todas las rutas, ya que toda ruta empieza por "/").
function NavLink({
  item,
  path,
  t,
}: {
  item: NavItem;
  path: string;
  t: (key: string) => string;
}) {
  const { href, labelKey, icon: Icon, primary, accent } = item;
  const active =
    href === "/" ? path === "/" : path === href || path.startsWith(`${href}/`);
  return (
    <Link
      href={href}
      className={cn(
        "group flex items-center justify-between gap-2 px-3 py-2 rounded-md text-[13px] transition-all border",
        active
          ? "bg-[--color-bg-elev-2] text-[--color-fg] border-[--color-border]"
          : primary
            ? "border-[--color-accent]/30 bg-[--color-accent-soft] text-[--color-accent-strong] hover:bg-[--color-accent]/20"
            : accent
              ? "text-[--color-fg] hover:bg-[--color-bg-elev]/50 border-transparent font-medium"
              : "text-[--color-fg-muted] hover:text-[--color-fg] hover:bg-[--color-bg-elev]/50 border-transparent",
      )}
    >
      <span className="flex items-center gap-3">
        <Icon
          size={15}
          aria-hidden
          className={active ? "text-[--color-accent-strong]" : primary ? "text-[--color-accent-strong]" : ""}
        />
        {t(labelKey)}
      </span>
      {active && <ChevronRight size={12} className="text-[--color-fg-muted]" />}
    </Link>
  );
}
