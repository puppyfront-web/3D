"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  FileText,
  Edit3,
  Save,
  Sparkles,
  ChevronDown,
  ChevronRight,
  MessageSquare,
  Wand2,
  Copy,
  Download,
  PanelRightOpen,
  PanelRightClose,
  Clock,
  Loader2,
  CheckCircle2,
  CircleDot,
  RotateCcw,
} from "lucide-react";
import { AgentPanel } from "@/components/layout/agent-panel";
import {
  getProposal,
  generateProposal,
  updateProposalSection,
  updateSectionStatus,
  exportProposal,
} from "@/lib/api";
import type { Proposal } from "@/types";

export default function ProposalPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [expandedSections, setExpandedSections] = useState<string[]>([]);
  const [editingSection, setEditingSection] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const [agentOpen, setAgentOpen] = useState(true);

  const loadProposal = useCallback(async () => {
    setLoading(true);
    const res = await getProposal(projectId);
    if (res.success && res.data) {
      setProposal(res.data);
      setExpandedSections(res.data.sections.map((s) => s.id));
    }
    setLoading(false);
  }, [projectId]);

  useEffect(() => {
    loadProposal();
  }, [loadProposal]);

  const handleGenerate = async () => {
    setGenerating(true);
    const res = await generateProposal(projectId);
    if (res.success && res.data) {
      setProposal(res.data);
      setExpandedSections(res.data.sections.map((s) => s.id));
    }
    setGenerating(false);
  };

  const toggleSection = (id: string) => {
    setExpandedSections((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]
    );
  };

  const startEdit = (sectionId: string, content: string) => {
    setEditingSection(sectionId);
    setEditContent(content);
  };

  const saveEdit = async () => {
    if (!editingSection || !proposal) return;
    const res = await updateProposalSection(proposal.id, editingSection, editContent);
    if (res.success && res.data) {
      setProposal(res.data);
    } else {
      setProposal((prev) =>
        prev
          ? {
              ...prev,
              sections: prev.sections.map((s) =>
                s.id === editingSection ? { ...s, content: editContent } : s
              ),
            }
          : prev
      );
    }
    setEditingSection(null);
  };

  const statusColor = (status: string) => {
    if (status === "approved") return "bg-green-50 text-[#10B981]";
    if (status === "review") return "bg-amber-50 text-[#F59E0B]";
    return "bg-gray-100 text-gray-500";
  };

  const statusLabel = (status: string) => {
    if (status === "approved") return "已审核";
    if (status === "review") return "审核中";
    return "草稿";
  };

  const handleSectionStatus = async (sectionOrder: number, newStatus: "draft" | "review" | "approved") => {
    if (!proposal?.id) return;
    const res = await updateSectionStatus(proposal.id, sectionOrder, newStatus);
    if (res.success && res.data) {
      const updatedMeta = (res.data as Record<string, unknown>)?.sections_meta as Array<Record<string, unknown>> | undefined;
      if (updatedMeta && proposal) {
        setProposal({
          ...proposal,
          sections: proposal.sections.map((s): Proposal["sections"][number] => {
            const meta = updatedMeta.find((m) => m.order === s.order);
            const newStatus = (meta?.status as "draft" | "review" | "approved") || s.status;
            return meta ? { ...s, status: newStatus } : s;
          }),
        });
      }
    }
  };

  const approvedCount = proposal?.sections.filter((s) => s.status === "approved").length ?? 0;
  const totalCount = proposal?.sections.length ?? 0;
  const allApproved = totalCount > 0 && approvedCount === totalCount;

  const handleExport = async (format: "word" | "pdf" | "pptx") => {
    if (!proposal?.id) return;
    try {
      const blob = await exportProposal(proposal.id, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `proposal.${format === "word" ? "docx" : format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err instanceof Error ? err.message : "导出失败");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-[#1E3A5F]" />
      </div>
    );
  }

  if (!proposal) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-gray-400 gap-3">
        <FileText className="h-12 w-12 text-gray-300" />
        <p className="text-sm">暂无策划案数据</p>
        <Button
          onClick={handleGenerate}
          disabled={generating}
          className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-2"
        >
          {generating ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" /> 生成中...
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" /> 生成策划案
            </>
          )}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-8rem)]">
      {/* Main Editor Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Toolbar */}
        <div className="flex items-center justify-between px-6 py-3 bg-white border-b border-gray-200">
          <div className="flex items-center gap-3">
            <FileText className="h-5 w-5 text-[#1E3A5F]" />
            <div>
              <h2 className="text-sm font-semibold text-[#1A1A2E]">{proposal.title}</h2>
              <div className="flex items-center gap-2 text-xs text-gray-400">
                <Clock className="h-3 w-3" />
                <span>最后编辑：{new Date(proposal.lastEditedAt).toLocaleString("zh-CN")}</span>
                <span>·</span>
                <span>v{proposal.version}</span>
                <span>·</span>
                <span>{proposal.totalWords} 字</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Review progress */}
            {totalCount > 0 && (
              <div className="flex items-center gap-1.5 text-xs text-gray-500 mr-2">
                <div className="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[#10B981] rounded-full transition-all"
                    style={{ width: `${(approvedCount / totalCount) * 100}%` }}
                  />
                </div>
                <span>{approvedCount}/{totalCount} 已审核</span>
              </div>
            )}
            <Button variant="outline" size="sm" className="gap-1">
              <Copy className="h-3.5 w-3.5" /> 复制
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-1"
                  disabled={!allApproved}
                  title={!allApproved ? `${totalCount - approvedCount} 个章节未审核` : undefined}
                >
                  <Download className="h-3.5 w-3.5" /> 导出
                  {!allApproved && (
                    <span className="text-[10px] text-amber-500 ml-1">({totalCount - approvedCount}未审)</span>
                  )}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuItem onClick={() => handleExport("word")}>Word (.docx)</DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleExport("pdf")}>PDF</DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleExport("pptx")}>PPTX</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setAgentOpen(!agentOpen)}
              className="gap-1"
            >
              {agentOpen ? (
                <PanelRightClose className="h-3.5 w-3.5" />
              ) : (
                <PanelRightOpen className="h-3.5 w-3.5" />
              )}
              AI助手
            </Button>
          </div>
        </div>

        {/* Document Content */}
        <div className="flex-1 overflow-y-auto bg-white">
          <div className="max-w-3xl mx-auto px-8 py-6">
            {proposal.sections.map((section) => (
              <div key={section.id} className="mb-4">
                <div
                  className="flex items-center gap-2 cursor-pointer group"
                  onClick={() => toggleSection(section.id)}
                >
                  {expandedSections.includes(section.id) ? (
                    <ChevronDown className="h-4 w-4 text-gray-400" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-gray-400" />
                  )}
                  <h3 className="text-base font-semibold text-[#1A1A2E] flex-1">
                    {section.order}. {section.title}
                  </h3>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button
                        className="outline-none"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Badge
                          variant="outline"
                          className={`text-xs cursor-pointer hover:opacity-80 transition-opacity ${statusColor(section.status)}`}
                        >
                          {statusLabel(section.status)}
                        </Badge>
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={() => handleSectionStatus(section.order, "approved")}
                        className="gap-2 text-green-600"
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" /> 通过审核
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => handleSectionStatus(section.order, "review")}
                        className="gap-2 text-amber-600"
                      >
                        <CircleDot className="h-3.5 w-3.5" /> 标记审核中
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => handleSectionStatus(section.order, "draft")}
                        className="gap-2 text-gray-500"
                      >
                        <RotateCcw className="h-3.5 w-3.5" /> 退回草稿
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                  {editingSection !== section.id && expandedSections.includes(section.id) && (
                    <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0"
                        onClick={(e) => {
                          e.stopPropagation();
                          startEdit(section.id, section.content);
                        }}
                      >
                        <Edit3 className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Wand2 className="h-3.5 w-3.5 text-[#00D4FF]" />
                      </Button>
                    </div>
                  )}
                </div>

                {expandedSections.includes(section.id) && (
                  <div className="mt-3 ml-6">
                    {editingSection === section.id ? (
                      <div className="space-y-2">
                        <Textarea
                          value={editContent}
                          onChange={(e) => setEditContent(e.target.value)}
                          rows={10}
                          className="text-sm leading-relaxed"
                        />
                        <div className="flex gap-2">
                          <Button size="sm" onClick={saveEdit} className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-1">
                            <Save className="h-3 w-3" /> 保存
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => setEditingSection(null)}>
                            取消
                          </Button>
                          <Button size="sm" variant="outline" className="gap-1 text-[#00D4FF]">
                            <Sparkles className="h-3 w-3" /> AI优化
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap bg-gray-50/50 rounded-lg p-4 border border-gray-100">
                        {section.content}
                      </div>
                    )}
                  </div>
                )}
                <Separator className="mt-4" />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Agent Panel */}
      <AgentPanel isOpen={agentOpen} onClose={() => setAgentOpen(false)} />
    </div>
  );
}
