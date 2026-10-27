"use client";

// TeamRoster — the four built-in AI employees. Roles map 1:1 to real
// pipeline agents / skills (company_analysis + web_search,
// proposal_generation, visual_prompt + image_generation) — presentation
// only, no invented capabilities.

import { BrainCircuit, SearchCheck, PenLine, Palette } from "lucide-react";
import { Reveal } from "@/components/ui/reveal";

const ROSTER = [
  {
    Icon: BrainCircuit,
    role: "AI 大脑 · CEO",
    duty: "理解任务目标，拆解并派发给团队成员；验收产出、控制预算与轮次，关键分歧升级人工决策。",
    skills: ["任务拆解", "调度", "验收"],
  },
  {
    Icon: SearchCheck,
    role: "调研专员",
    duty: "解析企业资料与公开信息，受控联网检索补充客观数据，产出可溯源的企业画像。",
    skills: ["企业解析", "联网检索"],
  },
  {
    Icon: PenLine,
    role: "策划专家",
    duty: "基于 SOP 与方案模板撰写结构化策划案，引用真实案例与知识库，缺失信息显式标记待确认。",
    skills: ["方案生成", "章节撰写"],
  },
  {
    Icon: Palette,
    role: "视觉设计师",
    duty: "制定视觉策略并生成正负向 Prompt，产出视觉概念图，支持版本分支与对比。",
    skills: ["视觉策略", "概念图"],
  },
];

export function TeamRoster() {
  return (
    <section className="py-20 lg:py-28 border-t border-outline-variant">
      <div className="max-w-container-max mx-auto px-margin-desktop">
        <div className="flex flex-wrap justify-between items-end gap-6 mb-12">
          <div className="max-w-2xl">
            <p className="text-[13px] font-medium text-inverse-primary tracking-wide mb-3">
              团队阵容
            </p>
            <h2 className="text-3xl md:text-4xl font-semibold text-on-background tracking-tight leading-tight">
              内置四位 AI 员工，各司其职
            </h2>
          </div>
          <p className="text-sm text-on-surface-variant max-w-sm leading-relaxed">
            像管理真实团队一样管理 AI 员工：能力来自真实注册的 Skill 与
            Tool，每一步执行都有日志与溯源。
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {ROSTER.map(({ Icon, role, duty, skills }, i) => (
            <Reveal key={role} delay={i * 80} className="h-full">
            <div
              className="bg-surface-container-lowest rounded-xl border border-outline-variant p-6 flex flex-col gap-4 hover:border-primary/50 transition-colors h-full"
            >
              <div className="w-11 h-11 rounded-lg bg-primary-fixed text-on-primary-fixed flex items-center justify-center">
                <Icon className="h-5 w-5" strokeWidth={1.75} />
              </div>
              <h3 className="text-base font-medium text-on-surface">{role}</h3>
              <p className="text-sm text-on-surface-variant leading-relaxed flex-1">
                {duty}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {skills.map((s) => (
                  <span
                    key={s}
                    className="text-[11px] text-on-surface-variant bg-surface-container-low border border-outline-variant rounded-full px-2.5 py-0.5"
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
