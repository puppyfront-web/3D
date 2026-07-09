"use client";

// Renders the canvas_fill_proposal SSE block emitted by the research→smart-fill
// pipeline. auto mode (first message): read-only summary of what was filled,
// grouped by board → node, with source citations. ask mode (Task 7): adds
// per-node checkboxes (default all selected) + 「采纳所选」 that POSTs the
// selection to /canvas/fill-accept, toasts, reloads the canvas via onAccepted,
// and switches the block to a 「已采纳」 state.

import { useMemo, useState } from "react";
import { Check, Loader2, Search } from "lucide-react";
import { toast } from "sonner";
import { acceptCanvasFill } from "@/lib/canvas-api";

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
  projectId,
  onAccepted,
}: {
  data: CanvasFillProposalData;
  projectId?: string;
  onAccepted?: () => void;
}) {
  const isAuto = data.mode === "auto";
  // Memoize so allKeys (and its downstream useMemo) don't recompute each render.
  const boards = useMemo(() => data.boards ?? [], [data.boards]);

  // ask 模式：默认全选
  const allKeys = useMemo(
    () => boards.flatMap((b) => b.nodes.map((n) => `${b.board_key}/${n.node_key}`)),
    [boards],
  );
  const [selected, setSelected] = useState<Set<string>>(() => new Set(allKeys));
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  function toggle(key: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  async function handleAccept() {
    if (busy || done || !projectId) return;
    setBusy(true);
    const payload = {
      boards: boards
        .map((b) => ({
          board_key: b.board_key,
          nodes: b.nodes
            .filter((n) => selected.has(`${b.board_key}/${n.node_key}`))
            .map((n) => ({
              node_key: n.node_key,
              points: n.points,
              citations: n.citations ?? [],
            })),
        }))
        .filter((b) => b.nodes.length > 0),
      change_summary: `采集采纳：${selected.size} 个节点`,
    };
    const res = await acceptCanvasFill(projectId, payload);
    setBusy(false);
    if (res.success) {
      setDone(true);
      toast.success("已采纳到画布");
      onAccepted?.();
    } else {
      toast.error(res.message ?? "采纳失败，请重试");
    }
  }

  return (
    <div className="rounded-lg border border-primary/30 bg-primary-fixed/40 p-3 space-y-3">
      <div className="flex items-center gap-1.5 text-[10px] text-primary font-semibold uppercase tracking-wider">
        <Search className="h-3 w-3" />
        {isAuto ? "已采集并填充到画布" : "搜索到可归档的内容"}
      </div>

      {boards.map((b) => (
        <div key={b.board_key} className="space-y-1.5">
          <div className="text-xs font-semibold text-on-surface">{b.board_title}</div>
          {b.nodes.map((n) => {
            const key = `${b.board_key}/${n.node_key}`;
            const checked = selected.has(key);
            return (
              <div key={key} className="pl-2 border-l border-outline/40 space-y-1">
                <div className="flex items-center gap-1.5">
                  {!isAuto ? (
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggle(key)}
                      className="h-3 w-3 accent-primary"
                    />
                  ) : null}
                  <span className="text-[11px] text-tertiary">{n.node_title}</span>
                </div>
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
            );
          })}
        </div>
      ))}

      {!isAuto && (data.summary?.missing_info ?? []).length > 0 ? (
        <div className="text-[11px] text-tertiary">
          缺失信息：{(data.summary?.missing_info ?? []).join("；")}
        </div>
      ) : null}

      {!isAuto ? (
        <button
          onClick={handleAccept}
          disabled={busy || done || selected.size === 0}
          className="w-full mt-1 inline-flex items-center justify-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-on-primary disabled:opacity-60 hover:opacity-90"
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
          {done ? "已采纳" : `采纳所选（${selected.size}）`}
        </button>
      ) : null}
    </div>
  );
}
