import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Sidebar } from "@/components/layout/sidebar";
import { ChatProvider } from "@/lib/chat-context";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "3D提案工作台",
  description: "智能3D可视化方案生成与管理平台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-CN"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
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
        </TooltipProvider>
      </body>
    </html>
  );
}
