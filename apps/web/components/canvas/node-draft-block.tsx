"use client";

// Renders the structured node_draft emitted by the node-scoped conversation
// (backend _handle_node_edit, Task 2) and offers a one-click 「采纳到节点」
// that POSTs to the adopt endpoint (Task 3) via adoptNode (Task 6).

import { useState } from "react";
import { Check, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { adoptNode } from "@/lib/canvas-api";

export interface NodeDraftData {
  planning: string[];
  pending_questions?: string[];
  sources?: Array<{ type: string; name?: string; quote?: string }>;
}

export function NodeDraftBlock({
  projectId,
  nodeId,
  data,
  onAdopted,
}: {
  projectId: string;
  nodeId: string;
  data: NodeDraftData;
  onAdopted?: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [adopted, setAdopted] = useState(false);

  async function handleAdopt() {
    if (busy || adopted) return;
    setBusy(true);
    const res = await adoptNode(projectId, nodeId, {
      planning: data.planning,
      pending_questions: data.pending_questions,
      sources: data.sources,
    });
    setBusy(false);
    if (res.success) {
      setAdopted(true);
      toast.success("已采纳到节点");
      onAdopted?.();
    } else {
      toast.error(res.message ?? "采纳失败，请重试");
    }
  }

  const pending = data.pending_questions ?? [];
  const sources = data.sources ?? [];

  return (
    <div className="rounded-lg border border-primary/30 bg-primary-fixed/40 p-3 space-y-2">
      <div className="flex items-center gap-1.5 text-[10px] text-primary font-semibold uppercase tracking-wider">
        <Check className="h-3 w-3" />
        已生成节点内容
      </div>
      <div className="text-xs text-on-surface whitespace-pre-wrap space-y-2">
        {data.planning.map((p, i) => (
          <p key={i}>{p}</p>
        ))}
      </div>
      {pending.length > 0 ? (
        <div className="text-xs text-tertiary">
          <div className="font-semibold mb-1">为补全本节点，还需要你提供：</div>
          <ul className="space-y-1">
            {pending.map((q, i) => (
              <li key={i}>• {q}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {sources.length > 0 ? (
        <div className="text-[10px] text-outline">
          来源：{sources.map((s) => s.name || s.type).join("、")}
        </div>
      ) : null}
      <button
        onClick={handleAdopt}
        disabled={busy || adopted}
        className="w-full mt-1 inline-flex items-center justify-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-on-primary disabled:opacity-60 hover:opacity-90"
      >
        {busy ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Check className="h-3.5 w-3.5" />
        )}
        {adopted ? "已采纳" : "采纳到节点"}
      </button>
    </div>
  );
}
