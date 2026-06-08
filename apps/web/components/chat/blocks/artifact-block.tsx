"use client";

import { FileText, Download } from "lucide-react";

interface ArtifactBlockProps {
  data: Record<string, unknown>;
}

export function ArtifactBlock({ data }: ArtifactBlockProps) {
  const title = String(data.title || "产物文件");
  const url = data.url ? String(data.url) : null;

  return (
    <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-[#1E3A5F]" />
          <span className="text-sm text-gray-800">{title}</span>
        </div>
        {url && (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 px-2 py-1 rounded text-xs text-[#00D4FF] hover:bg-[#00D4FF]/10 transition-colors"
          >
            <Download className="h-3 w-3" />
            下载
          </a>
        )}
      </div>
    </div>
  );
}
