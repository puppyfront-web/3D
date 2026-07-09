// ValueGrid — the four-card value proposition section.
// Aligns with Stitch code_home.html "Value Proposition & Grid Section".

import type { LucideIcon } from "lucide-react";
import {
  SearchCheck,
  Workflow,
  RefreshCcw,
  Users,
  Wrench,
} from "lucide-react";

const VALUES: {
  Icon: LucideIcon;
  title: string;
  desc: string;
  tint: string;
  onTint: string;
}[] = [
  {
    Icon: SearchCheck,
    title: "高效调研",
    desc: "多源信息全方位自动整理，大幅节省调研时间，提升效率超过70%。",
    tint: "bg-primary-fixed",
    onTint: "text-primary",
  },
  {
    Icon: Workflow,
    title: "结构化输出",
    desc: "基于成熟的标准SOP框架，确保方案逻辑严密，专业度对齐行业标杆。",
    tint: "bg-secondary-fixed",
    onTint: "text-secondary",
  },
  {
    Icon: RefreshCcw,
    title: "持续迭代",
    desc: "每次更新自动生成新版本。支持版本追溯，记录全流程修改历史。",
    tint: "bg-tertiary-fixed",
    onTint: "text-tertiary",
  },
  {
    Icon: Users,
    title: "团队协同",
    desc: "知识沉淀与复用。提升交付一致性，新成员可快速接手历史项目。",
    tint: "bg-primary-fixed",
    onTint: "text-primary",
  },
];

export function ValueGrid() {
  return (
    <section className="py-20 bg-surface border-y border-outline-variant">
      <div className="max-w-container-max mx-auto px-margin-desktop">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-gutter items-start">
          {/* Left intro */}
          <div className="lg:col-span-4 space-y-4 pr-0 lg:pr-8">
            <div className="inline-flex items-center gap-2 text-primary font-bold px-3 py-1 bg-primary-fixed rounded-full w-fit">
              <Wrench className="h-4 w-4" />
              <span className="text-xs">产品简介</span>
            </div>
            <h2 className="text-2xl font-semibold text-on-background leading-snug">
              花生ONE 售前助手，帮助售前团队快速获取企业信息、梳理需求，生成结构化方案。
            </h2>
            <p className="text-on-surface-variant text-sm leading-relaxed">
              让每一次客户沟通更高效、更专业、更有说服力。通过AI自动识别客户痛点并匹配最佳3D数字化解决方案。
            </p>
          </div>

          {/* Right bento grid */}
          <div className="lg:col-span-8">
            <h3 className="text-lg font-semibold text-on-background mb-8 flex items-center gap-2">
              为您带来的价值
              <div className="flex-grow border-t border-outline-variant ml-4" />
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {VALUES.map((v) => {
                const Icon = v.Icon;
                return (
                  <div
                    key={v.title}
                    className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant hover:border-primary transition-all group shadow-sm"
                  >
                    <div
                      className={`w-12 h-12 ${v.tint} rounded-lg flex items-center justify-center mb-4 ${v.onTint} group-hover:scale-110 transition-transform`}
                    >
                      <Icon className="h-6 w-6" strokeWidth={1.75} />
                    </div>
                    <h4 className="text-lg font-semibold mb-2">{v.title}</h4>
                    <p className="text-on-surface-variant text-sm leading-relaxed">
                      {v.desc}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
