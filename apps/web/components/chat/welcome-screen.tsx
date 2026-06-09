"use client";

import { useState, useEffect } from "react";
import {
  Building2,
  FileText,
  Image,
  Sparkles,
  Search,
  Download,
  X,
  Palette,
  Rocket,
} from "lucide-react";
import { getVisualStyles } from "@/lib/api";

interface WelcomeScreenProps {
  onSendMessage: (message: string) => void;
}

interface VisualStyle {
  id: string;
  name: string;
  description?: string;
  primary_color?: string;
  accent_color?: string;
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
  {
    icon: Rocket,
    title: "完整方案",
    description: "从企业解析到导出的端到端方案生成",
    message: "帮我设计一套完整的3D幕墙方案",
  },
];

export function WelcomeScreen({ onSendMessage }: WelcomeScreenProps) {
  const [expandedSkill, setExpandedSkill] = useState<string | null>(null);
  const [visualStyles, setVisualStyles] = useState<VisualStyle[]>([]);
  const [stylesLoading, setStylesLoading] = useState(false);

  // Prefetch visual styles when component mounts
  useEffect(() => {
    getVisualStyles()
      .then((res) => {
        if (res.success && res.data) {
          setVisualStyles(res.data);
        }
      })
      .catch(() => {});
  }, []);

  const handleCardClick = (s: (typeof suggestions)[number]) => {
    if (s.title === "视觉方案") {
      setExpandedSkill("visual");
      setStylesLoading(visualStyles.length === 0);
      // Re-fetch in case prefetch failed
      if (visualStyles.length === 0) {
        getVisualStyles()
          .then((res) => {
            if (res.success && res.data) setVisualStyles(res.data);
          })
          .catch(() => {})
          .finally(() => setStylesLoading(false));
      }
    } else {
      onSendMessage(s.message);
    }
  };

  const handleStyleSelect = (styleName: string) => {
    onSendMessage(`生成视觉方案，风格：${styleName}`);
    setExpandedSkill(null);
  };

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
                onClick={() => handleCardClick(s)}
                className={`flex items-start gap-3 p-4 rounded-xl bg-white border transition-all text-left group ${
                  expandedSkill === "visual" && s.title === "视觉方案"
                    ? "border-violet-400 shadow-md ring-1 ring-violet-200"
                    : "border-gray-200 hover:border-[#00D4FF]/40 hover:shadow-md"
                }`}
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

        {/* Visual Style Selection Panel */}
        {expandedSkill === "visual" && (
          <div className="mt-4 p-5 rounded-xl bg-white border border-violet-200 shadow-sm text-left">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Palette className="h-4 w-4 text-violet-500" />
                <span className="text-sm font-medium text-gray-700">
                  选择视觉风格，或直接描述需求
                </span>
              </div>
              <button
                onClick={() => setExpandedSkill(null)}
                className="p-1 rounded-md hover:bg-gray-100 transition-colors"
              >
                <X className="h-4 w-4 text-gray-400" />
              </button>
            </div>

            {stylesLoading ? (
              <div className="flex items-center gap-2 py-2">
                <div className="h-4 w-4 border-2 border-violet-300 border-t-violet-600 rounded-full animate-spin" />
                <span className="text-xs text-gray-500">加载风格列表...</span>
              </div>
            ) : visualStyles.length > 0 ? (
              <div className="flex flex-wrap gap-2 mb-3">
                {visualStyles.map((style) => (
                  <button
                    key={style.id}
                    onClick={() => handleStyleSelect(style.name)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium
                               bg-violet-50 text-violet-700 border border-violet-200
                               hover:bg-violet-100 hover:border-violet-400
                               transition-all hover:scale-105 cursor-pointer"
                  >
                    {style.primary_color && (
                      <span
                        className="w-3 h-3 rounded-full border border-white shadow-sm"
                        style={{ backgroundColor: style.primary_color }}
                      />
                    )}
                    {style.name}
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-400 mb-3">
                暂无风格数据，可直接描述需求
              </p>
            )}

            <button
              onClick={() => {
                onSendMessage("生成视觉方案");
                setExpandedSkill(null);
              }}
              className="text-xs text-gray-500 hover:text-gray-700 underline transition-colors"
            >
              跳过，自定义描述
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
