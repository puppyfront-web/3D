"use client";

import { CheckCircle2, Circle, Loader2, XCircle, SkipForward } from "lucide-react";

interface PlanStep {
  step_id: string;
  name: string;
  status: "pending" | "running" | "completed" | "failed" | "skipped";
}

interface PlanProgressProps {
  steps: PlanStep[];
  domain?: string;
  planId?: string;
}

const statusConfig = {
  pending: {
    icon: Circle,
    color: "text-gray-300",
    bg: "bg-gray-50",
    border: "border-gray-200",
    label: "待执行",
  },
  running: {
    icon: Loader2,
    color: "text-blue-500",
    bg: "bg-blue-50",
    border: "border-blue-200",
    label: "执行中",
  },
  completed: {
    icon: CheckCircle2,
    color: "text-green-500",
    bg: "bg-green-50",
    border: "border-green-200",
    label: "已完成",
  },
  failed: {
    icon: XCircle,
    color: "text-red-500",
    bg: "bg-red-50",
    border: "border-red-200",
    label: "失败",
  },
  skipped: {
    icon: SkipForward,
    color: "text-gray-400",
    bg: "bg-gray-50",
    border: "border-gray-200",
    label: "已跳过",
  },
};

const domainLabels: Record<string, string> = {
  curtain_wall: "幕墙项目",
  exhibition: "展厅项目",
  culture_tourism: "文旅项目",
  multimedia: "多媒体项目",
};

export function PlanProgressBlock({ steps, domain, planId }: PlanProgressProps) {
  const completedCount = steps.filter((s) => s.status === "completed").length;
  const totalCount = steps.length;
  const progress = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded bg-[#1E3A5F]/10 flex items-center justify-center">
            <span className="text-[10px] font-bold text-[#1E3A5F]">📋</span>
          </div>
          <span className="text-sm font-medium text-gray-700">
            方案执行计划
          </span>
          {domain && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-[#00D4FF]/10 text-[#1E3A5F]">
              {domainLabels[domain] || domain}
            </span>
          )}
        </div>
        <span className="text-xs text-gray-400">
          {completedCount}/{totalCount} 完成
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-1.5 bg-gray-100 rounded-full mb-4 overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-[#00D4FF] to-[#1E3A5F] rounded-full transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Steps */}
      <div className="space-y-1.5">
        {steps.map((step, index) => {
          const config = statusConfig[step.status];
          const Icon = config.icon;
          const isLast = index === steps.length - 1;

          return (
            <div key={step.step_id} className="flex items-stretch">
              {/* Step indicator + connector */}
              <div className="flex flex-col items-center mr-3">
                <div
                  className={`w-6 h-6 rounded-full flex items-center justify-center ${config.bg} ${config.border} border`}
                >
                  <Icon
                    className={`h-3.5 w-3.5 ${config.color} ${
                      step.status === "running" ? "animate-spin" : ""
                    }`}
                  />
                </div>
                {!isLast && (
                  <div
                    className={`w-px flex-1 my-0.5 ${
                      step.status === "completed"
                        ? "bg-green-200"
                        : "bg-gray-200"
                    }`}
                  />
                )}
              </div>

              {/* Step content */}
              <div className="flex items-center py-0.5 min-h-[24px]">
                <span
                  className={`text-xs ${
                    step.status === "completed"
                      ? "text-gray-500 line-through"
                      : step.status === "running"
                      ? "text-gray-800 font-medium"
                      : step.status === "failed"
                      ? "text-red-600"
                      : "text-gray-400"
                  }`}
                >
                  {step.name}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
