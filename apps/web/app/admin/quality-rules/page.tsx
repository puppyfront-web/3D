"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
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
import {
  Plus,
  Edit3,
  Trash2,
  Download,
  ShieldCheck,
  ToggleLeft,
  ToggleRight,
  ChevronDown,
  ChevronRight,
  Loader2,
} from "lucide-react";
import { useState, useEffect, useCallback } from "react";
import {
  getQualityRules,
  createQualityRule,
  updateQualityRule,
  deleteQualityRule,
  importQualityRules,
  exportQualityRules,
  exportQualityRule,
} from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import { FileUploadButton } from "@/components/admin/file-upload-button";
import type { QualityRule, ImportMode } from "@/types";

export default function QualityRulesPage() {
  const [rules, setRules] = useState<QualityRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Form state
  const [formName, setFormName] = useState("");
  const [formCategory, setFormCategory] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formPassingScore, setFormPassingScore] = useState("");

  const fetchRules = useCallback(async () => {
    setLoading(true);
    const res = await getQualityRules();
    if (res.success && res.data) {
      setRules(res.data);
      setExpanded((prev) =>
        prev.length === 0 && res.data.length > 0 ? [res.data[0].id] : prev
      );
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  const resetForm = () => {
    setFormName("");
    setFormCategory("");
    setFormDescription("");
    setFormPassingScore("");
  };

  const handleImport = async (file: File, mode: ImportMode) => {
    const res = await importQualityRules(file, mode);
    if (res.success && res.data) {
      await fetchRules();
      return res.data;
    }
    throw new Error(res.message || "导入失败");
  };

  const handleExport = async () => {
    const blob = await exportQualityRules();
    downloadBlob(blob, "quality_rules.json");
  };

  const handleExportOne = async (rule: QualityRule) => {
    const blob = await exportQualityRule(rule.id);
    downloadBlob(blob, `${rule.name.replace(/[/\\:*?"<>|]/g, "_")}.json`);
  };

  const handleCreate = async () => {
    setSubmitting(true);
    const res = await createQualityRule({
      name: formName,
      category: formCategory,
      description: formDescription,
      passingScore: Number(formPassingScore) || 80,
      criteria: [],
      isActive: true,
    });
    setSubmitting(false);
    if (res.success) {
      setDialogOpen(false);
      resetForm();
      fetchRules();
    }
  };

  const handleToggle = async (rule: QualityRule) => {
    const res = await updateQualityRule(rule.id, { isActive: !rule.isActive });
    if (res.success) {
      fetchRules();
    }
  };

  const handleDelete = async (id: string) => {
    const res = await deleteQualityRule(id);
    if (res.success) {
      fetchRules();
    }
  };

  const toggleExpand = (id: string) => {
    setExpanded((prev) =>
      prev.includes(id) ? prev.filter((e) => e !== id) : [...prev, id]
    );
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#1A1A2E]">质量标准管理</h1>
          <p className="text-sm text-gray-500 mt-1">管理方案质量评估标准和评分规则</p>
        </div>
        <div className="flex items-center gap-2">
          <FileUploadButton
            accept=".json,.txt"
            dialogTitle="导入质量规则"
            dialogDescription="支持 JSON、TXT 格式。TXT 用空行分隔多条规则。"
            onUpload={handleImport}
          />
          <Button variant="outline" size="sm" className="gap-1.5" onClick={handleExport}>
            <Download className="h-3.5 w-3.5" />
            导出
          </Button>
          <Dialog open={dialogOpen} onOpenChange={(open) => { setDialogOpen(open); if (!open) resetForm(); }}>
            <DialogTrigger asChild>
              <Button className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-2">
                <Plus className="h-4 w-4" /> 新建标准
              </Button>
            </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>新建质量标准</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>标准名称</Label>
                  <Input placeholder="输入标准名称" value={formName} onChange={(e) => setFormName(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label>分类</Label>
                  <Input placeholder="输入分类" value={formCategory} onChange={(e) => setFormCategory(e.target.value)} />
                </div>
              </div>
              <div className="space-y-2">
                <Label>描述</Label>
                <Textarea rows={3} placeholder="描述质量标准..." value={formDescription} onChange={(e) => setFormDescription(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>通过分数线</Label>
                <Input type="number" placeholder="80" value={formPassingScore} onChange={(e) => setFormPassingScore(e.target.value)} />
              </div>
              <Button className="w-full bg-[#1E3A5F] hover:bg-[#2D5A8E]" onClick={handleCreate} disabled={submitting}>
                {submitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                创建标准
              </Button>
            </div>
          </DialogContent>
        </Dialog>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-[#1E3A5F]" />
          <span className="ml-2 text-sm text-gray-500">加载中...</span>
        </div>
      ) : (
        <div className="space-y-4">
          {rules.map((rule) => {
            const totalWeight = rule.criteria.reduce((acc, c) => acc + c.weight, 0);
            return (
              <Card key={rule.id} className="border-gray-200">
                <CardHeader
                  className="pb-3 cursor-pointer"
                  onClick={() => toggleExpand(rule.id)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      {expanded.includes(rule.id) ? (
                        <ChevronDown className="h-4 w-4 text-gray-400" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-gray-400" />
                      )}
                      <ShieldCheck className="h-5 w-5 text-[#1E3A5F]" />
                      <div>
                        <CardTitle className="text-sm font-medium">{rule.name}</CardTitle>
                        <p className="text-xs text-gray-500 mt-0.5">{rule.description}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge variant="secondary" className="text-xs">{rule.category}</Badge>
                      <Badge variant="outline" className="text-xs">
                        通过线 {rule.passingScore}分
                      </Badge>
                      <Badge className={`text-xs ${rule.isActive ? "bg-green-50 text-[#10B981]" : "bg-gray-100 text-gray-500"}`}>
                        {rule.isActive ? "启用" : "停用"}
                      </Badge>
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={(e) => { e.stopPropagation(); handleToggle(rule); }}>
                        {rule.isActive ? <ToggleRight className="h-3.5 w-3.5 text-[#10B981]" /> : <ToggleLeft className="h-3.5 w-3.5 text-gray-400" />}
                      </Button>
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-[#EF4444]" onClick={(e) => { e.stopPropagation(); handleDelete(rule.id); }}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                      <Button variant="ghost" size="sm" className="h-7 gap-1" onClick={(e) => { e.stopPropagation(); handleExportOne(rule); }}>
                        <Download className="h-3 w-3" /> 导出
                      </Button>
                      <Button variant="ghost" size="sm" className="h-7 gap-1">
                        <Edit3 className="h-3 w-3" /> 编辑
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                {expanded.includes(rule.id) && (
                  <CardContent className="pt-0">
                    <Separator className="mb-4" />
                    <div className="ml-7">
                      <div className="grid grid-cols-12 gap-3 text-xs font-medium text-gray-500 mb-2 px-3">
                        <div className="col-span-5">评分标准</div>
                        <div className="col-span-2">权重</div>
                        <div className="col-span-4">评分指南</div>
                        <div className="col-span-1 text-right">操作</div>
                      </div>
                      {rule.criteria.map((criteria) => (
                        <div
                          key={criteria.id}
                          className="grid grid-cols-12 gap-3 items-center px-3 py-2 bg-gray-50 rounded-lg mb-1.5"
                        >
                          <div className="col-span-5 text-sm text-[#1A1A2E]">{criteria.description}</div>
                          <div className="col-span-2">
                            <div className="flex items-center gap-2">
                              <Progress value={(criteria.weight / totalWeight) * 100} className="h-1.5 flex-1" />
                              <span className="text-xs text-gray-600 font-medium">{criteria.weight}%</span>
                            </div>
                          </div>
                          <div className="col-span-4 text-xs text-gray-500">{criteria.scoringGuide}</div>
                          <div className="col-span-1 text-right">
                            <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
                              <Edit3 className="h-3 w-3" />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
