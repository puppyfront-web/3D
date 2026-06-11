"use client";

import { CheckCircle2, Loader2, XCircle } from "lucide-react";

interface SkillProgressBlockProps {
  data: Record<string, unknown>;
}

export function SkillProgressBlock({ data }: SkillProgressBlockProps) {
  const skillId = String(data.skill_id || "");
  const status = String(data.status || "running");
  const durationMs = Number(data.duration_ms || 0);

  const statusConfig = {
    completed: {
      icon: CheckCircle2,
      color: "text-green-500",
      bg: "bg-green-50",
      label: "完成",
    },
    running: {
      icon: Loader2,
      color: "text-blue-500",
      bg: "bg-blue-50",
      label: "执行中",
    },
    failed: {
      icon: XCircle,
      color: "text-red-500",
      bg: "bg-red-50",
      label: "失败",
    },
  };

  const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.running;
  const Icon = config.icon;

  const skillNames: Record<string, string> = {
    company_analysis: "企业解析",
    proposal_generation: "策划案生成",
    visual_prompt: "视觉方案",
    image_generation: "图片生成",
    case_retrieval: "案例检索",
    export: "方案导出",
  };

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg ${config.bg} text-xs`}>
      <Icon className={`h-3.5 w-3.5 ${config.color} ${status === "running" ? "animate-spin" : ""}`} />
      <span className="font-medium text-gray-700">
        {skillNames[skillId] || skillId}
      </span>
      <span className={`font-medium ${config.color}`}>{config.label}</span>
      {durationMs > 0 && (
        <span className="text-gray-400">{durationMs}ms</span>
      )}
    </div>
  );
}
