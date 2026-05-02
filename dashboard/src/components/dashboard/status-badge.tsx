import { cn } from "@/lib/cn";

const map: Record<string, string> = {
  running: "badge-running",
  idle: "badge-idle",
  error: "badge-error",
  failed: "badge-error",
  completed: "badge-running",
  cancelled: "badge-warn",
  offline: "badge-idle",
};

export function StatusBadge({ status }: { status: string }) {
  return <span className={cn("badge", map[status] ?? "badge-idle")}>{status}</span>;
}
