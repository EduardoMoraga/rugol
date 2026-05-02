"use client";

import { forwardRef, InputHTMLAttributes, TextareaHTMLAttributes, SelectHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

const baseInput =
  "w-full bg-[--color-bg] border border-[--color-border] rounded-md text-sm text-[--color-fg] placeholder:text-[--color-fg-subtle] focus:border-[--color-accent] focus:outline-none focus:ring-2 focus:ring-[--color-accent]/20 transition-colors";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return <input ref={ref} className={cn(baseInput, "h-9 px-3", className)} {...props} />;
  },
);

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...props }, ref) {
    return (
      <textarea
        ref={ref}
        className={cn(baseInput, "px-3 py-2 leading-relaxed font-mono text-[13px]", className)}
        {...props}
      />
    );
  },
);

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...props }, ref) {
    return (
      <select ref={ref} className={cn(baseInput, "h-9 px-3", className)} {...props}>
        {children}
      </select>
    );
  },
);

export function FieldLabel({ children, hint }: { children: React.ReactNode; hint?: string }) {
  return (
    <label className="block text-[11px] uppercase tracking-wider text-[--color-fg-muted] font-medium space-y-1.5">
      <div className="flex items-center justify-between">
        <span>{children}</span>
        {hint && <span className="text-[--color-fg-subtle] normal-case font-normal tracking-normal">{hint}</span>}
      </div>
    </label>
  );
}
