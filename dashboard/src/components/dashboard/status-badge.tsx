import { Badge } from "@/components/ui/badge";

const tone = (status: string) => {
  if (status === "running") return "running" as const;
  if (status === "error" || status === "failed") return "error" as const;
  if (status === "warn" || status === "cancelled") return "warn" as const;
  if (status === "completed") return "running" as const;
  return "idle" as const;
};

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={tone(status)}>{status}</Badge>;
}
