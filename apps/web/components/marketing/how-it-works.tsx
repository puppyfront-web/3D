"use client";

// HowItWorks — the 3-step flow section (id="how-it-works", anchored from hero).

import { FileUp, BrainCircuit, UserCheck } from "lucide-react";
import { Reveal } from "@/components/ui/reveal";

const STEPS = [
  {
    no: "01",
    Icon: FileUp,
    title: "描述任务与资料",
    desc: "输入需求、粘贴企业官网链接，或直接上传企业资料。资料优先、搜索补充、最小追问，不需要反复沟通。",
  },
  {
    no: "02",
    Icon: BrainCircuit,
    title: "AI 大脑拆解调度",
    desc: "CEO 角色理解目标后按 SOP 拆解任务，依次派发给调研、策划、视觉等 AI 员工并行执行，过程透明可控。",
  },
  {
    no: "03",
    Icon: UserCheck,
    title: "执行交付与确认",
    desc: "每个板块产出结构化、可编辑的版本；预算、报价等关键内容必须人工确认后才能导出，AI 只建议、人做决定。",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="py-20 lg:py-28 border-t border-outline-variant">
      <div className="max-w-container-max mx-auto px-margin-desktop">
        <Reveal className="max-w-2xl mb-12">
          <p className="text-[13px] font-medium text-inverse-primary tracking-wide mb-3">
            工作方式
          </p>
          <h2 className="text-3xl md:text-4xl font-semibold text-on-background tracking-tight leading-tight">
            从一段任务描述，
            <br className="hidden md:block" />
            到一份可交付方案
          </h2>
        </Reveal>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {STEPS.map(({ no, Icon, title, desc }, i) => (
            <Reveal key={no} delay={i * 100}>
            <div
              className="bg-surface-container-lowest rounded-xl border border-outline-variant p-6 hover:border-primary/50 transition-colors h-full"
            >
              <div className="flex items-center justify-between mb-5">
                <div className="w-10 h-10 rounded-lg bg-primary-fixed text-on-primary-fixed flex items-center justify-center">
                  <Icon className="h-5 w-5" strokeWidth={1.75} />
                </div>
                <span className="font-mono text-sm text-outline">{no}</span>
              </div>
              <h3 className="text-lg font-medium text-on-surface mb-2">
                {title}
              </h3>
              <p className="text-sm text-on-surface-variant leading-relaxed">
                {desc}
              </p>
            </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
