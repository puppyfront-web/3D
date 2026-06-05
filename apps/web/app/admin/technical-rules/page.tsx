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
import { Plus, Search, Edit3, Trash2, Cpu, ToggleLeft, ToggleRight } from "lucide-react";
import { mockTechnicalRules } from "@/lib/mock-data";

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
  const [search, setSearch] = useState("");
  const filtered = mockTechnicalRules.filter((r) =>
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
        <Dialog>
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
                  <Input placeholder="输入规则名称" />
                </div>
                <div className="space-y-2">
                  <Label>分类</Label>
                  <Select>
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
                  <Select>
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
                <Textarea rows={3} placeholder="描述规则用途和检查逻辑..." />
              </div>
              <div className="space-y-2">
                <Label>规则表达式</Label>
                <Input placeholder="例如：model.faceCount <= 5000000" className="font-mono text-sm" />
              </div>
              <Button className="w-full bg-[#1E3A5F] hover:bg-[#2D5A8E]">创建规则</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input placeholder="搜索规则..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9 h-9" />
        </div>
      </div>

      <Card className="border-gray-200">
        <CardContent className="p-0">
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
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
                        {rule.isActive ? <ToggleRight className="h-4 w-4 text-[#10B981]" /> : <ToggleLeft className="h-4 w-4 text-gray-400" />}
                      </Button>
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
