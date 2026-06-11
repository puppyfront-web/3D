"use client";

import { useState } from "react";
import type { ContentBlock } from "@/types";
import { TextBlock } from "./text-block";
import { CompanyAnalysisBlock } from "./company-analysis-block";
import { SkillProgressBlock } from "./skill-progress-block";
import { SkillExecutingBlock } from "./skill-executing-block";
import { ActionButtonsBlock } from "./action-buttons-block";
import { ArtifactBlock } from "./artifact-block";
import { VisualResultBlock } from "./visual-result-block";
import { VisualStrategyCard } from "./visual-strategy-card";
import { QualityCheckCard } from "./quality-check-card";
import { AttachmentBlock } from "./attachment-block";
import { ContextCardBlock } from "./context-card-block";
import { ParameterCardBlock } from "./parameter-card-block";
import { StageSummaryBlock } from "./stage-summary-block";
import { PlanProgressBlock } from "./plan-progress-block";
import { MarkdownRenderer } from "../markdown-renderer";
import { FileText, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";

interface BlockRendererProps {
  block: ContentBlock;
  onAction?: (value: string, action: string) => void;
}

export function BlockRenderer({ block, onAction }: BlockRendererProps) {
  // Skip text blocks that are just the message content (already rendered in bubble)
  if (block.type === "text") {
    return <TextBlock content={block.content || ""} />;
  }

  if (block.type === "company_analysis_card") {
    return <CompanyAnalysisBlock data={block.data || {}} />;
  }

  if (block.type === "skill_progress") {
    return <SkillProgressBlock data={block.data || {}} />;
  }

  if (block.type === "skill_executing") {
    return <SkillExecutingBlock data={block.data || {}} />;
  }

  if (block.type === "action_buttons") {
    return <ActionButtonsBlock data={block.data || {}} onAction={onAction} />;
  }

  if (block.type === "artifact") {
    return <ArtifactBlock data={block.data || {}} />;
  }

  if (block.type === "visual_result") {
    return <VisualResultBlock data={block.data || {}} />;
  }

  if (block.type === "attachment") {
    return <AttachmentBlock data={block.data || {}} />;
  }

  if (block.type === "visual_strategy") {
    return <VisualStrategyCard data={block.data || {}} onAction={onAction} />;
  }

  if (block.type === "quality_check") {
    return <QualityCheckCard data={block.data || {}} />;
  }

  // Context card — shows auto-loaded project context
  if (block.type === "context_card") {
    return <ContextCardBlock data={block.data || {}} />;
  }

  // Parameter card — concise field selection for visual generation
  if (block.type === "parameter_card") {
    return <ParameterCardBlock data={block.data || {}} onAction={onAction} />;
  }

  // Stage summary — compact completion card with timing + metrics
  if (block.type === "stage_summary") {
    return <StageSummaryBlock data={block.data || {}} />;
  }

  // Plan progress — dynamic execution plan visualization
  if (block.type === "plan_progress") {
    const data = (block.data || {}) as Record<string, unknown>;
    const steps = Array.isArray(data.steps) ? (data.steps as Array<{ step_id: string; name: string; status: "pending" | "running" | "completed" | "failed" | "skipped" }>) : [];
    const domain = typeof data.domain === "string" ? data.domain : undefined;
    return <PlanProgressBlock steps={steps} domain={domain} />;
  }

  // Proposal section — sections overview + missing info + collapsible full content
  if (block.type === "proposal_section") {
    const data = (block.data || {}) as Record<string, unknown>;
    const missingInfo = Array.isArray(data.missing_info) ? (data.missing_info as string[]) : [];
    const sections = Array.isArray(data.sections) ? (data.sections as Array<Record<string, unknown>>) : [];
    const fullContent = typeof data.content === "string" ? data.content : "";

    return <ProposalSectionBlock sections={sections} missingInfo={missingInfo} fullContent={fullContent} />;
  }

  // Fallback for unknown block types
  return null;
}

/** Proposal section card with collapsible full content. */
function ProposalSectionBlock({
  sections,
  missingInfo,
  fullContent,
}: {
  sections: Array<Record<string, unknown>>;
  missingInfo: string[];
  fullContent: string;
}) {
  const [showContent, setShowContent] = useState(false);

  return (
    <div className="rounded-lg border border-blue-100 bg-gradient-to-r from-blue-50/60 to-white overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 bg-[#1E3A5F]/5 border-b border-blue-100">
        <FileText className="h-4 w-4 text-[#1E3A5F]" />
        <span className="text-sm font-medium text-[#1E3A5F]">策划方案</span>
      </div>

      <div className="p-4 space-y-3">
        {/* Sections overview */}
        {sections.length > 0 && (
          <div>
            <div className="text-xs text-gray-500 mb-1.5">章节概览</div>
            <div className="space-y-1">
              {sections.map((sec, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <span className="flex-shrink-0 w-5 h-5 rounded-full bg-blue-100 text-[#1E3A5F] text-xs flex items-center justify-center font-medium">
                    {i + 1}
                  </span>
                  <span className="text-gray-700">{String(sec.title || sec.name || `章节 ${i + 1}`)}</span>
                  {typeof sec.status === "string" && sec.status && (
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                        sec.status === "approved"
                          ? "bg-green-100 text-green-700"
                          : sec.status === "review"
                            ? "bg-yellow-100 text-yellow-700"
                            : "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {sec.status}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Missing info warnings */}
        {missingInfo.length > 0 && (
          <div>
            <div className="text-xs text-gray-500 mb-1.5">待确认事项</div>
            <ul className="space-y-1">
              {missingInfo.map((item, i) => (
                <li key={i} className="flex items-start gap-1.5 text-sm text-amber-700">
                  <span className="flex-shrink-0 mt-0.5">⚠</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Collapsible full content */}
        {fullContent && (
          <div className="border-t border-blue-100 pt-3">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 text-xs text-[#1E3A5F] hover:text-[#2D5A8E] gap-1 px-2"
              onClick={() => setShowContent(!showContent)}
            >
              {showContent ? (
                <>
                  <ChevronUp className="h-3.5 w-3.5" /> 收起完整策划案
                </>
              ) : (
                <>
                  <ChevronDown className="h-3.5 w-3.5" /> 查看完整策划案
                </>
              )}
            </Button>
            {showContent && (
              <div className="mt-2 rounded-md border border-gray-200 bg-white p-4 max-h-[60vh] overflow-y-auto">
                <MarkdownRenderer content={fullContent} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
