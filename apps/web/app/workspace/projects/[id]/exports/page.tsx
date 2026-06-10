"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
  CheckCircle2,
  Loader2,
  ChevronDown,
  Sparkles,
} from "lucide-react";
import { exportProposal, getProposalTasksForExport } from "@/lib/api";

interface ExportRecord {
  id: string;
  outputId: string;
  filename: string;
  format: string;
  exportedAt: string;
  status: string;
}

function formatTime(iso: string): string {
  if (!iso) return "-";
  try {
    return new Date(iso).toLocaleString("zh-CN", {
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
}

export default function ExportsPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [records, setRecords] = useState<ExportRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  // Latest proposal output id for export
  const [latestOutputId, setLatestOutputId] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getProposalTasksForExport(projectId);
      if (result.success) {
        setLatestOutputId(result.latestOutputId);
        setRecords(result.records.map((r) => ({
          ...r,
          format: "DOCX",
          exportedAt: formatTime(r.exportedAt),
        })));
      }
    } catch {
      // ignore
    }
    setLoading(false);
  }, [projectId]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleExport = async (outputId: string, format: "word" | "pdf" | "pptx") => {
    setExporting(true);
    try {
      const blob = await exportProposal(outputId, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `proposal.${format === "word" ? "docx" : format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err instanceof Error ? err.message : "导出失败");
    }
    setExporting(false);
  };

  const completedCount = records.filter((r) => r.status === "completed" || r.status === "completed_proposal").length;

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
          <p className="text-sm text-gray-500 mt-1">导出策划案为 Word / PDF / PPTX 格式</p>
        </div>
        {latestOutputId && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-2"
                disabled={exporting}
              >
                {exporting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Download className="h-4 w-4" />
                )}
                导出策划案
                <ChevronDown className="h-3.5 w-3.5 ml-1" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => handleExport(latestOutputId, "word")}>
                Word (.docx)
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExport(latestOutputId, "pdf")}>
                PDF
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExport(latestOutputId, "pptx")}>
                PPTX
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <Card className="border-gray-200">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-green-50 flex items-center justify-center">
              <CheckCircle2 className="h-5 w-5 text-[#10B981]" />
            </div>
            <div>
              <p className="text-xs text-gray-500">可导出方案</p>
              <p className="text-xl font-bold text-[#10B981]">{completedCount}</p>
            </div>
          </CardContent>
        </Card>
        <Card className="border-gray-200">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
              <FileText className="h-5 w-5 text-[#1E3A5F]" />
            </div>
            <div>
              <p className="text-xs text-gray-500">历史版本</p>
              <p className="text-xl font-bold text-[#1E3A5F]">{records.length}</p>
            </div>
          </CardContent>
        </Card>
        <Card className="border-gray-200">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-purple-50 flex items-center justify-center">
              <Sparkles className="h-5 w-5 text-purple-600" />
            </div>
            <div>
              <p className="text-xs text-gray-500">支持格式</p>
              <p className="text-xl font-bold text-purple-600">3</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {records.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400">
          <FileText className="h-12 w-12 mb-3 text-gray-300" />
          <p className="text-sm">暂无可导出的策划案</p>
          <p className="text-xs mt-1">请先在「方案编辑」页面生成策划案</p>
        </div>
      ) : (
        <Card className="border-gray-200">
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">方案名称</TableHead>
                  <TableHead className="text-xs">最后更新</TableHead>
                  <TableHead className="text-xs">状态</TableHead>
                  <TableHead className="text-xs text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {records.map((rec) => (
                  <TableRow key={rec.id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <FileText className="h-4 w-4 text-blue-500" />
                        <span className="text-sm text-[#1A1A2E]">{rec.filename}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-gray-500">{rec.exportedAt}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-[#10B981] border-green-200 text-xs">
                        可导出
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="outline" size="sm" className="gap-1" disabled={exporting}>
                            <Download className="h-3.5 w-3.5" /> 导出
                            <ChevronDown className="h-3 w-3" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => handleExport(rec.outputId, "word")}>
                            Word (.docx)
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleExport(rec.outputId, "pdf")}>
                            PDF
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleExport(rec.outputId, "pptx")}>
                            PPTX
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
