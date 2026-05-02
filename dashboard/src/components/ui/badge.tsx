import { HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type Tone = "running" | "error" | "warn" | "idle" | "accent";

const toneClass: Record<Tone, string> = {
  running: "pill-running",
  error: "pill-error",
  warn: "pill-warn",
  idle: "pill-idle",
  accent: "pill-accent",
};

export function Badge({ tone = "idle", className, ...props }: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return <span className={cn("pill", toneClass[tone], className)} {...props} />;
}
