"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  GitBranch,
  Plus,
  Play,
  Pause,
  Edit3,
  ChevronDown,
  ChevronRight,
  Clock,
  Bot,
  ArrowRight,
} from "lucide-react";
import { mockSOPWorkflows } from "@/lib/mock-data";

export default function SOPWorkflowsPage() {
  const [expanded, setExpanded] = useState<string[]>([mockSOPWorkflows[0].id]);

  const toggleExpand = (id: string) => {
    setExpanded((prev) =>
      prev.includes(id) ? prev.filter((e) => e !== id) : [...prev, id]
    );
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#1A1A2E]">SOP工作流配置</h1>
          <p className="text-sm text-gray-500 mt-1">配置方案生成的自动化工作流程和步骤</p>
        </div>
        <Dialog>
          <DialogTrigger asChild>
            <Button className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-2">
              <Plus className="h-4 w-4" /> 新建工作流
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>新建SOP工作流</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div className="space-y-2">
                <Label>工作流名称</Label>
                <Input placeholder="输入工作流名称" />
              </div>
              <div className="space-y-2">
                <Label>描述</Label>
                <Textarea placeholder="描述工作流用途..." rows={3} />
              </div>
              <div className="space-y-2">
                <Label>分类</Label>
                <Input placeholder="输入分类" />
              </div>
              <Button className="w-full bg-[#1E3A5F] hover:bg-[#2D5A8E]">创建工作流</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="space-y-4">
        {mockSOPWorkflows.map((wf) => (
          <Card key={wf.id} className="border-gray-200">
            <CardHeader className="pb-3 cursor-pointer" onClick={() => toggleExpand(wf.id)}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {expanded.includes(wf.id) ? (
                    <ChevronDown className="h-4 w-4 text-gray-400" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-gray-400" />
                  )}
                  <GitBranch className="h-5 w-5 text-[#1E3A5F]" />
                  <div>
                    <CardTitle className="text-sm font-medium">{wf.name}</CardTitle>
                    <p className="text-xs text-gray-500 mt-0.5">{wf.description}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Badge variant="secondary" className="text-xs">{wf.category}</Badge>
                  <Badge variant="outline" className="text-xs">{wf.steps.length} 个步骤</Badge>
                  <Badge className={`text-xs ${wf.isActive ? "bg-green-50 text-[#10B981]" : "bg-gray-100 text-gray-500"}`}>
                    {wf.isActive ? "启用中" : "已停用"}
                  </Badge>
                  <Button variant="ghost" size="sm" className="h-7 gap-1">
                    {wf.isActive ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3" />}
                    {wf.isActive ? "停用" : "启用"}
                  </Button>
                  <Button variant="ghost" size="sm" className="h-7 gap-1">
                    <Edit3 className="h-3 w-3" /> 编辑
                  </Button>
                </div>
              </div>
            </CardHeader>
            {expanded.includes(wf.id) && (
              <CardContent className="pt-0">
                <Separator className="mb-4" />
                <div className="space-y-3 ml-7">
                  {wf.steps.map((step, i) => (
                    <div key={step.id} className="flex items-start gap-4">
                      <div className="flex flex-col items-center">
                        <div className="w-8 h-8 rounded-full bg-[#1E3A5F] text-white flex items-center justify-center text-xs font-medium">
                          {i + 1}
                        </div>
                        {i < wf.steps.length - 1 && (
                          <div className="w-px h-8 bg-gray-200 mt-1" />
                        )}
                      </div>
                      <div className="flex-1 p-3 bg-gray-50 rounded-lg">
                        <div className="flex items-center justify-between mb-1">
                          <p className="text-sm font-medium text-[#1A1A2E]">{step.name}</p>
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className="text-xs">
                              <Bot className="h-3 w-3 mr-1" /> {step.agentType}
                            </Badge>
                            <Badge variant="secondary" className="text-xs">
                              <Clock className="h-3 w-3 mr-1" /> {step.estimatedTime}
                            </Badge>
                          </div>
                        </div>
                        <p className="text-xs text-gray-500 mb-2">{step.description}</p>
                        <div className="flex gap-4 text-xs text-gray-400">
                          <span>输入：{step.requiredInputs.join("、")}</span>
                          <ArrowRight className="h-3 w-3" />
                          <span>输出：{step.outputs.join("、")}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
