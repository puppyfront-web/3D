"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import {
  Calendar,
  User,
  Clock,
  Tag,
  ArrowRight,
  TrendingUp,
  FileText,
  Image,
  CheckCircle2,
  Loader2,
} from "lucide-react";
import { StatusTag, PriorityTag } from "@/components/workspace/status-tag";
import { getProjectById } from "@/lib/api";
import type { Project } from "@/types";

export default function ProjectOverviewPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);

  const loadProject = useCallback(async () => {
    setLoading(true);
    const res = await getProjectById(projectId);
    if (res.success && res.data) {
      setProject(res.data);
    }
    setLoading(false);
  }, [projectId]);

  useEffect(() => {
    loadProject();
  }, [loadProject]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-[#1E3A5F]" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        项目未找到
      </div>
    );
  }

  const steps = [
    { label: "需求确认", status: "completed" },
    { label: "企业分析", status: project.progress! >= 35 ? "completed" : "current" },
    { label: "方案撰写", status: project.progress! >= 65 ? "completed" : project.progress! >= 35 ? "current" : "pending" },
    { label: "视觉设计", status: project.progress! >= 78 ? "completed" : project.progress! >= 65 ? "current" : "pending" },
    { label: "审核导出", status: project.progress! >= 90 ? "completed" : project.progress! >= 78 ? "current" : "pending" },
  ];

  return (
    <div className="p-6 max-w-6xl">
      {/* Project Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-xl font-semibold text-[#1A1A2E]">{project.name}</h1>
            <StatusTag status={project.status} />
            {project.priority && <PriorityTag priority={project.priority} />}
          </div>
          <p className="text-sm text-gray-500">{project.client} | {project.industry}</p>
        </div>
        <Button variant="outline" size="sm" className="gap-1">
          编辑项目
        </Button>
      </div>

      {/* Description */}
      <Card className="mb-6 border-gray-200">
        <CardContent className="p-5">
          <p className="text-sm text-gray-600 leading-relaxed">{project.description}</p>
          <div className="flex flex-wrap gap-2 mt-4">
            {(project.tags || []).map((tag) => (
              <Badge key={tag} variant="secondary" className="text-xs bg-blue-50 text-[#1E3A5F]">
                {tag}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-3 gap-6 mb-6">
        {/* Progress */}
        <Card className="col-span-2 border-gray-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">项目进度</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-500">整体完成度</span>
              <span className="text-lg font-bold text-[#1E3A5F]">{project.progress}%</span>
            </div>
            <Progress value={project.progress} className="h-2 mb-6" />
            <div className="flex items-center justify-between">
              {steps.map((step, i) => (
                <div key={i} className="flex flex-col items-center gap-2">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium ${
                      step.status === "completed"
                        ? "bg-[#10B981] text-white"
                        : step.status === "current"
                        ? "bg-[#1E3A5F] text-white"
                        : "bg-gray-100 text-gray-400"
                    }`}
                  >
                    {step.status === "completed" ? (
                      <CheckCircle2 className="h-4 w-4" />
                    ) : (
                      i + 1
                    )}
                  </div>
                  <span className="text-xs text-gray-500">{step.label}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Info */}
        <Card className="border-gray-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">项目信息</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-3">
              <User className="h-4 w-4 text-gray-400" />
              <div>
                <p className="text-xs text-gray-400">负责人</p>
                <p className="text-sm text-[#1A1A2E]">{project.assignee}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Calendar className="h-4 w-4 text-gray-400" />
              <div>
                <p className="text-xs text-gray-400">截止日期</p>
                <p className="text-sm text-[#1A1A2E]">{project.dueDate}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Clock className="h-4 w-4 text-gray-400" />
              <div>
                <p className="text-xs text-gray-400">创建时间</p>
                <p className="text-sm text-[#1A1A2E]">{project.createdAt}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <TrendingUp className="h-4 w-4 text-gray-400" />
              <div>
                <p className="text-xs text-gray-400">最后更新</p>
                <p className="text-sm text-[#1A1A2E]">{project.updatedAt}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { icon: <FileText className="h-5 w-5" />, label: "企业分析", desc: "查看分析报告", href: "company-analysis" },
          { icon: <FileText className="h-5 w-5" />, label: "方案编辑", desc: "编辑方案内容", href: "proposal" },
          { icon: <Image className="h-5 w-5" />, label: "视觉创作", desc: "生成视觉素材", href: "visual" },
          { icon: <CheckCircle2 className="h-5 w-5" />, label: "审核校验", desc: "检查方案质量", href: "review" },
        ].map((action) => (
          <a
            key={action.href}
            href={`/workspace/projects/${projectId}/${action.href}`}
            className="group"
          >
            <Card className="border-gray-200 hover:border-[#2D5A8E]/30 hover:shadow-sm transition-all">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="w-10 h-10 rounded-lg bg-[#1E3A5F]/5 flex items-center justify-center text-[#1E3A5F] group-hover:bg-[#1E3A5F] group-hover:text-white transition-colors">
                  {action.icon}
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-[#1A1A2E]">{action.label}</p>
                  <p className="text-xs text-gray-400">{action.desc}</p>
                </div>
                <ArrowRight className="h-4 w-4 text-gray-300 group-hover:text-[#1E3A5F] transition-colors" />
              </CardContent>
            </Card>
          </a>
        ))}
      </div>
    </div>
  );
}
