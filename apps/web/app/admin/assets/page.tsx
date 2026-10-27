"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  ChevronLeft,
  ChevronRight,
  Eye,
  Download,
} from "lucide-react";
import { toast } from "sonner";
import {
  getAssets,
  uploadAsset,
  deleteAsset,
  deleteAssetsBatch,
  exportAssets,
  importKnowledgePack,
  indexDocument,
  indexBatchDocuments,
} from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import { DocumentDetailDialog } from "@/components/admin/document-detail-dialog";
import { Checkbox } from "@/components/ui/checkbox";
import type { Asset, AssetType } from "@/types";

const PAGE_SIZE = 20;

const DOC_CATEGORIES = [
  "企业介绍",
  "产品资料",
  "技术资料",
  "荣誉资质",
  "案例资料",
  "发展历程",
  "社会责任",
  "参考案例",
  "其他资料",
] as const;

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

const parseStatusConfig: Record<string, { label: string; color: string }> = {
  uploaded: { label: "待解析", color: "bg-gray-100 text-gray-600" },
  parsing: { label: "解析中", color: "bg-blue-100 text-blue-700" },
  parsed: { label: "已解析", color: "bg-green-100 text-green-700" },
  parse_failed: { label: "解析失败", color: "bg-red-100 text-red-700" },
  classified: { label: "已归类", color: "bg-purple-100 text-purple-700" },
  pending_confirm: { label: "待确认", color: "bg-amber-100 text-amber-700" },
  indexed: { label: "已解析", color: "bg-green-100 text-green-700" },
  error: { label: "失败", color: "bg-red-100 text-red-700" },
};

function AssetsPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const docParam = searchParams.get("doc");

  const [assets, setAssets] = useState<Asset[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [filterType, setFilterType] = useState<string>("all");
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [filterParseStatus, setFilterParseStatus] = useState<string>("all");
  const [filterCategory, setFilterCategory] = useState<string>("all");
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [selected, setSelected] = useState<Asset | null>(null);
  const [indexingIds, setIndexingIds] = useState<Set<string>>(new Set());
  const [batchIndexing, setBatchIndexing] = useState(false);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [detailDocId, setDetailDocId] = useState<string | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchDeleteOpen, setBatchDeleteOpen] = useState(false);
  const [batchDeleting, setBatchDeleting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [packImporting, setPackImporting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const packInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (docParam) {
      setDetailDocId(docParam);
      setDetailOpen(true);
    }
  }, [docParam]);

  const loadAssets = useCallback(async () => {
    setLoading(true);
    const result = await getAssets({
      page,
      pageSize: PAGE_SIZE,
      status: filterStatus !== "all" ? filterStatus : undefined,
      parseStatus: filterParseStatus !== "all" ? filterParseStatus : undefined,
      category: filterCategory !== "all" ? filterCategory : undefined,
      q: search || undefined,
    });
    if (result.success && result.data) {
      setAssets(result.data.items);
      setTotal(result.data.total);
      setTotalPages(result.data.totalPages);
      // Selection is page-scoped: drop ids that are no longer visible so a
      // batch action can never hit a row the admin can't see.
      const visible = new Set(result.data.items.map((a) => a.id));
      setSelectedIds((prev) => new Set([...prev].filter((id) => visible.has(id))));
    }
    setLoading(false);
  }, [page, filterStatus, filterParseStatus, filterCategory, search]);

  useEffect(() => {
    loadAssets();
  }, [loadAssets]);

  function handleSearchSubmit(e?: React.FormEvent) {
    e?.preventDefault();
    setPage(1);
    setSearch(searchInput.trim());
  }

  function handleDetailClose(open: boolean) {
    setDetailOpen(open);
    if (!open && docParam) {
      router.replace("/admin/assets");
    }
  }

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    const result = await uploadAsset(file, undefined, true);
    if (result.success) {
      await loadAssets();
    }
    setUploading(false);
    setUploadDialogOpen(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

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
        await loadAssets();
      }
      setDeleteOpen(false);
      setSelected(null);
    } finally {
      setDeleting(false);
    }
  };

  const handleIndex = async (id: string) => {
    setIndexingIds((prev) => new Set(prev).add(id));
    const result = await indexDocument(id);
    if (result.success) {
      await loadAssets();
    }
    setIndexingIds((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  };

  const handleBatchIndex = async () => {
    const unindexedIds = assets
      .filter((a) => a.status !== "indexed")
      .map((a) => a.id);
    if (unindexedIds.length === 0) return;

    setBatchIndexing(true);
    setIndexingIds(new Set(unindexedIds));
    const result = await indexBatchDocuments(unindexedIds);
    if (result.success) {
      await loadAssets();
    }
    setBatchIndexing(false);
    setIndexingIds(new Set());
  };

  const handleBatchDelete = async () => {
    const ids = [...selectedIds];
    if (ids.length === 0) return;
    setBatchDeleting(true);
    try {
      const result = await deleteAssetsBatch(ids);
      if (result.success && result.data) {
        toast.success(`已删除 ${result.data.deleted} 份资料`);
        setSelectedIds(new Set());
        await loadAssets();
      } else {
        toast.error(result.message ?? "批量删除失败");
      }
      setBatchDeleteOpen(false);
    } finally {
      setBatchDeleting(false);
    }
  };

  const handleExport = async (scope: "selection" | "filtered") => {
    setExporting(true);
    try {
      const blob = await exportAssets(
        scope === "selection"
          ? { documentIds: [...selectedIds] }
          : {
              status: filterStatus !== "all" ? filterStatus : undefined,
              parseStatus: filterParseStatus !== "all" ? filterParseStatus : undefined,
              category: filterCategory !== "all" ? filterCategory : undefined,
              q: search || undefined,
            },
      );
      downloadBlob(blob, `资料清单-${new Date().toISOString().slice(0, 10)}.csv`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "导出失败");
    } finally {
      setExporting(false);
    }
  };

  const filteredByType =
    filterType === "all" ? assets : assets.filter((a) => a.type === filterType);
  const unindexedOnPage = filteredByType.filter((a) => a.status !== "indexed").length;
  const selectedOnPage = filteredByType.filter((a) => selectedIds.has(a.id)).length;
  const allSelectedOnPage =
    filteredByType.length > 0 && selectedOnPage === filteredByType.length;

  function toggleSelectAll(checked: boolean) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      filteredByType.forEach((a) => (checked ? next.add(a.id) : next.delete(a.id)));
      return next;
    });
  }

  function toggleSelected(id: string, checked: boolean) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  return (
    <div className="p-6">
      <DocumentDetailDialog
        documentId={detailDocId}
        open={detailOpen}
        onOpenChange={handleDetailClose}
        onUpdated={() => loadAssets()}
      />

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-on-surface">知识库资料管理</h1>
          <p className="text-sm text-gray-500 mt-1">
            上传文档到知识库，自动解析入库供 RAG 检索使用 · 共 {total} 份
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            className="gap-2"
            onClick={() => handleExport(selectedIds.size > 0 ? "selection" : "filtered")}
            disabled={exporting || (total === 0 && selectedIds.size === 0)}
          >
            {exporting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            {selectedIds.size > 0 ? `导出所选 (${selectedIds.size})` : "导出清单"}
          </Button>

          {selectedIds.size > 0 && (
            <Button
              variant="outline"
              className="gap-2 border-error text-error hover:bg-error/5"
              onClick={() => setBatchDeleteOpen(true)}
            >
              <Trash2 className="h-4 w-4" />
              批量删除 ({selectedIds.size})
            </Button>
          )}

          {unindexedOnPage > 0 && (
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
              本页批量入库 ({unindexedOnPage})
            </Button>
          )}

          <input
            ref={packInputRef}
            type="file"
            accept=".zip,application/zip"
            className="hidden"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              setPackImporting(true);
              const res = await importKnowledgePack(file);
              setPackImporting(false);
              if (packInputRef.current) packInputRef.current.value = "";
              if (res.success && res.data) {
                if (res.data.skipped) {
                  toast.message("该 Pack 已导入过（内容相同）");
                } else {
                  toast.success(
                    `Pack 导入完成：${res.data.documents_imported} 份资料，${res.data.talking_points_imported} 条话术`
                  );
                }
                await loadAssets();
              } else {
                toast.error(res.message ?? "Pack 导入失败");
              }
            }}
          />
          <Button
            variant="outline"
            className="gap-2"
            disabled={packImporting}
            onClick={() => packInputRef.current?.click()}
          >
            {packImporting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Package className="h-4 w-4" />
            )}
            导入 Knowledge Pack
          </Button>

          <Dialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}>
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
                      <p className="text-sm text-primary">上传并入库中...</p>
                    </>
                  ) : (
                    <>
                      <Upload className="h-8 w-8 mx-auto text-gray-400 mb-2" />
                      <p className="text-sm text-gray-500">点击选择文件上传</p>
                      <p className="text-xs text-gray-400 mt-1">
                        支持 PDF / PPTX / DOCX / XLSX / TXT / MD
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

      <div className="flex flex-col gap-3 mb-4">
        <form onSubmit={handleSearchSubmit} className="flex items-center gap-3 flex-wrap">
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              placeholder="搜索文件名..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="pl-9 h-9"
            />
          </div>
          <Button type="submit" variant="outline" size="sm">
            搜索
          </Button>
          <Select
            value={filterStatus}
            onValueChange={(v) => {
              setFilterStatus(v);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-32 h-9">
              <SelectValue placeholder="入库状态" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部状态</SelectItem>
              <SelectItem value="uploaded">待入库</SelectItem>
              <SelectItem value="indexed">已入库</SelectItem>
              <SelectItem value="error">入库失败</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={filterParseStatus}
            onValueChange={(v) => {
              setFilterParseStatus(v);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-32 h-9">
              <SelectValue placeholder="解析状态" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部解析</SelectItem>
              <SelectItem value="uploaded">待解析</SelectItem>
              <SelectItem value="parsed">已解析</SelectItem>
              <SelectItem value="parse_failed">解析失败</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={filterCategory}
            onValueChange={(v) => {
              setFilterCategory(v);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-36 h-9">
              <SelectValue placeholder="分类" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部分类</SelectItem>
              {DOC_CATEGORIES.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </form>

        <div className="flex gap-1.5 flex-wrap">
          {["all", "image", "video", "document", "template", "model"].map((t) => (
            <Button
              key={t}
              variant={filterType === t ? "default" : "outline"}
              size="sm"
              onClick={() => setFilterType(t)}
              className={filterType === t ? "bg-primary hover:bg-primary" : ""}
            >
              {t === "all" ? "全部类型" : typeLabels[t as AssetType] || t}
            </Button>
          ))}
        </div>
      </div>

      <Card className="border-gray-200">
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 text-primary animate-spin" />
              <span className="ml-2 text-sm text-gray-500">加载中...</span>
            </div>
          ) : filteredByType.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-gray-400">
              <FileText className="h-8 w-8 mb-2" />
              <p className="text-sm">暂无资料，点击上传添加</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8">
                    <Checkbox
                      checked={allSelectedOnPage}
                      onCheckedChange={(v) => toggleSelectAll(v === true)}
                      aria-label="全选本页"
                    />
                  </TableHead>
                  <TableHead className="text-xs">资料名称</TableHead>
                  <TableHead className="text-xs">类型</TableHead>
                  <TableHead className="text-xs">分类</TableHead>
                  <TableHead className="text-xs">大小</TableHead>
                  <TableHead className="text-xs">入库状态</TableHead>
                  <TableHead className="text-xs">解析状态</TableHead>
                  <TableHead className="text-xs">分块数</TableHead>
                  <TableHead className="text-xs">上传时间</TableHead>
                  <TableHead className="text-xs text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredByType.map((asset) => {
                  const status = statusConfig[asset.status] || statusConfig.uploaded;
                  const parseMeta =
                    parseStatusConfig[asset.parse_status ?? ""] ??
                    parseStatusConfig.uploaded;
                  const isIndexing = indexingIds.has(asset.id);

                  return (
                    <TableRow key={asset.id} data-state={selectedIds.has(asset.id) ? "selected" : undefined}>
                      <TableCell>
                        <Checkbox
                          checked={selectedIds.has(asset.id)}
                          onCheckedChange={(v) => toggleSelected(asset.id, v === true)}
                          aria-label={`选择 ${asset.name}`}
                        />
                      </TableCell>
                      <TableCell>
                        <button
                          type="button"
                          className="flex items-center gap-2 text-left hover:text-primary"
                          onClick={() => {
                            setDetailDocId(asset.id);
                            setDetailOpen(true);
                          }}
                        >
                          {typeIcons[asset.type]}
                          <span className="text-sm font-medium text-on-surface">
                            {asset.name}
                          </span>
                        </button>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary" className="text-xs">
                          {typeLabels[asset.type] || asset.type}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-gray-600">
                        {asset.category && asset.category !== "document"
                          ? asset.category
                          : "—"}
                      </TableCell>
                      <TableCell className="text-sm text-gray-500">{asset.size}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className={`text-xs gap-1 ${status.color}`}>
                          {isIndexing ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            status.icon
                          )}
                          {isIndexing ? "入库中" : status.label}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className={`text-xs ${parseMeta.color}`}>
                          {parseMeta.label}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-gray-500">
                        {asset.status === "indexed" ? (
                          <span className="text-green-600 font-medium">
                            {asset.chunk_count}
                          </span>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </TableCell>
                      <TableCell className="text-sm text-gray-500">
                        {new Date(asset.uploadedAt).toLocaleDateString("zh-CN")}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 w-7 p-0 text-gray-500"
                            title="查看详情"
                            onClick={() => {
                              setDetailDocId(asset.id);
                              setDetailOpen(true);
                            }}
                          >
                            <Eye className="h-3.5 w-3.5" />
                          </Button>
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

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4 text-sm text-gray-500">
          <span>
            第 {page} / {totalPages} 页，共 {total} 条
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1 || loading}
              onClick={() => setPage((p) => p - 1)}
            >
              <ChevronLeft className="h-4 w-4" />
              上一页
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages || loading}
              onClick={() => setPage((p) => p + 1)}
            >
              下一页
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      <Dialog open={batchDeleteOpen} onOpenChange={setBatchDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认批量删除</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-gray-600">
            将删除所选 {selectedIds.size} 份资料及其知识库分块，删除后问答将不再引用这些内容。此操作不可撤销。
          </p>
          <DialogFooter className="mt-4 gap-2">
            <DialogClose asChild>
              <Button variant="outline">取消</Button>
            </DialogClose>
            <Button variant="destructive" onClick={handleBatchDelete} disabled={batchDeleting}>
              {batchDeleting ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
              删除 {selectedIds.size} 份
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-gray-600">
            确定要删除资料「{selected?.name}」吗？此操作不可撤销。
          </p>
          <DialogFooter className="mt-4 gap-2">
            <DialogClose asChild>
              <Button variant="outline">取消</Button>
            </DialogClose>
            <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
              {deleting ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null} 删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function AssetsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-6 w-6 text-primary animate-spin" />
        </div>
      }
    >
      <AssetsPageInner />
    </Suspense>
  );
}
