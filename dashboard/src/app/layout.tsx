import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import { Providers } from "./providers";
import { NavRail } from "@/components/dashboard/nav-rail";
import { Toaster } from "@/components/ui/toast";

export const metadata: Metadata = {
  title: "TeamAgent — Increxa",
  description: "Centro de operaciones de agentes IA para Market Qualification.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="min-h-screen flex">
        <Providers>
          <NavRail />
          <main className="flex-1 min-w-0 overflow-x-hidden">{children}</main>
          <Toaster />
        </Providers>
      </body>
    </html>
  );
}
