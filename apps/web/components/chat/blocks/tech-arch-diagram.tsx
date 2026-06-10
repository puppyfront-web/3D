"use client";

import { useState, useCallback } from "react";
import Image from "next/image";
import { Layers, Triangle, Loader2, Download, RefreshCw } from "lucide-react";
import type { TechnologyArchitecture } from "@/types";
import { directGenerateImage } from "@/lib/api";

// ─── Shared config ────────────────────────────────────────────────

const LEVEL_ORDER = ["top", "middle", "bottom"] as const;

const LAYER_STYLES: Record<
  string,
  { color: string; bg: string; border: string; label: string; funnelBg: string; funnelAccent: string }
> = {
  top: {
    color: "text-white",
    bg: "bg-blue-700",
    border: "border-blue-700",
    label: "顶层",
    funnelBg: "bg-red-500/80",
    funnelAccent: "text-red-300",
  },
  middle: {
    color: "text-white",
    bg: "bg-blue-500",
    border: "border-blue-500",
    label: "中层",
    funnelBg: "bg-amber-500/80",
    funnelAccent: "text-amber-300",
  },
  bottom: {
    color: "text-blue-900",
    bg: "bg-blue-200",
    border: "border-blue-200",
    label: "底层",
    funnelBg: "bg-blue-600/80",
    funnelAccent: "text-blue-300",
  },
};

const DEFAULT_STYLE = {
  color: "text-gray-700",
  bg: "bg-gray-300",
  border: "border-gray-300",
  label: "层级",
  funnelBg: "bg-slate-500/80",
  funnelAccent: "text-slate-300",
};

// ─── Build image prompt from tech arch data ───────────────────────

function buildCurationPrompt(data: TechnologyArchitecture): string {
  const sorted = [...data.layers].sort(
    (a, b) =>
      LEVEL_ORDER.indexOf(a.level as typeof LEVEL_ORDER[number]) -
      LEVEL_ORDER.indexOf(b.level as typeof LEVEL_ORDER[number])
  );

  const layerDescs = sorted
    .map((l, i) => {
      const levelNames: Record<string, string> = {
        top: "top/management",
        middle: "middle/control",
        bottom: "bottom/execution",
      };
      return `Layer ${i + 1} (${levelNames[l.level] || l.level}): "${l.name}" — ${l.description}${l.metaphor ? `. Metaphor: "${l.metaphor}"` : ""}`;
    })
    .join("\n");

  return `A professional enterprise technology architecture curation analysis chart, dark navy background (#0F172A), modern tech style.

Visual structure:
- Vertical funnel/pyramid shape with ${sorted.length} horizontal layers, narrowing from bottom to top
- Each layer is a colored horizontal band with rounded corners
- Layer colors from bottom to top: deep blue, blue, amber/yellow, red
- Left side labels showing metaphors in cyan (#00D4FF)
- Right side showing key technology descriptions

Content:
${layerDescs}

${data.visual_metaphor ? `Overall theme: ${data.visual_metaphor}` : ""}

Design requirements:
- Dark gradient background (navy to dark slate)
- White text with high contrast
- Cyan accent colors for labels and highlights
- Clean, modern, professional infographic style
- "CURATION ANALYSIS" header with subtle grid/tech pattern
- Each layer clearly separated with slight gaps
- Technology terms in white, layer names in bold
- No clip art, no cartoon style, pure professional data visualization
- Aspect ratio suitable for presentation slide`;
}

// ─── Layered Architecture View ────────────────────────────────────

function LayeredView({ data }: { data: TechnologyArchitecture }) {
  const sorted = [...data.layers].sort(
    (a, b) =>
      LEVEL_ORDER.indexOf(a.level as typeof LEVEL_ORDER[number]) -
      LEVEL_ORDER.indexOf(b.level as typeof LEVEL_ORDER[number])
  );

  return (
    <div className="space-y-0">
      {data.visual_metaphor && (
        <div className="text-center mb-3">
          <span className="text-[10px] px-2.5 py-1 rounded-full bg-[#1E3A5F]/10 text-[#1E3A5F] font-medium">
            {data.visual_metaphor}
          </span>
        </div>
      )}

      <div className="space-y-1.5">
        {sorted.map((layer, i) => {
          const style = LAYER_STYLES[layer.level] || DEFAULT_STYLE;
          return (
            <div key={i} className="rounded-lg overflow-hidden border border-gray-100 shadow-sm">
              <div className={`flex items-center gap-2 px-3 py-1.5 ${style.bg}`}>
                <span className={`text-[10px] font-semibold ${style.color}`}>
                  {style.label}
                </span>
                <span className={`text-xs font-medium ${style.color}`}>
                  {layer.name}
                </span>
                {layer.metaphor && (
                  <span className={`text-[10px] ml-auto px-1.5 py-0.5 rounded border border-white/30 ${style.color}`}>
                    {layer.metaphor}
                  </span>
                )}
              </div>
              <div className="px-3 py-2 bg-white">
                <p className="text-[11px] text-gray-600 leading-relaxed">
                  {layer.description}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {data.core_technology_summary && (
        <div className="mt-2 p-2.5 rounded-lg bg-blue-50/70 border border-blue-100">
          <p className="text-[11px] text-blue-800 leading-relaxed">
            {data.core_technology_summary}
          </p>
        </div>
      )}
    </div>
  );
}

// ─── Curation Analysis View (AI-generated image) ──────────────────

function CurationView({ data }: { data: TechnologyArchitecture }) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = useCallback(async () => {
    setIsGenerating(true);
    setError(null);
    try {
      const prompt = buildCurationPrompt(data);
      const res = await directGenerateImage(prompt, {
        negative_prompt:
          "blurry, low quality, watermark, text overflow, cluttered, cartoon, clip art, childish, hand-drawn",
        width: 1024,
        height: 768,
      });
      if (res.success && res.data?.image_url) {
        setImageUrl(res.data.image_url);
      } else {
        setError(res.message || "图片生成失败");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成失败");
    } finally {
      setIsGenerating(false);
    }
  }, [data]);

  const handleDownload = useCallback(() => {
    if (!imageUrl) return;
    const a = document.createElement("a");
    a.href = imageUrl;
    a.download = `curation-analysis-${Date.now()}.png`;
    a.target = "_blank";
    a.click();
  }, [imageUrl]);

  return (
    <div className="space-y-3">
      {/* Preview: CSS-rendered funnel as reference */}
      {!imageUrl && !isGenerating && (
        <div className="rounded-lg overflow-hidden bg-[#0F172A] text-white">
          <div className="flex items-center justify-between px-4 py-2 bg-[#1E293B] border-b border-white/10">
            <div>
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] font-bold text-[#00D4FF] tracking-widest">02</span>
                <span className="text-[10px] font-medium text-white/80 tracking-wider">
                  CURATION ANALYSIS
                </span>
              </div>
              <p className="text-[10px] text-white/50 mt-0.5">策展分析 · 预览（点击下方按钮生成高清图片）</p>
            </div>
          </div>
          <FunnelPreview data={data} />
        </div>
      )}

      {/* Loading state */}
      {isGenerating && (
        <div className="rounded-lg border border-blue-200 bg-blue-50/50 p-6 flex flex-col items-center gap-3">
          <div className="relative">
            <Loader2 className="h-8 w-8 text-[#1E3A5F] animate-spin" />
            <div className="absolute inset-0 h-8 w-8 rounded-full bg-[#1E3A5F]/10 animate-ping" />
          </div>
          <div className="text-center">
            <p className="text-sm font-medium text-[#1E3A5F]">正在生成策展分析图</p>
            <p className="text-xs text-gray-500 mt-1">AI 根据技术架构数据生成专业可视化图表...</p>
          </div>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3">
          <p className="text-xs text-red-600">{error}</p>
          <button
            onClick={handleGenerate}
            className="mt-2 text-xs text-red-700 underline hover:no-underline"
          >
            重试
          </button>
        </div>
      )}

      {/* Generated image */}
      {imageUrl && (
        <div className="space-y-2">
          <div className="rounded-lg overflow-hidden border border-gray-200 shadow-sm">
            <div className="relative aspect-[4/3] w-full">
              <Image
                src={imageUrl}
                alt="策展分析图"
                fill
                unoptimized
                className="object-contain"
              />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleDownload}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-white border border-gray-200 text-xs text-gray-600 hover:bg-gray-50 transition-colors"
            >
              <Download className="h-3 w-3" />
              下载图片
            </button>
            <button
              onClick={handleGenerate}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-white border border-gray-200 text-xs text-gray-600 hover:bg-gray-50 transition-colors"
            >
              <RefreshCw className="h-3 w-3" />
              重新生成
            </button>
          </div>
        </div>
      )}

      {/* Generate button (shown when no image yet) */}
      {!imageUrl && !isGenerating && !error && (
        <button
          onClick={handleGenerate}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-[#1E3A5F] text-white text-sm font-medium hover:bg-[#2D5A8E] transition-colors"
        >
          <Triangle className="h-4 w-4" />
          生成策展分析图
        </button>
      )}
    </div>
  );
}

// ─── CSS Funnel Preview (used before AI image is generated) ───────

function FunnelPreview({ data }: { data: TechnologyArchitecture }) {
  const sorted = [...data.layers].sort(
    (a, b) =>
      LEVEL_ORDER.indexOf(a.level as typeof LEVEL_ORDER[number]) -
      LEVEL_ORDER.indexOf(b.level as typeof LEVEL_ORDER[number])
  );
  const count = sorted.length || 1;

  const funnelWidths = sorted.map((_, i) => {
    const ratio = 0.4 + (i / Math.max(count - 1, 1)) * 0.55;
    return `${Math.round(ratio * 100)}%`;
  });

  return (
    <div className="px-4 py-5">
      <div className="flex items-center gap-3">
        <div className="flex flex-col items-end gap-1.5 w-20 shrink-0">
          {sorted.map((l, i) => (
            <div
              key={i}
              className="text-[9px] font-medium text-[#00D4FF] text-right leading-tight"
              style={{
                height: `${100 / count}%`,
                display: "flex",
                alignItems: "center",
                justifyContent: "flex-end",
              }}
            >
              {l.metaphor}
            </div>
          ))}
        </div>

        <div className="flex-1 flex flex-col items-center gap-1">
          {sorted.map((layer, i) => {
            const style = LAYER_STYLES[layer.level] || DEFAULT_STYLE;
            return (
              <div
                key={i}
                className={`rounded-md ${style.funnelBg} flex items-center justify-center gap-2 transition-all`}
                style={{ width: funnelWidths[i], padding: "8px 12px" }}
              >
                <span className="text-[11px] font-bold text-white">
                  {layer.name}
                </span>
              </div>
            );
          })}
        </div>

        <div className="flex flex-col items-start gap-1.5 w-20 shrink-0">
          {sorted.map((l, i) => (
            <div
              key={i}
              className="text-[9px] text-white/50 leading-tight"
              style={{
                height: `${100 / count}%`,
                display: "flex",
                alignItems: "center",
              }}
            >
              {l.description.split(/[，,;；]/)[0] || l.description.slice(0, 15)}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────

type ViewMode = "layered" | "curation";

interface TechArchDiagramProps {
  data: TechnologyArchitecture;
}

export function TechArchDiagram({ data }: TechArchDiagramProps) {
  const [mode, setMode] = useState<ViewMode>("layered");

  if (!data.layers || data.layers.length === 0) return null;

  return (
    <div>
      {/* Section header with mode toggle */}
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-medium text-gray-500 flex items-center gap-1">
          <Layers className="h-3.5 w-3.5" /> 技术一张图
        </p>
        <div className="flex items-center bg-gray-100 rounded-md p-0.5">
          <button
            onClick={() => setMode("layered")}
            className={`flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
              mode === "layered"
                ? "bg-white text-[#1E3A5F] shadow-sm"
                : "text-gray-400 hover:text-gray-600"
            }`}
          >
            <Layers className="h-3 w-3" />
            架构图
          </button>
          <button
            onClick={() => setMode("curation")}
            className={`flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
              mode === "curation"
                ? "bg-white text-[#1E3A5F] shadow-sm"
                : "text-gray-400 hover:text-gray-600"
            }`}
          >
            <Triangle className="h-3 w-3" />
            策展分析
          </button>
        </div>
      </div>

      {/* Content */}
      {mode === "layered" ? (
        <LayeredView data={data} />
      ) : (
        <CurationView data={data} />
      )}
    </div>
  );
}
