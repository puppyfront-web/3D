"use client";

import { FileIcon, ImageIcon, Download } from "lucide-react";

interface AttachmentBlockProps {
  data: Record<string, unknown>;
}

export function AttachmentBlock({ data }: AttachmentBlockProps) {
  const filename = String(data.filename || "文件");
  const fileSize = Number(data.file_size || 0);
  const isImage = Boolean(data.is_image);
  const url = data.url ? String(data.url) : null;
  const contentType = String(data.content_type || "");

  const formatSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="rounded-lg border border-gray-200 bg-white overflow-hidden max-w-xs">
      {/* Image preview */}
      {isImage && url && (
        <a href={url} target="_blank" rel="noopener noreferrer">
          <img
            src={url}
            alt={filename}
            className="w-full max-h-64 object-cover"
          />
        </a>
      )}

      {/* File info bar */}
      <div className="flex items-center gap-2 px-3 py-2">
        <div className="flex-shrink-0">
          {isImage ? (
            <ImageIcon className="h-4 w-4 text-purple-500" />
          ) : (
            <FileIcon className="h-4 w-4 text-gray-500" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-xs font-medium text-gray-800 truncate">
            {filename}
          </div>
          <div className="text-[10px] text-gray-500">
            {formatSize(fileSize)}
            {contentType && ` · ${contentType}`}
          </div>
        </div>
        {url && (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-shrink-0 p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600"
          >
            <Download className="h-3.5 w-3.5" />
          </a>
        )}
      </div>
    </div>
  );
}
