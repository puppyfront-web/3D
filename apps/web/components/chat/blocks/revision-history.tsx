"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Clock } from "lucide-react";

interface RevisionEntry {
  version_label: string;
  trigger: string;
  user_instruction?: string;
  created_at: string;
  image_url?: string;
}

interface RevisionHistoryProps {
  entries: RevisionEntry[];
}

export function RevisionHistory({ entries }: RevisionHistoryProps) {
  const [expanded, setExpanded] = useState(false);

  // Only show when there are multiple entries
  if (entries.length <= 1) return null;

  return (
    <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
      {/* Toggle header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-4 py-2.5 hover:bg-gray-50 transition-colors"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-gray-500 shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-gray-500 shrink-0" />
        )}
        <Clock className="h-4 w-4 text-gray-400 shrink-0" />
        <span className="text-sm font-medium text-gray-700">
          修订历史 ({entries.length})
        </span>
      </button>

      {/* Timeline */}
      {expanded && (
        <div className="px-4 pb-4 space-y-0">
          {entries.map((entry, i) => (
            <div key={i} className="flex items-start gap-3 relative">
              {/* Timeline line */}
              <div className="flex flex-col items-center shrink-0">
                <div className={`w-2.5 h-2.5 rounded-full mt-1.5 ${
                  i === 0
                    ? "bg-[#00D4FF] ring-2 ring-[#00D4FF]/30"
                    : "bg-gray-300"
                }`} />
                {i < entries.length - 1 && (
                  <div className="w-px h-full bg-gray-200 min-h-[24px]" />
                )}
              </div>

              {/* Content */}
              <div className="pb-3 min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-800">
                    {entry.version_label}
                  </span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 uppercase">
                    {entry.trigger}
                  </span>
                </div>
                {entry.user_instruction && (
                  <div className="text-xs text-gray-500 mt-0.5 truncate">
                    {entry.user_instruction}
                  </div>
                )}
                <div className="text-[10px] text-gray-400 mt-0.5">
                  {new Date(entry.created_at).toLocaleString("zh-CN", {
                    month: "2-digit",
                    day: "2-digit",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
