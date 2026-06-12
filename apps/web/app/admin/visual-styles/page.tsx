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
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Plus, Edit3, Trash2, Download, Palette, Eye, Loader2, Lamp, Layers } from "lucide-react";
import {
  getVisualStyles,
  createVisualStyle,
  deleteVisualStyle,
  importVisualStyles,
  exportVisualStyles,
  exportVisualStyle,
} from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import { FileUploadButton } from "@/components/admin/file-upload-button";
import type { VisualStyle, ImportMode } from "@/types";

export default function VisualStylesPage() {
  const [styles, setStyles] = useState<VisualStyle[]>([]);
  const [loading, setLoading] = useState(true);

  // Create dialog form state
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [formName, setFormName] = useState("");
  const [formCategory, setFormCategory] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formPrimaryColor, setFormPrimaryColor] = useState("#1E3A5F");
  const [formAccentColor, setFormAccentColor] = useState("#00D4FF");
  const [submitting, setSubmitting] = useState(false);

  // Delete state
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const loadStyles = useCallback(async () => {
    setLoading(true);
    const res = await getVisualStyles();
    if (res.success && res.data) {
      setStyles(res.data);
    }
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

  const handleCreate = async () => {
    setSubmitting(true);
    const res = await createVisualStyle({
      name: formName,
      category: formCategory,
      description: formDescription,
      parameters: {
        primaryColor: formPrimaryColor,
        accentColor: formAccentColor,
      },
      isActive: true,
    });
    setSubmitting(false);
    if (res.success) {
      setCreateDialogOpen(false);
      setFormName("");
      setFormCategory("");
      setFormDescription("");
      setFormPrimaryColor("#1E3A5F");
      setFormAccentColor("#00D4FF");
      loadStyles();
    }
  };

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    const res = await deleteVisualStyle(id);
    setDeletingId(null);
    if (res.success) {
      loadStyles();
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#1A1A2E]">视觉风格库</h1>
          <p className="text-sm text-gray-500 mt-1">管理视觉风格预设和参数配置</p>
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
          <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-2">
                <Plus className="h-4 w-4" /> 新建风格
              </Button>
            </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>新建视觉风格</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>风格名称</Label>
                  <Input
                    placeholder="输入风格名称"
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>分类</Label>
                  <Input
                    placeholder="输入分类"
                    value={formCategory}
                    onChange={(e) => setFormCategory(e.target.value)}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label>描述</Label>
                <Textarea
                  rows={3}
                  placeholder="描述风格特点..."
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>主色调</Label>
                <div className="flex gap-2">
                  <Input
                    type="color"
                    className="w-12 h-9 p-1"
                    value={formPrimaryColor}
                    onChange={(e) => setFormPrimaryColor(e.target.value)}
                  />
                  <Input
                    placeholder="#1E3A5F"
                    className="flex-1"
                    value={formPrimaryColor}
                    onChange={(e) => setFormPrimaryColor(e.target.value)}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label>强调色</Label>
                <div className="flex gap-2">
                  <Input
                    type="color"
                    className="w-12 h-9 p-1"
                    value={formAccentColor}
                    onChange={(e) => setFormAccentColor(e.target.value)}
                  />
                  <Input
                    placeholder="#00D4FF"
                    className="flex-1"
                    value={formAccentColor}
                    onChange={(e) => setFormAccentColor(e.target.value)}
                  />
                </div>
              </div>
              <Button
                className="w-full bg-[#1E3A5F] hover:bg-[#2D5A8E]"
                onClick={handleCreate}
                disabled={submitting}
              >
                {submitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                创建风格
              </Button>
            </div>
          </DialogContent>
        </Dialog>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-[#1E3A5F]" />
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {styles.map((style) => (
            <Card key={style.id} className="border-gray-200 hover:shadow-sm transition-shadow group">
              <CardContent className="p-0">
                {/* Preview */}
                <div
                  className="h-32 rounded-t-lg flex items-center justify-center relative"
                  style={{
                    background: `linear-gradient(135deg, ${style.parameters.primaryColor}, ${style.parameters.accentColor})`,
                  }}
                >
                  <Palette className="h-8 w-8 text-white/60" />
                  <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button variant="secondary" size="sm" className="h-6 w-6 p-0" onClick={() => handleExportOne(style)}><Download className="h-3 w-3" /></Button>
                    <Button variant="secondary" size="sm" className="h-6 w-6 p-0"><Eye className="h-3 w-3" /></Button>
                    <Button variant="secondary" size="sm" className="h-6 w-6 p-0"><Edit3 className="h-3 w-3" /></Button>
                  </div>
                </div>
                {/* Info */}
                <div className="p-4">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-medium text-[#1A1A2E]">{style.name}</h3>
                    <Badge className={`text-xs ${style.isActive ? "bg-green-50 text-[#10B981]" : "bg-gray-100 text-gray-500"}`}>
                      {style.isActive ? "启用" : "停用"}
                    </Badge>
                  </div>
                  <p className="text-xs text-gray-500 mb-3">{style.description}</p>

                  {/* Material Spec Preview */}
                  {style.materialSpec && (
                    <div className="mb-3 p-2 bg-gray-50 rounded-lg">
                      <div className="flex items-center gap-1 mb-1">
                        <Layers className="h-3 w-3 text-gray-400" />
                        <span className="text-[10px] font-medium text-gray-500">材质规范</span>
                        <Badge variant="secondary" className="text-[10px] ml-auto">{style.materialSpec.style || "未命名"}</Badge>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {(style.materialSpec.categories ?? []).map((cat, ci) => (
                          <span key={ci} className="text-[10px] px-1.5 py-0.5 bg-white border border-gray-100 rounded text-gray-600">
                            {cat.name} {cat.coverage}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Lighting Spec Preview */}
                  {style.lightingSpec && (
                    <div className="mb-3 p-2 bg-gray-50 rounded-lg">
                      <div className="flex items-center gap-1 mb-1">
                        <Lamp className="h-3 w-3 text-gray-400" />
                        <span className="text-[10px] font-medium text-gray-500">灯光规范</span>
                        {style.lightingSpec.color_temperature && (
                          <span className="text-[10px] text-amber-600 ml-auto">{style.lightingSpec.color_temperature.range}</span>
                        )}
                      </div>
                      <p className="text-[10px] text-gray-500">{style.lightingSpec.overall_atmosphere}</p>
                    </div>
                  )}

                  <div className="flex items-center justify-between">
                    <Badge variant="secondary" className="text-xs">{style.category}</Badge>
                    <div className="flex items-center gap-1">
                      <div className="w-4 h-4 rounded-full border border-gray-200" style={{ backgroundColor: style.parameters.primaryColor }} />
                      <div className="w-4 h-4 rounded-full border border-gray-200" style={{ backgroundColor: style.parameters.accentColor }} />
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0 ml-1 text-gray-400 hover:text-red-500"
                        onClick={() => handleDelete(style.id)}
                        disabled={deletingId === style.id}
                      >
                        {deletingId === style.id ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <Trash2 className="h-3 w-3" />
                        )}
                      </Button>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
