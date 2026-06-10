"use client";

import { useState } from "react";
import { ArrowLeftRight, Image as ImageIcon, Eye } from "lucide-react";
import type { VersionNode } from "@/types";

interface VersionCompareViewProps {
  nodes: Record<string, VersionNode>;
  nodeIds: string[];
}

export function VersionCompareView({
  nodes,
  nodeIds,
}: VersionCompareViewProps) {
  const [nodeA, setNodeA] = useState<string>(nodeIds[0] || "");
  const [nodeB, setNodeB] = useState<string>(nodeIds[1] || nodeIds[0] || "");

  if (nodeIds.length < 2) return null;

  const left = nodes[nodeA];
  const right = nodes[nodeB];

  /** Extract a readable concept from visual_strategy */
  const getStrategyLabel = (node: VersionNode | undefined): string | null => {
    if (!node?.visual_strategy) return null;
    const s = node.visual_strategy as Record<string, unknown>;
    if (typeof s.concept === "string") return s.concept;
    if (typeof s.style === "string") return s.style;
    return "已规划";
  };

  return (
    <div className="space-y-3">
      {/* Selectors */}
      <div className="flex items-center gap-2">
        <select
          value={nodeA}
          onChange={(e) => setNodeA(e.target.value)}
          className="flex-1 text-xs border border-gray-200 rounded-lg px-2 py-1.5 bg-white text-gray-700 focus:outline-none focus:border-[#00D4FF]"
        >
          {nodeIds.map((id) => (
            <option key={id} value={id}>
              {nodes[id]?.version_label || id}
            </option>
          ))}
        </select>

        <ArrowLeftRight className="h-4 w-4 text-gray-400 shrink-0" />

        <select
          value={nodeB}
          onChange={(e) => setNodeB(e.target.value)}
          className="flex-1 text-xs border border-gray-200 rounded-lg px-2 py-1.5 bg-white text-gray-700 focus:outline-none focus:border-[#00D4FF]"
        >
          {nodeIds.map((id) => (
            <option key={id} value={id}>
              {nodes[id]?.version_label || id}
            </option>
          ))}
        </select>
      </div>

      {/* Side-by-side comparison */}
      {left && right && (
        <div className="grid grid-cols-2 gap-3">
          {/* Left */}
          <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
            <div className="text-xs font-medium text-gray-600 px-3 py-2 bg-gray-50 border-b border-gray-100">
              {left.version_label}
            </div>
            <div className="p-3 space-y-2">
              <CompareField
                icon={<Eye className="h-3 w-3 text-violet-500" />}
                label="策略"
                value={getStrategyLabel(left)}
              />
              <CompareField
                icon={<ImageIcon className="h-3 w-3 text-emerald-500" />}
                label="图片"
                value={left.image_url ? "已生成" : null}
              />
            </div>
          </div>

          {/* Right */}
          <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
            <div className="text-xs font-medium text-gray-600 px-3 py-2 bg-gray-50 border-b border-gray-100">
              {right.version_label}
            </div>
            <div className="p-3 space-y-2">
              <CompareField
                icon={<Eye className="h-3 w-3 text-violet-500" />}
                label="策略"
                value={getStrategyLabel(right)}
              />
              <CompareField
                icon={<ImageIcon className="h-3 w-3 text-emerald-500" />}
                label="图片"
                value={right.image_url ? "已生成" : null}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CompareField({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | null;
}) {
  return (
    <div className="flex items-start gap-1.5">
      <div className="mt-0.5 shrink-0">{icon}</div>
      <div className="min-w-0">
        <div className="text-[10px] text-gray-400">{label}</div>
        <div className="text-xs text-gray-700 truncate">
          {value || "—"}
        </div>
      </div>
    </div>
  );
}
