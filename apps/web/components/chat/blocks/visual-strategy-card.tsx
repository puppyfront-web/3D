"use client";

import { Palette, Layout, Sparkles, Eye, BookOpen } from "lucide-react";

interface VisualStrategyCardProps {
  data: Record<string, unknown>;
  onAction?: (value: string, action: string) => void;
}

export function VisualStrategyCard({ data, onAction }: VisualStrategyCardProps) {
  const style = data.style ? String(data.style) : null;
  const colorTone = data.color_tone ? String(data.color_tone) : null;
  const composition = data.composition ? String(data.composition) : null;
  const keyElements = Array.isArray(data.key_elements)
    ? (data.key_elements as string[])
    : [];
  const focus = data.focus ? String(data.focus) : null;
  const mood = data.mood ? String(data.mood) : null;
  const notes = data.notes ? String(data.notes) : null;
  const citations = Array.isArray(data.citations)
    ? (data.citations as Record<string, unknown>[])
    : [];

  return (
    <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
      {/* Gradient header */}
      <div className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-violet-500 to-indigo-500">
        <Palette className="h-4 w-4 text-white" />
        <span className="text-sm font-medium text-white">视觉策略</span>
      </div>

      <div className="p-4 space-y-3">
        {/* Style */}
        {style && (
          <div className="flex items-start gap-2">
            <Layout className="h-4 w-4 text-violet-500 mt-0.5 shrink-0" />
            <div>
              <div className="text-xs text-gray-500">风格</div>
              <div className="text-sm text-gray-800">{style}</div>
            </div>
          </div>
        )}

        {/* Color Tone */}
        {colorTone && (
          <div className="flex items-start gap-2">
            <Palette className="h-4 w-4 text-violet-500 mt-0.5 shrink-0" />
            <div>
              <div className="text-xs text-gray-500">色调</div>
              <div className="text-sm text-gray-800">{colorTone}</div>
            </div>
          </div>
        )}

        {/* Composition */}
        {composition && (
          <div className="flex items-start gap-2">
            <Layout className="h-4 w-4 text-violet-500 mt-0.5 shrink-0" />
            <div>
              <div className="text-xs text-gray-500">构图</div>
              <div className="text-sm text-gray-800">{composition}</div>
            </div>
          </div>
        )}

        {/* Key Elements as tags */}
        {keyElements.length > 0 && (
          <div className="flex items-start gap-2">
            <Sparkles className="h-4 w-4 text-violet-500 mt-0.5 shrink-0" />
            <div>
              <div className="text-xs text-gray-500 mb-1">核心元素</div>
              <div className="flex flex-wrap gap-1.5">
                {keyElements.map((el, i) => (
                  <button
                    key={i}
                    onClick={() => onAction?.(el, "quick_reply")}
                    className="inline-block px-2 py-0.5 rounded-full text-xs font-medium
                               bg-violet-50 text-violet-700 border border-violet-200
                               hover:bg-violet-100 hover:border-violet-300 cursor-pointer
                               transition-colors"
                  >
                    {el}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Focus */}
        {focus && (
          <div className="flex items-start gap-2">
            <Eye className="h-4 w-4 text-violet-500 mt-0.5 shrink-0" />
            <div>
              <div className="text-xs text-gray-500">焦点</div>
              <div className="text-sm text-gray-800">{focus}</div>
            </div>
          </div>
        )}

        {/* Mood */}
        {mood && (
          <div className="flex items-start gap-2">
            <Sparkles className="h-4 w-4 text-violet-500 mt-0.5 shrink-0" />
            <div>
              <div className="text-xs text-gray-500">氛围</div>
              <div className="text-sm text-gray-800">{mood}</div>
            </div>
          </div>
        )}

        {/* Notes */}
        {notes && (
          <div className="flex items-start gap-2">
            <Eye className="h-4 w-4 text-violet-500 mt-0.5 shrink-0" />
            <div>
              <div className="text-xs text-gray-500">备注</div>
              <div className="text-sm text-gray-800">{notes}</div>
            </div>
          </div>
        )}

        {/* Citations count */}
        {citations.length > 0 && (
          <div className="flex items-center gap-1.5 pt-2 border-t border-gray-100">
            <BookOpen className="h-3.5 w-3.5 text-gray-400" />
            <span className="text-xs text-gray-500">
              引用 {citations.length} 条来源
            </span>
          </div>
        )}

        {/* Fallback when no known fields */}
        {!style && !colorTone && !composition && keyElements.length === 0 && !focus && !mood && !notes && (
          <div className="text-sm text-gray-500 text-center py-3">
            视觉策略正在规划中…
          </div>
        )}
      </div>
    </div>
  );
}
