"use client";

import dynamic from "next/dynamic";
import { PageHeader } from "@/components/ui/card";

const AntFarmCanvas = dynamic(
  () => import("@/components/ant-farm/ant-farm-canvas").then((m) => m.AntFarmCanvas),
  { ssr: false, loading: () => <p className="text-sm text-[--color-fg-muted]">Loading the farm…</p> },
);

export default function AntFarmPage() {
  return (
    <div className="p-8 h-screen flex flex-col gap-4">
      <PageHeader
        title="Ant farm"
        description="Each ant is an agent. Green = working, gray = idle, red = errored. Pulse and wobble follow the live SSE feed."
      />
      <div className="flex-1 surface overflow-hidden p-0 min-h-0">
        <AntFarmCanvas />
      </div>
    </div>
  );
}
