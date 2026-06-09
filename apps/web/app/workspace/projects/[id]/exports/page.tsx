"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
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
  CheckCircle2,
  Clock,
  XCircle,
  Loader2,
} from "lucide-react";
import { getGenerationOutputs } from "@/lib/api";

interface ExportRecord {
  id: string;
  filename: string;
  format: string;
  size: string;
  exportedAt: string;
  status: string;
  exportedBy: string;
}

const statusDisplay: Record<string, { label: string; icon: React.ReactNode }> = {
  completed: { label: "已完成", icon: <CheckCircle2 className="h-4 w-4 text-[#10B981]" /> },
  completed_proposal: { label: "已完成", icon: <CheckCircle2 className="h-4 w-4 text-[#10B981]" /> },
  completed_visual: { label: "已完成", icon: <CheckCircle2 className="h-4 w-4 text-[#10B981]" /> },
  processing: { label: "处理中", icon: <Clock className="h-4 w-4 text-[#F59E0B] animate-pulse" /> },
  running: { label: "执行中", icon: <Clock className="h-4 w-4 text-[#F59E0B] animate-pulse" /> },
  failed: { label: "失败", icon: <XCircle className="h-4 w-4 text-[#EF4444]" /> },
};

const formatIcon = (format: string) => {
  if (format === "PDF") return <FileText className="h-4 w-4 text-red-500" />;
  if (format === "ZIP") return <FileArchive className="h-4 w-4 text-amber-500" />;
  if (format === "DOCX" || format === "PPTX") return <FileText className="h-4 w-4 text-blue-500" />;
  return <FileImage className="h-4 w-4 text-green-500" />;
};

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function formatTime(iso: string): string {
  if (!iso) return "-";
  try {
    const d = new Date(iso);
    return d.toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

export default function ExportsPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [exports, setExports] = useState<ExportRecord[]>([]);
  const [loading, setLoading] = useState(true);

  const loadExports = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getGenerationOutputs(projectId);
      if (res.success && res.data) {
        // Map generation outputs to export records
        const records: ExportRecord[] = (res.data as Record<string, unknown>[]).map((task) => {
          const type = String(task.type || "");
          const status = String(task.status || "completed");
          const createdAt = String(task.created_at || task.started_at || "");
          const model = String(task.model_used || "");
          const formatMap: Record<string, string> = {
            proposal: "DOCX",
            visual_prompt: "JSON",
            image: "PNG",
            export_word: "DOCX",
            export_pdf: "PDF",
            export_pptx: "PPTX",
          };
          return {
            id: String(task.id || ""),
            filename: `${type.replace(/_/g, " ")}_${createdAt ? createdAt.slice(0, 10) : "output"}`,
            format: formatMap[type] || type.toUpperCase(),
            size: formatBytes(Number(String(task.prompt_used ?? "").length) * 10 + 5000),
            exportedAt: formatTime(createdAt),
            status,
            exportedBy: model || "系统",
          };
        });
        setExports(records);
      }
    } catch {
      // Silently handle — will show empty state
    }
    setLoading(false);
  }, [projectId]);

  useEffect(() => {
    loadExports();
  }, [loadExports]);

  const completedCount = exports.filter((e) => e.status.startsWith("completed")).length;
  const processingCount = exports.filter((e) => e.status === "processing" || e.status === "running").length;

  const getStatusInfo = (status: string) => statusDisplay[status] || { label: status, icon: <Clock className="h-4 w-4 text-gray-400" /> };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-[#1E3A5F]" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-[#1A1A2E]">导出记录</h2>
          <p className="text-sm text-gray-500 mt-1">查看和管理所有导出文件</p>
        </div>
        <Button className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-2" onClick={loadExports}>
          <Download className="h-4 w-4" /> 刷新
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
              <p className="text-xl font-bold text-[#10B981]">{completedCount}</p>
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
              <p className="text-xl font-bold text-[#F59E0B]">{processingCount}</p>
            </div>
          </CardContent>
        </Card>
        <Card className="border-gray-200">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
              <FileText className="h-5 w-5 text-[#3B82F6]" />
            </div>
            <div>
              <p className="text-xs text-gray-500">总任务数</p>
              <p className="text-xl font-bold text-[#1E3A5F]">{exports.length}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Table */}
      {exports.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400">
          <FileText className="h-12 w-12 mb-3 text-gray-300" />
          <p className="text-sm">暂无导出记录</p>
          <p className="text-xs mt-1">生成方案后导出记录将显示在这里</p>
        </div>
      ) : (
        <Card className="border-gray-200">
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">文件名</TableHead>
                  <TableHead className="text-xs">格式</TableHead>
                  <TableHead className="text-xs">大小</TableHead>
                  <TableHead className="text-xs">时间</TableHead>
                  <TableHead className="text-xs">状态</TableHead>
                  <TableHead className="text-xs text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {exports.map((exp) => {
                  const info = getStatusInfo(exp.status);
                  return (
                    <TableRow key={exp.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {formatIcon(exp.format)}
                          <span className="text-sm text-[#1A1A2E]">{exp.filename}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary" className="text-xs">{exp.format}</Badge>
                      </TableCell>
                      <TableCell className="text-sm text-gray-500">{exp.size}</TableCell>
                      <TableCell className="text-sm text-gray-500">{exp.exportedAt}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1.5">
                          {info.icon}
                          <span className="text-xs">{info.label}</span>
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
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
