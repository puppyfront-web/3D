"use client";

// CtaBanner — closing call-to-action panel (Linear cta-banner style).

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Reveal } from "@/components/ui/reveal";

export function CtaBanner() {
  return (
    <section className="py-20 lg:py-28 border-t border-outline-variant">
      <div className="max-w-container-max mx-auto px-margin-desktop">
        <Reveal>
        <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant px-6 py-14 md:p-16 text-center">
          <h2 className="text-3xl md:text-4xl font-semibold text-on-background tracking-tight mb-4">
            把下一个方案，交给 AI 团队
          </h2>
          <p className="text-base text-on-surface-variant max-w-xl mx-auto mb-8 leading-relaxed">
            描述任务、上传资料，其余的交给 AI 大脑与它的团队。你只需要在关键节点做决定。
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <Link
              href="/workspace/projects/new"
              className="inline-flex items-center gap-2 bg-primary text-on-primary px-6 py-3 rounded-lg text-sm font-medium hover:bg-primary-container active:scale-95 transition-all"
            >
              创建团队任务
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/admin/cases"
              className="inline-flex items-center gap-2 bg-surface-container-low text-on-surface border border-outline-variant px-6 py-3 rounded-lg text-sm font-medium hover:bg-surface-container transition-colors"
            >
              查看案例
            </Link>
          </div>
        </div>
        </Reveal>
      </div>
    </section>
  );
}
