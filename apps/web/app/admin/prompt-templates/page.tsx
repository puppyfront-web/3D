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
import { Plus, Search, Eye, Edit3, Copy, Trash2, MessageSquareCode, Loader2 } from "lucide-react";
import {
  getPromptTemplates,
  createPromptTemplate,
  deletePromptTemplate,
  importPromptTemplates,
} from "@/lib/api";
import { FileUploadButton } from "@/components/admin/file-upload-button";
import type { PromptTemplate } from "@/types";

export default function PromptTemplatesPage() {
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    name: "",
    category: "",
    description: "",
    prompt: "",
  });
  const [creating, setCreating] = useState(false);

  const loadTemplates = useCallback(async () => {
    setLoading(true);
    const res = await getPromptTemplates();
    if (res.success && res.data) {
      setTemplates(res.data);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  const filtered = templates.filter(
    (t) =>
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      t.category.toLowerCase().includes(search.toLowerCase())
  );

  const handleImport = async (file: File) => {
    const res = await importPromptTemplates(file);
    if (res.success && res.data) {
      await loadTemplates();
      return res.data;
    }
    throw new Error(res.message || "导入失败");
  };

  const handleCreate = async () => {
    if (!createForm.name || !createForm.prompt) return;
    setCreating(true);
    const res = await createPromptTemplate({
      name: createForm.name,
      category: createForm.category,
      description: createForm.description,
      prompt: createForm.prompt,
      variables: [],
      usageCount: 0,
    });
    if (res.success) {
      setCreateOpen(false);
      setCreateForm({ name: "", category: "", description: "", prompt: "" });
      await loadTemplates();
    }
    setCreating(false);
  };

  const handleCopy = async (tpl: PromptTemplate) => {
    await createPromptTemplate({
      ...tpl,
      name: tpl.name + " (副本)",
    });
    await loadTemplates();
  };

  const handleDelete = async (id: string) => {
    await deletePromptTemplate(id);
    await loadTemplates();
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#1A1A2E]">提示词模板管理</h1>
          <p className="text-sm text-gray-500 mt-1">管理AI提示词模板和变量配置</p>
        </div>
        <div className="flex items-center gap-2">
          <FileUploadButton
            accept=".json,.txt,.md"
            dialogTitle="导入 Prompt 模板"
            dialogDescription="支持 JSON、TXT、Markdown 格式。TXT/MD 首行为名称，正文为模板，{{变量}} 自动提取。"
            onUpload={handleImport}
          />
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-2">
                <Plus className="h-4 w-4" /> 新建提示词
              </Button>
            </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>新建提示词模板</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>模板名称</Label>
                  <Input
                    placeholder="输入模板名称"
                    value={createForm.name}
                    onChange={(e) => setCreateForm((f) => ({ ...f, name: e.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label>分类</Label>
                  <Input
                    placeholder="输入分类"
                    value={createForm.category}
                    onChange={(e) => setCreateForm((f) => ({ ...f, category: e.target.value }))}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label>描述</Label>
                <Input
                  placeholder="简要描述模板用途"
                  value={createForm.description}
                  onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label>提示词内容</Label>
                <Textarea
                  rows={8}
                  placeholder="输入提示词，使用 {{变量名}} 标记变量..."
                  className="font-mono text-sm"
                  value={createForm.prompt}
                  onChange={(e) => setCreateForm((f) => ({ ...f, prompt: e.target.value }))}
                />
              </div>
              <p className="text-xs text-gray-400">使用双花括号 {`{{变量名}}`} 标记可替换变量</p>
              <Button
                className="w-full bg-[#1E3A5F] hover:bg-[#2D5A8E]"
                onClick={handleCreate}
                disabled={creating}
              >
                {creating ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                创建模板
              </Button>
            </div>
          </DialogContent>
        </Dialog>
        </div>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input placeholder="搜索提示词..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9 h-9" />
        </div>
      </div>

      <Card className="border-gray-200">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">模板名称</TableHead>
                <TableHead className="text-xs">分类</TableHead>
                <TableHead className="text-xs">变量数</TableHead>
                <TableHead className="text-xs">使用次数</TableHead>
                <TableHead className="text-xs">创建时间</TableHead>
                <TableHead className="text-xs text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-12">
                    <Loader2 className="h-6 w-6 animate-spin mx-auto text-gray-400" />
                    <p className="text-sm text-gray-400 mt-2">加载中...</p>
                  </TableCell>
                </TableRow>
              ) : filtered.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-12 text-sm text-gray-400">
                    暂无提示词模板
                  </TableCell>
                </TableRow>
              ) : (
                filtered.map((tpl) => (
                  <TableRow key={tpl.id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <MessageSquareCode className="h-4 w-4 text-[#00D4FF]" />
                        <div>
                          <p className="text-sm font-medium text-[#1A1A2E]">{tpl.name}</p>
                          <p className="text-xs text-gray-400 mt-0.5 max-w-xs truncate">{tpl.description}</p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell><Badge variant="secondary" className="text-xs">{tpl.category}</Badge></TableCell>
                    <TableCell className="text-sm text-gray-600">{tpl.variables.length} 个</TableCell>
                    <TableCell><Badge variant="outline" className="text-xs">{tpl.usageCount} 次</Badge></TableCell>
                    <TableCell className="text-sm text-gray-500">{tpl.createdAt}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" className="h-7 w-7 p-0"><Eye className="h-3.5 w-3.5" /></Button>
                        <Button variant="ghost" size="sm" className="h-7 w-7 p-0"><Edit3 className="h-3.5 w-3.5" /></Button>
                        <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => handleCopy(tpl)}><Copy className="h-3.5 w-3.5" /></Button>
                        <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-[#EF4444]" onClick={() => handleDelete(tpl.id)}><Trash2 className="h-3.5 w-3.5" /></Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
