"use client";

import { useState } from "react";
import {
  Building2,
  RotateCcw,
  RotateCw,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  ArrowDown,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
} from "lucide-react";
import { TechArchDiagram } from "./tech-arch-diagram";

interface CompanyAnalysisBlockProps {
  data: Record<string, unknown>;
}

const SIX_VIEW_CONFIG = [
  { key: "backward_history", label: "向后看·发展历史", Icon: RotateCcw, color: "text-purple-600", bg: "bg-purple-50" },
  { key: "forward_planning", label: "向前看·发展规划", Icon: RotateCw, color: "text-blue-600", bg: "bg-blue-50" },
  { key: "left_competitors", label: "向左看·竞争对手", Icon: ArrowLeft, color: "text-orange-600", bg: "bg-orange-50" },
  { key: "right_industry", label: "向右看·行业情况", Icon: ArrowRight, color: "text-teal-600", bg: "bg-teal-50" },
  { key: "upward_policy", label: "向上看·政策背景", Icon: ArrowUp, color: "text-emerald-600", bg: "bg-emerald-50" },
  { key: "downward_niche", label: "向下看·生态位", Icon: ArrowDown, color: "text-rose-600", bg: "bg-rose-50" },
];

export function CompanyAnalysisBlock({ data }: CompanyAnalysisBlockProps) {
  const [expandedDim, setExpandedDim] = useState<string | null>(null);

  // Extract structured data from the new output format
  const analysis = (data.analysis || data) as Record<string, unknown>;
  const sixViews = (data.six_views || analysis.six_views) as Record<string, Record<string, string>> | undefined;
  const techArch = (data.technology_arch || analysis.technology_arch) as {
    layers?: { name: string; level: string; description: string; metaphor: string }[];
    core_technology_summary?: string;
    visual_metaphor?: string;
  } | undefined;
  const projBg = (data.project_background || analysis.project_background) as Record<string, { title: string; content: string }> | undefined;
  const missingInfo = (data.missing_info || analysis.missing_info) as string[] | undefined;

  // Check if we have any structured data
  const hasStructuredData = !!(sixViews || techArch || projBg);
  const hasRawData = !!(analysis.industry || analysis.brand_positioning || analysis.target_audience || analysis.visual_preferences);

  return (
    <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2.5 bg-[#1E3A5F]/5 border-b border-gray-100">
        <Building2 className="h-4 w-4 text-[#1E3A5F]" />
        <span className="text-sm font-medium text-[#1E3A5F]">企业解析报告</span>
      </div>

      <div className="p-4 space-y-4">
        {/* Six Views */}
        {sixViews && (
          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">企业六看</p>
            <div className="grid grid-cols-2 gap-2">
              {SIX_VIEW_CONFIG.map(({ key, label, Icon, color, bg }) => {
                const dimData = sixViews[key];
                if (!dimData) return null;
                const entries = Object.entries(dimData).filter(([, v]) => v);
                if (entries.length === 0) return null;
                const isExpanded = expandedDim === key;
                return (
                  <div
                    key={key}
                    className={`rounded-lg border p-2.5 cursor-pointer transition-all ${bg} border-gray-100 hover:shadow-sm`}
                    onClick={() => setExpandedDim(isExpanded ? null : key)}
                  >
                    <div className="flex items-center gap-1.5 mb-1">
                      <Icon className={`h-3.5 w-3.5 ${color}`} />
                      <span className="text-[11px] font-medium text-gray-700">{label}</span>
                      {isExpanded ? (
                        <ChevronDown className="h-3 w-3 text-gray-400 ml-auto" />
                      ) : (
                        <ChevronRight className="h-3 w-3 text-gray-400 ml-auto" />
                      )}
                    </div>
                    {isExpanded ? (
                      <div className="mt-1.5 space-y-1">
                        {entries.map(([k, v]) => (
                          <div key={k} className="text-[11px]">
                            <span className="text-gray-500">{k}:</span>{" "}
                            <span className="text-gray-700">{String(v)}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-[10px] text-gray-500 line-clamp-1 mt-0.5">
                        {entries.map(([, v]) => String(v)).join(" · ")}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Technology Architecture — dual-mode visualization */}
        {techArch && techArch.layers && techArch.layers.length > 0 && (
          <TechArchDiagram
            data={{
              layers: techArch.layers.map((l) => ({
                name: l.name,
                level: l.level as "top" | "middle" | "bottom",
                description: l.description,
                metaphor: l.metaphor,
              })),
              core_technology_summary: techArch.core_technology_summary || "",
              visual_metaphor: techArch.visual_metaphor || "",
            }}
          />
        )}

        {/* Project Background */}
        {projBg && (
          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">项目背景</p>
            <div className="space-y-1.5">
              {[
                { key: "national_policy", label: "宏观", color: "border-red-200 bg-red-50/50" },
                { key: "city_or_industry", label: "中观", color: "border-amber-200 bg-amber-50/50" },
                { key: "project_positioning", label: "微观", color: "border-emerald-200 bg-emerald-50/50" },
              ].map(({ key, label, color }) => {
                const level = projBg[key];
                if (!level) return null;
                return (
                  <div key={key} className={`rounded border p-2 ${color}`}>
                    <span className="text-[10px] font-semibold text-gray-600">{label}</span>
                    {level.title && <span className="text-[10px] text-[#1E3A5F] ml-1">— {level.title}</span>}
                    {level.content && <p className="text-[10px] text-gray-600 mt-0.5">{level.content}</p>}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Missing Info — todolist style */}
        {missingInfo && missingInfo.length > 0 && (
          <div className="rounded border border-amber-200 bg-amber-50/50 overflow-hidden">
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-100/60 border-b border-amber-200">
              <AlertTriangle className="h-3.5 w-3.5 text-amber-600 shrink-0" />
              <span className="text-[11px] font-semibold text-amber-700">待确认信息</span>
              <span className="text-[10px] text-amber-500 ml-1">{missingInfo.length} 项</span>
            </div>
            <ul className="divide-y divide-amber-100">
              {missingInfo.map((item, i) => (
                <li key={i} className="flex items-start gap-2 px-3 py-1.5">
                  <span className="mt-0.5 flex-shrink-0 h-4 w-4 rounded border-2 border-amber-400 bg-white flex items-center justify-center">
                    <span className="text-[8px] text-amber-400 font-bold">{i + 1}</span>
                  </span>
                  <span className="text-[11px] text-amber-700 leading-relaxed">{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Fallback: raw analysis fields if no structured data */}
        {!hasStructuredData && hasRawData && (
          <div className="space-y-2">
            {Object.entries(analysis).map(([key, value]) => {
              if (!value || typeof value === "object") return null;
              return (
                <div key={key} className="text-xs">
                  <span className="text-gray-500">{key}:</span>{" "}
                  <span className="text-gray-700">{String(value)}</span>
                </div>
              );
            })}
          </div>
        )}

        {/* Fallback for anything else */}
        {!hasStructuredData && !hasRawData && Object.keys(data).length > 0 && (
          <div className="text-sm text-gray-500 text-center py-3">
            企业分析报告生成中，请稍候…
          </div>
        )}
      </div>
    </div>
  );
}
