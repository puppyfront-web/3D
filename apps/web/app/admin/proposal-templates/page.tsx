"use client";

import { useState } from "react";
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
import { Plus, Search, Eye, Edit3, Copy, Trash2, FileText } from "lucide-react";
import { mockProposalTemplates } from "@/lib/mock-data";

export default function ProposalTemplatesPage() {
  const [search, setSearch] = useState("");
  const filtered = mockProposalTemplates.filter((t) =>
    t.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#1A1A2E]">方案模板管理</h1>
          <p className="text-sm text-gray-500 mt-1">管理方案文档模板和章节结构</p>
        </div>
        <Dialog>
          <DialogTrigger asChild>
            <Button className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-2">
              <Plus className="h-4 w-4" /> 新建模板
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>新建方案模板</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>模板名称</Label>
                  <Input placeholder="输入模板名称" />
                </div>
                <div className="space-y-2">
                  <Label>所属行业</Label>
                  <Select>
                    <SelectTrigger><SelectValue placeholder="选择行业" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="政务">政务</SelectItem>
                      <SelectItem value="工业制造">工业制造</SelectItem>
                      <SelectItem value="通用">通用</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-2">
                <Label>分类</Label>
                <Input placeholder="输入分类" />
              </div>
              <div className="space-y-2">
                <Label>描述</Label>
                <Textarea rows={3} placeholder="描述模板用途..." />
              </div>
              <Button className="w-full bg-[#1E3A5F] hover:bg-[#2D5A8E]">创建模板</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input placeholder="搜索模板..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9 h-9" />
        </div>
      </div>

      <Card className="border-gray-200">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">模板名称</TableHead>
                <TableHead className="text-xs">分类</TableHead>
                <TableHead className="text-xs">行业</TableHead>
                <TableHead className="text-xs">章节数</TableHead>
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
                  <TableCell><Badge variant="secondary" className="text-xs">{tpl.category}</Badge></TableCell>
                  <TableCell className="text-sm text-gray-500">{tpl.industry}</TableCell>
                  <TableCell className="text-sm text-gray-600">{tpl.sections.length} 个</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-xs">{tpl.usageCount} 次</Badge>
                  </TableCell>
                  <TableCell className="text-sm text-gray-500">{tpl.updatedAt}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0"><Eye className="h-3.5 w-3.5" /></Button>
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0"><Edit3 className="h-3.5 w-3.5" /></Button>
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0"><Copy className="h-3.5 w-3.5" /></Button>
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-[#EF4444]"><Trash2 className="h-3.5 w-3.5" /></Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
