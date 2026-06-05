"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Search, Eye, ClipboardCheck, TrendingUp, BarChart3, Calendar } from "lucide-react";
import { mockEvaluations } from "@/lib/mock-data";

const statusColor = {
  completed: "text-[#10B981] bg-green-50",
  pending: "text-[#F59E0B] bg-amber-50",
  disputed: "text-[#EF4444] bg-red-50",
};

const statusLabel = {
  completed: "已完成",
  pending: "待审核",
  disputed: "有异议",
};

export default function EvaluationsPage() {
  const [selectedEval, setSelectedEval] = useState<string | null>(null);

  const selected = mockEvaluations.find((e) => e.id === selectedEval);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#1A1A2E]">评估记录</h1>
          <p className="text-sm text-gray-500 mt-1">查看方案质量评估历史和详细报告</p>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <Card className="border-gray-200">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-[#1E3A5F]/5 flex items-center justify-center">
              <ClipboardCheck className="h-5 w-5 text-[#1E3A5F]" />
            </div>
            <div>
              <p className="text-xs text-gray-500">总评估数</p>
              <p className="text-xl font-bold text-[#1E3A5F]">{mockEvaluations.length}</p>
            </div>
          </CardContent>
        </Card>
        <Card className="border-gray-200">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-green-50 flex items-center justify-center">
              <TrendingUp className="h-5 w-5 text-[#10B981]" />
            </div>
            <div>
              <p className="text-xs text-gray-500">平均分</p>
              <p className="text-xl font-bold text-[#10B981]">
                {Math.round(mockEvaluations.reduce((acc, e) => acc + e.overallScore, 0) / mockEvaluations.length)}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card className="border-gray-200">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-amber-50 flex items-center justify-center">
              <BarChart3 className="h-5 w-5 text-[#F59E0B]" />
            </div>
            <div>
              <p className="text-xs text-gray-500">已完成</p>
              <p className="text-xl font-bold text-[#F59E0B]">
                {mockEvaluations.filter((e) => e.status === "completed").length}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="flex gap-6">
        {/* Table */}
        <Card className={`border-gray-200 flex-1 ${selectedEval ? "hidden lg:block" : ""}`}>
          <CardContent className="p-0">
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
                {mockEvaluations.map((evalItem) => (
                  <TableRow key={evalItem.id} className={selectedEval === evalItem.id ? "bg-[#1E3A5F]/5" : ""}>
                    <TableCell className="text-sm font-medium text-[#1A1A2E]">{evalItem.projectName}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span className={`text-sm font-bold ${evalItem.overallScore >= 80 ? "text-[#10B981]" : evalItem.overallScore >= 60 ? "text-[#F59E0B]" : "text-[#EF4444]"}`}>
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
          </CardContent>
        </Card>

        {/* Detail Panel */}
        {selected && (
          <Card className="border-gray-200 w-96 hidden lg:block">
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-[#1A1A2E]">评估详情</h3>
                <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={() => setSelectedEval(null)}>
                  x
                </Button>
              </div>
              <div className="text-center mb-4 py-3 bg-gray-50 rounded-lg">
                <p className="text-xs text-gray-500 mb-1">综合评分</p>
                <p className={`text-4xl font-bold ${selected.overallScore >= 80 ? "text-[#10B981]" : selected.overallScore >= 60 ? "text-[#F59E0B]" : "text-[#EF4444]"}`}>
                  {selected.overallScore}
                </p>
              </div>
              <div className="space-y-3">
                {selected.categories.map((cat, i) => (
                  <div key={i}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-gray-600">{cat.name}</span>
                      <span className={`text-xs font-medium ${cat.score >= 80 ? "text-[#10B981]" : cat.score >= 60 ? "text-[#F59E0B]" : "text-[#EF4444]"}`}>
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
