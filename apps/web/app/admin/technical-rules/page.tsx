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
import { Plus, Search, Edit3, Trash2, Cpu, ToggleLeft, ToggleRight, Loader2 } from "lucide-react";
import {
  getTechnicalRules,
  createTechnicalRule,
  updateTechnicalRule,
  deleteTechnicalRule,
  importTechnicalRules,
} from "@/lib/api";
import { FileUploadButton } from "@/components/admin/file-upload-button";
import type { TechnicalRule } from "@/types";

const severityColor = {
  critical: "text-[#EF4444] bg-red-50 border-red-200",
  warning: "text-[#F59E0B] bg-amber-50 border-amber-200",
  info: "text-[#3B82F6] bg-blue-50 border-blue-200",
};

const severityLabel = {
  critical: "严重",
  warning: "警告",
  info: "提示",
};

export default function TechnicalRulesPage() {
  const [rules, setRules] = useState<TechnicalRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Form state
  const [formName, setFormName] = useState("");
  const [formCategory, setFormCategory] = useState("");
  const [formSeverity, setFormSeverity] = useState<"critical" | "warning" | "info">("info");
  const [formDescription, setFormDescription] = useState("");
  const [formRule, setFormRule] = useState("");

  const fetchRules = useCallback(async () => {
    setLoading(true);
    const res = await getTechnicalRules();
    if (res.success && res.data) {
      setRules(res.data);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  const resetForm = () => {
    setFormName("");
    setFormCategory("");
    setFormSeverity("info");
    setFormDescription("");
    setFormRule("");
  };

  const handleImport = async (file: File) => {
    const res = await importTechnicalRules(file);
    if (res.success && res.data) {
      await fetchRules();
      return res.data;
    }
    throw new Error(res.message || "导入失败");
  };

  const handleCreate = async () => {
    setSubmitting(true);
    const res = await createTechnicalRule({
      name: formName,
      category: formCategory,
      severity: formSeverity,
      description: formDescription,
      rule: formRule,
      isActive: true,
    });
    setSubmitting(false);
    if (res.success) {
      setDialogOpen(false);
      resetForm();
      fetchRules();
    }
  };

  const handleToggle = async (rule: TechnicalRule) => {
    const res = await updateTechnicalRule(rule.id, { isActive: !rule.isActive });
    if (res.success) {
      fetchRules();
    }
  };

  const handleDelete = async (id: string) => {
    const res = await deleteTechnicalRule(id);
    if (res.success) {
      fetchRules();
    }
  };

  const filtered = rules.filter(
    (r) =>
      r.name.toLowerCase().includes(search.toLowerCase()) ||
      r.category.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#1A1A2E]">技术规则配置</h1>
          <p className="text-sm text-gray-500 mt-1">配置技术方案生成的约束规则和检查标准</p>
        </div>
        <div className="flex items-center gap-2">
          <FileUploadButton
            accept=".json,.txt"
            dialogTitle="导入技术规则"
            dialogDescription="支持 JSON、TXT 格式。TXT 用空行分隔多条规则。"
            onUpload={handleImport}
          />
          <Dialog open={dialogOpen} onOpenChange={(open) => { setDialogOpen(open); if (!open) resetForm(); }}>
            <DialogTrigger asChild>
              <Button className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-2">
                <Plus className="h-4 w-4" /> 新建规则
              </Button>
            </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>新建技术规则</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>规则名称</Label>
                  <Input placeholder="输入规则名称" value={formName} onChange={(e) => setFormName(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label>分类</Label>
                  <Select value={formCategory} onValueChange={setFormCategory}>
                    <SelectTrigger><SelectValue placeholder="选择分类" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="3D渲染">3D渲染</SelectItem>
                      <SelectItem value="性能">性能</SelectItem>
                      <SelectItem value="兼容性">兼容性</SelectItem>
                      <SelectItem value="安全">安全</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>严重程度</Label>
                  <Select value={formSeverity} onValueChange={(v) => setFormSeverity(v as "critical" | "warning" | "info")}>
                    <SelectTrigger><SelectValue placeholder="选择严重程度" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="critical">严重</SelectItem>
                      <SelectItem value="warning">警告</SelectItem>
                      <SelectItem value="info">提示</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-2">
                <Label>规则描述</Label>
                <Textarea rows={3} placeholder="描述规则用途和检查逻辑..." value={formDescription} onChange={(e) => setFormDescription(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>规则表达式</Label>
                <Input placeholder="例如：model.faceCount <= 5000000" className="font-mono text-sm" value={formRule} onChange={(e) => setFormRule(e.target.value)} />
              </div>
              <Button className="w-full bg-[#1E3A5F] hover:bg-[#2D5A8E]" onClick={handleCreate} disabled={submitting}>
                {submitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                创建规则
              </Button>
            </div>
          </DialogContent>
        </Dialog>
        </div>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input placeholder="搜索规则..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9 h-9" />
        </div>
      </div>

      <Card className="border-gray-200">
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-[#1E3A5F]" />
              <span className="ml-2 text-sm text-gray-500">加载中...</span>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">规则名称</TableHead>
                  <TableHead className="text-xs">分类</TableHead>
                  <TableHead className="text-xs">描述</TableHead>
                  <TableHead className="text-xs">严重程度</TableHead>
                  <TableHead className="text-xs">状态</TableHead>
                  <TableHead className="text-xs text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((rule) => (
                  <TableRow key={rule.id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Cpu className="h-4 w-4 text-[#1E3A5F]" />
                        <span className="text-sm font-medium text-[#1A1A2E]">{rule.name}</span>
                      </div>
                    </TableCell>
                    <TableCell><Badge variant="secondary" className="text-xs">{rule.category}</Badge></TableCell>
                    <TableCell className="text-sm text-gray-500 max-w-xs truncate">{rule.description}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={`text-xs ${severityColor[rule.severity]}`}>
                        {severityLabel[rule.severity]}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge className={`text-xs ${rule.isActive ? "bg-green-50 text-[#10B981]" : "bg-gray-100 text-gray-500"}`}>
                        {rule.isActive ? "启用" : "停用"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => handleToggle(rule)}>
                          {rule.isActive ? <ToggleRight className="h-4 w-4 text-[#10B981]" /> : <ToggleLeft className="h-4 w-4 text-gray-400" />}
                        </Button>
                        <Button variant="ghost" size="sm" className="h-7 w-7 p-0"><Edit3 className="h-3.5 w-3.5" /></Button>
                        <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-[#EF4444]" onClick={() => handleDelete(rule.id)}><Trash2 className="h-3.5 w-3.5" /></Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
