import type { Metadata } from "next";
import "./globals.css";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import { Sidebar } from "@/components/layout/sidebar";
import { ChatProvider } from "@/lib/chat-context";

export const metadata: Metadata = {
  title: "花生ONE",
  description: "展厅·文旅 AI 专家工作台 — 企业展厅、科技文旅、多媒体展项方案生成与管理平台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-CN"
      className="h-full antialiased"
    >
      <body className="min-h-full h-full">
        <TooltipProvider>
          <ChatProvider>
            <div className="flex h-screen">
              <Sidebar />
              <main className="flex-1 h-full bg-[#F5F7FA] overflow-hidden">
                {children}
              </main>
            </div>
          </ChatProvider>
          <Toaster position="top-right" richColors closeButton duration={6000} />
        </TooltipProvider>
      </body>
    </html>
  );
}
