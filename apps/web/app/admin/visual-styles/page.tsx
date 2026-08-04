"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Plus, Edit3, Trash2, Download, Palette, Loader2, Lamp, Layers } from "lucide-react";
import {
  getVisualStyles,
  createVisualStyle,
  updateVisualStyle,
  deleteVisualStyle,
  importVisualStyles,
  exportVisualStyles,
  exportVisualStyle,
} from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import { FileUploadButton } from "@/components/admin/file-upload-button";
import { VISUAL_STYLE_SUB_TYPES } from "@/lib/constants";
import type { VisualStyle, ImportMode } from "@/types";

interface StyleForm {
  name: string;
  category: string;
  subType: string;
  description: string;
  primaryColor: string;
  accentColor: string;
}

const EMPTY_FORM: StyleForm = {
  name: "",
  category: "",
  subType: "",
  description: "",
  primaryColor: "#1E3A5F",
  accentColor: "#00D4FF",
};

export default function VisualStylesPage() {
  const [styles, setStyles] = useState<VisualStyle[]>([]);
  const [loading, setLoading] = useState(true);

  // Create / edit dialog state
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<StyleForm>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);

  // Delete confirmation state
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [selected, setSelected] = useState<VisualStyle | null>(null);
  const [deleting, setDeleting] = useState(false);

  const loadStyles = useCallback(async () => {
    setLoading(true);
    const res = await getVisualStyles();
    if (res.success && res.data) setStyles(res.data);
    setLoading(false);
  }, []);

  useEffect(() => {
    loadStyles();
  }, [loadStyles]);

  const handleImport = async (file: File, mode: ImportMode) => {
    const res = await importVisualStyles(file, mode);
    if (res.success && res.data) {
      await loadStyles();
      return res.data;
    }
    throw new Error(res.message || "导入失败");
  };

  const handleExport = async () => {
    const blob = await exportVisualStyles();
    downloadBlob(blob, "visual_styles.json");
  };

  const handleExportOne = async (style: VisualStyle) => {
    const blob = await exportVisualStyle(style.id);
    downloadBlob(blob, `${style.name.replace(/[/\\:*?"<>|]/g, "_")}.json`);
  };

  function openCreate() {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setFormOpen(true);
  }

  function openEdit(style: VisualStyle) {
    setForm({
      name: style.name,
      category: style.category ?? "",
      subType: style.subType ?? "",
      description: style.description ?? "",
      primaryColor: style.primaryColor ?? style.parameters?.primaryColor ?? "#1E3A5F",
      accentColor: style.accentColor ?? style.parameters?.accentColor ?? "#00D4FF",
    });
    setEditingId(style.id);
    setFormOpen(true);
  }

  async function handleSubmit() {
    if (!form.name.trim()) return;
    setSubmitting(true);
    const subType = form.subType && form.subType !== "none" ? form.subType : "";
    const payload = {
      name: form.name,
      category: form.category || undefined,
      subType: subType || undefined,
      description: form.description,
      primaryColor: form.primaryColor,
      accentColor: form.accentColor,
    };
    const res = editingId
      ? await updateVisualStyle(editingId, payload)
      : await createVisualStyle({ ...payload, isActive: true });
    setSubmitting(false);
    if (res.success) {
      setFormOpen(false);
      await loadStyles();
    }
  }

  function openDelete(style: VisualStyle) {
    setSelected(style);
    setDeleteOpen(true);
  }

  async function confirmDelete() {
    if (!selected) return;
    setDeleting(true);
    const res = await deleteVisualStyle(selected.id);
    setDeleting(false);
    if (res.success) {
      setDeleteOpen(false);
      setSelected(null);
      await loadStyles();
    }
  }

  async function toggleActive(style: VisualStyle) {
    await updateVisualStyle(style.id, { isActive: !style.isActive });
    await loadStyles();
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-on-surface">视觉风格库</h1>
          <p className="text-sm text-on-surface-variant mt-1">管理颜色预设、UI 规范、大屏设计案例与 3D 视觉参考</p>
        </div>
        <div className="flex items-center gap-2">
          <FileUploadButton
            accept=".json"
            dialogTitle="导入视觉风格"
            dialogDescription="支持 JSON 格式，含颜色、字体、布局参数。"
            onUpload={handleImport}
          />
          <Button variant="outline" size="sm" className="gap-1.5" onClick={handleExport}>
            <Download className="h-3.5 w-3.5" />
            导出
          </Button>
          <Button className="bg-primary hover:bg-primary gap-2" onClick={openCreate}>
            <Plus className="h-4 w-4" /> 新建风格
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      ) : styles.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-outline">
          <Palette className="h-10 w-10 mb-3" />
          <p className="text-sm">暂无视觉风格，点击「新建风格」开始</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {styles.map((style) => {
            const primary = style.primaryColor ?? style.parameters?.primaryColor ?? "#1E3A5F";
            const accent = style.accentColor ?? style.parameters?.accentColor ?? "#00D4FF";
            const subLabel = VISUAL_STYLE_SUB_TYPES.find((s) => s.value === (style.subType ?? ""))?.label;
            return (
              <Card key={style.id} className="border-outline-variant hover:shadow-sm transition-shadow group">
                <CardContent className="p-0">
                  {/* Preview */}
                  <div
                    className="h-32 rounded-t-lg flex items-center justify-center relative"
                    style={{ background: `linear-gradient(135deg, ${primary}, ${accent})` }}
                  >
                    <Palette className="h-8 w-8 text-white/60" />
                    {subLabel && (
                      <Badge className="absolute top-2 left-2 bg-white/80 text-on-surface text-[10px]">{subLabel}</Badge>
                    )}
                    <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Button variant="secondary" size="sm" className="h-6 w-6 p-0" onClick={() => handleExportOne(style)} title="导出">
                        <Download className="h-3 w-3" />
                      </Button>
                      <Button variant="secondary" size="sm" className="h-6 w-6 p-0" onClick={() => openEdit(style)} title="编辑">
                        <Edit3 className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                  {/* Info */}
                  <div className="p-4">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-sm font-medium text-on-surface">{style.name}</h3>
                      <button onClick={() => toggleActive(style)} title={style.isActive ? "点击停用" : "点击启用"}>
                        <Badge className={`text-xs cursor-pointer ${style.isActive ? "bg-primary-fixed text-primary" : "bg-surface-container-high text-outline"}`}>
                          {style.isActive ? "启用" : "停用"}
                        </Badge>
                      </button>
                    </div>
                    <p className="text-xs text-on-surface-variant mb-3 line-clamp-2">{style.description}</p>

                    {style.materialSpec && (
                      <div className="mb-3 p-2 bg-surface-container rounded-lg">
                        <div className="flex items-center gap-1 mb-1">
                          <Layers className="h-3 w-3 text-outline" />
                          <span className="text-[10px] font-medium text-on-surface-variant">材质规范</span>
                          <Badge variant="secondary" className="text-[10px] ml-auto">{style.materialSpec.style || "未命名"}</Badge>
                        </div>
                      </div>
                    )}

                    {style.lightingSpec && (
                      <div className="mb-3 p-2 bg-surface-container rounded-lg">
                        <div className="flex items-center gap-1 mb-1">
                          <Lamp className="h-3 w-3 text-outline" />
                          <span className="text-[10px] font-medium text-on-surface-variant">灯光规范</span>
                        </div>
                        <p className="text-[10px] text-on-surface-variant">{style.lightingSpec.overall_atmosphere}</p>
                      </div>
                    )}

                    <div className="flex items-center justify-between">
                      <Badge variant="secondary" className="text-xs">{style.category || "未分类"}</Badge>
                      <div className="flex items-center gap-1">
                        <div className="w-4 h-4 rounded-full border border-outline-variant" style={{ backgroundColor: primary }} />
                        <div className="w-4 h-4 rounded-full border border-outline-variant" style={{ backgroundColor: accent }} />
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0 ml-1 text-outline hover:text-error"
                          onClick={() => openDelete(style)}
                          title="删除"
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Create / Edit dialog */}
      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingId ? "编辑视觉风格" : "新建视觉风格"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>风格名称</Label>
                <Input
                  placeholder="输入风格名称"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>分类</Label>
                <Input
                  placeholder="输入分类"
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>子库类型</Label>
              <Select value={form.subType} onValueChange={(v) => setForm({ ...form, subType: v })}>
                <SelectTrigger><SelectValue placeholder="选择子库类型" /></SelectTrigger>
                <SelectContent>
                  {VISUAL_STYLE_SUB_TYPES.map((s) => (
                    <SelectItem key={s.value || "none"} value={s.value || "none"}>{s.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>描述</Label>
              <Textarea
                rows={3}
                placeholder="描述风格特点..."
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>主色调</Label>
                <div className="flex gap-2">
                  <Input type="color" className="w-12 h-9 p-1" value={form.primaryColor} onChange={(e) => setForm({ ...form, primaryColor: e.target.value })} />
                  <Input className="flex-1" value={form.primaryColor} onChange={(e) => setForm({ ...form, primaryColor: e.target.value })} />
                </div>
              </div>
              <div className="space-y-2">
                <Label>强调色</Label>
                <div className="flex gap-2">
                  <Input type="color" className="w-12 h-9 p-1" value={form.accentColor} onChange={(e) => setForm({ ...form, accentColor: e.target.value })} />
                  <Input className="flex-1" value={form.accentColor} onChange={(e) => setForm({ ...form, accentColor: e.target.value })} />
                </div>
              </div>
            </div>
            <Button className="w-full bg-primary hover:bg-primary" onClick={handleSubmit} disabled={submitting || !form.name.trim()}>
              {submitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {editingId ? "保存修改" : "创建风格"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-on-surface-variant">
            确定要删除视觉风格「{selected?.name}」吗？此操作不可撤销。
          </p>
          <DialogFooter className="mt-4 gap-2">
            <DialogClose asChild><Button variant="outline">取消</Button></DialogClose>
            <Button variant="destructive" onClick={confirmDelete} disabled={deleting}>
              {deleting && <Loader2 className="h-4 w-4 mr-1 animate-spin" />} 删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
