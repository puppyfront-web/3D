"use client";

import type { ProjectStatus, ReviewStatus, Priority } from "@/types";

const statusConfig: Record<
  ProjectStatus,
  { label: string; color: string; bgColor: string }
> = {
  draft: { label: "草稿", color: "text-gray-600", bgColor: "bg-gray-100" },
  in_progress: { label: "进行中", color: "text-[#3B82F6]", bgColor: "bg-blue-50" },
  company_analysis: { label: "企业分析", color: "text-[#8B5CF6]", bgColor: "bg-purple-50" },
  proposal_draft: { label: "方案撰写", color: "text-[#F59E0B]", bgColor: "bg-amber-50" },
  visual_design: { label: "视觉设计", color: "text-[#EC4899]", bgColor: "bg-pink-50" },
  review: { label: "审核中", color: "text-[#00D4FF]", bgColor: "bg-cyan-50" },
  approved: { label: "已通过", color: "text-[#10B981]", bgColor: "bg-green-50" },
  exported: { label: "已导出", color: "text-[#1E3A5F]", bgColor: "bg-blue-50" },
  archived: { label: "已归档", color: "text-gray-500", bgColor: "bg-gray-100" },
};

const priorityConfig: Record<Priority, { label: string; color: string; bgColor: string }> = {
  high: { label: "高", color: "text-[#EF4444]", bgColor: "bg-red-50" },
  medium: { label: "中", color: "text-[#F59E0B]", bgColor: "bg-amber-50" },
  low: { label: "低", color: "text-gray-500", bgColor: "bg-gray-100" },
};

const reviewStatusConfig: Record<
  ReviewStatus,
  { label: string; color: string; bgColor: string }
> = {
  pass: { label: "通过", color: "text-[#10B981]", bgColor: "bg-green-50" },
  warning: { label: "警告", color: "text-[#F59E0B]", bgColor: "bg-amber-50" },
  fail: { label: "不通过", color: "text-[#EF4444]", bgColor: "bg-red-50" },
  pending: { label: "待审核", color: "text-gray-500", bgColor: "bg-gray-100" },
};

export function StatusTag({ status }: { status: ProjectStatus }) {
  const config = statusConfig[status];
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${config.color} ${config.bgColor}`}
    >
      {config.label}
    </span>
  );
}

export function PriorityTag({ priority }: { priority: Priority }) {
  const config = priorityConfig[priority];
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${config.color} ${config.bgColor}`}
    >
      {config.label}
    </span>
  );
}

export function ReviewStatusTag({ status }: { status: ReviewStatus }) {
  const config = reviewStatusConfig[status];
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${config.color} ${config.bgColor}`}
    >
      {config.label}
    </span>
  );
}
