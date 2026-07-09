"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import {
  Search,
  Upload,
  Trash2,
  Package,
  Image as ImageIcon,
  FileText,
  Video,
  RotateCw,
  Database,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Clock,
} from "lucide-react";
import {
  getAssets,
  uploadAsset,
  deleteAsset,
  indexDocument,
  indexBatchDocuments,
} from "@/lib/api";
import type { Asset, AssetType } from "@/types";

const typeIcons: Record<AssetType, React.ReactNode> = {
  image: <ImageIcon className="h-4 w-4 text-green-500" />,
  video: <Video className="h-4 w-4 text-purple-500" />,
  document: <FileText className="h-4 w-4 text-blue-500" />,
  template: <FileText className="h-4 w-4 text-amber-500" />,
  model: <Package className="h-4 w-4 text-surface-tint" />,
};

const typeLabels: Record<AssetType, string> = {
  image: "图片",
  video: "视频",
  document: "文档",
  template: "模板",
  model: "3D模型",
};

const statusConfig: Record<
  string,
  { label: string; color: string; icon: React.ReactNode }
> = {
  uploaded: {
    label: "待入库",
    color: "bg-amber-100 text-amber-700",
    icon: <Clock className="h-3 w-3" />,
  },
  indexed: {
    label: "已入库",
    color: "bg-green-100 text-green-700",
    icon: <CheckCircle2 className="h-3 w-3" />,
  },
  error: {
    label: "入库失败",
    color: "bg-red-100 text-red-700",
    icon: <AlertCircle className="h-3 w-3" />,
  },
  pending: {
    label: "处理中",
    color: "bg-gray-100 text-gray-600",
    icon: <Loader2 className="h-3 w-3 animate-spin" />,
  },
};

export default function AssetsPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filterType, setFilterType] = useState<string>("all");
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [selected, setSelected] = useState<Asset | null>(null);
  const [indexingIds, setIndexingIds] = useState<Set<string>>(new Set());
  const [batchIndexing, setBatchIndexing] = useState(false);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadAssets = useCallback(async () => {
    setLoading(true);
    const result = await getAssets();
    if (result.success && result.data) {
      setAssets(result.data);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadAssets();
  }, [loadAssets]);

  // --- Upload ---
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    const result = await uploadAsset(file, undefined, true);
    if (result.success && result.data) {
      setAssets((prev) => [result.data!, ...prev]);
    }
    setUploading(false);
    setUploadDialogOpen(false);
    // Reset file input
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // --- Delete ---
  const openDelete = (asset: Asset) => {
    setSelected(asset);
    setDeleteOpen(true);
  };

  const handleDelete = async () => {
    if (!selected) return;
    setDeleting(true);
    try {
      const result = await deleteAsset(selected.id);
      if (result.success) {
        setAssets((prev) => prev.filter((a) => a.id !== selected.id));
      }
      setDeleteOpen(false);
      setSelected(null);
    } finally {
      setDeleting(false);
    }
  };

  // --- Single index ---
  const handleIndex = async (id: string) => {
    setIndexingIds((prev) => new Set(prev).add(id));
    const result = await indexDocument(id);
    if (result.success && result.data) {
      setAssets((prev) =>
        prev.map((a) =>
          a.id === id
            ? {
                ...a,
                status: result.data!.status as Asset["status"],
                chunk_count: result.data!.chunk_count,
              }
            : a
        )
      );
    }
    setIndexingIds((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  };

  // --- Batch index ---
  const handleBatchIndex = async () => {
    const unindexedIds = assets
      .filter((a) => a.status !== "indexed")
      .map((a) => a.id);
    if (unindexedIds.length === 0) return;

    setBatchIndexing(true);
    // Mark all as indexing
    setIndexingIds((prev) => {
      const next = new Set(prev);
      unindexedIds.forEach((id) => next.add(id));
      return next;
    });

    const result = await indexBatchDocuments(unindexedIds);
    if (result.success) {
      // Reload to get updated statuses
      await loadAssets();
    }
    setBatchIndexing(false);
    setIndexingIds(new Set());
  };

  // --- Filtering ---
  const filtered = assets.filter((a) => {
    const matchesSearch = a.name.toLowerCase().includes(search.toLowerCase());
    const matchesType = filterType === "all" || a.type === filterType;
    return matchesSearch && matchesType;
  });

  const unindexedCount = assets.filter((a) => a.status !== "indexed").length;

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-on-surface">
            知识库资料管理
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            上传文档到知识库，自动解析入库供 RAG 检索使用
          </p>
        </div>
        <div className="flex gap-2">
          {unindexedCount > 0 && (
            <Button
              variant="outline"
              className="gap-2 border-primary text-primary"
              onClick={handleBatchIndex}
              disabled={batchIndexing}
            >
              {batchIndexing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Database className="h-4 w-4" />
              )}
              批量入库 ({unindexedCount})
            </Button>
          )}

          {/* Upload Dialog */}
          <Dialog
            open={uploadDialogOpen}
            onOpenChange={setUploadDialogOpen}
          >
            <DialogTrigger asChild>
              <Button className="bg-primary hover:bg-primary gap-2">
                <Upload className="h-4 w-4" /> 上传资料
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>上传资料到知识库</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 mt-4">
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-primary transition-colors">
                  {uploading ? (
                    <>
                      <Loader2 className="h-8 w-8 mx-auto text-primary mb-2 animate-spin" />
                      <p className="text-sm text-primary">
                        上传并入库中...
                      </p>
                    </>
                  ) : (
                    <>
                      <Upload className="h-8 w-8 mx-auto text-gray-400 mb-2" />
                      <p className="text-sm text-gray-500">
                        点击选择文件上传
                      </p>
                      <p className="text-xs text-gray-400 mt-1">
                        支持 PDF / PPTX / DOCX / XLSX / TXT / MD
                      </p>
                      <p className="text-xs text-gray-400">
                        上传后自动解析入库到知识库
                      </p>
                    </>
                  )}
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.pptx,.docx,.xlsx,.txt,.md"
                  className="hidden"
                  onChange={handleFileSelect}
                />
                <Button
                  className="w-full bg-primary hover:bg-primary"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                >
                  {uploading ? "处理中..." : "选择文件"}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            placeholder="搜索资料..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 h-9"
          />
        </div>
        <div className="flex gap-1.5">
          {["all", "image", "video", "document", "template", "model"].map(
            (t) => (
              <Button
                key={t}
                variant={filterType === t ? "default" : "outline"}
                size="sm"
                onClick={() => setFilterType(t)}
                className={
                  filterType === t ? "bg-primary hover:bg-primary" : ""
                }
              >
                {t === "all"
                  ? "全部"
                  : typeLabels[t as AssetType] || t}
              </Button>
            )
          )}
        </div>
      </div>

      {/* Table */}
      <Card className="border-gray-200">
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 text-primary animate-spin" />
              <span className="ml-2 text-sm text-gray-500">加载中...</span>
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-gray-400">
              <FileText className="h-8 w-8 mb-2" />
              <p className="text-sm">暂无资料，点击上传添加</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">资料名称</TableHead>
                  <TableHead className="text-xs">类型</TableHead>
                  <TableHead className="text-xs">大小</TableHead>
                  <TableHead className="text-xs">知识库状态</TableHead>
                  <TableHead className="text-xs">分块数</TableHead>
                  <TableHead className="text-xs">上传时间</TableHead>
                  <TableHead className="text-xs">标签</TableHead>
                  <TableHead className="text-xs text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((asset) => {
                  const status = statusConfig[asset.status] || statusConfig.uploaded;
                  const isIndexing = indexingIds.has(asset.id);

                  return (
                    <TableRow key={asset.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {typeIcons[asset.type]}
                          <span className="text-sm font-medium text-on-surface">
                            {asset.name}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary" className="text-xs">
                          {typeLabels[asset.type] || asset.type}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-gray-500">
                        {asset.size}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={`text-xs gap-1 ${status.color}`}
                        >
                          {isIndexing ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            status.icon
                          )}
                          {isIndexing ? "入库中" : status.label}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-gray-500">
                        {asset.status === "indexed" ? (
                          <span className="text-green-600 font-medium">
                            {asset.chunk_count}
                          </span>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </TableCell>
                      <TableCell className="text-sm text-gray-500">
                        {asset.uploadedAt}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          {asset.tags.slice(0, 2).map((tag) => (
                            <Badge
                              key={tag}
                              variant="outline"
                              className="text-xs"
                            >
                              {tag}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          {asset.status !== "indexed" && !isIndexing && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 w-7 p-0 text-primary"
                              title="入知识库"
                              onClick={() => handleIndex(asset.id)}
                            >
                              <Database className="h-3.5 w-3.5" />
                            </Button>
                          )}
                          {asset.status === "indexed" && !isIndexing && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 w-7 p-0 text-gray-400"
                              title="重新入库"
                              onClick={() => handleIndex(asset.id)}
                            >
                              <RotateCw className="h-3.5 w-3.5" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 w-7 p-0 text-error"
                            title="删除"
                            onClick={() => openDelete(asset)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation */}
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-gray-600">
            确定要删除资料「{selected?.name}」吗？此操作不可撤销。
          </p>
          <DialogFooter className="mt-4 gap-2">
            <DialogClose asChild><Button variant="outline">取消</Button></DialogClose>
            <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
              {deleting ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null} 删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
