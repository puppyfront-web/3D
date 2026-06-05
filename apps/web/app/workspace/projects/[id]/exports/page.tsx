"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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
  Download,
  FileText,
  FileArchive,
  FileImage,
  Eye,
  RotateCcw,
  CheckCircle2,
  Clock,
  XCircle,
} from "lucide-react";

const exportHistory = [
  {
    id: "exp-001",
    filename: "智慧城市数字化展厅方案_v3.pdf",
    format: "PDF",
    size: "12.5 MB",
    exportedAt: "2026-06-03 16:30",
    status: "completed",
    exportedBy: "张明",
  },
  {
    id: "exp-002",
    filename: "智慧城市数字化展厅方案_v3.docx",
    format: "DOCX",
    size: "8.2 MB",
    exportedAt: "2026-06-03 16:28",
    status: "completed",
    exportedBy: "张明",
  },
  {
    id: "exp-003",
    filename: "视觉素材包_科技蓝.zip",
    format: "ZIP",
    size: "156 MB",
    exportedAt: "2026-06-03 15:45",
    status: "completed",
    exportedBy: "李婷",
  },
  {
    id: "exp-004",
    filename: "智慧城市数字化展厅方案_v2.pdf",
    format: "PDF",
    size: "11.8 MB",
    exportedAt: "2026-05-28 10:15",
    status: "completed",
    exportedBy: "张明",
  },
  {
    id: "exp-005",
    filename: "3D渲染图高清包.zip",
    format: "ZIP",
    size: "520 MB",
    exportedAt: "2026-05-27 14:20",
    status: "completed",
    exportedBy: "王磊",
  },
  {
    id: "exp-006",
    filename: "方案评审材料.pptx",
    format: "PPTX",
    size: "45 MB",
    exportedAt: "2026-06-04 09:00",
    status: "processing",
    exportedBy: "赵雪",
  },
];

const statusDisplay = {
  completed: { label: "已完成", icon: <CheckCircle2 className="h-4 w-4 text-[#10B981]" /> },
  processing: { label: "处理中", icon: <Clock className="h-4 w-4 text-[#F59E0B] animate-pulse" /> },
  failed: { label: "失败", icon: <XCircle className="h-4 w-4 text-[#EF4444]" /> },
};

const formatIcon = (format: string) => {
  if (format === "PDF") return <FileText className="h-4 w-4 text-red-500" />;
  if (format === "ZIP") return <FileArchive className="h-4 w-4 text-amber-500" />;
  if (format === "DOCX" || format === "PPTX") return <FileText className="h-4 w-4 text-blue-500" />;
  return <FileImage className="h-4 w-4 text-green-500" />;
};

export default function ExportsPage() {
  return (
    <div className="p-6 max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-[#1A1A2E]">导出记录</h2>
          <p className="text-sm text-gray-500 mt-1">查看和管理所有导出文件</p>
        </div>
        <Button className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-2">
          <Download className="h-4 w-4" /> 新建导出
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <Card className="border-gray-200">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-green-50 flex items-center justify-center">
              <CheckCircle2 className="h-5 w-5 text-[#10B981]" />
            </div>
            <div>
              <p className="text-xs text-gray-500">已完成</p>
              <p className="text-xl font-bold text-[#10B981]">
                {exportHistory.filter((e) => e.status === "completed").length}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card className="border-gray-200">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-amber-50 flex items-center justify-center">
              <Clock className="h-5 w-5 text-[#F59E0B]" />
            </div>
            <div>
              <p className="text-xs text-gray-500">处理中</p>
              <p className="text-xl font-bold text-[#F59E0B]">
                {exportHistory.filter((e) => e.status === "processing").length}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card className="border-gray-200">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
              <FileText className="h-5 w-5 text-[#3B82F6]" />
            </div>
            <div>
              <p className="text-xs text-gray-500">总文件数</p>
              <p className="text-xl font-bold text-[#1E3A5F]">{exportHistory.length}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Table */}
      <Card className="border-gray-200">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">文件名</TableHead>
                <TableHead className="text-xs">格式</TableHead>
                <TableHead className="text-xs">大小</TableHead>
                <TableHead className="text-xs">导出时间</TableHead>
                <TableHead className="text-xs">操作人</TableHead>
                <TableHead className="text-xs">状态</TableHead>
                <TableHead className="text-xs text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {exportHistory.map((exp) => (
                <TableRow key={exp.id}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      {formatIcon(exp.format)}
                      <span className="text-sm text-[#1A1A2E]">{exp.filename}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="text-xs">
                      {exp.format}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-gray-500">{exp.size}</TableCell>
                  <TableCell className="text-sm text-gray-500">{exp.exportedAt}</TableCell>
                  <TableCell className="text-sm text-gray-600">{exp.exportedBy}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5">
                      {statusDisplay[exp.status as keyof typeof statusDisplay].icon}
                      <span className="text-xs">
                        {statusDisplay[exp.status as keyof typeof statusDisplay].label}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
                        <Eye className="h-3.5 w-3.5" />
                      </Button>
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
                        <Download className="h-3.5 w-3.5" />
                      </Button>
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
