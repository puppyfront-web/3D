"use client";

// VersionPanel — a slide-in drawer (triggered from the canvas top-right
// "版本管理" button) listing all ProjectVersions with the current version
// highlighted. Converted from a persistent right sidebar to an on-demand
// drawer so the canvas gets the full width by default.
//
// Timeline: vertical line + dots, current version in a primary-fixed card,
// historical versions as bordered cards. Restore branches a new current.

import { useEffect, useState } from "react";
import { RotateCcw, Download, History, X, FileText, GitBranch, BookOpen, FileBox, Link2 } from "lucide-react";
import { toast } from "sonner";

import { listVersions, restoreVersion } from "@/lib/canvas-api";
import type { ProjectVersion } from "@/types/canvas";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

export function VersionPanel({
  projectId,
  currentVersionId,
  onSelectVersion,
  onRestored,
  open,
  onClose,
  onExport,
}: {
  projectId: string;
  currentVersionId: string | null;
  onSelectVersion: (versionId: string) => void;
  onRestored: () => void;
  open: boolean;
  onClose: () => void;
  onExport?: (format: "word" | "pdf") => void;
}) {
  const [versions, setVersions] = useState<ProjectVersion[]>([]);
  const [loading, setLoading] = useState(false);
  const [restoring, setRestoring] = useState<string | null>(null);
  // The version whose detail card is shown below the timeline. Defaults to the
  // current version; switches when a historical version is clicked so the user
  // can inspect any version's change summary + related assets (PRD §16.3).
  const [detailId, setDetailId] = useState<string | null>(null);
  // Restore confirmation state — restoring branches a new current version, so
  // we confirm before acting (PRD §16: "历史版本恢复后不会误覆盖当前版本").
  const [restoreTarget, setRestoreTarget] = useState<ProjectVersion | null>(null);

  // Only load when the drawer is open; skip work while hidden.
  useEffect(() => {
    if (!open) return;
    setLoading(true);
    listVersions(projectId)
      .then((res) => {
        if (res.success && res.data) {
          setVersions(res.data);
          // Default the detail view to the current version.
          const cur = res.data.find((v) => v.isCurrent);
          if (cur && !detailId) setDetailId(cur.id);
        }
      })
      .finally(() => setLoading(false));
  }, [projectId, open, detailId]);

  if (!open) return null;

  const current = versions.find((v) => v.isCurrent);
  const detail = versions.find((v) => v.id === detailId) ?? current;

  async function confirmRestore() {
    if (!restoreTarget) return;
    setRestoring(restoreTarget.id);
    try {
      const res = await restoreVersion(restoreTarget.id);
      if (res.success) {
        toast.success(`已从 ${restoreTarget.versionName ?? "历史版本"} 恢复，生成新当前版本`);
        onRestored();
      } else {
        toast.error(res.message ?? "恢复失败");
      }
    } catch (e) {
      toast.error(`恢复失败：${e instanceof Error ? e.message : "未知"}`);
    } finally {
      setRestoring(null);
      setRestoreTarget(null);
    }
  }

  return (
    <>
      {/* Backdrop: click anywhere outside to close. */}
      <div
        className="absolute inset-0 z-30 bg-black/30"
        onClick={onClose}
        aria-hidden
      />
      <aside className="absolute right-0 top-0 bottom-0 w-80 z-40 shadow-xl border-l border-outline-variant bg-surface-container-lowest flex flex-col overflow-y-auto scrollbar-thin animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="p-4 border-b border-outline-variant flex items-center justify-between sticky top-0 bg-surface-container-lowest z-10">
          <h2 className="font-semibold text-on-surface flex items-center gap-2">
            <History className="h-4 w-4 text-primary" />
            版本管理
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-surface-container-high text-on-surface-variant"
            aria-label="关闭"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-4 space-y-6">
          {loading && (
            <div className="text-sm text-outline text-center py-4">加载中…</div>
          )}
          {!loading && versions.length === 0 && (
            <div className="text-sm text-outline text-center py-4">
              暂无版本，创建第一个版本开始
            </div>
          )}

          {/* Timeline */}
          {versions.map((v) => {
            const isCurrent = v.id === currentVersionId;
            return (
              <div key={v.id} className="relative pl-6">
                {/* Vertical line */}
                <div className="absolute left-0 top-0 bottom-0 w-[2px] bg-outline-variant" />
                {/* Dot */}
                <div
                  className={cn(
                    "absolute -left-[5px] top-0 w-2.5 h-2.5 rounded-full",
                    isCurrent && "ring-4 ring-primary-fixed",
                  )}
                  style={{
                    background: isCurrent
                      ? "var(--primary)"
                      : "var(--outline-variant)",
                  }}
                />
                {isCurrent ? (
                  <div
                    onClick={() => setDetailId(v.id)}
                    className={cn(
                      "bg-primary-fixed text-primary p-4 rounded-xl border border-primary-fixed shadow-sm cursor-pointer",
                      detailId === v.id && "ring-2 ring-primary",
                    )}
                  >
                    <div className="flex justify-between items-start mb-2">
                      <span className="font-bold text-lg">
                        {v.versionName ?? `V${v.versionNo}`}
                      </span>
                      <span className="bg-primary text-on-primary text-[10px] px-1.5 py-0.5 rounded uppercase font-bold">
                        当前
                      </span>
                    </div>
                    <p className="text-xs font-medium mb-1">
                      {v.changeSummary ?? "当前版本"}
                    </p>
                    <p className="text-[10px] opacity-70">
                      {new Date(v.createdAt).toLocaleString("zh-CN", {
                        month: "2-digit",
                        day: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  </div>
                ) : (
                  <div
                    onClick={() => {
                      onSelectVersion(v.id);
                      setDetailId(v.id);
                    }}
                    className={cn(
                      "p-4 rounded-xl border hover:bg-surface-container-low cursor-pointer transition-all",
                      detailId === v.id
                        ? "border-primary ring-1 ring-primary/40 bg-surface-container-low"
                        : "border-outline-variant",
                    )}
                  >
                    <span className="font-bold block mb-1 text-on-surface">
                      {v.versionName ?? `V${v.versionNo}`}
                    </span>
                    <p className="text-xs text-on-surface-variant mb-1">
                      {v.changeSummary ?? "—"}
                    </p>
                    <div className="flex items-center justify-between">
                      <p className="text-[10px] text-outline">
                        {new Date(v.createdAt).toLocaleString("zh-CN", {
                          month: "2-digit",
                          day: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </p>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setRestoreTarget(v);
                        }}
                        className="flex items-center gap-1 text-primary hover:underline text-xs"
                      >
                        <RotateCcw className="h-3 w-3" />
                        恢复
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}

          {/* Version details — shows for whichever version is selected in the
              timeline (current by default, or any historical one the user
              clicked). Surfaces change summary, timestamps, related knowledge
              assets, and (for the current version) the document export. */}
          {detail && (
            <>
              <hr className="border-outline-variant" />
              <div>
                <h3 className="text-xs font-semibold mb-4 uppercase tracking-wider text-outline">
                  版本详情 ({detail.versionName ?? `V${detail.versionNo}`})
                </h3>
                <div className="space-y-4">
                  <div>
                    <p className="text-[10px] text-outline uppercase font-semibold mb-1">
                      更新说明
                    </p>
                    <p className="text-sm leading-relaxed text-on-surface">
                      {detail.changeSummary ?? "—"}
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] text-outline uppercase font-semibold mb-1">
                      创建时间
                    </p>
                    <p className="text-sm text-on-surface">
                      {new Date(detail.createdAt).toLocaleString("zh-CN")}
                    </p>
                  </div>

                  {/* Related knowledge assets (PRD §16.3 / §23.6) */}
                  <RelatedAssets version={detail} />

                  {detail.isCurrent && onExport && (
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        className="flex-1 border-outline-variant text-on-surface-variant"
                        onClick={() => onExport("word")}
                      >
                        <Download className="h-3.5 w-3.5" /> Word
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="flex-1 border-outline-variant text-on-surface-variant"
                        onClick={() => onExport("pdf")}
                      >
                        <Download className="h-3.5 w-3.5" /> PDF
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </aside>

      {/* Restore confirmation — restoring branches a new current version. */}
      <Dialog open={!!restoreTarget} onOpenChange={(o) => !o && setRestoreTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认恢复版本</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-on-surface-variant">
            将从「{restoreTarget?.versionName ?? "历史版本"}」恢复，生成一个新的当前版本。
            当前版本不会被覆盖，仍可在版本列表中查看。
          </p>
          <DialogFooter className="mt-4 gap-2">
            <DialogClose asChild><Button variant="outline">取消</Button></DialogClose>
            <Button
              onClick={confirmRestore}
              disabled={!!restoring}
              className="bg-primary hover:bg-primary text-on-primary"
            >
              {restoring ? "恢复中…" : "确认恢复"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/** Renders the related materials / SOP / cases / templates a version used.
 * Empty when the version predates the snapshot aggregates. */
function RelatedAssets({ version }: { version: ProjectVersion }) {
  const materials = version.relatedMaterials ?? [];
  const internal = version.relatedInternalAssets ?? {};
  const groups: { label: string; icon: React.ReactNode; items?: string[] }[] = [
    { label: "引用资料", icon: <FileText className="h-3 w-3" />, items: materials },
    { label: "引用 SOP", icon: <GitBranch className="h-3 w-3" />, items: internal.internal_sop },
    { label: "引用案例", icon: <BookOpen className="h-3 w-3" />, items: internal.internal_case },
    { label: "引用模板", icon: <FileBox className="h-3 w-3" />, items: internal.internal_template },
  ];
  const hasAny = groups.some((g) => (g.items?.length ?? 0) > 0);
  if (!hasAny) {
    return (
      <div>
        <p className="text-[10px] text-outline uppercase font-semibold mb-1 flex items-center gap-1">
          <Link2 className="h-3 w-3" /> 关联知识资产
        </p>
        <p className="text-xs text-outline italic">该版本未记录关联资产</p>
      </div>
    );
  }
  return (
    <div>
      <p className="text-[10px] text-outline uppercase font-semibold mb-2 flex items-center gap-1">
        <Link2 className="h-3 w-3" /> 关联知识资产
      </p>
      <div className="space-y-2">
        {groups.map(
          (g) =>
            (g.items?.length ?? 0) > 0 && (
              <div key={g.label}>
                <p className="text-[10px] text-outline flex items-center gap-1 mb-0.5">
                  {g.icon} {g.label}
                </p>
                <ul className="text-xs text-on-surface-variant space-y-0.5 pl-4">
                  {g.items!.map((name, i) => (
                    <li key={i} className="truncate">• {name}</li>
                  ))}
                </ul>
              </div>
            ),
        )}
      </div>
    </div>
  );
}
