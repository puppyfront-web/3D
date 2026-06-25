"use client";

import { useEffect, useState } from "react";
import { ChevronDown, Sparkles } from "lucide-react";
import { MarkdownRenderer } from "@/components/chat/markdown-renderer";

interface ThinkingPanelProps {
  /** Accumulated reasoning text (grows while the model thinks). */
  text: string;
  /**
   * Whether the surrounding stream is still producing thinking tokens.
   * - true  → panel expanded, shows a pulsing "思考中" header
   * - false → panel auto-collapses, shows "已深度思考" (click to re-expand)
   */
  isThinking: boolean;
  /** Whether any visible content has started arriving (auto-collapse trigger). */
  hasContent: boolean;
}

/**
 * Claude-style collapsible reasoning panel.
 *
 * Behavior:
 * - While `isThinking` and no content yet → expanded, live-streaming.
 * - The moment `hasContent` becomes true (first content token) → auto-collapse.
 * - After collapse the user can click to re-expand and read the full reasoning.
 */
export function ThinkingPanel({ text, isThinking, hasContent }: ThinkingPanelProps) {
  // Auto-collapse once visible content starts. Stay collapsed unless the user
  // explicitly toggles. `userToggled` remembers an explicit choice so the
  // auto-collapse doesn't fight a user who re-opened it.
  const [collapsed, setCollapsed] = useState(false);
  const [userToggled, setUserToggled] = useState(false);

  useEffect(() => {
    if (hasContent && !userToggled) {
      setCollapsed(true);
    }
  }, [hasContent, userToggled]);

  // Reset state when a new thinking session begins (text emptied then refilled)
  useEffect(() => {
    if (!text) {
      setCollapsed(false);
      setUserToggled(false);
    }
  }, [!text]);

  if (!text?.trim()) return null;

  const toggle = () => {
    setUserToggled(true);
    setCollapsed((c) => !c);
  };

  const thinking = isThinking && !hasContent;

  return (
    <div className="mb-2 rounded-xl border border-slate-200 bg-slate-50/80 overflow-hidden">
      <button
        type="button"
        onClick={toggle}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-slate-100/70 transition-colors"
      >
        <Sparkles
          className={`h-3.5 w-3.5 ${thinking ? "text-cyan-500 animate-pulse" : "text-slate-400"}`}
        />
        <span className={`text-xs font-medium ${thinking ? "text-cyan-600" : "text-slate-500"}`}>
          {thinking ? "思考中…" : "已深度思考"}
        </span>
        <span className="text-[11px] text-slate-400 ml-1">
          {thinking ? "" : "点击查看推理过程"}
        </span>
        <ChevronDown
          className={`h-3.5 w-3.5 ml-auto text-slate-400 transition-transform ${collapsed ? "" : "rotate-180"}`}
        />
      </button>
      {!collapsed && (
        <div className="px-3 pb-3 pt-1 text-[13px] leading-relaxed text-slate-600 border-t border-slate-200/70">
          <div className={thinking ? "prose prose-sm max-w-none prose-slate" : "prose prose-sm max-w-none prose-slate opacity-80"}>
            <MarkdownRenderer content={text} />
          </div>
        </div>
      )}
    </div>
  );
}
