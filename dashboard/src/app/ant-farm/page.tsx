"use client";

import dynamic from "next/dynamic";

const AntFarmCanvas = dynamic(
  () => import("@/components/ant-farm/ant-farm-canvas").then((m) => m.AntFarmCanvas),
  { ssr: false, loading: () => <p className="p-6 text-sm text-[--color-fg-muted]">Loading the farm…</p> },
);

export default function AntFarmPage() {
  return (
    <div className="p-6 h-screen flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Ant farm</h1>
        <p className="text-sm text-[--color-fg-muted]">Each ant is an agent. Green = working, gray = idle, red = errored.</p>
      </header>
      <div className="flex-1 card overflow-hidden p-0">
        <AntFarmCanvas />
      </div>
    </div>
  );
}
