"use client";

// 报价经验库 (Pricing experience — PRD §12.7).
// Historical pricing reference ranges. All figures are REFERENCE ONLY and must
// be human-confirmed before any quote reaches a client (AGENTS.md §5 禁止编造报价).

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
import { Plus, Edit3, Trash2, Download, Loader2, CircleDollarSign, AlertTriangle } from "lucide-react";
import {
  getPricingExperiences,
  createPricingExperience,
  updatePricingExperience,
  deletePricingExperience,
  importPricingExperiences,
  exportPricingExperiences,
} from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import { FileUploadButton } from "@/components/admin/file-upload-button";
import { INDUSTRIES } from "@/lib/constants";
import type { PricingExperience, ImportMode } from "@/types";

interface FormState {
  title: string;
  industry: string;
  projectType: string;
  budgetRange: string;
  duration: string;
  notes: string;
}

const EMPTY: FormState = { title: "", industry: "", projectType: "", budgetRange: "", duration: "", notes: "" };

export default function PricingExperiencesPage() {
  const [items, setItems] = useState<PricingExperience[]>([]);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [submitting, setSubmitting] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [selected, setSelected] = useState<PricingExperience | null>(null);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const res = await getPricingExperiences();
    if (res.success && res.data) setItems(res.data);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleImport = async (file: File, mode: ImportMode) => {
    const res = await importPricingExperiences(file, mode);
    if (res.success && res.data) { await load(); return res.data; }
    throw new Error(res.message || "导入失败");
  };

  const handleExport = async () => {
    const blob = await exportPricingExperiences();
    downloadBlob(blob, "pricing_experiences.json");
  };

  function openCreate() { setForm(EMPTY); setEditingId(null); setFormOpen(true); }
  function openEdit(it: PricingExperience) {
    setForm({ title: it.title, industry: it.industry ?? "", projectType: it.projectType ?? "", budgetRange: it.budgetRange ?? "", duration: it.duration ?? "", notes: it.notes ?? "" });
    setEditingId(it.id); setFormOpen(true);
  }

  async function handleSubmit() {
    if (!form.title.trim()) return;
    setSubmitting(true);
    const payload = { ...form, industry: form.industry || undefined, projectType: form.projectType || undefined, budgetRange: form.budgetRange || undefined, duration: form.duration || undefined };
    const res = editingId ? await updatePricingExperience(editingId, payload) : await createPricingExperience({ ...payload, isActive: true });
    setSubmitting(false);
    if (res.success) { setFormOpen(false); await load(); }
  }

  function openDelete(it: PricingExperience) { setSelected(it); setDeleteOpen(true); }
  async function confirmDelete() {
    if (!selected) return;
    setDeleting(true);
    const res = await deletePricingExperience(selected.id);
    setDeleting(false);
    if (res.success) { setDeleteOpen(false); setSelected(null); await load(); }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-on-surface">报价经验库</h1>
          <p className="text-sm text-on-surface-variant mt-1">历史报价参考，所有数据仅供参考，正式报价必须人工确认</p>
        </div>
        <div className="flex items-center gap-2">
          <FileUploadButton accept=".json,.csv" dialogTitle="导入报价经验" dialogDescription="支持 JSON / CSV 格式" onUpload={handleImport} />
          <Button variant="outline" size="sm" className="gap-1.5" onClick={handleExport}><Download className="h-3.5 w-3.5" />导出</Button>
          <Button className="bg-primary hover:bg-primary gap-2" onClick={openCreate}><Plus className="h-4 w-4" />新建经验</Button>
        </div>
      </div>

      {/* Pricing is reference-only — surface the human-confirm rule prominently. */}
      <div className="mb-4 flex items-start gap-2 rounded-lg border border-tertiary/30 bg-tertiary-fixed/40 p-3 text-xs text-tertiary-container">
        <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
        <span>本库所有金额与工期为历史参考，禁止直接对外承诺。任何对外报价必须经过人工审核确认（AGENTS.md §5）。</span>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-outline">
          <CircleDollarSign className="h-10 w-10 mb-3" />
          <p className="text-sm">暂无报价经验，点击「新建经验」开始</p>
        </div>
      ) : (
        <div className="border border-outline-variant rounded-lg overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">标题</TableHead>
                <TableHead className="text-xs">行业</TableHead>
                <TableHead className="text-xs">项目类型</TableHead>
                <TableHead className="text-xs">预算范围</TableHead>
                <TableHead className="text-xs">工期</TableHead>
                <TableHead className="text-xs text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((it) => (
                <TableRow key={it.id}>
                  <TableCell className="text-sm font-medium text-on-surface max-w-xs truncate">{it.title}</TableCell>
                  <TableCell className="text-sm text-on-surface-variant">{it.industry ?? "—"}</TableCell>
                  <TableCell className="text-sm text-on-surface-variant">{it.projectType ?? "—"}</TableCell>
                  <TableCell><Badge variant="secondary" className="text-xs">{it.budgetRange ?? "—"}</Badge></TableCell>
                  <TableCell className="text-xs text-outline">{it.duration ?? "—"}</TableCell>
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

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>{editingId ? "编辑报价经验" : "新建报价经验"}</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-4">
            <div className="space-y-2">
              <Label>标题</Label>
              <Input placeholder="如：智慧园区 3D 展示标准报价" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
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
                <Label>项目类型</Label>
                <Input placeholder="如 企业3D数字化展示" value={form.projectType} onChange={(e) => setForm({ ...form, projectType: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>预算范围</Label>
                <Input placeholder="如 30万-80万" value={form.budgetRange} onChange={(e) => setForm({ ...form, budgetRange: e.target.value })} />
              </div>
              <div className="space-y-2">
                <Label>工期</Label>
                <Input placeholder="如 4-8 周" value={form.duration} onChange={(e) => setForm({ ...form, duration: e.target.value })} />
              </div>
            </div>
            <div className="space-y-2">
              <Label>备注</Label>
              <Textarea rows={4} placeholder="影响报价的关键因素、注意事项..." value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </div>
            <Button className="w-full bg-primary hover:bg-primary" onClick={handleSubmit} disabled={submitting || !form.title.trim()}>
              {submitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}{editingId ? "保存修改" : "创建"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>确认删除</DialogTitle></DialogHeader>
          <p className="text-sm text-on-surface-variant">确定要删除报价经验「{selected?.title}」吗？此操作不可撤销。</p>
          <DialogFooter className="mt-4 gap-2">
            <DialogClose asChild><Button variant="outline">取消</Button></DialogClose>
            <Button variant="destructive" onClick={confirmDelete} disabled={deleting}>{deleting && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}删除</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
