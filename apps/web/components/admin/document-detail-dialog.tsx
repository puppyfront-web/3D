"use client";

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loader2, Database, RotateCw } from "lucide-react";
import { getDocument, indexDocument } from "@/lib/api";
import type { Asset } from "@/types";

const STATUS_LABEL: Record<string, string> = {
  uploaded: "待入库",
  indexed: "已入库",
  error: "入库失败",
  pending: "处理中",
};

const PARSE_LABEL: Record<string, string> = {
  uploaded: "待解析",
  parsing: "解析中",
  parsed: "已解析",
  parse_failed: "解析失败",
  classified: "已归类",
  pending_confirm: "待确认",
  indexed: "已解析",
  error: "解析失败",
};

interface DocumentDetailDialogProps {
  documentId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUpdated?: (asset: Asset) => void;
}

export function DocumentDetailDialog({
  documentId,
  open,
  onOpenChange,
  onUpdated,
}: DocumentDetailDialogProps) {
  const [loading, setLoading] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [doc, setDoc] = useState<Asset | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !documentId) {
      setDoc(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    getDocument(documentId).then((res) => {
      if (cancelled) return;
      if (res.success && res.data) {
        setDoc(res.data);
        setError(null);
      } else {
        setDoc(null);
        setError(res.message ?? "加载失败");
      }
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [open, documentId]);

  async function handleReindex() {
    if (!doc) return;
    setIndexing(true);
    const res = await indexDocument(doc.id);
    if (res.success) {
      const refreshed = await getDocument(doc.id);
      if (refreshed.success && refreshed.data) {
        setDoc(refreshed.data);
        onUpdated?.(refreshed.data);
      }
    }
    setIndexing(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="truncate pr-6">{doc?.name ?? "资料详情"}</DialogTitle>
        </DialogHeader>
        {loading ? (
          <div className="flex items-center justify-center py-8 text-outline">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        ) : error ? (
          <p className="text-sm text-error py-4">{error}</p>
        ) : doc ? (
          <div className="space-y-4 text-sm">
            <dl className="grid grid-cols-2 gap-3">
              <div>
                <dt className="text-xs text-outline">知识库状态</dt>
                <dd className="mt-0.5">
                  <Badge variant="outline">{STATUS_LABEL[doc.status] ?? doc.status}</Badge>
                </dd>
              </div>
              <div>
                <dt className="text-xs text-outline">解析状态</dt>
                <dd className="mt-0.5">
                  <Badge variant="secondary">
                    {PARSE_LABEL[doc.parse_status ?? ""] ?? doc.parse_status ?? "—"}
                  </Badge>
                </dd>
              </div>
              <div>
                <dt className="text-xs text-outline">分类</dt>
                <dd className="mt-0.5 text-on-surface">{doc.category || "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-outline">分块数</dt>
                <dd className="mt-0.5 text-on-surface">{doc.chunk_count || "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-outline">文件大小</dt>
                <dd className="mt-0.5 text-on-surface">{doc.size}</dd>
              </div>
              <div>
                <dt className="text-xs text-outline">上传时间</dt>
                <dd className="mt-0.5 text-on-surface">
                  {new Date(doc.uploadedAt).toLocaleString("zh-CN")}
                </dd>
              </div>
            </dl>
            <div className="flex gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5"
                onClick={handleReindex}
                disabled={indexing}
              >
                {indexing ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : doc.status === "indexed" ? (
                  <RotateCw className="h-3.5 w-3.5" />
                ) : (
                  <Database className="h-3.5 w-3.5" />
                )}
                {doc.status === "indexed" ? "重新入库" : "入知识库"}
              </Button>
            </div>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
