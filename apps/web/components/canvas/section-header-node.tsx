"use client";

// SectionHeaderNode — a non-interactive React Flow node rendered above each
// board's nodes, matching the Stitch code_workspace.html section pills:
//   "1. 企业介绍"            → blue pill   + Building2 icon
//   "2. 产品 / 技术 / 应用场景" → green pill  + Boxes icon
//   "3. 未来 / 社会责任"       → orange pill + Globe icon
//
// Synthesised client-side in canvas-store.hydrate() from the group records.
// Non-selectable + non-draggable — purely a visual section anchor.

import { memo } from "react";
import type { Node, NodeProps } from "@xyflow/react";
import type { LucideIcon } from "lucide-react";

/** RF node type carrying the section-header pill data. */
export type SectionHeaderRFNode = Node<{
  groupKey: string;
  title: string;
  index: number; // 1-based section number shown in the pill
  Icon: LucideIcon; // lucide-react icon component
  accent: string; // hex accent
  tintClass: string; // tailwind bg + text classes for the pill
  borderClass: string; // tailwind border class for the pill
}, "sectionHeader">;

function SectionHeaderNodeImpl({ data }: NodeProps<SectionHeaderRFNode>) {
  const Icon = data.Icon;
  return (
    <div className="select-none pointer-events-none">
      <div
        className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg border ${data.tintClass} ${data.borderClass} shadow-sm`}
      >
        <Icon className="h-4 w-4" style={{ color: data.accent }} />
        <span className="font-bold text-sm whitespace-nowrap">
          {data.index}. {data.title}
        </span>
      </div>
    </div>
  );
}

export const SectionHeaderNode = memo(SectionHeaderNodeImpl);
