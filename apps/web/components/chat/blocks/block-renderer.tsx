"use client";

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

  // Proposal section - render as expandable card
  if (block.type === "proposal_section") {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <div className="text-xs font-medium text-[#1E3A5F] uppercase tracking-wide mb-2">
          策划方案
        </div>
        <pre className="text-xs text-gray-700 whitespace-pre-wrap font-sans max-h-64 overflow-y-auto">
          {JSON.stringify(block.data, null, 2)}
        </pre>
      </div>
    );
  }

  // Fallback for unknown block types
  return null;
}
