import type { Metadata, Viewport } from "next";
import "./globals.css";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";

export const metadata: Metadata = {
  title: {
    default: "AI 团队平台 — 自建 AI 团队，AI 大脑（CEO）统筹交付",
    template: "%s · AI 团队平台",
  },
  description:
    "自建 AI 团队 · AI 大脑（CEO）统一调度 — 调研、策划、视觉多 Agent 协作交付，关键节点人工确认，产出全程可追溯。",
  applicationName: "AI 团队平台",
  openGraph: {
    title: "AI 团队平台 — 自建 AI 团队，AI 大脑（CEO）统筹交付",
    description:
      "调研、策划、视觉多 Agent 协作交付，关键节点人工确认，产出全程可追溯。",
    type: "website",
    locale: "zh_CN",
  },
};

export const viewport: Viewport = {
  themeColor: "#010102",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Font: --font-inter is defined in globals.css as a system font stack
  // (Inter → ui-sans-serif → system-ui → …). We intentionally do NOT use
  // next/font/google here — that fetches Google Fonts at build time, which
  // fails in CN environments without Google access and breaks the build.
  return (
    <html lang="zh-CN" className="h-full antialiased">
      <body className="min-h-full h-full">
        <TooltipProvider>
          {/*
            Layout chrome is intentionally bare here — each route group
            (marketing / workspace / admin) renders its own TopNav in its
            group layout. The global dark sidebar was removed per the
            Enterprise Blueprint redesign (every page owns its own top nav).
          */}
          {children}
          <Toaster position="top-right" richColors closeButton duration={6000} />
        </TooltipProvider>
      </body>
    </html>
  );
}
