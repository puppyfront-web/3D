"use client";

import {
  Building2,
  FileText,
  Image,
  Sparkles,
  Search,
  Download,
} from "lucide-react";

interface WelcomeScreenProps {
  onSendMessage: (message: string) => void;
}

const suggestions = [
  {
    icon: Building2,
    title: "企业解析",
    description: "分析企业行业、品牌定位、目标客户",
    message: "帮我进行企业解析",
  },
  {
    icon: FileText,
    title: "策划案生成",
    description: "基于企业画像生成完整策划方案",
    message: "生成策划案",
  },
  {
    icon: Image,
    title: "视觉方案",
    description: "生成视觉策略和 AI 绘图 Prompt",
    message: "生成视觉方案",
  },
  {
    icon: Search,
    title: "案例检索",
    description: "从案例库中检索相似项目案例",
    message: "查找类似案例",
  },
  {
    icon: Download,
    title: "方案导出",
    description: "将策划案导出为 Word 或 PDF",
    message: "导出方案文档",
  },
];

export function WelcomeScreen({ onSendMessage }: WelcomeScreenProps) {
  return (
    <div className="flex-1 min-h-0 overflow-y-auto flex items-center justify-center p-8">
      <div className="max-w-2xl w-full text-center">
        {/* Logo & Title */}
        <div className="flex items-center justify-center gap-3 mb-3">
          <div className="w-12 h-12 rounded-2xl bg-[#00D4FF]/10 flex items-center justify-center">
            <Sparkles className="h-6 w-6 text-[#00D4FF]" />
          </div>
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          3D展示幕墙 AI 专家
        </h1>
        <p className="text-gray-500 text-sm mb-8">
          描述你的项目需求，或选择下方技能快速开始
        </p>

        {/* Skill Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {suggestions.map((s) => {
            const Icon = s.icon;
            return (
              <button
                key={s.title}
                onClick={() => onSendMessage(s.message)}
                className="flex items-start gap-3 p-4 rounded-xl bg-white border border-gray-200 hover:border-[#00D4FF]/40 hover:shadow-md transition-all text-left group"
              >
                <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-[#1E3A5F]/5 flex items-center justify-center group-hover:bg-[#00D4FF]/10 transition-colors">
                  <Icon className="h-4 w-4 text-[#1E3A5F] group-hover:text-[#00D4FF] transition-colors" />
                </div>
                <div>
                  <div className="text-sm font-medium text-gray-800">
                    {s.title}
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {s.description}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
