import type { Metadata } from "next";
import "./globals.css";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";

export const metadata: Metadata = {
  title: "企业知识助手",
  description: "内部知识库与可追溯问答 — 资料入库、检索测试、多轮问答",
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
