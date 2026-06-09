"use client";

import { Building2, Palette, Sparkles } from "lucide-react";

interface ContextCardBlockProps {
  data: Record<string, unknown>;
}

export function ContextCardBlock({ data }: ContextCardBlockProps) {
  const companyName = data.company_name as string | undefined;
  const industry = data.industry as string | undefined;
  const visualStyle = data.visual_style as string | undefined;
  const colors = data.colors as Record<string, string> | undefined;
  const autoFilled = data.auto_filled as Record<string, string> | undefined;

  if (!companyName && !visualStyle && !autoFilled) return null;

  return (
    <div className="rounded-lg border border-blue-100 bg-gradient-to-r from-blue-50/60 to-white overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2 bg-[#1E3A5F]/5 border-b border-blue-100">
        <Sparkles className="h-3.5 w-3.5 text-blue-600" />
        <span className="text-xs font-medium text-[#1E3A5F]">已自动加载项目上下文</span>
      </div>

      <div className="p-3 space-y-2">
        {/* Company info row */}
        {companyName && (
          <div className="flex items-center gap-2 text-sm">
            <Building2 className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />
            <span className="text-gray-700">
              {companyName}
              {industry && <span className="text-gray-400 ml-1">· {industry}</span>}
            </span>
          </div>
        )}

        {/* Visual style + colors row */}
        {visualStyle && (
          <div className="flex items-center gap-2 text-sm">
            <Palette className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />
            <span className="text-gray-700">{visualStyle}</span>
            {colors && (
              <div className="flex items-center gap-1 ml-1">
                {colors.primary && (
                  <span
                    className="w-3.5 h-3.5 rounded-full border border-white shadow-sm"
                    style={{ backgroundColor: colors.primary }}
                  />
                )}
                {colors.secondary && (
                  <span
                    className="w-3.5 h-3.5 rounded-full border border-white shadow-sm"
                    style={{ backgroundColor: colors.secondary }}
                  />
                )}
                {colors.accent && (
                  <span
                    className="w-3.5 h-3.5 rounded-full border border-white shadow-sm"
                    style={{ backgroundColor: colors.accent }}
                  />
                )}
              </div>
            )}
          </div>
        )}

        {/* Auto-filled summary */}
        {autoFilled && Object.keys(autoFilled).length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {Object.entries(autoFilled).map(([key, value]) => (
              <span
                key={key}
                className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-50 text-blue-600 font-medium"
              >
                {value}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
