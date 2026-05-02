"use client";

import dynamic from "next/dynamic";
import Link from "next/link";

const AntFarmCanvas = dynamic(
  () => import("./ant-farm-canvas").then((m) => m.AntFarmCanvas),
  { ssr: false, loading: () => <p className="p-6 text-sm text-[--color-fg-muted]">Loading the farm…</p> },
);

export function AntFarmPreview() {
  return (
    <div className="card p-0 overflow-hidden h-[420px] flex flex-col">
      <header className="flex items-center justify-between p-4 border-b border-[--color-border]">
        <div>
          <h3 className="font-semibold">Ant farm</h3>
          <p className="text-xs text-[--color-fg-muted]">A live colony of your agents.</p>
        </div>
        <Link href="/ant-farm" className="text-xs text-[--color-fg-muted] hover:text-[--color-fg]">
          Full view →
        </Link>
      </header>
      <div className="flex-1 min-h-0">
        <AntFarmCanvas />
      </div>
    </div>
  );
}
