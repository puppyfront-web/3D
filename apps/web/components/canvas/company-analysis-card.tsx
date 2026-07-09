"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChevronDown, ChevronRight, ExternalLink, Search, AlertTriangle } from "lucide-react";

/**
 * Displays the ACTUAL fetched web_search content for a company analysis —
 * source list (clickable URLs), key points, conflicts — rather than
 * guidance/suggestion text. Per AGENTS.md §3, the user wants to see what was
 * really retrieved; suggestion-style text only appears when web_search
 * genuinely failed to fetch anything (the "未联网核实" state + missing info
 * list at the bottom).
 */

// Matches the raw output dict from the backend company_analysis skill
// (snake_case, as sent in the `company_analysis_card` content block).
export interface CompanyAnalysisCardData {
  external_search?: {
    status: "ok" | "degraded" | "failed";
    provider?: string;
    degraded_reason?: string;
    key_points?: string[];
    conflicts?: string[];
    missing_info?: string[];
    recommended_usage?: string;
  };
  used_external_sources?: Array<{
    title: string;
    url: string;
    domain: string;
    snippet: string;
    published_at?: string;
    source_type?: string;
    confidence?: number;
  }>;
  missing_info?: string[];
}

interface CompanyAnalysisCardProps {
  data: CompanyAnalysisCardData;
}

const STATUS_OK = "ok";

function confidenceColor(c?: number): string {
  if (c == null) return "text-outline";
  if (c >= 0.7) return "text-emerald-600";
  if (c >= 0.4) return "text-amber-600";
  return "text-rose-600";
}

export function CompanyAnalysisCard({ data }: CompanyAnalysisCardProps) {
  const es = data.external_search;
  const sources = data.used_external_sources ?? [];
  const missing = data.missing_info ?? [];
  const [missingOpen, setMissingOpen] = useState(false);

  // Nothing to show — analysis ran but web_search produced nothing and no
  // missing info was collected. Don't render an empty card.
  if (!es && sources.length === 0 && missing.length === 0) {
    return null;
  }

  const isOk = es?.status === STATUS_OK;
  const hasFetchFailed = es && !isOk; // degraded or failed

  return (
    <Card className="mt-2">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center gap-1.5">
            <Search className="h-3.5 w-3.5 text-primary" />
            联网检索结果
          </CardTitle>
          <Badge
            variant="secondary"
            className={
              isOk
                ? "bg-emerald-100 text-emerald-800"
                : "bg-gray-100 text-gray-600"
            }
          >
            {isOk ? "已联网核实" : "未联网核实"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Fetch-failure banner — the ONLY place suggestion-style guidance
            text is allowed, and only when web genuinely failed to fetch. */}
        {hasFetchFailed && (
          <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
            <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
            <span>
              本次未能联网核实客观信息
              {es?.degraded_reason ? `（${es.degraded_reason}）` : ""}，下方未展示的字段均为未获取到。
            </span>
          </div>
        )}

        {/* Key points — actual extracted findings */}
        {es?.key_points && es.key_points.length > 0 && (
          <div>
            <div className="text-xs font-semibold text-on-surface-variant mb-1">
              关键发现
            </div>
            <ul className="space-y-1 text-xs text-on-surface">
              {es.key_points.map((kp, i) => (
                <li key={i} className="flex gap-1.5">
                  <span className="text-primary shrink-0">•</span>
                  <span>{kp}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Conflicts — when different sources disagree */}
        {es?.conflicts && es.conflicts.length > 0 && (
          <div>
            <div className="text-xs font-semibold text-amber-700 mb-1 flex items-center gap-1">
              <AlertTriangle className="h-3 w-3" />
              信息冲突（不同来源说法不一致）
            </div>
            <ul className="space-y-1 text-xs text-on-surface">
              {es.conflicts.map((c, i) => (
                <li key={i} className="flex gap-1.5">
                  <span className="text-amber-600 shrink-0">•</span>
                  <span>{c}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Source list — the actual retrieved snippets, clickable & traceable */}
        {sources.length > 0 && (
          <div>
            <div className="text-xs font-semibold text-on-surface-variant mb-1.5">
              信息来源 ({sources.length})
            </div>
            <div className="space-y-1.5">
              {sources.map((s, i) => (
                <div
                  key={i}
                  className="rounded-md border border-outline-variant bg-surface-container p-2 text-xs"
                >
                  <div className="flex items-start justify-between gap-2 mb-0.5">
                    {s.url ? (
                      <a
                        href={s.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium text-primary hover:underline flex items-center gap-1 min-w-0"
                      >
                        <span className="truncate">{s.title || "（无标题）"}</span>
                        <ExternalLink className="h-3 w-3 shrink-0" />
                      </a>
                    ) : (
                      <span className="font-medium text-on-surface truncate">
                        {s.title || "（无标题）"}
                      </span>
                    )}
                    {s.confidence != null && (
                      <span className={`text-[10px] shrink-0 ${confidenceColor(s.confidence)}`}>
                        {Math.round(s.confidence * 100)}%
                      </span>
                    )}
                  </div>
                  {(s.domain || s.published_at) && (
                    <div className="text-outline truncate mb-0.5">
                      {[s.domain, s.published_at].filter(Boolean).join(" · ")}
                    </div>
                  )}
                  {s.snippet && (
                    <div className="text-on-surface-variant italic line-clamp-3">
                      {s.snippet}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Missing info — collapsible. Only shown when something is genuinely
            unavailable. This is the suggestion-style fallback position. */}
        {missing.length > 0 && (
          <div>
            <button
              type="button"
              onClick={() => setMissingOpen((v) => !v)}
              className="flex items-center gap-1 text-xs font-semibold text-on-surface-variant hover:text-on-surface"
            >
              {missingOpen ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
              以下信息未能获取，如需要可补充 ({missing.length})
            </button>
            {missingOpen && (
              <ul className="mt-1.5 space-y-1 text-xs text-on-surface-variant pl-4">
                {missing.map((m, i) => (
                  <li key={i} className="flex gap-1.5">
                    <span className="text-outline shrink-0">•</span>
                    <span>{m}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
