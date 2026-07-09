"use client";

// 话术库 (Talking points — PRD §12.6).
// Reusable sales scripts keyed by scenario (首次接洽 / 需求确认 / 异议处理 / ...).

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
import { Plus, Edit3, Trash2, Download, Loader2, MessageSquareQuote } from "lucide-react";
import {
  getTalkingPoints,
  createTalkingPoint,
  updateTalkingPoint,
  deleteTalkingPoint,
  importTalkingPoints,
  exportTalkingPoints,
} from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import { FileUploadButton } from "@/components/admin/file-upload-button";
import { INDUSTRIES } from "@/lib/constants";
import type { TalkingPoint, ImportMode } from "@/types";

const SCENARIOS = ["首次接洽", "需求确认", "方案介绍", "异议处理", "报价沟通", "客户汇报", "通用"] as const;

interface FormState {
  scenario: string;
  title: string;
  content: string;
  industry: string;
  tags: string;
}

const EMPTY: FormState = { scenario: "通用", title: "", content: "", industry: "", tags: "" };

export default function TalkingPointsPage() {
  const [items, setItems] = useState<TalkingPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [submitting, setSubmitting] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [selected, setSelected] = useState<TalkingPoint | null>(null);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const res = await getTalkingPoints();
    if (res.success && res.data) setItems(res.data);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleImport = async (file: File, mode: ImportMode) => {
    const res = await importTalkingPoints(file, mode);
    if (res.success && res.data) { await load(); return res.data; }
    throw new Error(res.message || "导入失败");
  };

  const handleExport = async () => {
    const blob = await exportTalkingPoints();
    downloadBlob(blob, "talking_points.json");
  };

  function openCreate() { setForm(EMPTY); setEditingId(null); setFormOpen(true); }
  function openEdit(it: TalkingPoint) {
    setForm({ scenario: it.scenario, title: it.title, content: it.content ?? "", industry: it.industry ?? "", tags: it.tags ?? "" });
    setEditingId(it.id); setFormOpen(true);
  }

  async function handleSubmit() {
    if (!form.title.trim()) return;
    setSubmitting(true);
    const payload = { ...form, industry: form.industry || undefined, tags: form.tags || undefined };
    const res = editingId ? await updateTalkingPoint(editingId, payload) : await createTalkingPoint({ ...payload, isActive: true });
    setSubmitting(false);
    if (res.success) { setFormOpen(false); await load(); }
  }

  function openDelete(it: TalkingPoint) { setSelected(it); setDeleteOpen(true); }
  async function confirmDelete() {
    if (!selected) return;
    setDeleting(true);
    const res = await deleteTalkingPoint(selected.id);
    setDeleting(false);
    if (res.success) { setDeleteOpen(false); setSelected(null); await load(); }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-on-surface">话术库</h1>
          <p className="text-sm text-on-surface-variant mt-1">按场景沉淀售前话术，保持对外表达一致可追溯</p>
        </div>
        <div className="flex items-center gap-2">
          <FileUploadButton accept=".json,.txt,.md" dialogTitle="导入话术" dialogDescription="支持 JSON / TXT / MD 格式" onUpload={handleImport} />
          <Button variant="outline" size="sm" className="gap-1.5" onClick={handleExport}><Download className="h-3.5 w-3.5" />导出</Button>
          <Button className="bg-primary hover:bg-primary gap-2" onClick={openCreate}><Plus className="h-4 w-4" />新建话术</Button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-outline">
          <MessageSquareQuote className="h-10 w-10 mb-3" />
          <p className="text-sm">暂无话术，点击「新建话术」开始</p>
        </div>
      ) : (
        <div className="border border-outline-variant rounded-lg overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">场景</TableHead>
                <TableHead className="text-xs">标题</TableHead>
                <TableHead className="text-xs">行业</TableHead>
                <TableHead className="text-xs">标签</TableHead>
                <TableHead className="text-xs text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((it) => (
                <TableRow key={it.id}>
                  <TableCell><Badge variant="secondary" className="text-xs">{it.scenario}</Badge></TableCell>
                  <TableCell className="text-sm font-medium text-on-surface max-w-xs truncate">{it.title}</TableCell>
                  <TableCell className="text-sm text-on-surface-variant">{it.industry ?? "通用"}</TableCell>
                  <TableCell className="text-xs text-outline max-w-[160px] truncate">{it.tags ?? "—"}</TableCell>
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
          <DialogHeader><DialogTitle>{editingId ? "编辑话术" : "新建话术"}</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>场景</Label>
                <Select value={form.scenario} onValueChange={(v) => setForm({ ...form, scenario: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{SCENARIOS.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>行业</Label>
                <Select value={form.industry} onValueChange={(v) => setForm({ ...form, industry: v })}>
                  <SelectTrigger><SelectValue placeholder="通用" /></SelectTrigger>
                  <SelectContent>{INDUSTRIES.map((i) => <SelectItem key={i} value={i}>{i}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label>标题</Label>
              <Input placeholder="话术标题" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>话术正文</Label>
              <Textarea rows={6} placeholder="完整话术内容..." value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>标签（逗号分隔）</Label>
              <Input placeholder="如：高客单价, 决策链长" value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} />
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
          <p className="text-sm text-on-surface-variant">确定要删除话术「{selected?.title}」吗？此操作不可撤销。</p>
          <DialogFooter className="mt-4 gap-2">
            <DialogClose asChild><Button variant="outline">取消</Button></DialogClose>
            <Button variant="destructive" onClick={confirmDelete} disabled={deleting}>{deleting && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}删除</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
