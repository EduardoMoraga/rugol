"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

const AntFarmCanvas = dynamic(
  () => import("./ant-farm-canvas").then((m) => m.AntFarmCanvas),
  { ssr: false, loading: () => <p className="p-6 text-sm text-[--color-fg-muted]">Loading…</p> },
);

export function AntFarmPreview() {
  return (
    <div className="surface h-[420px] flex flex-col p-0 overflow-hidden">
      <header className="flex items-center justify-between px-4 py-3 border-b border-[--color-border]">
        <div>
          <h3 className="text-sm font-semibold tracking-tight">Ant farm</h3>
          <p className="text-xs text-[--color-fg-muted]">A live colony of your agents.</p>
        </div>
        <Link
          href="/ant-farm"
          className="text-xs text-[--color-fg-muted] hover:text-[--color-fg] inline-flex items-center gap-1"
        >
          Full view <ArrowUpRight size={11} />
        </Link>
      </header>
      <div className="flex-1 min-h-0">
        <AntFarmCanvas />
      </div>
    </div>
  );
}
