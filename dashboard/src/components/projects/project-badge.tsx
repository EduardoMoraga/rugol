"use client";

import Link from "next/link";
import {
  Briefcase,
  Sparkles,
  Heart,
  Rocket,
  Brain,
  Gamepad2,
  Users,
  Palette,
  Target,
  Leaf,
  BookOpen,
  Headphones,
  type LucideIcon,
} from "lucide-react";

const ICON_MAP: Record<string, LucideIcon> = {
  briefcase: Briefcase,
  sparkles: Sparkles,
  heart: Heart,
  rocket: Rocket,
  brain: Brain,
  gamepad: Gamepad2,
  "gamepad-2": Gamepad2,
  users: Users,
  palette: Palette,
  target: Target,
  leaf: Leaf,
  "book-open": BookOpen,
  headphones: Headphones,
};

export const PROJECT_ICONS = Object.keys(ICON_MAP);

export function projectIcon(name: string | null | undefined): LucideIcon {
  if (!name) return Briefcase;
  return ICON_MAP[name.toLowerCase()] ?? Briefcase;
}

interface ProjectBadgeProps {
  slug: string | null | undefined;
  name: string | null | undefined;
  color?: string | null;
  icon?: string | null;
  size?: "sm" | "md";
  asLink?: boolean;
  className?: string;
}

/** Small inline chip showing the project an agent belongs to. */
export function ProjectBadge({
  slug,
  name,
  color,
  icon,
  size = "sm",
  asLink = true,
  className,
}: ProjectBadgeProps) {
  if (!slug || !name) return null;
  const Icon = projectIcon(icon);
  const tone = color || "#7280a8";
  const inner = (
    <span
      className={[
        "inline-flex items-center gap-1.5 rounded-full border font-medium tracking-tight transition",
        size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs",
        className || "",
      ].join(" ")}
      style={{
        borderColor: `${tone}55`,
        background: `${tone}14`,
        color: tone,
      }}
    >
      <Icon size={size === "sm" ? 10 : 12} />
      {name}
    </span>
  );
  if (!asLink) return inner;
  return (
    <Link href={`/projects/${slug}`} onClick={(e) => e.stopPropagation()}>
      {inner}
    </Link>
  );
}
