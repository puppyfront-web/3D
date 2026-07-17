"use client";

// ProposalEditorPanel — slide-in drawer (triggered from the canvas top-right
// "策划案" button) that surfaces the latest proposal_generation output (设计
// Brief) for the current project.
//
// Each章节 shows title + content preview + review-status badge. The user can
// flip a section between draft / review / approved; sections flagged
// `require_human_review` must reach `approved` before the export gate opens
// (PRESALE_DELIVERY_SPEC §9.1 / §10.2).
//
// Phase 1 scope (per plan Task 3): read-only preview + 审核状态切换 + 章节
// content 折叠. Inline content editing lands in a later pass — the spec calls
// it out as deferrable (plan §"风险与依赖").

import { useCallback, useEffect, useState } from "react";
import { ClipboardCheck, Loader2, X, AlertTriangle, CheckCircle2, Clock } from "lucide-react";
import { toast } from "sonner";

import {
  getProposalOutput,
  updateSectionStatus,
  type ProposalOutput,
  type ProposalSectionMeta,
  type SectionReviewStatus,
} from "@/lib/canvas-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ProposalEditorPanelProps {
  projectId: string;
  open: boolean;
  onClose: () => void;
  /** Optional callback after a section status changes — lets the canvas page
   * re-evaluate the export gate without refetching. */
  onSectionStatusChanged?: () => void;
}

const STATUS_LABEL: Record<SectionReviewStatus, string> = {
  draft: "待审核",
  review: "审核中",
  approved: "已通过",
};

function StatusBadge({ status }: { status: SectionReviewStatus }) {
  if (status === "approved") {
    return (
      <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200">
        <CheckCircle2 className="h-3 w-3" /> {STATUS_LABEL.approved}
      </Badge>
    );
  }
  if (status === "review") {
    return (
      <Badge className="bg-amber-100 text-amber-700 border-amber-200">
        <Clock className="h-3 w-3" /> {STATUS_LABEL.review}
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="text-on-surface-variant">
      {STATUS_LABEL.draft}
    </Badge>
  );
}

export function ProposalEditorPanel({
  projectId,
  open,
  onClose,
  onSectionStatusChanged,
}: ProposalEditorPanelProps) {
  const [output, setOutput] = useState<ProposalOutput | null>(null);
  const [loading, setLoading] = useState(false);
  const [busyOrder, setBusyOrder] = useState<number | null>(null);
  // Expanded section order (1-based). Toggling shows the full content preview.
  const [expandedOrder, setExpandedOrder] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getProposalOutput(projectId);
      if (res.success && res.data) {
        setOutput(res.data);
      } else {
        setOutput(null);
        if (res.message) {
          toast.error(res.message);
        }
      }
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (!open) return;
    void load();
  }, [open, load]);

  if (!open) return null;

  const handleStatusChange = async (
    section: ProposalSectionMeta,
    next: SectionReviewStatus,
  ) => {
    if (!output) return;
    if ((section.status || "draft") === next) return;
    setBusyOrder(section.order);
    try {
      const res = await updateSectionStatus(output.outputId, section.order, next);
      if (res.success && res.data) {
        setOutput(res.data);
        onSectionStatusChanged?.();
        toast.success(`「${section.title || `章节 ${section.order}`}」已标记为 ${STATUS_LABEL[next]}`);
      } else {
        toast.error(res.message || "更新审核状态失败");
      }
    } finally {
      setBusyOrder(null);
    }
  };

  const sections = output?.sectionsMeta ?? [];
  const approvedCount = sections.filter((s) => s.status === "approved").length;
  const needsReview = sections.filter((s) => s.require_human_review && s.status !== "approved");

  return (
    <div className="absolute top-0 right-0 h-full w-[440px] max-w-[92vw] z-20 p-4 overflow-auto">
      <div className="relative bg-surface-container-lowest border border-outline-variant rounded-xl shadow-lg flex flex-col max-h-full">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-outline-variant sticky top-0 bg-surface-container-lowest rounded-t-xl z-10">
          <div className="flex items-center gap-2">
            <ClipboardCheck className="h-5 w-5 text-primary" />
            <div>
              <h2 className="font-semibold text-on-surface">策划案（设计 Brief）</h2>
              <p className="text-xs text-on-surface-variant">
                {sections.length > 0
                  ? `${approvedCount}/${sections.length} 章节已通过`
                  : "暂无章节"}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-full hover:bg-surface-container-low"
            aria-label="关闭"
          >
            <X className="h-4 w-4 text-on-surface-variant" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto px-5 py-4 space-y-3">
          {loading && (
            <div className="flex items-center justify-center py-12 text-on-surface-variant">
              <Loader2 className="h-5 w-5 animate-spin mr-2" /> 加载中…
            </div>
          )}

          {!loading && !output && (
            <div className="text-center py-12 text-on-surface-variant text-sm">
              还没有策划案。请在对话中触发首轮 auto-fill（输入企业名 + 需求描述）。
            </div>
          )}

          {!loading && output && sections.length === 0 && (
            <div className="text-center py-12 text-on-surface-variant text-sm">
              策划案暂无章节元数据（sections_meta 为空）。
            </div>
          )}

          {!loading &&
            sections.map((section) => {
              const isExpanded = expandedOrder === section.order;
              const isBusy = busyOrder === section.order;
              return (
                <div
                  key={section.order}
                  className="border border-outline-variant rounded-lg p-3 bg-surface-container-low/40"
                >
                  <div className="flex items-start justify-between gap-2">
                    <button
                      onClick={() => setExpandedOrder(isExpanded ? null : section.order)}
                      className="flex-1 text-left"
                    >
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs text-on-surface-variant">
                          {String(section.order).padStart(2, "0")}
                        </span>
                        <span className="font-medium text-sm text-on-surface">
                          {section.title || section.key || `章节 ${section.order}`}
                        </span>
                        <StatusBadge status={(section.status || "draft") as SectionReviewStatus} />
                        {section.require_human_review && (
                          <Badge className="bg-rose-100 text-rose-700 border-rose-200">
                            <AlertTriangle className="h-3 w-3" /> 需人工确认
                          </Badge>
                        )}
                      </div>
                    </button>
                  </div>

                  {section.content && (
                    <div
                      className={cn(
                        "mt-2 text-xs text-on-surface-variant whitespace-pre-wrap leading-relaxed",
                        isExpanded ? "" : "line-clamp-3",
                      )}
                    >
                      {section.content}
                    </div>
                  )}

                  {isExpanded && (section.used_cases?.length || section.missing_info?.length) ? (
                    <div className="mt-2 space-y-1 text-xs">
                      {section.used_cases && section.used_cases.length > 0 && (
                        <p className="text-on-surface-variant">
                          引用案例：{section.used_cases.length} 个
                        </p>
                      )}
                      {section.missing_info && section.missing_info.length > 0 && (
                        <p className="text-amber-700">
                          ⚠️ 待确认：{section.missing_info.join("；")}
                        </p>
                      )}
                    </div>
                  ) : null}

                  {/* Status switcher */}
                  <div className="mt-3 flex items-center gap-1.5">
                    {(["draft", "review", "approved"] as SectionReviewStatus[]).map((s) => {
                      const active = (section.status || "draft") === s;
                      return (
                        <Button
                          key={s}
                          size="sm"
                          variant={active ? "default" : "outline"}
                          disabled={isBusy}
                          onClick={() => handleStatusChange(section, s)}
                          className="h-7 px-2.5 text-xs"
                        >
                          {isBusy ? <Loader2 className="h-3 w-3 animate-spin" /> : STATUS_LABEL[s]}
                        </Button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
        </div>

        {/* Footer — export gate hint */}
        {output && sections.length > 0 && (
          <div className="border-t border-outline-variant px-5 py-3 sticky bottom-0 bg-surface-container-lowest rounded-b-xl">
            {needsReview.length > 0 ? (
              <p className="text-xs text-amber-700 flex items-center gap-1.5">
                <AlertTriangle className="h-3.5 w-3.5" />
                {needsReview.length} 个需人工确认的章节尚未通过，导出将被阻断。
              </p>
            ) : (
              <p className="text-xs text-emerald-700 flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5" />
                所有需人工确认的章节已通过，可以导出。
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
