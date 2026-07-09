"use client";

import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
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
  DialogFooter,
  DialogClose,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Plus, Search, Eye, Edit3, Trash2, Download, Loader2, ImageIcon } from "lucide-react";
import { getCases, createCase, updateCase, deleteCase, importCases, exportCases, exportCase } from "@/lib/api";
import { INDUSTRIES } from "@/lib/constants";
import { downloadBlob } from "@/lib/download";
import { FileUploadButton } from "@/components/admin/file-upload-button";
import type { CaseItem, ImportMode } from "@/types";

const statusColor = {
  published: "text-[#00875a] bg-green-50",
  draft: "text-gray-500 bg-gray-100",
  archived: "text-error bg-red-50",
};

const statusLabel = {
  published: "已发布",
  draft: "草稿",
  archived: "已归档",
};

export default function CasesPage() {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [editingCase, setEditingCase] = useState<CaseItem | null>(null);
  const [deletingCase, setDeletingCase] = useState<CaseItem | null>(null);

  // Form state
  const [formTitle, setFormTitle] = useState("");
  const [formClient, setFormClient] = useState("");
  const [formIndustry, setFormIndustry] = useState("");
  const [formStatus, setFormStatus] = useState<CaseItem["status"]>("draft");
  const [formOutcome, setFormOutcome] = useState("");
  const [formHighlights, setFormHighlights] = useState("");
  // New edit-only fields
  const [formProjectType, setFormProjectType] = useState("");
  const [formStyleTag, setFormStyleTag] = useState("");
  const [formTags, setFormTags] = useState("");
  const [formIsDesensitized, setFormIsDesensitized] = useState(false);

  const resetForm = () => {
    setFormTitle("");
    setFormClient("");
    setFormIndustry("");
    setFormStatus("draft");
    setFormOutcome("");
    setFormHighlights("");
    setFormProjectType("");
    setFormStyleTag("");
    setFormTags("");
    setFormIsDesensitized(false);
  };

  const loadCases = useCallback(async () => {
    setLoading(true);
    const result = await getCases();
    if (result.success && result.data) {
      setCases(result.data);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadCases();
  }, [loadCases]);

  // --- Import ---
  const handleImport = async (file: File, mode: ImportMode) => {
    const res = await importCases(file, undefined, mode);
    if (res.success && res.data) {
      await loadCases();
      return res.data;
    }
    throw new Error(res.message || "导入失败");
  };

  // --- Export ---
  const handleExport = async () => {
    const blob = await exportCases();
    downloadBlob(blob, "cases.json");
  };

  const handleExportOne = async (item: CaseItem) => {
    const blob = await exportCase(item.id);
    downloadBlob(blob, `${item.title.replace(/[/\\:*?"<>|]/g, "_")}.json`);
  };

  // --- Create ---
  const handleCreate = async () => {
    setSubmitting(true);
    const data: Partial<CaseItem> = {
      title: formTitle,
      client: formClient,
      industry: formIndustry,
      status: formStatus,
      outcome: formOutcome,
      highlights: formHighlights
        .split("\n")
        .map((h) => h.trim())
        .filter(Boolean),
    };
    const result = await createCase(data);
    if (result.success) {
      setCreateDialogOpen(false);
      resetForm();
      await loadCases();
    }
    setSubmitting(false);
  };

  // --- Edit ---
  const openEdit = (item: CaseItem) => {
    setEditingCase(item);
    setFormTitle(item.title);
    setFormClient(item.client);
    setFormIndustry(item.industry);
    setFormStatus(item.status);
    setFormOutcome(item.outcome);
    setFormHighlights(item.highlights.join("\n"));
    setFormProjectType(item.projectType ?? "");
    setFormStyleTag(item.styleTag ?? "");
    setFormTags((item.tags ?? []).join(", "));
    setFormIsDesensitized(item.isDesensitized ?? false);
    setEditDialogOpen(true);
  };

  const handleEdit = async () => {
    if (!editingCase) return;
    setSubmitting(true);
    const data: Partial<CaseItem> = {
      title: formTitle,
      client: formClient,
      industry: formIndustry,
      status: formStatus,
      outcome: formOutcome,
      highlights: formHighlights
        .split("\n")
        .map((h) => h.trim())
        .filter(Boolean),
      projectType: formProjectType,
      styleTag: formStyleTag,
      tags: formTags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
      isDesensitized: formIsDesensitized,
    };
    const result = await updateCase(editingCase.id, data);
    if (result.success) {
      setEditDialogOpen(false);
      setEditingCase(null);
      resetForm();
      await loadCases();
    }
    setSubmitting(false);
  };

  // --- Delete (with confirmation) ---
  const openDelete = (item: CaseItem) => {
    setDeletingCase(item);
    setDeleteDialogOpen(true);
  };

  const handleDelete = async () => {
    if (!deletingCase) return;
    setSubmitting(true);
    const result = await deleteCase(deletingCase.id);
    if (result.success) {
      setCases((prev) => prev.filter((c) => c.id !== deletingCase.id));
      setDeleteDialogOpen(false);
      setDeletingCase(null);
    }
    setSubmitting(false);
  };

  const filtered = cases.filter(
    (c) =>
      c.title.toLowerCase().includes(search.toLowerCase()) ||
      c.client.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-on-surface">案例库管理</h1>
          <p className="text-sm text-gray-500 mt-1">
            管理成功案例，用于方案参考和素材复用
          </p>
        </div>
        <div className="flex items-center gap-2">
          <FileUploadButton
            accept=".json,.csv"
            dialogTitle="导入案例"
            dialogDescription="支持 JSON、CSV 格式。JSON 支持单条或数组。CSV 首行为表头。"
            onUpload={handleImport}
          />
          <Button variant="outline" size="sm" className="gap-1.5" onClick={handleExport}>
            <Download className="h-3.5 w-3.5" />
            导出
          </Button>
          <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button className="bg-primary hover:bg-primary gap-2">
                <Plus className="h-4 w-4" /> 新建案例
              </Button>
            </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>新建案例</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>案例标题</Label>
                  <Input
                    placeholder="输入案例标题"
                    value={formTitle}
                    onChange={(e) => setFormTitle(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>客户名称</Label>
                  <Input
                    placeholder="输入客户名称"
                    value={formClient}
                    onChange={(e) => setFormClient(e.target.value)}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>所属行业</Label>
                  <Select
                    value={formIndustry}
                    onValueChange={setFormIndustry}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="选择行业" />
                    </SelectTrigger>
                    <SelectContent>
                      {INDUSTRIES.map((ind) => (
                        <SelectItem key={ind} value={ind}>{ind}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>状态</Label>
                  <Select
                    value={formStatus}
                    onValueChange={(v) =>
                      setFormStatus(v as CaseItem["status"])
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="draft">草稿</SelectItem>
                      <SelectItem value="published">发布</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-2">
                <Label>项目成果</Label>
                <Input
                  placeholder="描述项目成果"
                  value={formOutcome}
                  onChange={(e) => setFormOutcome(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>项目亮点</Label>
                <Textarea
                  rows={3}
                  placeholder="每行一个亮点..."
                  value={formHighlights}
                  onChange={(e) => setFormHighlights(e.target.value)}
                />
              </div>
              <Button
                className="w-full bg-primary hover:bg-primary"
                onClick={handleCreate}
                disabled={submitting}
              >
                {submitting ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : null}
                创建案例
              </Button>
            </div>
          </DialogContent>
        </Dialog>
        </div>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            placeholder="搜索案例..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 h-9"
          />
        </div>
      </div>

      <Card className="border-gray-200">
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 text-primary animate-spin" />
              <span className="ml-2 text-sm text-gray-500">加载中...</span>
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-gray-400">
              <Eye className="h-8 w-8 mb-2" />
              <p className="text-sm">暂无案例，点击新建添加</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">案例标题</TableHead>
                  <TableHead className="text-xs">客户</TableHead>
                  <TableHead className="text-xs">行业</TableHead>
                  <TableHead className="text-xs">项目成果</TableHead>
                  <TableHead className="text-xs">创建时间</TableHead>
                  <TableHead className="text-xs">参考图</TableHead>
                  <TableHead className="text-xs">状态</TableHead>
                  <TableHead className="text-xs text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="text-sm font-medium text-on-surface">
                      {item.title}
                    </TableCell>
                    <TableCell className="text-sm text-gray-600">
                      {item.client}
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="text-xs">
                        {item.industry}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-gray-500 max-w-xs truncate">
                      {item.outcome}
                    </TableCell>
                    <TableCell className="text-sm text-gray-500">
                      {item.createdAt}
                    </TableCell>
                    <TableCell>
                      {item.referenceImages && item.referenceImages.length > 0 ? (
                        <div className="flex -space-x-1">
                          {item.referenceImages.slice(0, 3).map((img, i) => (
                            <div
                              key={i}
                              className="relative w-6 h-6 rounded border border-white bg-gray-100 overflow-hidden"
                              title={img.caption || img.photo_type}
                            >
                              {img.url ? (
                                <Image
                                  src={img.url}
                                  alt=""
                                  fill
                                  unoptimized
                                  className="object-cover"
                                />
                              ) : (
                                <ImageIcon className="w-3 h-3 m-auto text-gray-300" />
                              )}
                            </div>
                          ))}
                          {item.referenceImages.length > 3 && (
                            <span className="text-[10px] text-gray-400 ml-2">+{item.referenceImages.length - 3}</span>
                          )}
                        </div>
                      ) : (
                        <span className="text-xs text-gray-300">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${statusColor[item.status]}`}
                      >
                        {statusLabel[item.status]}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 w-7 p-0"
                          onClick={() => handleExportOne(item)}
                        >
                          <Download className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 w-7 p-0"
                          onClick={() => openEdit(item)}
                          title="查看/编辑"
                        >
                          <Eye className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 w-7 p-0"
                          onClick={() => openEdit(item)}
                          title="编辑"
                        >
                          <Edit3 className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 w-7 p-0 text-error"
                          onClick={() => openDelete(item)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>编辑案例</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>案例标题</Label>
                <Input
                  placeholder="输入案例标题"
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>客户名称</Label>
                <Input
                  placeholder="输入客户名称"
                  value={formClient}
                  onChange={(e) => setFormClient(e.target.value)}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>所属行业</Label>
                <Select value={formIndustry} onValueChange={setFormIndustry}>
                  <SelectTrigger>
                    <SelectValue placeholder="选择行业" />
                  </SelectTrigger>
                  <SelectContent>
                    {INDUSTRIES.map((ind) => (
                      <SelectItem key={ind} value={ind}>{ind}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>状态</Label>
                <Select
                  value={formStatus}
                  onValueChange={(v) =>
                    setFormStatus(v as CaseItem["status"])
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="draft">草稿</SelectItem>
                    <SelectItem value="published">发布</SelectItem>
                    <SelectItem value="archived">已归档</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label>项目成果</Label>
              <Input
                placeholder="描述项目成果"
                value={formOutcome}
                onChange={(e) => setFormOutcome(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>项目类型</Label>
                <Input
                  placeholder="如：智慧城市可视化"
                  value={formProjectType}
                  onChange={(e) => setFormProjectType(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>风格标签</Label>
                <Input
                  placeholder="如：科技感/深色系"
                  value={formStyleTag}
                  onChange={(e) => setFormStyleTag(e.target.value)}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>标签</Label>
              <Input
                placeholder="多个标签用英文逗号分隔..."
                value={formTags}
                onChange={(e) => setFormTags(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>项目亮点</Label>
              <Textarea
                rows={3}
                placeholder="每行一个亮点..."
                value={formHighlights}
                onChange={(e) => setFormHighlights(e.target.value)}
              />
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id="case-desensitized"
                checked={formIsDesensitized}
                onCheckedChange={(v) => setFormIsDesensitized(v === true)}
              />
              <Label htmlFor="case-desensitized" className="cursor-pointer">
                脱敏处理（开启后客户名称将作为脱敏标记，原始名称由后端保留）
              </Label>
            </div>

            {/* Reference Images (read-only preview, editable via API/JSON import) */}
            {editingCase?.referenceImages && editingCase.referenceImages.length > 0 && (
              <div className="space-y-2">
                <Label className="flex items-center gap-1.5">
                  <ImageIcon className="h-3.5 w-3.5" />
                  参考图片 ({editingCase.referenceImages.length})
                </Label>
                <div className="grid grid-cols-3 gap-2">
                  {editingCase.referenceImages.map((img, i) => (
                    <div key={i} className="rounded-lg border border-gray-200 overflow-hidden bg-gray-50">
                      {img.url ? (
                        <div className="relative h-24 w-full">
                          <Image
                            src={img.url}
                            alt={img.caption || img.photo_type}
                            fill
                            unoptimized
                            className="object-cover"
                          />
                        </div>
                      ) : (
                        <div className="w-full h-24 flex items-center justify-center">
                          <ImageIcon className="h-6 w-6 text-gray-300" />
                        </div>
                      )}
                      <div className="p-1.5">
                        <p className="text-[10px] text-gray-600 truncate">{img.caption || img.photo_type}</p>
                        {img.style_label && (
                          <Badge variant="secondary" className="text-[9px] mt-0.5">{img.style_label}</Badge>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
                <p className="text-[10px] text-gray-400">提示：参考图片可通过 JSON 导入方式批量添加</p>
              </div>
            )}

            <DialogFooter className="gap-2">
              <DialogClose asChild>
                <Button variant="outline">取消</Button>
              </DialogClose>
              <Button
                className="bg-primary hover:bg-primary"
                onClick={handleEdit}
                disabled={submitting}
              >
                {submitting ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : null}
                保存修改
              </Button>
            </DialogFooter>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-gray-600">
            确定要删除案例「{deletingCase?.title}」吗？此操作不可撤销。
          </p>
          <DialogFooter className="mt-4 gap-2">
            <DialogClose asChild>
              <Button variant="outline">取消</Button>
            </DialogClose>
            <Button variant="destructive" onClick={handleDelete} disabled={submitting}>
              {submitting ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
