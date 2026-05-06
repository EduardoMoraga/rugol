"use client";

import { create } from "zustand";
import { CheckCircle2, AlertCircle, AlertTriangle, Info, X } from "lucide-react";
import { useEffect } from "react";

type ToastTone = "success" | "error" | "warning" | "info";

interface ToastItem {
  id: number;
  tone: ToastTone;
  title: string;
  body?: string;
}

interface Store {
  items: ToastItem[];
  push: (t: Omit<ToastItem, "id">) => void;
  dismiss: (id: number) => void;
}

let nextId = 1;

const useToastStore = create<Store>((set) => ({
  items: [],
  push: (t) => {
    const id = nextId++;
    set((s) => ({ items: [...s.items, { id, ...t }] }));
    setTimeout(() => set((s) => ({ items: s.items.filter((x) => x.id !== id) })), 4500);
  },
  dismiss: (id) => set((s) => ({ items: s.items.filter((x) => x.id !== id) })),
}));

export function toast(t: Omit<ToastItem, "id">) {
  useToastStore.getState().push(t);
}

const ICON: Record<ToastTone, React.ComponentType<{ size?: number; className?: string }>> = {
  success: CheckCircle2,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

const COLOR: Record<ToastTone, string> = {
  success: "text-[--color-success]",
  error: "text-[--color-error]",
  warning: "text-yellow-400",
  info: "text-[--color-accent-strong]",
};

export function Toaster() {
  const { items, dismiss } = useToastStore();

  // Avoid hydration mismatch by mounting only after first render.
  useEffect(() => {}, []);

  return (
    <div className="fixed bottom-4 right-4 z-[60] space-y-2 pointer-events-none">
      {items.map((t) => {
        const Icon = ICON[t.tone];
        return (
          <div
            key={t.id}
            role="status"
            className="surface px-4 py-3 pr-10 min-w-[260px] max-w-sm shadow-xl shadow-black/40 pointer-events-auto relative"
          >
            <div className="flex items-start gap-3">
              <Icon size={16} className={COLOR[t.tone]} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium leading-tight">{t.title}</p>
                {t.body && <p className="text-xs text-[--color-fg-muted] mt-0.5">{t.body}</p>}
              </div>
            </div>
            <button
              onClick={() => dismiss(t.id)}
              className="absolute top-3 right-3 text-[--color-fg-muted] hover:text-[--color-fg]"
            >
              <X size={12} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
