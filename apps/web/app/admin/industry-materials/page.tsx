"use client";

// 行业资料库 (Industry materials — PRD §12.5).
// Curated cross-project industry reference: trends, policy notes, benchmarking.

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
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
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Plus, Edit3, Trash2, Download, Loader2, BookMarked } from "lucide-react";
import {
  getIndustryMaterials,
  createIndustryMaterial,
  updateIndustryMaterial,
  deleteIndustryMaterial,
  importIndustryMaterials,
  exportIndustryMaterials,
} from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import { FileUploadButton } from "@/components/admin/file-upload-button";
import { INDUSTRIES } from "@/lib/constants";
import type { IndustryMaterial, ImportMode } from "@/types";

interface FormState {
  title: string;
  industry: string;
  category: string;
  content: string;
  sourceUrl: string;
}

const EMPTY: FormState = { title: "", industry: "", category: "", content: "", sourceUrl: "" };

export default function IndustryMaterialsPage() {
  const [items, setItems] = useState<IndustryMaterial[]>([]);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [submitting, setSubmitting] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [selected, setSelected] = useState<IndustryMaterial | null>(null);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const res = await getIndustryMaterials();
    if (res.success && res.data) setItems(res.data);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleImport = async (file: File, mode: ImportMode) => {
    const res = await importIndustryMaterials(file, mode);
    if (res.success && res.data) { await load(); return res.data; }
    throw new Error(res.message || "导入失败");
  };

  const handleExport = async () => {
    const blob = await exportIndustryMaterials();
    downloadBlob(blob, "industry_materials.json");
  };

  function openCreate() { setForm(EMPTY); setEditingId(null); setFormOpen(true); }
  function openEdit(it: IndustryMaterial) {
    setForm({ title: it.title, industry: it.industry ?? "", category: it.category ?? "", content: it.content ?? "", sourceUrl: it.sourceUrl ?? "" });
    setEditingId(it.id); setFormOpen(true);
  }

  async function handleSubmit() {
    if (!form.title.trim()) return;
    setSubmitting(true);
    const payload = { ...form, industry: form.industry || undefined, category: form.category || undefined, sourceUrl: form.sourceUrl || undefined };
    const res = editingId ? await updateIndustryMaterial(editingId, payload) : await createIndustryMaterial({ ...payload, isActive: true });
    setSubmitting(false);
    if (res.success) { setFormOpen(false); await load(); }
  }

  function openDelete(it: IndustryMaterial) { setSelected(it); setDeleteOpen(true); }
  async function confirmDelete() {
    if (!selected) return;
    setDeleting(true);
    const res = await deleteIndustryMaterial(selected.id);
    setDeleting(false);
    if (res.success) { setDeleteOpen(false); setSelected(null); await load(); }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-on-surface">行业资料库</h1>
          <p className="text-sm text-on-surface-variant mt-1">行业趋势、政策解读、对标分析等可复用的参考资料</p>
        </div>
        <div className="flex items-center gap-2">
          <FileUploadButton accept=".json,.txt,.md" dialogTitle="导入行业资料" dialogDescription="支持 JSON / TXT / MD 格式" onUpload={handleImport} />
          <Button variant="outline" size="sm" className="gap-1.5" onClick={handleExport}><Download className="h-3.5 w-3.5" />导出</Button>
          <Button className="bg-primary hover:bg-primary gap-2" onClick={openCreate}><Plus className="h-4 w-4" />新建资料</Button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-outline">
          <BookMarked className="h-10 w-10 mb-3" />
          <p className="text-sm">暂无行业资料，点击「新建资料」开始</p>
        </div>
      ) : (
        <div className="border border-outline-variant rounded-lg overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">标题</TableHead>
                <TableHead className="text-xs">行业</TableHead>
                <TableHead className="text-xs">分类</TableHead>
                <TableHead className="text-xs">来源</TableHead>
                <TableHead className="text-xs text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((it) => (
                <TableRow key={it.id}>
                  <TableCell className="text-sm font-medium text-on-surface max-w-xs truncate">{it.title}</TableCell>
                  <TableCell className="text-sm text-on-surface-variant">{it.industry ?? "—"}</TableCell>
                  <TableCell className="text-sm text-on-surface-variant">{it.category ?? "—"}</TableCell>
                  <TableCell className="text-xs text-outline max-w-[200px] truncate">{it.sourceUrl ?? "—"}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => openEdit(it)} title="编辑"><Edit3 className="h-3.5 w-3.5" /></Button>
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-outline hover:text-error" onClick={() => openDelete(it)} title="删除"><Trash2 className="h-3.5 w-3.5" /></Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Create / Edit */}
      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>{editingId ? "编辑行业资料" : "新建行业资料"}</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-4">
            <div className="space-y-2">
              <Label>标题</Label>
              <Input placeholder="资料标题" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>行业</Label>
                <Select value={form.industry} onValueChange={(v) => setForm({ ...form, industry: v })}>
                  <SelectTrigger><SelectValue placeholder="选择行业" /></SelectTrigger>
                  <SelectContent>{INDUSTRIES.map((i) => <SelectItem key={i} value={i}>{i}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>分类</Label>
                <Input placeholder="如 政策 / 趋势 / 对标" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
              </div>
            </div>
            <div className="space-y-2">
              <Label>来源链接</Label>
              <Input placeholder="https://..." value={form.sourceUrl} onChange={(e) => setForm({ ...form, sourceUrl: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>内容</Label>
              <Textarea rows={6} placeholder="资料正文或摘要..." value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} />
            </div>
            <Button className="w-full bg-primary hover:bg-primary" onClick={handleSubmit} disabled={submitting || !form.title.trim()}>
              {submitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}{editingId ? "保存修改" : "创建"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete confirm */}
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>确认删除</DialogTitle></DialogHeader>
          <p className="text-sm text-on-surface-variant">确定要删除行业资料「{selected?.title}」吗？此操作不可撤销。</p>
          <DialogFooter className="mt-4 gap-2">
            <DialogClose asChild><Button variant="outline">取消</Button></DialogClose>
            <Button variant="destructive" onClick={confirmDelete} disabled={deleting}>{deleting && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}删除</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
