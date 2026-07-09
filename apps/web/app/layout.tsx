import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "花生ONE",
  description: "企业3D数字化整体解决方案售前助手 — AI + SOP + 企业资料 + 网络搜索",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" className={`h-full antialiased ${inter.variable}`}>
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
