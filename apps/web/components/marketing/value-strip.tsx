"use client";

// ValueStrip — three hairline-divided differentiators (Linear-style compact
// strip, replaces the old ValueGrid bento).

import { ShieldCheck, Workflow, GitBranch } from "lucide-react";
import { Reveal } from "@/components/ui/reveal";

const VALUES = [
  {
    Icon: GitBranch,
    title: "全程可追溯",
    desc: "每条结论标注来源：企业资料、内部案例、知识库或联网检索，引用可回查。",
  },
  {
    Icon: Workflow,
    title: "SOP 化交付",
    desc: "按标准作业流程产出结构化方案，版本自动留痕，支持历史对比与回滚。",
  },
  {
    Icon: ShieldCheck,
    title: "人机协同门控",
    desc: "预算、报价、风险等关键内容强制人工确认，导出前完成完整性检查。",
  },
];

export function ValueStrip() {
  return (
    <section className="py-20 lg:py-24 border-t border-outline-variant">
      <div className="max-w-container-max mx-auto px-margin-desktop">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-0 md:divide-x md:divide-outline-variant">
          {VALUES.map(({ Icon, title, desc }, i) => (
            <Reveal
              key={title}
              delay={i * 100}
              className={
                i === 0
                  ? "md:pr-8"
                  : i === VALUES.length - 1
                    ? "md:pl-8"
                    : "md:px-8"
              }
            >
              <div className="flex items-center gap-2.5 mb-3">
                <Icon className="h-5 w-5 text-primary" strokeWidth={1.75} />
                <h3 className="text-base font-medium text-on-surface">
                  {title}
                </h3>
              </div>
              <p className="text-sm text-on-surface-variant leading-relaxed">
                {desc}
              </p>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
