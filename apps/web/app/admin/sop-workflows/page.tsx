"use client";

import { useState, useEffect, useCallback } from "react";
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
  Loader2,
} from "lucide-react";
import {
  getSOPWorkflows,
  createSOPWorkflow,
  updateSOPWorkflow,
  deleteSOPWorkflow,
  importSOPWorkflows,
} from "@/lib/api";
import { FileUploadButton } from "@/components/admin/file-upload-button";
import type { SOPWorkflow, PipelineStage } from "@/types";

export default function SOPWorkflowsPage() {
  const [workflows, setWorkflows] = useState<SOPWorkflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string[]>([]);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    name: "",
    description: "",
    category: "",
  });
  const [creating, setCreating] = useState(false);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  const loadWorkflows = useCallback(async () => {
    const res = await getSOPWorkflows();
    if (res.success && res.data) {
      setWorkflows(res.data);
      setExpanded((prev) => {
        if (prev.length === 0 && res.data!.length > 0) {
          return [res.data![0].id];
        }
        return prev;
      });
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    loadWorkflows().finally(() => setLoading(false));
  }, [loadWorkflows]);

  const toggleExpand = (id: string) => {
    setExpanded((prev) =>
      prev.includes(id) ? prev.filter((e) => e !== id) : [...prev, id]
    );
  };

  const handleImport = async (file: File) => {
    const res = await importSOPWorkflows(file);
    if (res.success && res.data) {
      await loadWorkflows();
      return res.data;
    }
    throw new Error(res.message || "导入失败");
  };

  const handleCreate = async () => {
    setCreating(true);
    const res = await createSOPWorkflow({
      name: createForm.name,
      description: createForm.description,
      category: createForm.category,
      steps: [],
      isActive: true,
    });
    if (res.success) {
      setCreateDialogOpen(false);
      setCreateForm({ name: "", description: "", category: "" });
      await loadWorkflows();
    }
    setCreating(false);
  };

  const handleToggleActive = async (wf: SOPWorkflow) => {
    setTogglingId(wf.id);
    const res = await updateSOPWorkflow(wf.id, { isActive: !wf.isActive });
    if (res.success) {
      await loadWorkflows();
    }
    setTogglingId(null);
  };

  const handleDelete = async (id: string) => {
    const res = await deleteSOPWorkflow(id);
    if (res.success) {
      await loadWorkflows();
    }
  };

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-[#1E3A5F]" />
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#1A1A2E]">SOP工作流配置</h1>
          <p className="text-sm text-gray-500 mt-1">配置方案生成的自动化工作流程和步骤</p>
        </div>
        <div className="flex items-center gap-2">
          <FileUploadButton
            accept=".json"
            dialogTitle="导入 SOP 工作流"
            dialogDescription="支持 JSON 格式，含 steps 数组定义。"
            onUpload={handleImport}
          />
          <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
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
                <Input
                  placeholder="输入工作流名称"
                  value={createForm.name}
                  onChange={(e) =>
                    setCreateForm((prev) => ({ ...prev, name: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>描述</Label>
                <Textarea
                  placeholder="描述工作流用途..."
                  rows={3}
                  value={createForm.description}
                  onChange={(e) =>
                    setCreateForm((prev) => ({ ...prev, description: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>分类</Label>
                <Input
                  placeholder="输入分类"
                  value={createForm.category}
                  onChange={(e) =>
                    setCreateForm((prev) => ({ ...prev, category: e.target.value }))
                  }
                />
              </div>
              <Button
                className="w-full bg-[#1E3A5F] hover:bg-[#2D5A8E]"
                onClick={handleCreate}
                disabled={creating || !createForm.name.trim()}
              >
                {creating ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" /> 创建中...
                  </>
                ) : (
                  "创建工作流"
                )}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
        </div>
      </div>

      <div className="space-y-4">
        {workflows.map((wf) => (
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
                  <Badge variant="outline" className="text-xs">{(wf.steps ?? []).length} 个步骤</Badge>
                  <Badge className={`text-xs ${wf.isActive ? "bg-green-50 text-[#10B981]" : "bg-gray-100 text-gray-500"}`}>
                    {wf.isActive ? "启用中" : "已停用"}
                  </Badge>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 gap-1"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleToggleActive(wf);
                    }}
                    disabled={togglingId === wf.id}
                  >
                    {togglingId === wf.id ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : wf.isActive ? (
                      <Pause className="h-3 w-3" />
                    ) : (
                      <Play className="h-3 w-3" />
                    )}
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

                {/* Pipeline Stages Overview */}
                {wf.pipelineStages && wf.pipelineStages.length > 0 && (
                  <div className="ml-7 mb-5">
                    <p className="text-xs font-medium text-gray-500 mb-2">PIPELINE 阶段</p>
                    <div className="flex items-center gap-2 flex-wrap">
                      {wf.pipelineStages.map((stage, i) => (
                        <div key={stage.stage} className="flex items-center gap-2">
                          <div className="px-3 py-1.5 bg-blue-50 border border-blue-100 rounded-lg text-xs">
                            <span className="font-medium text-[#1E3A5F]">{stage.name}</span>
                            {stage.description && (
                              <span className="text-gray-400 ml-1">— {stage.description}</span>
                            )}
                          </div>
                          {i < wf.pipelineStages!.length - 1 && (
                            <ArrowRight className="h-3 w-3 text-gray-300" />
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="space-y-3 ml-7">
                  {(wf.steps ?? []).map((step, i) => (
                    <div key={i} className="flex items-start gap-4">
                      <div className="flex flex-col items-center">
                        <div className="w-8 h-8 rounded-full bg-[#1E3A5F] text-white flex items-center justify-center text-xs font-medium">
                          {i + 1}
                        </div>
                        {i < (wf.steps ?? []).length - 1 && (
                          <div className="w-px h-8 bg-gray-200 mt-1" />
                        )}
                      </div>
                      <div className="flex-1 p-3 bg-gray-50 rounded-lg">
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-medium text-[#1A1A2E]">{step.name}</p>
                            {step.stage && (
                              <Badge variant="secondary" className="text-[10px] bg-purple-50 text-purple-600">
                                {step.stage}
                              </Badge>
                            )}
                          </div>
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
                          <span>输入：{(step.requiredInputs ?? []).join("、")}</span>
                          <ArrowRight className="h-3 w-3" />
                          <span>输出：{(step.outputs ?? []).join("、")}</span>
                        </div>

                        {/* Rules */}
                        {step.rules && step.rules.length > 0 && (
                          <div className="mt-2 pt-2 border-t border-gray-100">
                            <p className="text-[10px] font-medium text-gray-400 mb-1">规则</p>
                            <div className="space-y-1">
                              {step.rules.map((rule, ri) => (
                                <div key={ri} className="flex items-start gap-1.5 text-[11px]">
                                  <Badge variant="outline" className={`text-[10px] px-1 py-0 ${rule.type === "custom" ? "border-orange-200 text-orange-600" : "border-gray-200 text-gray-500"}`}>
                                    {rule.type === "custom" ? "定制" : "通用"}
                                  </Badge>
                                  <span className="text-gray-600">{rule.description}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Prompts */}
                        {step.prompts && step.prompts.length > 0 && (
                          <div className="mt-2 pt-2 border-t border-gray-100">
                            <p className="text-[10px] font-medium text-gray-400 mb-1">分析问题</p>
                            <div className="space-y-1">
                              {step.prompts.map((p, pi) => (
                                <div key={pi} className="text-[11px] text-gray-600">
                                  <span className="text-gray-400 mr-1">{p.number}.</span>
                                  {p.question}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Dependencies */}
                        {step.dependencies && step.dependencies.length > 0 && (
                          <div className="mt-2 pt-2 border-t border-gray-100 text-[11px] text-gray-400">
                            依赖：{step.dependencies.join("、")}
                          </div>
                        )}
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
