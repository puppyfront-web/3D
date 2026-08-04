"use client";

// VisualDrawer — right-side drawer that surfaces the visual-concept version
// tree for the current project. Consolidates the legacy standalone
// `/workspace/projects/[id]/visual` tab into the canvas workspace.
//
// Data flow:
//   projectId → getProjectConversation() → conversationId (cached)
//             → getVersionTree(conversationId) → untyped version-tree JSON
//   per-node actions → executeVisualConceptAction(conversationId, action, ...)
//
// The version-tree API returns untyped JSON (Record<string, unknown>), so the
// tree is parsed defensively into a small local view model — no `any`, no
// unsafe casts. We intentionally do NOT reuse <VersionTreeDrawer> from
// components/chat: that component ships its own trigger button + backdrop +
// drawer shell and uses hardcoded (non-token) colours, which would clash with
// the Enterprise Blueprint token system used everywhere else in the canvas.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Loader2,
  X,
  RefreshCw,
  Image as ImageIcon,
  RotateCcw,
  GitBranch,
} from "lucide-react";

import { getProjectConversation } from "@/lib/canvas-api";
import {
  getVersionTree,
  executeVisualConceptAction,
} from "@/lib/visual-concept-api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface VisualDrawerProps {
  projectId: string;
  open: boolean;
  onClose: () => void;
}

// ─── Safe readers for untyped version-tree JSON ──────────────────────────────
// The API payload is loosely typed; these helpers extract fields without `any`
// or unsafe casts. Each reader returns undefined / empty on a shape mismatch.

function readString(obj: unknown, key: string): string | undefined {
  if (obj && typeof obj === "object" && key in obj) {
    const v = (obj as Record<string, unknown>)[key];
    return typeof v === "string" ? v : undefined;
  }
  return undefined;
}

/** Read a string-keyed object value (e.g. `nodes`, `branches`). */
function readObject(
  obj: unknown,
  key: string,
): Record<string, unknown> | undefined {
  if (obj && typeof obj === "object" && key in obj) {
    const v = (obj as Record<string, unknown>)[key];
    if (v && typeof v === "object" && !Array.isArray(v)) {
      return v as Record<string, unknown>;
    }
  }
  return undefined;
}

/** A version node flattened into a render-friendly shape. */
interface VersionNodeView {
  nodeId: string;
  branchId: string;
  versionLabel: string;
  imageUrl?: string;
  status?: string;
  createdAt?: string;
  userInstruction?: string;
}

function parseNode(raw: unknown): VersionNodeView | null {
  if (!raw || typeof raw !== "object") return null;
  const nodeId = readString(raw, "node_id");
  if (!nodeId) return null;
  return {
    nodeId,
    branchId: readString(raw, "branch_id") ?? "",
    versionLabel: readString(raw, "version_label") ?? nodeId,
    imageUrl: readString(raw, "image_url"),
    status: readString(raw, "status"),
    createdAt: readString(raw, "created_at"),
    userInstruction: readString(raw, "user_instruction"),
  };
}

/** True when the fetched payload actually contains version nodes. */
function hasNodes(data: Record<string, unknown> | null): boolean {
  if (!data) return false;
  const nodes = readObject(data, "nodes");
  return !!nodes && Object.keys(nodes).length > 0;
}

/** Resolve the current node id from the active branch metadata. */
function resolveCurrentNodeId(
  data: Record<string, unknown>,
): string | undefined {
  const activeBranch = readString(data, "active_branch");
  if (!activeBranch) return undefined;
  const branches = readObject(data, "branches");
  if (!branches) return undefined;
  const branchMeta = branches[activeBranch];
  return readString(branchMeta, "current_node_id");
}

const STATUS_LABEL: Record<string, string> = {
  completed: "已完成",
  active: "当前",
  abandoned: "已废弃",
};

export function VisualDrawer({ projectId, open, onClose }: VisualDrawerProps) {
  // Cache the conversation id for this project so repeated opens don't
  // re-fetch it. getProjectConversation is idempotent anyway, but avoiding
  // the extra round-trip keeps the drawer feeling snappy.
  const conversationIdRef = useRef<string | null>(null);

  const [versionTree, setVersionTree] = useState<Record<string, unknown> | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // nodeId currently executing a rollback (for spinner state).
  const [actionNodeId, setActionNodeId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. resolve (and cache) the project conversation id.
      let conversationId = conversationIdRef.current;
      if (!conversationId) {
        const convRes = await getProjectConversation(projectId);
        if (!convRes.success || !convRes.data) {
          setError(convRes.message ?? "无法获取项目对话");
          setLoading(false);
          return;
        }
        conversationId = convRes.data.id;
        conversationIdRef.current = conversationId;
      }

      // 2. fetch the visual version tree.
      const treeRes = await getVersionTree(conversationId);
      if (treeRes.success && treeRes.data) {
        setVersionTree(treeRes.data);
      } else {
        // No tree yet — show the empty state.
        setVersionTree(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载视觉版本树失败");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (!open) return;
    void load();
  }, [open, load]);

  // Roll a branch back to a given node, then refresh the tree.
  const handleRollback = useCallback(
    async (nodeId: string) => {
      const conversationId = conversationIdRef.current;
      if (!conversationId) return;
      setActionNodeId(nodeId);
      try {
        await executeVisualConceptAction(conversationId, "rollback", {
          node_id: nodeId,
        });
        await load();
      } catch (e) {
        setError(e instanceof Error ? e.message : "回滚操作失败");
      } finally {
        setActionNodeId(null);
      }
    },
    [load],
  );

  if (!open) return null;

  const treeExists = hasNodes(versionTree);
  const nodes = treeExists
    ? (Object.values(readObject(versionTree, "nodes") ?? {})
        .map(parseNode)
        .filter((n): n is VersionNodeView => n !== null)
        .sort((a, b) => {
          const ta = a.createdAt ? Date.parse(a.createdAt) : 0;
          const tb = b.createdAt ? Date.parse(b.createdAt) : 0;
          return tb - ta;
        }))
    : [];
  const currentNodeId = treeExists ? resolveCurrentNodeId(versionTree!) : undefined;

  return (
    <aside className="absolute right-0 top-0 bottom-0 w-80 bg-surface-container-lowest border-l border-outline-variant shadow-xl z-40 flex flex-col overflow-y-auto scrollbar-thin">
      {/* Header */}
      <div className="p-4 border-b border-outline-variant flex items-center justify-between sticky top-0 bg-surface-container-lowest z-10">
        <h2 className="font-semibold text-on-surface">视觉创作</h2>
        <button
          onClick={onClose}
          className="p-1 hover:bg-surface-container-low rounded-md text-on-surface-variant"
          aria-label="关闭"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Body */}
      <div className="p-4 flex-1 flex flex-col gap-4">
        {loading && (
          <div className="flex items-center justify-center gap-2 text-on-surface-variant text-sm py-8">
            <Loader2 className="h-4 w-4 animate-spin" />
            加载视觉版本树…
          </div>
        )}

        {!loading && error && (
          <div className="text-sm text-error py-4 text-center">{error}</div>
        )}

        {/* Empty state — no visual creation records yet */}
        {!loading && !error && !treeExists && (
          <div className="flex flex-col items-center text-center gap-3 py-10">
            <div className="p-3 rounded-full bg-surface-container text-on-surface-variant">
              <ImageIcon className="h-6 w-6" />
            </div>
            <p className="text-sm text-on-surface-variant leading-relaxed">
              该项目还没有视觉创作记录。在工作台对话中发送视觉相关指令（如「生成概念图」）即可创建。
            </p>
            <Button variant="outline" size="sm" onClick={onClose}>
              打开对话
            </Button>
          </div>
        )}

        {/* Version tree — minimal inline list */}
        {!loading && !error && treeExists && (
          <ul className="space-y-3">
            {nodes.map((node) => {
              const isCurrent = node.nodeId === currentNodeId;
              const isAbandoned = node.status === "abandoned";
              return (
                <li
                  key={node.nodeId}
                  className={cn(
                    "rounded-xl border p-3 transition-colors",
                    isCurrent
                      ? "border-primary bg-primary-fixed/40"
                      : "border-outline-variant bg-surface-container-low",
                    isAbandoned && "opacity-60",
                  )}
                >
                  <div className="flex items-start gap-3">
                    {/* Thumbnail */}
                    {node.imageUrl ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={node.imageUrl}
                        alt={node.versionLabel}
                        className="h-14 w-14 rounded-lg object-cover border border-outline-variant shrink-0 bg-surface-container"
                      />
                    ) : (
                      <div className="h-14 w-14 rounded-lg border border-outline-variant bg-surface-container flex items-center justify-center shrink-0">
                        <ImageIcon className="h-5 w-5 text-outline" />
                      </div>
                    )}

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="font-medium text-sm text-on-surface truncate">
                          {node.versionLabel}
                        </span>
                        {isCurrent && (
                          <span className="bg-primary text-on-primary text-[10px] px-1.5 py-0.5 rounded uppercase font-bold">
                            当前
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-1.5 mt-1 text-[11px] text-on-surface-variant">
                        <GitBranch className="h-3 w-3" />
                        <span className="truncate">{node.branchId || "—"}</span>
                        {node.status && (
                          <>
                            <span className="text-outline">·</span>
                            <span>
                              {STATUS_LABEL[node.status] ?? node.status}
                            </span>
                          </>
                        )}
                      </div>

                      {node.createdAt && (
                        <p className="text-[10px] text-outline mt-0.5">
                          {new Date(node.createdAt).toLocaleString("zh-CN", {
                            month: "2-digit",
                            day: "2-digit",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </p>
                      )}

                      {node.userInstruction && (
                        <p className="text-[11px] text-on-surface-variant mt-1.5 line-clamp-2">
                          {node.userInstruction}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Per-node actions */}
                  {!isCurrent && !isAbandoned && (
                    <button
                      onClick={() => handleRollback(node.nodeId)}
                      disabled={actionNodeId === node.nodeId}
                      className="mt-2.5 flex items-center gap-1 text-xs text-primary hover:underline disabled:opacity-50 disabled:no-underline"
                    >
                      {actionNodeId === node.nodeId ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <RotateCcw className="h-3 w-3" />
                      )}
                      {actionNodeId === node.nodeId ? "回滚中…" : "回滚到此版本"}
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Footer — refresh (only when a tree exists) */}
      {treeExists && (
        <div className="p-4 border-t border-outline-variant sticky bottom-0 bg-surface-container-lowest">
          <Button
            variant="outline"
            size="sm"
            className="w-full border-outline-variant text-on-surface hover:bg-surface-container-low"
            onClick={() => void load()}
            disabled={loading}
          >
            <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
            刷新
          </Button>
        </div>
      )}
    </aside>
  );
}
