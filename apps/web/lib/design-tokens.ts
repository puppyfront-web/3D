// Enterprise Blueprint — design system tokens & shared canvas constants.
//
// Single source of truth for the three-board colour system and node status
// mapping. Previously duplicated in components/canvas/module-node.tsx and
// components/canvas/canvas-viewport.tsx — both now import from here.
//
// Source: design/stitch/design_system.md (Stitch project 2205002937190653634)
// Palette aligned to Tailwind's default colour scale (blue/emerald/orange)
// to match the Stitch code_workspace.html section pills exactly.

import type { LucideIcon } from "lucide-react";
import { Building2, Boxes, Globe } from "lucide-react";

/** Board accent system. Each canvas board owns an accent colour + soft tints.
 *  Hex values mirror Tailwind's default scale (blue-500 / emerald-500 / orange-500)
 *  so they stay in lockstep with the bg-* / text-* tint classes below. */
export const BOARD_COLOURS: Record<
  string,
  {
    /** Hex accent — used for inline style (left stripe, dots, legends). */
    accent: string;
    /** Soft background tint class. */
    tint: string;
    /** Text colour class on the tint. */
    onTint: string;
    /** Badge tint class (used on module-node status pills). */
    pill: string;
  }
> = {
  company_intro: {
    accent: "#3b82f6", // blue-500
    tint: "bg-blue-50",
    onTint: "text-blue-700",
    pill: "bg-blue-100 text-blue-700",
  },
  product_tech_scenarios: {
    accent: "#10b981", // emerald-500
    tint: "bg-emerald-50",
    onTint: "text-emerald-700",
    pill: "bg-emerald-100 text-emerald-700",
  },
  future_social_responsibility: {
    accent: "#f97316", // orange-500
    tint: "bg-orange-50",
    onTint: "text-orange-700",
    pill: "bg-orange-100 text-orange-700",
  },
};

/** Fallback board colour when a node has no recognised groupKey. */
export const BOARD_DEFAULT = BOARD_COLOURS.company_intro;

/** Human-readable label for each canvas board groupKey. */
export const BOARD_TITLES: Record<string, string> = {
  company_intro: "企业介绍",
  product_tech_scenarios: "产品 / 技术 / 应用场景",
  future_social_responsibility: "未来 / 社会责任",
};

/** Canvas node status → label. */
export const STATUS_LABEL: Record<string, string> = {
  draft: "待填充",
  filling: "填充中",
  filled: "已填充",
  pending_review: "待确认",
};

/** Status → dot colour (hex, used inline). Kept in sync with the board palette
 *  so a "filled" node on the green board uses the same emerald as its board. */
export const STATUS_DOT: Record<string, string> = {
  draft: "#c3c6d7",
  filling: "#3b82f6", // blue-500
  filled: "#10b981", // emerald-500
  pending_review: "#f97316", // orange-500
};

export const STATUS_DEFAULT = "#c3c6d7";

/** NodeSource.sourceType → Chinese label.
 * Covers all 9 provenance categories required by PRD §4.5 / §15.1. The ninth
 * — 「待用户确认」 — marks AI-filled content the user has not yet confirmed
 * (paired with the node's pending_questions slot). */
export const SOURCE_TYPE_LABEL: Record<string, string> = {
  uploaded_file: "上传资料",
  conversation: "对话输入",
  internal_sop: "内部 SOP",
  internal_case: "内部案例",
  internal_template: "内部模板",
  internal_ui: "UI 资料",
  web_search: "网络搜索",
  ai_completed: "AI 补全",
  pending_user: "待用户确认",
};

/** Resolve a source type to its label, with a safe fallback so an unknown
 * backend value never renders as a raw english key to end users. */
export function sourceTypeLabel(sourceType?: string): string {
  if (!sourceType) return "未知来源";
  return SOURCE_TYPE_LABEL[sourceType] ?? sourceType;
}

/** Source confidence → colour class. */
export const CONFIDENCE_COLOR: Record<string, string> = {
  high: "text-emerald-600",
  medium: "text-orange-600",
  low: "text-red-700",
};

/** Source confidence → Chinese label (PRD §15.1 sources carry a confidence). */
export const CONFIDENCE_LABEL: Record<string, string> = {
  high: "高可信",
  medium: "中可信",
  low: "低可信",
};

export function confidenceLabel(c?: string): string {
  if (!c) return "";
  return CONFIDENCE_LABEL[c] ?? c;
}

/** Resolve a board colour safely (falls back to company accent). */
export function boardColour(groupKey?: string) {
  if (!groupKey) return BOARD_DEFAULT;
  return BOARD_COLOURS[groupKey] ?? BOARD_DEFAULT;
}

/** Resolve a status dot colour safely. */
export function statusDot(status?: string) {
  if (!status) return STATUS_DEFAULT;
  return STATUS_DOT[status] ?? STATUS_DEFAULT;
}

/**
 * Section-header pill styling per board — matches the Stitch
 * code_workspace.html section pills (soft tint bg + icon + numbered title).
 * Used by the canvas-store to synthesise section-header RF nodes.
 */
export const SECTION_HEADER_STYLE: Record<
  string,
  {
    index: number;
    Icon: LucideIcon;
    accent: string;
    tintClass: string;
    borderClass: string;
  }
> = {
  company_intro: {
    index: 1,
    Icon: Building2,
    accent: "#3b82f6",
    tintClass: "bg-blue-50 text-blue-700",
    borderClass: "border-blue-200",
  },
  product_tech_scenarios: {
    index: 2,
    Icon: Boxes,
    accent: "#10b981",
    tintClass: "bg-emerald-50 text-emerald-700",
    borderClass: "border-emerald-200",
  },
  future_social_responsibility: {
    index: 3,
    Icon: Globe,
    accent: "#f97316",
    tintClass: "bg-orange-50 text-orange-700",
    borderClass: "border-orange-200",
  },
};
