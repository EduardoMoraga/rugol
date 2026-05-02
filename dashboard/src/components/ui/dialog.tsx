"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { ReactNode } from "react";
import { cn } from "@/lib/cn";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;

export function DialogContent({
  children,
  className,
  title,
  description,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
  description?: string;
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in-0" />
      <DialogPrimitive.Content
        className={cn(
          "fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-[92%] max-w-2xl",
          "surface p-6 shadow-xl shadow-black/50",
          className,
        )}
      >
        {title && (
          <DialogPrimitive.Title className="text-lg font-semibold tracking-tight">
            {title}
          </DialogPrimitive.Title>
        )}
        {description && (
          <DialogPrimitive.Description className="text-sm text-[--color-fg-muted] mt-1 mb-4">
            {description}
          </DialogPrimitive.Description>
        )}
        {children}
        <DialogPrimitive.Close
          className="absolute right-4 top-4 text-[--color-fg-muted] hover:text-[--color-fg] focus-visible:outline-none"
          aria-label="Close"
        >
          <X size={16} />
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

export const DialogClose = DialogPrimitive.Close;
