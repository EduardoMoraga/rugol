import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-jetbrains-mono",
});
import { Providers } from "./providers";
import { NavRail } from "@/components/dashboard/nav-rail";
import { Toaster } from "@/components/ui/toast";

export const metadata: Metadata = {
  title: "Rugol — Agent Operations Center",
  description: "Open-source operations center for Claude Code agents.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${inter.variable} ${jetbrainsMono.variable}`}>
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
