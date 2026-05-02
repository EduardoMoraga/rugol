"use client";

import * as TabsPrimitive from "@radix-ui/react-tabs";
import { cn } from "@/lib/cn";

export const Tabs = TabsPrimitive.Root;

export function TabsList({ className, ...p }: React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn(
        "inline-flex h-9 items-center gap-1 rounded-md border border-[--color-border] bg-[--color-bg-elev] p-1",
        className,
      )}
      {...p}
    />
  );
}

export function TabsTrigger({ className, ...p }: React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "inline-flex h-7 items-center justify-center rounded px-3 text-xs font-medium transition-all",
        "text-[--color-fg-muted] hover:text-[--color-fg]",
        "data-[state=active]:bg-[--color-bg-elev-2] data-[state=active]:text-[--color-fg]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[--color-accent]",
        className,
      )}
      {...p}
    />
  );
}

export const TabsContent = TabsPrimitive.Content;
