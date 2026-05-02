import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import { Providers } from "./providers";
import { NavRail } from "@/components/dashboard/nav-rail";

export const metadata: Metadata = {
  title: "Rogologo — Agent Operations Center",
  description: "Open-source operations center for Claude Code agents.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="min-h-screen flex">
        <Providers>
          <NavRail />
          <main className="flex-1 min-w-0">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
