"use client";

import Link from "next/link";
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

const items: NavItem[] = [
  { href: "/projects", labelKey: "nav.projects", icon: Briefcase, accent: true },
  { href: "/architect", labelKey: "nav.architect", icon: Sparkles, primary: true },
  { href: "/config-assistant", labelKey: "nav.configAssistant", icon: Wand2 },
  { href: "/agents", labelKey: "nav.agents", icon: Users },
  { href: "/skills", labelKey: "nav.skills", icon: Wrench },
  { href: "/schedules", labelKey: "nav.schedules", icon: CalendarClock },
  { href: "/operations", labelKey: "nav.operations", icon: LayoutDashboard },
  { href: "/ant-farm", labelKey: "nav.antFarm", icon: Hexagon },
  { href: "/ontology", labelKey: "nav.ontology", icon: Network },
  { href: "/improvements", labelKey: "nav.improvements", icon: GitBranch },
  { href: "/settings", labelKey: "nav.settings", icon: Settings },
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
    : "Increxa Edition";
  return (
    <nav className="w-60 shrink-0 border-r border-[--color-border] flex flex-col p-3 bg-gradient-to-b from-[--color-bg-elev] to-[--color-bg]">
      <Link href="/" className="px-3 py-3 mb-2 group block">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[--color-accent] to-[--color-accent-strong] grid place-items-center text-white text-xs font-bold shadow-lg shadow-[--color-accent]/30">
            TA
          </div>
          <div>
            <div className="text-base font-semibold tracking-tight">TeamAgent</div>
            <div className="text-[10px] text-[--color-fg-muted] uppercase tracking-widest">
              {versionLabel}
            </div>
          </div>
        </div>
      </Link>

      <div className="space-y-0.5 flex-1">
        {items.map(({ href, labelKey, icon: Icon, primary, accent }) => {
          const active = path === href || path.startsWith(`${href}/`);
          return (
            <Link
              key={href}
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
        })}
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
