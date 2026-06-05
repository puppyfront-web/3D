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
import { Plus, Search, Eye, Edit3, Trash2, BookOpen } from "lucide-react";
import { mockCases } from "@/lib/mock-data";

const statusColor = {
  published: "text-[#10B981] bg-green-50",
  draft: "text-gray-500 bg-gray-100",
  archived: "text-[#EF4444] bg-red-50",
};

const statusLabel = {
  published: "已发布",
  draft: "草稿",
  archived: "已归档",
};

export default function CasesPage() {
  const [search, setSearch] = useState("");

  const filtered = mockCases.filter((c) =>
    c.title.toLowerCase().includes(search.toLowerCase()) ||
    c.client.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#1A1A2E]">案例库管理</h1>
          <p className="text-sm text-gray-500 mt-1">管理成功案例，用于方案参考和素材复用</p>
        </div>
        <Dialog>
          <DialogTrigger asChild>
            <Button className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-2">
              <Plus className="h-4 w-4" /> 新建案例
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>新建案例</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>案例标题</Label>
                  <Input placeholder="输入案例标题" />
                </div>
                <div className="space-y-2">
                  <Label>客户名称</Label>
                  <Input placeholder="输入客户名称" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>所属行业</Label>
                  <Select>
                    <SelectTrigger><SelectValue placeholder="选择行业" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="智慧城市">智慧城市</SelectItem>
                      <SelectItem value="工业制造">工业制造</SelectItem>
                      <SelectItem value="金融科技">金融科技</SelectItem>
                      <SelectItem value="能源电力">能源电力</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>状态</Label>
                  <Select defaultValue="draft">
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="draft">草稿</SelectItem>
                      <SelectItem value="published">发布</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-2">
                <Label>项目成果</Label>
                <Input placeholder="描述项目成果" />
              </div>
              <div className="space-y-2">
                <Label>项目亮点</Label>
                <Textarea rows={3} placeholder="每行一个亮点..." />
              </div>
              <Button className="w-full bg-[#1E3A5F] hover:bg-[#2D5A8E]">创建案例</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input placeholder="搜索案例..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9 h-9" />
        </div>
      </div>

      <Card className="border-gray-200">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">案例标题</TableHead>
                <TableHead className="text-xs">客户</TableHead>
                <TableHead className="text-xs">行业</TableHead>
                <TableHead className="text-xs">项目成果</TableHead>
                <TableHead className="text-xs">创建时间</TableHead>
                <TableHead className="text-xs">状态</TableHead>
                <TableHead className="text-xs text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="text-sm font-medium text-[#1A1A2E]">{item.title}</TableCell>
                  <TableCell className="text-sm text-gray-600">{item.client}</TableCell>
                  <TableCell><Badge variant="secondary" className="text-xs">{item.industry}</Badge></TableCell>
                  <TableCell className="text-sm text-gray-500 max-w-xs truncate">{item.outcome}</TableCell>
                  <TableCell className="text-sm text-gray-500">{item.createdAt}</TableCell>
                  <TableCell>
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${statusColor[item.status]}`}>
                      {statusLabel[item.status]}
                    </span>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0"><Eye className="h-3.5 w-3.5" /></Button>
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0"><Edit3 className="h-3.5 w-3.5" /></Button>
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
