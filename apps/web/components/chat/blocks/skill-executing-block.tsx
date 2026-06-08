"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

interface SkillExecutingBlockProps {
  data: Record<string, unknown>;
}

const SKILL_NAMES: Record<string, string> = {
  company_analysis: "企业解析",
  proposal_generation: "策划案生成",
  visual_prompt: "视觉方案生成",
  image_generation: "图片生成",
  case_retrieval: "案例检索",
  export: "方案导出",
};

const STATUS_MESSAGES: Record<string, string[]> = {
  company_analysis: ["正在分析企业信息", "正在生成六看分析", "正在构建技术架构", "正在整理分析报告"],
  proposal_generation: ["正在检索案例库", "正在生成策划方案", "正在优化方案内容"],
  visual_prompt: ["正在分析视觉需求", "正在生成视觉策略", "正在构建 Prompt"],
  image_generation: ["正在准备生成参数", "正在调用图片生成"],
  case_retrieval: ["正在检索案例库", "正在匹配相似案例"],
  export: ["正在准备导出", "正在生成文件"],
};

/**
 * Animated skill execution status card.
 * Shows skill name, rotating status messages, and a progress bar animation.
 */
export function SkillExecutingBlock({ data }: SkillExecutingBlockProps) {
  const [msgIndex, setMsgIndex] = useState(0);
  const [dots, setDots] = useState("");
  const [elapsed, setElapsed] = useState(0);

  const skillId = (data.skill_id as string) || "";
  const displayName = (data.name as string) || SKILL_NAMES[skillId] || skillId;
  const messages = STATUS_MESSAGES[skillId] || ["正在执行中"];

  // Rotate through status messages
  useEffect(() => {
    const timer = setInterval(() => {
      setMsgIndex((prev) => (prev + 1) % messages.length);
    }, 2500);
    return () => clearInterval(timer);
  }, [messages.length]);

  // Animate dots
  useEffect(() => {
    const timer = setInterval(() => {
      setDots((prev) => (prev.length >= 3 ? "" : prev + "."));
    }, 500);
    return () => clearInterval(timer);
  }, []);

  // Elapsed counter
  useEffect(() => {
    const timer = setInterval(() => {
      setElapsed((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const formatElapsed = (s: number) => {
    if (s < 60) return `${s}s`;
    return `${Math.floor(s / 60)}m ${s % 60}s`;
  };

  return (
    <div className="rounded-lg border border-blue-100 bg-gradient-to-r from-blue-50/80 to-white p-4">
      <div className="flex items-center gap-3">
        {/* Animated spinner */}
        <div className="flex-shrink-0">
          <div className="relative">
            <Loader2 className="h-6 w-6 text-[#1E3A5F] animate-spin" />
            <div className="absolute inset-0 h-6 w-6 rounded-full bg-[#1E3A5F]/10 animate-ping" />
          </div>
        </div>

        {/* Status info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-[#1E3A5F]">{displayName}</span>
            <span className="text-xs text-gray-400">{formatElapsed(elapsed)}</span>
          </div>
          <p className="text-xs text-gray-500 mt-0.5">
            {messages[msgIndex]}{dots}
          </p>
        </div>
      </div>

      {/* Animated progress bar */}
      <div className="mt-3 h-1 bg-blue-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-[#1E3A5F] to-[#00D4FF] rounded-full"
          style={{
            width: "100%",
            animation: "skill-progress 3s ease-in-out infinite",
          }}
        />
      </div>

      {/* Inline keyframes */}
      <style jsx>{`
        @keyframes skill-progress {
          0% { width: 5%; }
          50% { width: 70%; }
          100% { width: 95%; }
        }
      `}</style>
    </div>
  );
}
