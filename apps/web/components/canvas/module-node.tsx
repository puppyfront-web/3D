"use client";

// ModuleNode — custom React Flow node type, colour-coded by board.
//
// Board palette + status mapping now imported from lib/design-tokens.ts
// (single source of truth — the viewport's BoardLegend reads the same map).

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { memo } from "react";

import type { RFNode } from "@/lib/canvas-store";
import { useCanvasStore } from "@/lib/canvas-store";
import { boardColour, statusDot, STATUS_LABEL } from "@/lib/design-tokens";
import { cn } from "@/lib/utils";

function ModuleNodeImpl({ id, data, selected }: NodeProps<RFNode>) {
  const selectNode = useCanvasStore((s) => s.selectNode);
  const isReadOnly = useCanvasStore((s) => s.isReadOnly);

  const status = (data.status as string) || "draft";
  const board = boardColour(data.groupKey);

  return (
    <div
      onClick={() => selectNode(id)}
      className={cn(
        "group relative w-[200px] rounded-lg bg-surface-container-lowest shadow-sm border border-outline-variant transition hover:shadow-md cursor-pointer overflow-hidden",
      )}
      style={selected ? { boxShadow: `0 0 0 2px ${board.accent}` } : undefined}
    >
      {/* Coloured left accent stripe */}
      <div
        className="absolute left-0 top-0 bottom-0 w-1"
        style={{ background: board.accent }}
      />

      <Handle
        type="target"
        position={Position.Top}
        className="!h-2 !w-2 !bg-outline-variant"
      />

      <div className="pl-3.5 pr-3 py-2.5">
        <div className="flex items-start justify-between gap-2 mb-1.5">
          <span className="text-[13px] font-medium text-on-surface leading-tight">
            {data.title}
          </span>
          {/* Status dot */}
          <span
            className="mt-1 h-1.5 w-1.5 rounded-full shrink-0"
            style={{ background: statusDot(status) }}
          />
        </div>

        {/* Content preview — show the first planning item so users can see at
            a glance what's been filled. Draft nodes show a "待填充" hint. */}
        {data.preview ? (
          <p className="text-[11px] text-on-surface-variant leading-snug line-clamp-2 mb-1.5">
            {data.preview}
          </p>
        ) : (
          status === "draft" && (
            <p className="text-[11px] text-outline italic leading-snug mb-1.5">
              待填充
            </p>
          )
        )}

        <div className="flex items-center gap-1.5 flex-wrap">
          <span className={cn("px-1.5 py-0.5 rounded text-[10px] font-medium", board.pill)}>
            {STATUS_LABEL[status] ?? status}
          </span>
          {data.planningCount ? (
            <span className="text-[10px] text-outline">
              {data.planningCount} 条内容
            </span>
          ) : null}
          {data.sourceCount > 0 && (
            <span className="text-[10px] text-outline">
              {data.sourceCount} 来源
            </span>
          )}
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-2 !w-2 !bg-outline-variant"
      />

      {isReadOnly && (
        <span className="absolute -top-2 right-2 text-[9px] bg-inverse-surface text-inverse-on-surface px-1.5 py-0.5 rounded">
          只读
        </span>
      )}
    </div>
  );
}

export const ModuleNode = memo(ModuleNodeImpl);
