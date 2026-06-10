"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import {
  CheckCircle2,
  Clock,
  AlertTriangle,
  FileText,
  Image as ImageIcon,
  Download,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

interface StageSummaryBlockProps {
  data: Record<string, unknown>;
}

const STAGE_CONFIG: Record<string, { label: string; icon: React.ReactNode; borderColor: string; bgColor: string }> = {
  company_analysis: {
    label: "企业解析",
    icon: <FileText className="h-4 w-4" />,
    borderColor: "border-l-[#3B82F6]",
    bgColor: "bg-blue-50/40",
  },
  proposal_generation: {
    label: "策划案生成",
    icon: <FileText className="h-4 w-4" />,
    borderColor: "border-l-[#1E3A5F]",
    bgColor: "bg-[#1E3A5F]/5",
  },
  visual_generation: {
    label: "视觉方案生成",
    icon: <ImageIcon className="h-4 w-4" />,
    borderColor: "border-l-[#8B5CF6]",
    bgColor: "bg-purple-50/40",
  },
  export: {
    label: "方案导出",
    icon: <Download className="h-4 w-4" />,
    borderColor: "border-l-[#10B981]",
    bgColor: "bg-green-50/40",
  },
};

export function StageSummaryBlock({ data }: StageSummaryBlockProps) {
  const stage = String(data.stage || "");
  const status = String(data.status || "completed");
  const duration = Number(data.duration || 0);
  const metrics = (data.metrics || {}) as Record<string, unknown>;

  const config = STAGE_CONFIG[stage] || {
    label: stage,
    icon: <FileText className="h-4 w-4" />,
    borderColor: "border-l-gray-400",
    bgColor: "bg-gray-50/40",
  };

  const isFailed = status === "failed";
  const missingCount = Number(metrics.missing_count || 0);
  const sectionsCount = Number(metrics.sections_count || 0);
  const imagesCount = Number(metrics.images_count || 0);

  const [expanded, setExpanded] = useState(false);

  return (
    <Card className={`border border-gray-200 border-l-4 ${config.borderColor} overflow-hidden`}>
      <CardContent className="p-3.5">
        {/* Header row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className={`w-7 h-7 rounded-md ${config.bgColor} flex items-center justify-center text-[#1E3A5F]`}>
              {config.icon}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-[#1A1A2E]">{config.label}</span>
                {isFailed ? (
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-red-100 text-red-700 font-medium">失败</span>
                ) : (
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-green-100 text-green-700 font-medium flex items-center gap-0.5">
                    <CheckCircle2 className="h-2.5 w-2.5" /> 完成
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1 text-xs text-gray-400">
            <Clock className="h-3 w-3" />
            <span>{duration >= 60 ? `${Math.floor(duration / 60)}分${duration % 60}秒` : `${duration}秒`}</span>
          </div>
        </div>

        {/* Metrics row */}
        {(sectionsCount > 0 || imagesCount > 0 || missingCount > 0) && (
          <div className="flex items-center gap-3 mt-2.5 ml-[42px]">
            {sectionsCount > 0 && (
              <span className="text-xs text-gray-500 flex items-center gap-1">
                <FileText className="h-3 w-3" /> {sectionsCount} 个章节
              </span>
            )}
            {imagesCount > 0 && (
              <span className="text-xs text-gray-500 flex items-center gap-1">
                <ImageIcon className="h-3 w-3" /> {imagesCount} 张效果图
              </span>
            )}
            {missingCount > 0 && (
              <button
                onClick={() => setExpanded(!expanded)}
                className="text-xs text-amber-600 flex items-center gap-1 hover:text-amber-700 transition-colors cursor-pointer"
              >
                <AlertTriangle className="h-3 w-3" /> {missingCount} 项待确认
                {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              </button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
