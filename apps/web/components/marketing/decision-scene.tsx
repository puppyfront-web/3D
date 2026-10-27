"use client";

// DecisionScene — hero follow-up section: the generated "AI team discussion"
// illustration (platform's own image service) + a mock discussion stream that
// shows CEO dispatch → employee reports → HITL confirmation gate. The stream
// is illustrative and labelled as such (no fabricated real data).

import { Reveal } from "@/components/ui/reveal";
import { TeamDiscussionArt } from "@/components/marketing/team-discussion-art";
import { BrainCircuit, SearchCheck, PenLine, ShieldAlert } from "lucide-react";
import type { LucideIcon } from "lucide-react";

type StreamItem = {
  Icon: LucideIcon;
  who: string;
  text: string;
  tone: "ceo" | "member" | "hitl";
};

const STREAM: StreamItem[] = [
  {
    Icon: BrainCircuit,
    who: "AI 大脑 · CEO",
    text: "已拆解任务「企业展厅 3D 数字化方案」：调研 → 策划 → 视觉，依次派发。",
    tone: "ceo",
  },
  {
    Icon: SearchCheck,
    who: "调研专员",
    text: "企业画像完成：客观数据已填充，来源为企业资料与受控联网检索，均可回查。",
    tone: "member",
  },
  {
    Icon: PenLine,
    who: "策划专家",
    text: "策划案草稿 v2 已生成，引用内部案例与知识库；2 处关键信息标记待确认。",
    tone: "member",
  },
  {
    Icon: ShieldAlert,
    who: "人工确认门控",
    text: "预算区间涉及商业承诺，需人工审核后才能进入导出流程。",
    tone: "hitl",
  },
];

export function DecisionScene() {
  return (
    <section className="py-20 lg:py-24 border-t border-outline-variant">
      <div className="max-w-container-max mx-auto px-margin-desktop">
        <div className="grid lg:grid-cols-12 gap-10 lg:gap-14 items-center">
          {/* Illustration panel */}
          <Reveal className="lg:col-span-7">
            <div className="relative bg-surface-container-lowest rounded-2xl border border-outline-variant overflow-hidden">
              <TeamDiscussionArt />
              <span className="absolute bottom-3 right-3 text-[10px] text-on-surface-variant bg-surface-container/90 border border-outline-variant rounded-full px-2.5 py-0.5 backdrop-blur-sm">
                示意插画
              </span>
            </div>
          </Reveal>

          {/* Discussion stream */}
          <div className="lg:col-span-5">
            <Reveal delay={120}>
              <p className="text-[13px] font-medium text-inverse-primary tracking-wide mb-3">
                决策现场
              </p>
              <h2 className="text-3xl md:text-4xl font-semibold text-on-background tracking-tight leading-tight mb-4">
                每个任务，
                <br className="hidden lg:block" />
                都是一场团队讨论
              </h2>
              <p className="text-sm text-on-surface-variant leading-relaxed mb-8">
                AI 大脑主持讨论、员工带来源汇报，你只在关键节点出手。示意如下，实际产出以工作台为准。
              </p>
            </Reveal>

            <div className="space-y-3">
              {STREAM.map((item, i) => (
                <Reveal key={item.who} delay={200 + i * 90}>
                  <div
                    className={`flex gap-3 rounded-xl border p-4 ${
                      item.tone === "hitl"
                        ? "bg-tertiary-container/40 border-tertiary/40"
                        : "bg-surface-container-lowest border-outline-variant"
                    }`}
                  >
                    <div
                      className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                        item.tone === "ceo"
                          ? "bg-primary-fixed text-on-primary-fixed"
                          : item.tone === "hitl"
                            ? "bg-tertiary-container text-on-tertiary-container"
                            : "bg-surface-container-high text-on-surface-variant"
                      }`}
                    >
                      <item.Icon className="h-4 w-4" strokeWidth={1.75} />
                    </div>
                    <div className="min-w-0">
                      <p
                        className={`text-xs font-medium mb-1 ${
                          item.tone === "hitl"
                            ? "text-on-tertiary-container"
                            : "text-on-surface"
                        }`}
                      >
                        {item.who}
                      </p>
                      <p className="text-sm text-on-surface-variant leading-relaxed">
                        {item.text}
                      </p>
                    </div>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
