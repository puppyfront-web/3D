"use client";

// ToneCard — renders the 方案定调 (project tone) synthesised by the 方案定调
// Agent (PRD §13.4). The tone lives on the canvas's layoutConfig.tone and is
// surfaced read-only here. It gives the user an at-a-glance view of the
// project's theme / style keywords / narrative spine / UI principles so the
// three-board content stays visually coherent.
//
// Hidden entirely when no tone has been generated (e.g. a fresh V1 with no
// AI fill yet, or a read-only historical version predating the tone agent).

import { Sparkles, Palette, Compass, Layers, Activity, Target } from "lucide-react";
import type { ProjectTone } from "@/lib/canvas-store";

interface ToneCardProps {
  tone: ProjectTone | null;
  /** When true the card is collapsed to a single-line chip (e.g. the canvas
   * top overlay). When false it renders the full grid (e.g. a side drawer). */
  compact?: boolean;
}

function Keyword({ text }: { text: string }) {
  return (
    <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-primary-fixed text-primary border border-primary-fixed">
      {text}
    </span>
  );
}

export function ToneCard({ tone, compact = false }: ToneCardProps) {
  if (!tone) return null;

  const keywords = tone.styleKeywords ?? [];
  const uiPrinciples = tone.uiPrinciples ?? [];
  const infoHierarchy = tone.infoHierarchy ?? [];
  const keyModules = tone.keyModules ?? [];

  if (compact) {
    return (
      <div
        className="bg-primary-fixed text-primary border border-primary-fixed shadow-sm px-3 py-2 rounded-lg flex items-center gap-1.5 text-xs max-w-[280px]"
        title={tone.narrativeSpine}
      >
        <Sparkles className="h-3.5 w-3.5 shrink-0" />
        <span className="font-medium truncate">
          {tone.themeName || "方案定调"}
        </span>
        {keywords.length > 0 && (
          <span className="text-primary/70 truncate hidden md:inline">
            · {keywords.slice(0, 3).join(" / ")}
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="bg-surface-container-lowest rounded-xl border border-outline-variant shadow-sm overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 bg-primary-fixed text-primary">
        <Sparkles className="h-4 w-4" />
        <span className="font-semibold text-sm">方案定调</span>
        {tone.themeName && (
          <span className="text-sm text-primary/80 truncate">· {tone.themeName}</span>
        )}
      </div>

      <div className="p-4 space-y-4 text-sm">
        {keywords.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 text-xs font-medium text-on-surface-variant mb-2">
              <Palette className="h-3.5 w-3.5" />
              风格关键词
            </div>
            <div className="flex flex-wrap gap-1.5">
              {keywords.map((k, i) => (
                <Keyword key={i} text={k} />
              ))}
            </div>
          </div>
        )}

        {tone.narrativeSpine && (
          <div>
            <div className="flex items-center gap-1.5 text-xs font-medium text-on-surface-variant mb-1">
              <Compass className="h-3.5 w-3.5" />
              叙事主线
            </div>
            <p className="text-on-surface leading-relaxed">{tone.narrativeSpine}</p>
          </div>
        )}

        {tone.visualTone && (
          <div>
            <div className="flex items-center gap-1.5 text-xs font-medium text-on-surface-variant mb-1">
              <Layers className="h-3.5 w-3.5" />
              视觉基调
            </div>
            <p className="text-on-surface-variant leading-relaxed">{tone.visualTone}</p>
          </div>
        )}

        {infoHierarchy.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 text-xs font-medium text-on-surface-variant mb-1">
              <Activity className="h-3.5 w-3.5" />
              信息层级
            </div>
            <ol className="list-decimal list-inside text-on-surface-variant space-y-0.5">
              {infoHierarchy.map((h, i) => (
                <li key={i}>{h}</li>
              ))}
            </ol>
          </div>
        )}

        {keyModules.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 text-xs font-medium text-on-surface-variant mb-1">
              <Target className="h-3.5 w-3.5" />
              重点模块
            </div>
            <div className="flex flex-wrap gap-1.5">
              {keyModules.map((m, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 rounded text-xs bg-surface-container-low text-on-surface-variant border border-outline-variant"
                >
                  {m}
                </span>
              ))}
            </div>
          </div>
        )}

        {uiPrinciples.length > 0 && (
          <div className="pt-2 border-t border-outline-variant">
            <div className="flex items-center gap-1.5 text-xs font-medium text-on-surface-variant mb-1">
              <Palette className="h-3.5 w-3.5" />
              UI 设计原则
            </div>
            <ul className="space-y-0.5 text-on-surface-variant">
              {uiPrinciples.map((p, i) => (
                <li key={i} className="flex gap-1.5">
                  <span className="text-primary">·</span>
                  <span className="leading-relaxed">{p}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
