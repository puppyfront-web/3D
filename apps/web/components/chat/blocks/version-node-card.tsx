"use client";

import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  RotateCcw,
  GitBranch,
  Image as ImageIcon,
  FileText,
  Eye,
  CheckSquare,
  Clock,
} from "lucide-react";
import type { VersionNode } from "@/types";

interface VersionNodeCardProps {
  node: VersionNode;
  isActive: boolean;
  onRollback?: (nodeId: string) => void;
  onBranch?: (nodeId: string) => void;
}

export function VersionNodeCard({
  node,
  isActive,
  onRollback,
  onBranch,
}: VersionNodeCardProps) {
  const [expanded, setExpanded] = useState(isActive);

  const hasArtifacts =
    !!node.visual_strategy ||
    !!node.positive_prompt ||
    !!node.image_url ||
    (node.quality_check && node.quality_check.length > 0);

  const triggerLabels: Record<string, string> = {
    initial: "初始生成",
    modify: "修改",
    branch: "分支",
    rollback: "回滚",
  };

  return (
    <div
      className={`rounded-lg border overflow-hidden ${
        isActive
          ? "border-[#00D4FF]/50 bg-[#00D4FF]/5"
          : "border-gray-200 bg-white"
      }`}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-50/50 transition-colors"
      >
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 text-gray-400 shrink-0" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-gray-400 shrink-0" />
        )}

        <span className="text-sm font-medium text-gray-800">
          {node.version_label}
        </span>

        <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">
          {triggerLabels[node.trigger] || node.trigger}
        </span>

        {isActive && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#00D4FF]/20 text-[#00D4FF] font-medium">
            当前
          </span>
        )}

        <div className="flex-1" />

        <div className="flex items-center gap-1 text-[10px] text-gray-400">
          <Clock className="h-3 w-3" />
          {new Date(node.created_at).toLocaleString("zh-CN", {
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-3 pb-3 space-y-2 border-t border-gray-100 pt-2">
          {/* User instruction */}
          {node.user_instruction && (
            <div className="text-xs text-gray-500 italic">
              &ldquo;{node.user_instruction}&rdquo;
            </div>
          )}

          {/* Artifacts */}
          {hasArtifacts && (
            <div className="grid grid-cols-2 gap-1.5">
              {node.visual_strategy && (
                <div className="flex items-center gap-1.5 text-xs text-gray-600 bg-gray-50 rounded px-2 py-1.5">
                  <Eye className="h-3 w-3 text-violet-500" />
                  <span>视觉策略</span>
                </div>
              )}
              {node.positive_prompt && (
                <div className="flex items-center gap-1.5 text-xs text-gray-600 bg-gray-50 rounded px-2 py-1.5">
                  <FileText className="h-3 w-3 text-blue-500" />
                  <span>Prompt</span>
                </div>
              )}
              {node.image_url && (
                <div className="flex items-center gap-1.5 text-xs text-gray-600 bg-gray-50 rounded px-2 py-1.5">
                  <ImageIcon className="h-3 w-3 text-emerald-500" />
                  <span>生成图片</span>
                </div>
              )}
              {node.quality_check && node.quality_check.length > 0 && (
                <div className="flex items-center gap-1.5 text-xs text-gray-600 bg-gray-50 rounded px-2 py-1.5">
                  <CheckSquare className="h-3 w-3 text-amber-500" />
                  <span>质量检查</span>
                </div>
              )}
            </div>
          )}

          {/* Citations count */}
          {node.rag_citations.length > 0 && (
            <div className="text-[10px] text-gray-400">
              引用 {node.rag_citations.length} 条来源
            </div>
          )}

          {/* Action buttons */}
          {!isActive && (
            <div className="flex gap-2 pt-1">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onRollback?.(node.node_id);
                }}
                className="flex items-center gap-1 px-2 py-1 text-xs rounded border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors"
              >
                <RotateCcw className="h-3 w-3" />
                回滚至此版本
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onBranch?.(node.node_id);
                }}
                className="flex items-center gap-1 px-2 py-1 text-xs rounded border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors"
              >
                <GitBranch className="h-3 w-3" />
                从此版本创建分支
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
