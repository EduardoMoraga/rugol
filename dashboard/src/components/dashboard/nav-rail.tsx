"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
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
} from "lucide-react";
import { cn } from "@/lib/cn";

const items = [
  { href: "/projects", label: "Proyectos", icon: Briefcase, accent: true },
  { href: "/architect", label: "Architect", icon: Sparkles, primary: true },
  { href: "/agents", label: "Agentes", icon: Users },
  { href: "/skills", label: "Skills", icon: Wrench },
  { href: "/schedules", label: "Schedules", icon: CalendarClock },
  { href: "/operations", label: "Operations", icon: LayoutDashboard },
  { href: "/ant-farm", label: "Ant farm", icon: Hexagon },
  { href: "/ontology", label: "Ontology", icon: Network },
  { href: "/improvements", label: "Improvements", icon: GitBranch },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function NavRail() {
  const path = usePathname();
  return (
    <nav className="w-60 shrink-0 border-r border-[--color-border] flex flex-col p-3 bg-gradient-to-b from-[--color-bg-elev] to-[--color-bg]">
      <Link href="/" className="px-3 py-3 mb-2 group block">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[--color-accent] to-[--color-accent-strong] grid place-items-center text-white text-xs font-bold shadow-lg shadow-[--color-accent]/30">
            R
          </div>
          <div>
            <div className="text-base font-semibold tracking-tight">Rogologo</div>
            <div className="text-[10px] text-[--color-fg-muted] uppercase tracking-widest">
              v0.2 · alpha
            </div>
          </div>
        </div>
      </Link>

      <div className="space-y-0.5 flex-1">
        {items.map(({ href, label, icon: Icon, primary, accent }) => {
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
                {label}
              </span>
              {active && <ChevronRight size={12} className="text-[--color-fg-muted]" />}
            </Link>
          );
        })}
      </div>

      <div className="mt-2 px-3 py-2 text-[10px] text-[--color-fg-subtle]">
        Local · {process.env.NEXT_PUBLIC_API_URL ?? "127.0.0.1:8000"}
      </div>
    </nav>
  );
}
