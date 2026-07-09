"use client";

// NodeDetailDrawer — slides in when a node is selected. Shows the four-slot
// content skeleton (extracted / planning / uiSuggestion / pendingQuestions),
// the node's provenance sources (NodeSource[]), and a structured editor when
// the canvas is not read-only.
//
// Edit mode: each slot is an editable list (add/remove items) — replaces the
// old raw-JSON textarea. PATCH /nodes/{id} receives structured NodeContent.

import { useEffect, useState } from "react";
import { X, AlertCircle, Plus, Trash2, Save, Pencil, Sparkles, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { useCanvasStore } from "@/lib/canvas-store";
import {
  deleteNode,
  getAgentRun,
  getNode,
  triggerAgentRun,
  updateNode,
} from "@/lib/canvas-api";
import type { CanvasNode, NodeContent } from "@/types/canvas";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import {
  sourceTypeLabel,
  CONFIDENCE_COLOR,
  confidenceLabel,
} from "@/lib/design-tokens";
import { cn } from "@/lib/utils";

type SlotKey = "extracted" | "planning" | "uiSuggestion" | "pendingQuestions";

const SLOT_LABELS: Record<SlotKey, string> = {
  extracted: "资料提取",
  planning: "策划内容",
  uiSuggestion: "UI 建议",
  pendingQuestions: "待确认",
};

const EDITABLE_SLOTS: SlotKey[] = ["extracted", "planning", "uiSuggestion"];

function emptyContent(): NodeContent {
  return { extracted: [], planning: [], uiSuggestion: [], pendingQuestions: [] };
}

export function NodeDetailDrawer({
  onSaved,
  onUiRegenerated,
  onNodeDeleted,
}: {
  /** Kept for call-site compatibility; the drawer resolves nodes via the store. */
  projectId?: string;
  /** Invoked after a node's content is successfully saved. The page uses this
   *  to promote a new version (PRD §15.3-6 / §16: every confirmed edit must
   *  produce a new version) and to keep the drawer open across the reload. */
  onSaved?: (nodeId: string, nodeTitle: string) => void;
  /** Invoked after the UI-expert pass completes so the page can reload the
   *  canvas (and snapshot a new version) with the fresh ui_suggestion content. */
  onUiRegenerated?: () => void;
  /** Invoked after a node is deleted (PRD P1 #2) so the page reloads the
   *  canvas and the removed node disappears from the viewport. */
  onNodeDeleted?: () => void;
}) {
  const selectedNodeId = useCanvasStore((s) => s.selectedNodeId);
  const selectNode = useCanvasStore((s) => s.selectNode);
  const isReadOnly = useCanvasStore((s) => s.isReadOnly);
  const projectId = useCanvasStore((s) => s.activeProjectId);

  const [node, setNode] = useState<CanvasNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<NodeContent>(emptyContent());
  const [saving, setSaving] = useState(false);
  const [regenUi, setRegenUi] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    if (!selectedNodeId) {
      setNode(null);
      return;
    }
    setLoading(true);
    setEditing(false);
    getNode(selectedNodeId)
      .then((res) => {
        if (res.success && res.data) setNode(res.data);
      })
      .finally(() => setLoading(false));
  }, [selectedNodeId]);

  if (!selectedNodeId) return null;

  function startEdit() {
    const content = node?.content ?? emptyContent();
    setDraft({
      extracted: content.extracted ?? [],
      planning: content.planning ?? [],
      uiSuggestion: content.uiSuggestion ?? [],
      pendingQuestions: content.pendingQuestions ?? [],
    });
    setEditing(true);
  }

  async function save() {
    if (!node || !projectId) return;
    setSaving(true);
    try {
      const res = await updateNode(projectId, node.id, { content: draft });
      if (res.success && res.data) {
        setNode(res.data);
        setEditing(false);
        onSaved?.(node.id, node.title);
      }
    } finally {
      setSaving(false);
    }
  }

  // Re-trigger the UI 专家 pass for the whole canvas (the backend runs the UI
  // agent across all eligible nodes; a per-node endpoint would over-fit). Polls
  // until terminal status, then reloads so the ui_suggestion slot refreshes.
  // PRD §13.5: UI 建议 must be regenerable on demand without redoing extract.
  async function regenUiSuggestion() {
    if (!projectId || regenUi) return;
    setRegenUi(true);
    toast.info("正在生成 UI 建议…");
    try {
      const start = await triggerAgentRun(projectId, "ui_expert");
      if (!start.success || !start.data?.execution_id) {
        toast.error(start.message ?? "启动失败");
        return;
      }
      const execId = start.data.execution_id;
      for (let i = 0; i < 60; i++) {
        await new Promise((r) => setTimeout(r, 1500));
        const poll = await getAgentRun(execId);
        const st = poll.data?.status;
        if (st === "succeeded") {
          toast.success("UI 建议已更新");
          onUiRegenerated?.();
          return;
        }
        if (st === "failed") {
          toast.error(`生成失败：${poll.data?.error ?? "未知错误"}`);
          return;
        }
      }
      toast.warning("生成超时，请稍后查看节点");
    } catch (e) {
      toast.error(`生成异常：${e instanceof Error ? e.message : "未知"}`);
    } finally {
      setRegenUi(false);
    }
  }

  // PRD P1 #2: delete a custom module node. Board group nodes are protected
  // server-side; only module nodes can be removed. Reloads the canvas so the
  // node disappears from the viewport and the drawer closes.
  async function handleDelete() {
    if (!node || !projectId) return;
    setDeleting(true);
    try {
      const res = await deleteNode(projectId, node.id);
      if (res.success) {
        toast.success(`已删除节点：${node.title}`);
        selectNode(null);
        onNodeDeleted?.();
      } else {
        toast.error(res.message ?? "删除失败");
      }
    } catch (e) {
      toast.error(`删除失败：${e instanceof Error ? e.message : "未知"}`);
    } finally {
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  return (
    <aside className="absolute right-0 top-0 bottom-0 w-[380px] bg-surface-container-lowest border-l border-outline-variant shadow-xl z-30 flex flex-col">
      {/* Header */}
      <div className="px-4 h-14 flex items-center justify-between border-b border-outline-variant shrink-0">
        <h3 className="font-semibold text-on-surface truncate">
          {node?.title ?? "节点详情"}
        </h3>
        <button
          onClick={() => selectNode(null)}
          className="text-outline hover:text-on-surface-variant"
          aria-label="关闭"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {loading && (
        <div className="flex-1 flex items-center justify-center text-outline text-sm">
          加载中…
        </div>
      )}

      {!loading && node && (
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4 scrollbar-thin">
          {/* Status + key */}
          <div className="flex items-center gap-2 text-xs">
            <span className="px-2 py-0.5 rounded bg-surface-container text-on-surface-variant">
              {node.status}
            </span>
            {node.nodeKey && (
              <code className="text-[10px] text-outline">{node.nodeKey}</code>
            )}
          </div>

          {/* Content slots */}
          {editing ? (
            <EditableSlots draft={draft} onChange={setDraft} />
          ) : (
            <ReadonlySlots content={node.content} />
          )}

          {/* Edit / Save */}
          {!isReadOnly && (
            <div className="flex gap-2">
              {!editing ? (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={startEdit}
                >
                  <Pencil className="h-3.5 w-3.5" /> 编辑内容
                </Button>
              ) : (
                <>
                  <Button
                    size="sm"
                    className="flex-1 bg-primary hover:opacity-90"
                    disabled={saving}
                    onClick={save}
                  >
                    {saving ? (
                      <>
                        <Save className="h-3.5 w-3.5" /> 保存中…
                      </>
                    ) : (
                      <>
                        <Save className="h-3.5 w-3.5" /> 保存
                      </>
                    )}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setEditing(false)}
                  >
                    取消
                  </Button>
                </>
              )}
            </div>
          )}

          {/* Re-generate UI 建议 (UI 专家 Agent, on demand — PRD §13.5).
              Runs the UI pass on its own without redoing extract/plan. */}
          {!isReadOnly && !editing && (
            <Button
              variant="outline"
              size="sm"
              className="w-full border-primary/40 text-primary hover:bg-primary-fixed"
              disabled={regenUi}
              onClick={regenUiSuggestion}
              title="调用 UI 专家 Agent 重新生成 UI 表达建议"
            >
              {regenUi ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Sparkles className="h-3.5 w-3.5" />
              )}
              {(node.content?.uiSuggestion ?? []).length > 0
                ? "重新生成 UI 建议"
                : "生成 UI 建议"}
            </Button>
          )}

          {/* Sources */}
          <SourcesSection sources={node.sources ?? []} />

          {/* Pending questions */}
          {!editing &&
            (node.content?.pendingQuestions ?? []).length > 0 && (
              <div className="rounded-lg bg-tertiary-fixed/40 border border-tertiary/30 p-3">
                <div className="flex items-center gap-1.5 text-tertiary text-xs font-semibold mb-1.5">
                  <AlertCircle className="h-3.5 w-3.5" />
                  待确认项
                </div>
                <ul className="text-xs text-tertiary-container space-y-1">
                  {(node.content?.pendingQuestions ?? []).map((q, i) => (
                    <li key={i}>• {q}</li>
                  ))}
                </ul>
              </div>
            )}

          {/* Delete node (PRD P1 #2). Board group nodes are protected
              server-side, so this only affects module nodes. */}
          {!isReadOnly && (
            <Button
              variant="ghost"
              size="sm"
              className="w-full text-error hover:bg-error-container/40"
              onClick={() => setConfirmDelete(true)}
            >
              <Trash2 className="h-3.5 w-3.5" /> 删除该节点
            </Button>
          )}
        </div>
      )}

      <Dialog open={confirmDelete} onOpenChange={(o) => !o && setConfirmDelete(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除节点</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-on-surface-variant">
            将删除节点「{node?.title}」及其连线，该操作需保存为新版本后生效。板块节点不可删除。
          </p>
          <DialogFooter className="mt-4 gap-2">
            <DialogClose asChild>
              <Button variant="outline">取消</Button>
            </DialogClose>
            <Button
              onClick={handleDelete}
              disabled={deleting}
              className="bg-error text-on-error hover:bg-error/90"
            >
              {deleting ? "删除中…" : "确认删除"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </aside>
  );
}

function ReadonlySlots({ content }: { content?: NodeContent }) {
  const c = content ?? emptyContent();
  // Backend content slots may be null (schema allows Optional), so coerce each
  // to an array. Without this, a null slot crashes on `items.length` below with
  // "Cannot read properties of null (reading 'length')".
  const slots: [SlotKey, string[]][] = [
    ["extracted", c.extracted ?? []],
    ["planning", c.planning ?? []],
    ["uiSuggestion", c.uiSuggestion ?? []],
  ];
  return (
    <div className="space-y-3">
      {slots.map(([key, items]) => (
        <div key={key}>
          <div className="text-xs font-semibold text-on-surface-variant mb-1">
            {SLOT_LABELS[key]}
          </div>
          {items.length === 0 ? (
            <p className="text-xs text-outline italic">暂无</p>
          ) : (
            <ul className="text-xs text-on-surface space-y-1">
              {items.map((it, i) => (
                <li key={i}>• {it}</li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}

function EditableSlots({
  draft,
  onChange,
}: {
  draft: NodeContent;
  onChange: (c: NodeContent) => void;
}) {
  function addItem(key: SlotKey) {
    onChange({ ...draft, [key]: [...(draft[key] ?? []), ""] });
  }
  function removeItem(key: SlotKey, idx: number) {
    onChange({
      ...draft,
      [key]: (draft[key] ?? []).filter((_, i) => i !== idx),
    });
  }
  function editItem(key: SlotKey, idx: number, value: string) {
    const next = [...(draft[key] ?? [])];
    next[idx] = value;
    onChange({ ...draft, [key]: next });
  }

  return (
    <div className="space-y-3">
      {EDITABLE_SLOTS.map((key) => (
        <div key={key}>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-semibold text-on-surface-variant">
              {SLOT_LABELS[key]}
            </span>
            <button
              onClick={() => addItem(key)}
              className="text-primary hover:bg-primary-fixed rounded p-0.5"
              aria-label={`添加${SLOT_LABELS[key]}`}
            >
              <Plus className="h-3.5 w-3.5" />
            </button>
          </div>
          <div className="space-y-1.5">
            {(draft[key] ?? []).map((item, idx) => (
              <div key={idx} className="flex gap-1.5">
                <textarea
                  value={item}
                  onChange={(e) => editItem(key, idx, e.target.value)}
                  rows={2}
                  className="flex-1 text-xs rounded-md border border-outline-variant px-2 py-1 resize-none focus:outline-none focus:border-primary bg-surface-container-low"
                />
                <button
                  onClick={() => removeItem(key, idx)}
                  className="text-outline hover:text-error p-1"
                  aria-label="删除"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
            {(draft[key] ?? []).length === 0 && (
              <p className="text-xs text-outline italic">暂无，点击 + 添加</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function SourcesSection({
  sources,
}: {
  sources: CanvasNode["sources"];
}) {
  if (!sources || sources.length === 0) {
    return (
      <div>
        <div className="text-xs font-semibold text-on-surface-variant mb-1">
          内容来源
        </div>
        <p className="text-xs text-outline italic">暂无溯源</p>
      </div>
    );
  }
  return (
    <div>
      <div className="text-xs font-semibold text-on-surface-variant mb-1.5">
        内容来源 ({sources.length})
      </div>
      <div className="space-y-1.5">
        {sources.map((s) => {
          const isPending = s.sourceType === "pending_user";
          const isAi = s.sourceType === "ai_completed";
          return (
            <div
              key={s.id}
              className={cn(
                "rounded-md border p-2 text-xs",
                isPending
                  ? "border-amber-400 bg-amber-50"
                  : isAi
                    ? "border-primary/30 bg-primary/5"
                    : "border-outline-variant bg-surface-container",
              )}
            >
              <div className="flex items-center justify-between mb-0.5">
                <span className="font-medium text-on-surface flex items-center gap-1">
                  {sourceTypeLabel(s.sourceType)}
                  {(isPending || isAi) && (
                    <AlertCircle
                      className={cn(
                        "h-3 w-3",
                        isPending ? "text-amber-500" : "text-primary",
                      )}
                    />
                  )}
                </span>
                {s.confidence && (
                  <span
                    className={cn(
                      "text-[10px]",
                      CONFIDENCE_COLOR[s.confidence] ?? "text-outline",
                    )}
                  >
                    {confidenceLabel(s.confidence)}
                  </span>
                )}
              </div>
              {s.sourceName && (
                <div className="text-on-surface-variant truncate">{s.sourceName}</div>
              )}
              {s.quote && (
                <div className="text-on-surface-variant italic line-clamp-2 mt-0.5">
                  {s.quote}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
