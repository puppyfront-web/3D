"use client";

import type { ProjectStatus, Priority } from "@/types";
import {
  StatusBadge,
  type StatusBadgeVariant,
} from "@/components/ui/status-badge";

// 企业分析/方案撰写/视觉设计是 Canvas 时代的流水线阶段（已冻结），
// 统一降为中性色，只保留语义状态（进行/审核/通过/归档）的彩色编码。
const statusConfig: Record<ProjectStatus, { label: string; variant: StatusBadgeVariant }> = {
  draft: { label: "草稿", variant: "neutral" },
  in_progress: { label: "进行中", variant: "brand" },
  company_analysis: { label: "企业分析", variant: "neutral" },
  proposal_draft: { label: "方案撰写", variant: "neutral" },
  visual_design: { label: "视觉设计", variant: "neutral" },
  review: { label: "审核中", variant: "info" },
  approved: { label: "已通过", variant: "success" },
  exported: { label: "已导出", variant: "success" },
  archived: { label: "已归档", variant: "neutral" },
};

const priorityConfig: Record<Priority, { label: string; variant: StatusBadgeVariant }> = {
  high: { label: "高", variant: "error" },
  medium: { label: "中", variant: "warning" },
  low: { label: "低", variant: "neutral" },
};

export function StatusTag({ status }: { status: ProjectStatus }) {
  const config = statusConfig[status] ?? statusConfig.draft;
  return <StatusBadge variant={config.variant}>{config.label}</StatusBadge>;
}

export function PriorityTag({ priority }: { priority: Priority }) {
  const config = priorityConfig[priority] ?? priorityConfig.low;
  return <StatusBadge variant={config.variant}>{config.label}</StatusBadge>;
}
