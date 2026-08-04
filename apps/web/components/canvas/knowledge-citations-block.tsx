"use client";

import Link from "next/link";
import { BookOpen, ExternalLink, FileText } from "lucide-react";

export interface KnowledgeCitation {
  index?: number;
  source_type?: string;
  title?: string;
  document_id?: string;
  chunk_id?: string;
  case_id?: string;
  location?: string | null;
  snippet?: string;
  score?: number | null;
  scenario?: string;
}

export interface WebSource {
  title?: string;
  url?: string;
  snippet?: string;
}

export interface KnowledgeCitationsData {
  citations?: KnowledgeCitation[];
  web_sources?: WebSource[];
  kb_meta?: Record<string, unknown>;
}

export function KnowledgeCitationsBlock({ data }: { data: KnowledgeCitationsData }) {
  const citations = data.citations ?? [];
  const webSources = data.web_sources ?? [];

  if (citations.length === 0 && webSources.length === 0) {
    return null;
  }

  return (
    <div className="rounded-lg border border-outline-variant bg-surface-container-low p-3 space-y-3">
      <div className="flex items-center gap-1.5 text-[10px] text-primary font-semibold uppercase tracking-wider">
        <BookOpen className="h-3 w-3" />
        参考来源
      </div>

      {citations.length > 0 ? (
        <ul className="space-y-2">
          {citations.map((c, i) => (
            <li
              key={`kb-${c.chunk_id || c.case_id || i}`}
              className="text-xs text-on-surface-variant border-l-2 border-primary/40 pl-2"
            >
              <div className="flex items-start gap-1.5">
                <FileText className="h-3.5 w-3.5 shrink-0 mt-0.5 text-primary" />
                <div className="min-w-0">
                  <span className="font-medium text-on-surface">
                    [{c.index ?? i + 1}]{" "}
                    {c.document_id ? (
                      <Link
                        href={`/admin/assets?doc=${c.document_id}`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-primary hover:underline inline-flex items-center gap-0.5"
                      >
                        {c.title || "内部资料"}
                        <ExternalLink className="h-3 w-3 shrink-0" />
                      </Link>
                    ) : (
                      c.title || "内部资料"
                    )}
                  </span>
                  {c.location ? (
                    <span className="text-outline ml-1">({c.location})</span>
                  ) : null}
                  {c.snippet ? (
                    <p className="mt-0.5 text-outline line-clamp-2">{c.snippet}</p>
                  ) : null}
                </div>
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      {webSources.length > 0 ? (
        <div className="space-y-1.5 pt-1 border-t border-outline-variant">
          <div className="text-[10px] font-medium text-on-surface-variant">网络补充</div>
          {webSources.map((s, i) => (
            <div key={`web-${i}`} className="text-xs text-on-surface-variant flex items-start gap-1">
              <ExternalLink className="h-3 w-3 shrink-0 mt-0.5" />
              {s.url ? (
                <a
                  href={s.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-primary underline truncate"
                >
                  {s.title || s.url}
                </a>
              ) : (
                <span>{s.title || "网络来源"}</span>
              )}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
