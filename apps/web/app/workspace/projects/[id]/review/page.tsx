"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  ClipboardCheck,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  Download,
  RotateCcw,
  ArrowRight,
  Loader2,
} from "lucide-react";
import { getReviewChecklists } from "@/lib/api";
import type { ReviewChecklist } from "@/types";

export default function ReviewPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [checklists, setChecklists] = useState<ReviewChecklist[]>([]);
  const [loading, setLoading] = useState(true);

  const loadChecklists = useCallback(async () => {
    setLoading(true);
    const res = await getReviewChecklists(projectId);
    if (res.success && res.data) {
      setChecklists(res.data);
    }
    setLoading(false);
  }, [projectId]);

  useEffect(() => {
    loadChecklists();
  }, [loadChecklists]);

  const totalItems = checklists.reduce(
    (acc, cl) => acc + cl.items.length,
    0
  );
  const passItems = checklists.reduce(
    (acc, cl) => acc + cl.items.filter((i) => i.status === "pass").length,
    0
  );
  const warningItems = checklists.reduce(
    (acc, cl) => acc + cl.items.filter((i) => i.status === "warning").length,
    0
  );
  const failItems = checklists.reduce(
    (acc, cl) => acc + cl.items.filter((i) => i.status === "fail").length,
    0
  );
  const pendingItems = checklists.reduce(
    (acc, cl) => acc + cl.items.filter((i) => i.status === "pending").length,
    0
  );

  const statusIcon = (status: string) => {
    if (status === "pass") return <CheckCircle2 className="h-4 w-4 text-[#10B981]" />;
    if (status === "warning") return <AlertTriangle className="h-4 w-4 text-[#F59E0B]" />;
    if (status === "fail") return <XCircle className="h-4 w-4 text-[#EF4444]" />;
    return <Clock className="h-4 w-4 text-gray-400" />;
  };

  const statusBg = (status: string) => {
    if (status === "pass") return "bg-green-50";
    if (status === "warning") return "bg-amber-50";
    if (status === "fail") return "bg-red-50";
    return "bg-gray-50";
  };

  const statusLabel = (status: string) => {
    if (status === "pass") return "通过";
    if (status === "warning") return "警告";
    if (status === "fail") return "不通过";
    return "待审核";
  };

  const overallScore = totalItems > 0 ? Math.round((passItems / totalItems) * 100) : 0;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-[#1E3A5F]" />
      </div>
    );
  }

  if (checklists.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-gray-400 gap-3">
        <ClipboardCheck className="h-12 w-12 text-gray-300" />
        <p className="text-sm">暂无审核数据</p>
        <Button
          onClick={loadChecklists}
          className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-2"
        >
          <RotateCcw className="h-3.5 w-3.5" /> 重新审核
        </Button>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-[#1A1A2E]">审核校验</h2>
          <p className="text-sm text-gray-500 mt-1">自动质量审核 · 检查方案完整性、技术可行性与商务合规性</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" className="gap-1" onClick={loadChecklists}>
            <RotateCcw className="h-3.5 w-3.5" /> 重新审核
          </Button>
          <Button className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-1">
            <Download className="h-3.5 w-3.5" /> 导出报告
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-5 gap-4 mb-6">
        <Card className="border-gray-200">
          <CardContent className="p-4 text-center">
            <p className="text-xs text-gray-500 mb-1">总分</p>
            <p className="text-3xl font-bold text-[#1E3A5F]">{overallScore}</p>
            <Progress value={overallScore} className="h-1.5 mt-2" />
          </CardContent>
        </Card>
        <Card className="border-gray-200">
          <CardContent className="p-4 text-center">
            <p className="text-xs text-gray-500 mb-1">通过</p>
            <p className="text-2xl font-bold text-[#10B981]">{passItems}</p>
          </CardContent>
        </Card>
        <Card className="border-gray-200">
          <CardContent className="p-4 text-center">
            <p className="text-xs text-gray-500 mb-1">警告</p>
            <p className="text-2xl font-bold text-[#F59E0B]">{warningItems}</p>
          </CardContent>
        </Card>
        <Card className="border-gray-200">
          <CardContent className="p-4 text-center">
            <p className="text-xs text-gray-500 mb-1">不通过</p>
            <p className="text-2xl font-bold text-[#EF4444]">{failItems}</p>
          </CardContent>
        </Card>
        <Card className="border-gray-200">
          <CardContent className="p-4 text-center">
            <p className="text-xs text-gray-500 mb-1">待审核</p>
            <p className="text-2xl font-bold text-gray-400">{pendingItems}</p>
          </CardContent>
        </Card>
      </div>

      {/* Checklist Sections */}
      <div className="space-y-4">
        {checklists.map((checklist) => {
          const categoryPass = checklist.items.filter((i) => i.status === "pass").length;
          const categoryTotal = checklist.items.length;
          return (
            <Card key={checklist.id} className="border-gray-200">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <ClipboardCheck className="h-4 w-4 text-[#1E3A5F]" />
                    <CardTitle className="text-sm font-medium">{checklist.category}</CardTitle>
                  </div>
                  <Badge
                    variant="outline"
                    className={`text-xs ${
                      categoryPass === categoryTotal
                        ? "text-[#10B981] border-green-200"
                        : categoryPass > categoryTotal / 2
                        ? "text-[#F59E0B] border-amber-200"
                        : "text-[#EF4444] border-red-200"
                    }`}
                  >
                    {categoryPass}/{categoryTotal} 通过
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {checklist.items.map((item) => (
                    <div
                      key={item.id}
                      className={`flex items-start gap-3 p-3 rounded-lg ${statusBg(item.status)}`}
                    >
                      <div className="mt-0.5">{statusIcon(item.status)}</div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <p className="text-sm text-[#1A1A2E]">{item.description}</p>
                          <Badge
                            variant="outline"
                            className={`text-xs ${
                              item.status === "pass"
                                ? "text-[#10B981] border-green-200"
                                : item.status === "warning"
                                ? "text-[#F59E0B] border-amber-200"
                                : item.status === "fail"
                                ? "text-[#EF4444] border-red-200"
                                : "text-gray-400 border-gray-200"
                            }`}
                          >
                            {statusLabel(item.status)}
                          </Badge>
                        </div>
                        {item.comment && (
                          <p className="text-xs text-gray-500 mt-1">{item.comment}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Action */}
      {failItems > 0 && (
        <Card className="mt-6 border-red-200 bg-red-50/50">
          <CardContent className="p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <XCircle className="h-5 w-5 text-[#EF4444]" />
              <div>
                <p className="text-sm font-medium text-[#EF4444]">存在未通过项</p>
                <p className="text-xs text-gray-600">请修正标记为「不通过」的检查项后重新提交审核</p>
              </div>
            </div>
            <Button variant="outline" className="gap-1 border-red-200 text-[#EF4444] hover:bg-red-50">
              查看问题详情 <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
