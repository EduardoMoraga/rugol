"use client";

import { forwardRef, ButtonHTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

const button = cva(
  "inline-flex items-center justify-center gap-2 rounded-md text-sm font-medium transition-all whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[--color-accent] disabled:opacity-50 disabled:cursor-not-allowed",
  {
    variants: {
      variant: {
        primary:
          "bg-[--color-accent] text-[--color-accent-fg] hover:bg-[--color-accent-strong] shadow-sm shadow-[--color-accent]/20",
        secondary:
          "bg-[--color-bg-elev] text-[--color-fg] border border-[--color-border] hover:border-[--color-border-strong] hover:bg-[--color-bg-elev-2]",
        ghost:
          "text-[--color-fg-muted] hover:text-[--color-fg] hover:bg-[--color-bg-elev]",
        danger:
          "bg-[--color-error]/10 text-[--color-error] border border-[--color-error]/30 hover:bg-[--color-error]/20",
        outline:
          "border border-[--color-border] text-[--color-fg-muted] hover:border-[--color-border-strong] hover:text-[--color-fg]",
      },
      size: {
        sm: "h-7 px-2.5 text-xs",
        md: "h-9 px-4",
        lg: "h-10 px-5",
        icon: "h-8 w-8",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof button> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, ...props },
  ref,
) {
  return <button ref={ref} className={cn(button({ variant, size }), className)} {...props} />;
});
