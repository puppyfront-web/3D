"use client";

// Renders the canvas_fill_proposal SSE block emitted by the research→smart-fill
// pipeline. auto mode (first message): read-only summary of what was filled,
// grouped by board → node, with source citations. ask mode (Task 7): adds
// per-node checkboxes + 「采纳所选」 that POSTs to /canvas/fill-accept.

import { Search } from "lucide-react";

export interface FillCitation {
  name?: string;
  url?: string;
  snippet?: string;
  type?: string;
}

export interface FillProposalNode {
  node_key: string;
  node_title: string;
  points: string[];
  citations?: FillCitation[];
  pending_questions?: string[];
}

export interface FillProposalBoard {
  board_key: string;
  board_title: string;
  nodes: FillProposalNode[];
}

export interface CanvasFillProposalData {
  mode: "auto" | "ask";
  boards: FillProposalBoard[];
  summary?: { key_points?: string[]; missing_info?: string[] };
}

export function CanvasFillProposalBlock({
  data,
}: {
  data: CanvasFillProposalData;
  onAccepted?: () => void; // Task 7 ask 模式用;auto 模式不传
}) {
  const isAuto = data.mode === "auto";
  const boards = data.boards ?? [];
  return (
    <div className="rounded-lg border border-primary/30 bg-primary-fixed/40 p-3 space-y-3">
      <div className="flex items-center gap-1.5 text-[10px] text-primary font-semibold uppercase tracking-wider">
        <Search className="h-3 w-3" />
        {isAuto ? "已采集并填充到画布" : "搜索到可归档的内容"}
      </div>

      {boards.map((b) => (
        <div key={b.board_key} className="space-y-1.5">
          <div className="text-xs font-semibold text-on-surface">{b.board_title}</div>
          {b.nodes.map((n) => (
            <div key={n.node_key} className="pl-2 border-l border-outline/40 space-y-1">
              <div className="text-[11px] text-tertiary">{n.node_title}</div>
              <div className="text-xs text-on-surface whitespace-pre-wrap space-y-0.5">
                {n.points.map((p, i) => (
                  <p key={i}>• {p}</p>
                ))}
              </div>
              {(n.pending_questions ?? []).length > 0 ? (
                <div className="text-[11px] text-outline">
                  待确认：{(n.pending_questions ?? []).join("；")}
                </div>
              ) : null}
              {(n.citations ?? []).length > 0 ? (
                <div className="text-[10px] text-outline">
                  来源：
                  {(n.citations ?? []).map((c, i) => (
                    <span key={i}>
                      {i > 0 ? "、" : ""}
                      {c.url ? (
                        <a href={c.url} target="_blank" rel="noreferrer" className="underline">
                          {c.name || c.url}
                        </a>
                      ) : (
                        c.name || "网络来源"
                      )}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ))}

      {!isAuto && (data.summary?.missing_info ?? []).length > 0 ? (
        <div className="text-[11px] text-tertiary">
          缺失信息：{(data.summary?.missing_info ?? []).join("；")}
        </div>
      ) : null}
    </div>
  );
}
