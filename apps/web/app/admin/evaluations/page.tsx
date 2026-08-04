"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Eye, ClipboardCheck, TrendingUp, BarChart3, Loader2, X } from "lucide-react";
import { getEvaluations } from "@/lib/api";
import type { Evaluation } from "@/types";

const statusColor = {
  completed: "text-[#00875a] bg-green-50",
  pending: "text-[#e8740b] bg-amber-50",
  disputed: "text-error bg-red-50",
};

const statusLabel = {
  completed: "已完成",
  pending: "待审核",
  disputed: "有异议",
};

export default function EvaluationsPage() {
  const [selectedEval, setSelectedEval] = useState<string | null>(null);
  const [evaluations, setEvaluations] = useState<Evaluation[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchEvaluations = useCallback(async () => {
    setLoading(true);
    const res = await getEvaluations();
    if (res.success && res.data) {
      setEvaluations(res.data);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchEvaluations();
  }, [fetchEvaluations]);

  const selected = evaluations.find((e) => e.id === selectedEval);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-on-surface">评估记录</h1>
          <p className="text-sm text-gray-500 mt-1">查看方案质量评估历史和详细报告</p>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <Card className="border-gray-200">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-primary/5 flex items-center justify-center">
              <ClipboardCheck className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-xs text-gray-500">总评估数</p>
              <p className="text-xl font-bold text-primary">{evaluations.length}</p>
            </div>
          </CardContent>
        </Card>
        <Card className="border-gray-200">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-green-50 flex items-center justify-center">
              <TrendingUp className="h-5 w-5 text-[#00875a]" />
            </div>
            <div>
              <p className="text-xs text-gray-500">平均分</p>
              <p className="text-xl font-bold text-[#00875a]">
                {evaluations.length > 0
                  ? Math.round(evaluations.reduce((acc, e) => acc + e.overallScore, 0) / evaluations.length)
                  : 0}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card className="border-gray-200">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-amber-50 flex items-center justify-center">
              <BarChart3 className="h-5 w-5 text-[#e8740b]" />
            </div>
            <div>
              <p className="text-xs text-gray-500">已完成</p>
              <p className="text-xl font-bold text-[#e8740b]">
                {evaluations.filter((e) => e.status === "completed").length}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="flex gap-6">
        {/* Table */}
        <Card className={`border-gray-200 flex-1 ${selectedEval ? "hidden lg:block" : ""}`}>
          <CardContent className="p-0">
            {loading ? (
              <div className="flex items-center justify-center py-16">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
                <span className="ml-2 text-sm text-gray-500">加载中...</span>
              </div>
            ) : evaluations.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-gray-400">
                <ClipboardCheck className="h-10 w-10 mb-3" />
                <p className="text-sm">暂无评估记录</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">项目名称</TableHead>
                    <TableHead className="text-xs">总分</TableHead>
                    <TableHead className="text-xs">评估时间</TableHead>
                    <TableHead className="text-xs">评估人</TableHead>
                    <TableHead className="text-xs">状态</TableHead>
                    <TableHead className="text-xs text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {evaluations.map((evalItem) => (
                    <TableRow key={evalItem.id} className={selectedEval === evalItem.id ? "bg-primary/5" : ""}>
                      <TableCell className="text-sm font-medium text-on-surface">{evalItem.projectName}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <span className={`text-sm font-bold ${evalItem.overallScore >= 80 ? "text-[#00875a]" : evalItem.overallScore >= 60 ? "text-[#e8740b]" : "text-error"}`}>
                            {evalItem.overallScore}
                          </span>
                          <Progress value={evalItem.overallScore} className="h-1.5 w-16" />
                        </div>
                      </TableCell>
                      <TableCell className="text-sm text-gray-500">
                        {new Date(evalItem.evaluatedAt).toLocaleString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                      </TableCell>
                      <TableCell className="text-sm text-gray-600">{evalItem.evaluator}</TableCell>
                      <TableCell>
                        <Badge className={`text-xs ${statusColor[evalItem.status]}`}>
                          {statusLabel[evalItem.status]}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 gap-1"
                          onClick={() => setSelectedEval(selectedEval === evalItem.id ? null : evalItem.id)}
                        >
                          <Eye className="h-3.5 w-3.5" /> 详情
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Detail Panel — side card on lg+, full-width overlay on smaller screens
            (previously `hidden lg:block`, which left small screens blank after a row tap). */}
        {selected && (
          <Card className="border-gray-200 w-full lg:w-96 shrink-0">
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-on-surface">评估详情</h3>
                <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => setSelectedEval(null)} aria-label="关闭详情">
                  <X className="h-4 w-4" />
                </Button>
              </div>
              <div className="text-center mb-4 py-3 bg-gray-50 rounded-lg">
                <p className="text-xs text-gray-500 mb-1">综合评分</p>
                <p className={`text-4xl font-bold ${selected.overallScore >= 80 ? "text-[#00875a]" : selected.overallScore >= 60 ? "text-[#e8740b]" : "text-error"}`}>
                  {selected.overallScore}
                </p>
              </div>
              <div className="space-y-3">
                {selected.categories.map((cat, i) => (
                  <div key={i}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-gray-600">{cat.name}</span>
                      <span className={`text-xs font-medium ${cat.score >= 80 ? "text-[#00875a]" : cat.score >= 60 ? "text-[#e8740b]" : "text-error"}`}>
                        {cat.score}/{cat.maxScore}
                      </span>
                    </div>
                    <Progress value={(cat.score / cat.maxScore) * 100} className="h-1.5" />
                    <p className="text-xs text-gray-400 mt-1">{cat.comments}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
