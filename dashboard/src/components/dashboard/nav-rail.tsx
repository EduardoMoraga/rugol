"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Users, CalendarClock, Hexagon, Network, GitBranch, Settings } from "lucide-react";
import { cn } from "@/lib/cn";

const items = [
  { href: "/", label: "Operations", icon: LayoutDashboard },
  { href: "/agents", label: "Agents", icon: Users },
  { href: "/schedules", label: "Schedules", icon: CalendarClock },
  { href: "/ant-farm", label: "Ant farm", icon: Hexagon },
  { href: "/ontology", label: "Ontology", icon: Network },
  { href: "/improvements", label: "Improvements", icon: GitBranch },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function NavRail() {
  const path = usePathname();
  return (
    <nav className="w-56 shrink-0 border-r border-[--color-border] bg-[--color-bg-elev] p-3 flex flex-col gap-1">
      <div className="px-3 py-3 mb-2">
        <span className="text-lg font-semibold tracking-tight">Rogologo</span>
        <p className="text-[10px] text-[--color-fg-muted] uppercase tracking-widest">alpha</p>
      </div>
      {items.map(({ href, label, icon: Icon }) => {
        const active = href === "/" ? path === "/" : path.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition",
              active
                ? "bg-[--color-border] text-[--color-fg]"
                : "text-[--color-fg-muted] hover:text-[--color-fg] hover:bg-[--color-border]/50",
            )}
          >
            <Icon size={16} aria-hidden />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
