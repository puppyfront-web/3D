"use client";

// Home / marketing landing — aligns with Stitch code_home.html.
// Composition: TopNav → Hero → ValueGrid → CaseSection → footer strip.

import { CloudCog } from "lucide-react";
import { TopNav } from "@/components/layout/top-nav";
import { HeroSection } from "@/components/marketing/hero-section";
import { ValueGrid } from "@/components/marketing/value-grid";
import { CaseSection } from "@/components/marketing/case-section";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-surface flex flex-col">
      <TopNav variant="marketing" activeHref="/" />
      <main className="w-full flex-1">
        <HeroSection />
        <ValueGrid />
        <CaseSection />

        {/* Footer strip */}
        <section className="py-12 bg-surface-container border-t border-outline-variant">
          <div className="max-w-container-max mx-auto px-margin-desktop grid grid-cols-1 md:grid-cols-2 gap-8 text-on-surface-variant">
            <div className="flex items-start gap-4">
              <div className="w-2 h-2 rounded-full bg-primary mt-2 shrink-0" />
              <p className="text-sm leading-relaxed">
                输入问题或上传资料，系统基于内部知识库检索与 AI 分析，提供可追溯引用的问答与方案建议。
              </p>
            </div>
            <div className="flex items-start gap-4">
              <div className="w-2 h-2 rounded-full bg-primary mt-2 shrink-0" />
              <p className="text-sm leading-relaxed">
                支持资料入库、检索测试与多轮问答，减少反复查找文档的时间，让团队共享可验证的企业知识。
              </p>
            </div>
          </div>
        </section>
      </main>

      <footer className="bg-surface-container-lowest border-t border-outline-variant py-8">
        <div className="max-w-container-max mx-auto px-margin-desktop flex flex-col md:flex-row justify-between items-center gap-8">
          <div className="flex flex-col items-center md:items-start gap-2">
            <div className="font-semibold text-primary flex items-center gap-2">
              <CloudCog className="h-5 w-5" />
              <span>企业知识助手</span>
            </div>
            <p className="text-on-surface-variant text-xs">
              © {new Date().getFullYear()} 企业知识助手. All rights reserved.
            </p>
          </div>
          <nav className="flex gap-8 text-xs">
            <a href="#" className="text-on-surface-variant hover:text-primary hover:underline">
              关于我们
            </a>
            <a href="#" className="text-on-surface-variant hover:text-primary hover:underline">
              服务条款
            </a>
            <a href="#" className="text-on-surface-variant hover:text-primary hover:underline">
              隐私政策
            </a>
            <a href="#" className="text-on-surface-variant hover:text-primary hover:underline">
              联系支持
            </a>
          </nav>
        </div>
      </footer>
    </div>
  );
}
