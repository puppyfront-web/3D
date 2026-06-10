"use client";

import { ClipboardCheck, CheckCircle, AlertTriangle } from "lucide-react";

interface QualityCheckCardProps {
  data: Record<string, unknown>;
}

export function QualityCheckCard({ data }: QualityCheckCardProps) {
  const items = Array.isArray(data.items)
    ? (data.items as Array<Record<string, unknown>>)
    : [];

  return (
    <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
      {/* Header with emerald gradient */}
      <div className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-emerald-500 to-teal-500">
        <ClipboardCheck className="h-4 w-4 text-white" />
        <span className="text-sm font-medium text-white">质量检查</span>
      </div>

      <div className="p-4">
        {items.length > 0 ? (
          <ul className="space-y-2">
            {items.map((item, i) => {
              const status = String(item.status || "");
              const isPass = status === "✅";
              const note = item.note ? String(item.note) : "";
              const label = item.item ? String(item.item) : "";

              return (
                <li key={i} className="flex items-start gap-2">
                  {isPass ? (
                    <CheckCircle className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
                  ) : (
                    <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
                  )}
                  <div className="min-w-0">
                    <div className={`text-sm ${isPass ? "text-gray-800" : "text-amber-700 font-medium"}`}>
                      {label || `检查项 ${i + 1}`}
                    </div>
                    {note && (
                      <div className="text-xs text-gray-500 mt-0.5">{note}</div>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        ) : (
          <div className="text-sm text-gray-500 text-center py-3">
            质量检查进行中…
          </div>
        )}
      </div>
    </div>
  );
}
