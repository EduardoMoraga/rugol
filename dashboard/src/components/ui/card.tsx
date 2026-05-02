import { HTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/cn";

export const Card = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement> & { interactive?: boolean }>(
  function Card({ className, interactive, ...props }, ref) {
    return (
      <div
        ref={ref}
        className={cn(
          "surface p-5",
          interactive && "surface-hover cursor-pointer",
          className,
        )}
        {...props}
      />
    );
  },
);

export function CardHeader({ className, ...p }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("space-y-1 mb-4", className)} {...p} />;
}

export function CardTitle({ className, ...p }: HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("text-base font-semibold tracking-tight", className)} {...p} />;
}

export function CardDescription({ className, ...p }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("text-sm text-[--color-fg-muted]", className)} {...p} />;
}

export function CardSection({ className, ...p }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("space-y-2", className)} {...p} />;
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <header className="flex items-start justify-between gap-4 border-b border-[--color-border] pb-5">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="text-sm text-[--color-fg-muted] max-w-2xl">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
    </header>
  );
}

export function Stat({ label, value, hint, accent }: { label: string; value: string | number; hint?: string; accent?: boolean }) {
  return (
    <div className="surface p-4">
      <p className="text-[10px] uppercase tracking-wider text-[--color-fg-muted] font-medium">{label}</p>
      <p
        className={cn(
          "text-2xl font-semibold mt-1.5 font-mono tabular-nums",
          accent && "text-[--color-accent-strong]",
        )}
      >
        {value}
      </p>
      {hint && <p className="text-xs text-[--color-fg-muted] mt-1">{hint}</p>}
    </div>
  );
}
