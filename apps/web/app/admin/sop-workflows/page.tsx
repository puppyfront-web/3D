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
  DialogFooter,
  DialogClose,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  GitBranch,
  Plus,
  Play,
  Pause,
  Edit3,
  Trash2,
  ChevronUp,
  ChevronDown,
  ChevronRight,
  Clock,
  Bot,
  ArrowRight,
  Download,
  Loader2,
} from "lucide-react";
import {
  getSOPWorkflows,
  createSOPWorkflow,
  updateSOPWorkflow,
  deleteSOPWorkflow,
  importSOPWorkflows,
  exportSOPWorkflows,
  exportSOPWorkflow,
} from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import { FileUploadButton } from "@/components/admin/file-upload-button";
import type { SOPWorkflow, SOPStep, ImportMode } from "@/types";

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
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [editingWf, setEditingWf] = useState<SOPWorkflow | null>(null);
  const [deletingWf, setDeletingWf] = useState<SOPWorkflow | null>(null);
  const [saving, setSaving] = useState(false);

  // Edit form state
  const [editForm, setEditForm] = useState({
    name: "",
    description: "",
    category: "",
    boundAgent: "",
    versionNote: "",
    isActive: true,
  });
  // Steps editor state — minimal core fields only
  const [editSteps, setEditSteps] = useState<
    { name: string; description: string; agent: string }[]
  >([]);

  const resetEditForm = () => {
    setEditForm({
      name: "",
      description: "",
      category: "",
      boundAgent: "",
      versionNote: "",
      isActive: true,
    });
    setEditSteps([]);
    setEditingWf(null);
  };

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

  const handleImport = async (file: File, mode: ImportMode) => {
    const res = await importSOPWorkflows(file, mode);
    if (res.success && res.data) {
      await loadWorkflows();
      return res.data;
    }
    throw new Error(res.message || "导入失败");
  };

  const handleExport = async () => {
    const blob = await exportSOPWorkflows();
    downloadBlob(blob, "sop_workflows.json");
  };

  const handleExportOne = async (wf: SOPWorkflow) => {
    const blob = await exportSOPWorkflow(wf.id);
    downloadBlob(blob, `${wf.name.replace(/[/\\:*?"<>|]/g, "_")}.json`);
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

  // --- Edit ---
  const openEdit = (wf: SOPWorkflow) => {
    setEditingWf(wf);
    setEditForm({
      name: wf.name,
      description: wf.description,
      category: wf.category,
      boundAgent: wf.boundAgent ?? "",
      versionNote: wf.versionNote ?? "",
      isActive: wf.isActive,
    });
    setEditSteps(
      (wf.steps ?? []).map((s) => ({
        name: s.name,
        description: s.description,
        agent: s.agentType,
      })),
    );
    setEditDialogOpen(true);
  };

  const handleEditSave = async () => {
    if (!editingWf) return;
    if (!editForm.name.trim()) return;
    setSaving(true);
    try {
      const steps: SOPStep[] = editSteps.map((s, i) => ({
        id: `${i + 1}`,
        name: s.name,
        description: s.description,
        order: i + 1,
        agentType: s.agent,
        estimatedTime: "",
        requiredInputs: [],
        outputs: [],
      }));
      const res = await updateSOPWorkflow(editingWf.id, {
        name: editForm.name,
        description: editForm.description,
        category: editForm.category,
        boundAgent: editForm.boundAgent,
        versionNote: editForm.versionNote,
        isActive: editForm.isActive,
        steps,
      });
      if (res.success) {
        setEditDialogOpen(false);
        resetEditForm();
        await loadWorkflows();
      }
    } finally {
      setSaving(false);
    }
  };

  // --- Delete (with confirmation) ---
  const openDelete = (wf: SOPWorkflow) => {
    setDeletingWf(wf);
    setDeleteDialogOpen(true);
  };

  const handleDelete = async () => {
    if (!deletingWf) return;
    setSaving(true);
    try {
      const res = await deleteSOPWorkflow(deletingWf.id);
      if (res.success) {
        setDeleteDialogOpen(false);
        setDeletingWf(null);
        await loadWorkflows();
      }
    } finally {
      setSaving(false);
    }
  };

  // --- Steps editor helpers ---
  const addStep = () =>
    setEditSteps((prev) => [...prev, { name: "", description: "", agent: "" }]);
  const updateStep = (
    i: number,
    field: "name" | "description" | "agent",
    value: string,
  ) =>
    setEditSteps((prev) =>
      prev.map((s, idx) => (idx === i ? { ...s, [field]: value } : s)),
    );
  const removeStep = (i: number) =>
    setEditSteps((prev) => prev.filter((_, idx) => idx !== i));
  const moveStep = (i: number, dir: -1 | 1) =>
    setEditSteps((prev) => {
      const j = i + dir;
      if (j < 0 || j >= prev.length) return prev;
      const next = [...prev];
      [next[i], next[j]] = [next[j], next[i]];
      return next;
    });

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-on-surface">SOP工作流配置</h1>
          <p className="text-sm text-gray-500 mt-1">配置方案生成的自动化工作流程和步骤</p>
        </div>
        <div className="flex items-center gap-2">
          <FileUploadButton
            accept=".json"
            dialogTitle="导入 SOP 工作流"
            dialogDescription="支持 JSON 格式，含 steps 数组定义。"
            onUpload={handleImport}
          />
          <Button variant="outline" size="sm" className="gap-1.5" onClick={handleExport}>
            <Download className="h-3.5 w-3.5" />
            导出
          </Button>
          <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button className="bg-primary hover:bg-primary gap-2">
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
                className="w-full bg-primary hover:bg-primary"
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
                  <GitBranch className="h-5 w-5 text-primary" />
                  <div>
                    <CardTitle className="text-sm font-medium">{wf.name}</CardTitle>
                    <p className="text-xs text-gray-500 mt-0.5">{wf.description}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Badge variant="secondary" className="text-xs">{wf.category}</Badge>
                  <Badge variant="outline" className="text-xs">{(wf.steps ?? []).length} 个步骤</Badge>
                  <Badge className={`text-xs ${wf.isActive ? "bg-green-50 text-[#00875a]" : "bg-gray-100 text-gray-500"}`}>
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
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 gap-1"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleExportOne(wf);
                    }}
                  >
                    <Download className="h-3 w-3" /> 导出
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 gap-1"
                    onClick={(e) => {
                      e.stopPropagation();
                      openEdit(wf);
                    }}
                  >
                    <Edit3 className="h-3 w-3" /> 编辑
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 gap-1 text-error"
                    onClick={(e) => {
                      e.stopPropagation();
                      openDelete(wf);
                    }}
                  >
                    <Trash2 className="h-3 w-3" /> 删除
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
                            <span className="font-medium text-primary">{stage.name}</span>
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
                        <div className="w-8 h-8 rounded-full bg-primary text-white flex items-center justify-center text-xs font-medium">
                          {i + 1}
                        </div>
                        {i < (wf.steps ?? []).length - 1 && (
                          <div className="w-px h-8 bg-gray-200 mt-1" />
                        )}
                      </div>
                      <div className="flex-1 p-3 bg-gray-50 rounded-lg">
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-medium text-on-surface">{step.name}</p>
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

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>编辑工作流</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>工作流名称</Label>
                <Input
                  value={editForm.name}
                  onChange={(e) =>
                    setEditForm((prev) => ({ ...prev, name: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>分类</Label>
                <Input
                  value={editForm.category}
                  onChange={(e) =>
                    setEditForm((prev) => ({ ...prev, category: e.target.value }))
                  }
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>描述</Label>
              <Textarea
                rows={2}
                value={editForm.description}
                onChange={(e) =>
                  setEditForm((prev) => ({ ...prev, description: e.target.value }))
                }
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>绑定 Agent</Label>
                <Input
                  placeholder="如：proposal_writer_agent"
                  value={editForm.boundAgent}
                  onChange={(e) =>
                    setEditForm((prev) => ({ ...prev, boundAgent: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-2 flex items-end pb-2">
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="wf-active"
                    checked={editForm.isActive}
                    onCheckedChange={(v) =>
                      setEditForm((prev) => ({ ...prev, isActive: v === true }))
                    }
                  />
                  <Label htmlFor="wf-active" className="cursor-pointer">启用状态</Label>
                </div>
              </div>
            </div>
            <div className="space-y-2">
              <Label>版本说明</Label>
              <Textarea
                rows={2}
                placeholder="说明本次修改..."
                value={editForm.versionNote}
                onChange={(e) =>
                  setEditForm((prev) => ({ ...prev, versionNote: e.target.value }))
                }
              />
            </div>

            {/* Steps editor (minimal core fields) */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>步骤（{editSteps.length}）</Label>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 gap-1"
                  onClick={addStep}
                >
                  <Plus className="h-3 w-3" /> 添加步骤
                </Button>
              </div>
              <div className="space-y-2">
                {editSteps.length === 0 && (
                  <p className="text-xs text-gray-400">暂无步骤，点击「添加步骤」创建。</p>
                )}
                {editSteps.map((step, i) => (
                  <div
                    key={i}
                    className="rounded-lg border border-gray-200 p-3 space-y-2 bg-gray-50"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-gray-500">
                        步骤 {i + 1}
                      </span>
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0"
                          onClick={() => moveStep(i, -1)}
                          disabled={i === 0}
                        >
                          <ChevronUp className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0"
                          onClick={() => moveStep(i, 1)}
                          disabled={i === editSteps.length - 1}
                        >
                          <ChevronDown className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0 text-error"
                          onClick={() => removeStep(i)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <Input
                        placeholder="步骤名称"
                        value={step.name}
                        onChange={(e) => updateStep(i, "name", e.target.value)}
                      />
                      <Input
                        placeholder="Agent（如：writer_agent）"
                        value={step.agent}
                        onChange={(e) => updateStep(i, "agent", e.target.value)}
                      />
                    </div>
                    <Textarea
                      rows={2}
                      placeholder="步骤描述..."
                      value={step.description}
                      onChange={(e) => updateStep(i, "description", e.target.value)}
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter className="mt-4 gap-2">
            <DialogClose asChild>
              <Button variant="outline">取消</Button>
            </DialogClose>
            <Button
              className="bg-primary hover:bg-primary"
              onClick={handleEditSave}
              disabled={saving || !editForm.name.trim()}
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-gray-600">
            确定要删除工作流「{deletingWf?.name}」吗？此操作不可撤销。
          </p>
          <DialogFooter className="mt-4 gap-2">
            <DialogClose asChild>
              <Button variant="outline">取消</Button>
            </DialogClose>
            <Button variant="destructive" onClick={handleDelete} disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
