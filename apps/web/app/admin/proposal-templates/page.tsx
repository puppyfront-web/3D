"use client";

import { useState, useEffect, useCallback } from "react";
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
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Plus, Search, Eye, Edit3, Copy, Trash2, FileText, Loader2 } from "lucide-react";
import {
  getProposalTemplates,
  createProposalTemplate,
  updateProposalTemplate,
  deleteProposalTemplate,
  importProposalTemplates,
} from "@/lib/api";
import { FileUploadButton } from "@/components/admin/file-upload-button";
import type { ProposalTemplate } from "@/types";

export default function ProposalTemplatesPage() {
  const [templates, setTemplates] = useState<ProposalTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [selected, setSelected] = useState<ProposalTemplate | null>(null);
  const [saving, setSaving] = useState(false);

  // Form state
  const [formName, setFormName] = useState("");
  const [formCategory, setFormCategory] = useState("");
  const [formIndustry, setFormIndustry] = useState("");
  const [formDescription, setFormDescription] = useState("");

  const loadTemplates = useCallback(async () => {
    setLoading(true);
    const res = await getProposalTemplates();
    if (res.success && res.data) {
      setTemplates(res.data);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  const handleImport = async (file: File) => {
    const res = await importProposalTemplates(file);
    if (res.success && res.data) {
      await loadTemplates();
      return res.data;
    }
    throw new Error(res.message || "导入失败");
  };

  const resetForm = () => {
    setFormName("");
    setFormCategory("");
    setFormIndustry("");
    setFormDescription("");
  };

  const openCreate = () => {
    resetForm();
    setCreateOpen(true);
  };

  const openEdit = (tpl: ProposalTemplate) => {
    setSelected(tpl);
    setFormName(tpl.name);
    setFormCategory(tpl.category || "");
    setFormIndustry(tpl.industry || "");
    setFormDescription(tpl.description || "");
    setEditOpen(true);
  };

  const openDelete = (tpl: ProposalTemplate) => {
    setSelected(tpl);
    setDeleteOpen(true);
  };

  const handleCreate = async () => {
    if (!formName.trim()) return;
    setSaving(true);
    try {
      const res = await createProposalTemplate({
        name: formName,
        category: formCategory,
        industry: formIndustry,
        description: formDescription,
        sections: [],
      });
      if (res.success) {
        setCreateOpen(false);
        resetForm();
        await loadTemplates();
      }
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async () => {
    if (!selected || !formName.trim()) return;
    setSaving(true);
    try {
      const res = await updateProposalTemplate(selected.id, {
        name: formName,
        category: formCategory,
        industry: formIndustry,
        description: formDescription,
      });
      if (res.success) {
        setEditOpen(false);
        setSelected(null);
        resetForm();
        await loadTemplates();
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      await deleteProposalTemplate(selected.id);
      setDeleteOpen(false);
      setSelected(null);
      await loadTemplates();
    } finally {
      setSaving(false);
    }
  };

  const handleCopy = async (tpl: ProposalTemplate) => {
    const res = await createProposalTemplate({
      name: `${tpl.name} (副本)`,
      category: tpl.category,
      industry: tpl.industry,
      description: tpl.description,
      sections: tpl.sections || [],
    });
    if (res.success) {
      await loadTemplates();
    }
  };

  const filtered = templates.filter((t) =>
    t.name.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-[#1E3A5F]" />
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#1A1A2E]">方案模板管理</h1>
          <p className="text-sm text-gray-500 mt-1">管理方案文档模板和章节结构</p>
        </div>
        <div className="flex items-center gap-2">
          <FileUploadButton
            accept=".json"
            dialogTitle="导入方案模板"
            dialogDescription="支持 JSON 格式，含 sections 结构定义。"
            onUpload={handleImport}
          />
          <Button className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-2" onClick={openCreate}>
            <Plus className="h-4 w-4" /> 新建模板
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input placeholder="搜索模板..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9 h-9" />
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400">
          <FileText className="h-12 w-12 mb-3 text-gray-300" />
          <p className="text-sm">暂无方案模板</p>
        </div>
      ) : (
        <Card className="border-gray-200">
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">模板名称</TableHead>
                  <TableHead className="text-xs">分类</TableHead>
                  <TableHead className="text-xs">行业</TableHead>
                  <TableHead className="text-xs">使用次数</TableHead>
                  <TableHead className="text-xs">更新时间</TableHead>
                  <TableHead className="text-xs text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((tpl) => (
                  <TableRow key={tpl.id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <FileText className="h-4 w-4 text-[#1E3A5F]" />
                        <span className="text-sm font-medium text-[#1A1A2E]">{tpl.name}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="text-xs">
                        {tpl.category || "未分类"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-gray-500">{tpl.industry || "-"}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-xs">{tpl.usageCount ?? 0} 次</Badge>
                    </TableCell>
                    <TableCell className="text-sm text-gray-500">{tpl.updatedAt || "-"}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" className="h-7 w-7 p-0"><Eye className="h-3.5 w-3.5" /></Button>
                        <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => openEdit(tpl)}><Edit3 className="h-3.5 w-3.5" /></Button>
                        <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => handleCopy(tpl)}><Copy className="h-3.5 w-3.5" /></Button>
                        <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-[#EF4444]" onClick={() => openDelete(tpl)}><Trash2 className="h-3.5 w-3.5" /></Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Create Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建方案模板</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>模板名称</Label>
                <Input placeholder="输入模板名称" value={formName} onChange={(e) => setFormName(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>所属行业</Label>
                <Select value={formIndustry} onValueChange={setFormIndustry}>
                  <SelectTrigger><SelectValue placeholder="选择行业" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="政务">政务</SelectItem>
                    <SelectItem value="工业制造">工业制造</SelectItem>
                    <SelectItem value="科技">科技</SelectItem>
                    <SelectItem value="汽车">汽车</SelectItem>
                    <SelectItem value="商业综合体">商业综合体</SelectItem>
                    <SelectItem value="文旅">文旅</SelectItem>
                    <SelectItem value="通用">通用</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label>分类</Label>
              <Input placeholder="输入分类" value={formCategory} onChange={(e) => setFormCategory(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>描述</Label>
              <Textarea rows={3} placeholder="描述模板用途..." value={formDescription} onChange={(e) => setFormDescription(e.target.value)} />
            </div>
          </div>
          <DialogFooter className="mt-4 gap-2">
            <DialogClose asChild><Button variant="outline">取消</Button></DialogClose>
            <Button className="bg-[#1E3A5F] hover:bg-[#2D5A8E]" onClick={handleCreate} disabled={saving || !formName.trim()}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null} 创建模板
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>编辑方案模板</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>模板名称</Label>
                <Input value={formName} onChange={(e) => setFormName(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>所属行业</Label>
                <Select value={formIndustry} onValueChange={setFormIndustry}>
                  <SelectTrigger><SelectValue placeholder="选择行业" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="政务">政务</SelectItem>
                    <SelectItem value="工业制造">工业制造</SelectItem>
                    <SelectItem value="科技">科技</SelectItem>
                    <SelectItem value="汽车">汽车</SelectItem>
                    <SelectItem value="商业综合体">商业综合体</SelectItem>
                    <SelectItem value="文旅">文旅</SelectItem>
                    <SelectItem value="通用">通用</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label>分类</Label>
              <Input value={formCategory} onChange={(e) => setFormCategory(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>描述</Label>
              <Textarea rows={3} value={formDescription} onChange={(e) => setFormDescription(e.target.value)} />
            </div>
          </div>
          <DialogFooter className="mt-4 gap-2">
            <DialogClose asChild><Button variant="outline">取消</Button></DialogClose>
            <Button className="bg-[#1E3A5F] hover:bg-[#2D5A8E]" onClick={handleUpdate} disabled={saving || !formName.trim()}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null} 保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-gray-600">
            确定要删除模板「{selected?.name}」吗？此操作不可撤销。
          </p>
          <DialogFooter className="mt-4 gap-2">
            <DialogClose asChild><Button variant="outline">取消</Button></DialogClose>
            <Button variant="destructive" onClick={handleDelete} disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null} 删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
