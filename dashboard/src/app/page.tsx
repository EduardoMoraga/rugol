import { OverviewGrid } from "@/components/dashboard/overview-grid";
import { LiveFeed } from "@/components/dashboard/live-feed";
import { AntFarmPreview } from "@/components/ant-farm/ant-farm-preview";

export default function Page() {
  return (
    <div className="p-6 space-y-6">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Operations</h1>
          <p className="text-sm text-[--color-fg-muted]">
            Live status across every registered agent.
          </p>
        </div>
      </header>

      <OverviewGrid />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <AntFarmPreview />
        </div>
        <div>
          <LiveFeed />
        </div>
      </div>
    </div>
  );
}
