"use client";

import { useState, useRef, useCallback, KeyboardEvent } from "react";
import Image from "next/image";
import {
  Send,
  Paperclip,
  Building2,
  FileText,
  Image as ImageIconLucide,
  Download,
  X,
  Loader2,
  ImageIcon,
  FileIcon,
  Sparkles,
} from "lucide-react";

interface PendingAttachment {
  file: File;
  preview: string | null; // data URL for images
}

interface ChatInputProps {
  onSend: (message: string) => void;
  onFileUpload: (file: File, caption: string) => void;
  disabled?: boolean;
  isUploading?: boolean;
}

const skillShortcuts = [
  { label: "企业解析", icon: Building2, message: "帮我进行企业解析" },
  { label: "策划案", icon: FileText, message: "生成策划案" },
  { label: "视觉生成", icon: ImageIconLucide, message: "生成视觉方案" },
  { label: "生成概念图", icon: Sparkles, message: "帮我生成一个视觉概念图" },
  { label: "导出", icon: Download, message: "导出方案文档" },
];

const ACCEPTED_TYPES =
  "image/*,.pdf,.ppt,.pptx,.doc,.docx,.txt,.md,.zip,.rar";

function getFileIcon(file: File) {
  if (file.type.startsWith("image/")) return ImageIcon;
  return FileIcon;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ChatInput({
  onSend,
  onFileUpload,
  disabled,
  isUploading,
}: ChatInputProps) {
  const [input, setInput] = useState("");
  const [attachment, setAttachment] = useState<PendingAttachment | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = useCallback(() => {
    const trimmed = input.trim();

    // If there's an attachment, upload it with the caption
    if (attachment) {
      onFileUpload(attachment.file, trimmed);
      setAttachment(null);
      setInput("");
      if (textareaRef.current) textareaRef.current.style.height = "auto";
      return;
    }

    if (!trimmed || disabled) return;
    onSend(trimmed);
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }, [input, disabled, onSend, onFileUpload, attachment]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  const handleSkillClick = useCallback(
    (message: string) => {
      if (disabled) return;
      onSend(message);
    },
    [disabled, onSend]
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      // Create preview for images
      let preview: string | null = null;
      if (file.type.startsWith("image/")) {
        preview = URL.createObjectURL(file);
      }

      setAttachment({ file, preview });
      // Reset input so same file can be selected again
      e.target.value = "";
    },
    []
  );

  const removeAttachment = useCallback(() => {
    if (attachment?.preview) {
      URL.revokeObjectURL(attachment.preview);
    }
    setAttachment(null);
  }, [attachment]);

  // Auto-resize textarea
  const handleInput = useCallback(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = "auto";
      ta.style.height = Math.min(ta.scrollHeight, 160) + "px";
    }
  }, []);

  const canSend =
    !disabled &&
    !isUploading &&
    (input.trim().length > 0 || attachment !== null);

  return (
    <div className="shrink-0 border-t border-gray-200 bg-white">
      {/* Skill shortcuts */}
      <div className="px-4 pt-3 pb-1">
        <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
          {skillShortcuts.map((s) => {
            const Icon = s.icon;
            return (
              <button
                key={s.label}
                onClick={() => handleSkillClick(s.message)}
                disabled={disabled}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-[#1E3A5F]/5 text-[#1E3A5F] hover:bg-[#1E3A5F]/10 transition-colors whitespace-nowrap disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Icon className="h-3.5 w-3.5" />
                {s.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Attachment preview */}
      {attachment && (
        <div className="px-4 pb-2">
          <div className="inline-flex items-start gap-2 p-2 rounded-lg bg-gray-50 border border-gray-200 max-w-xs">
            {/* Thumbnail */}
            {attachment.preview ? (
              <div className="relative h-16 w-16">
                <Image
                  src={attachment.preview}
                  alt={`${attachment.file.name} 预览`}
                  fill
                  unoptimized
                  className="rounded object-cover"
                />
              </div>
            ) : (
              <div className="w-16 h-16 rounded bg-gray-200 flex items-center justify-center">
                {(() => {
                  const Icon = getFileIcon(attachment.file);
                  return <Icon className="h-6 w-6 text-gray-500" />;
                })()}
              </div>
            )}
            <div className="min-w-0 flex-1">
              <div className="text-xs font-medium text-gray-800 truncate">
                {attachment.file.name}
              </div>
              <div className="text-[10px] text-gray-500">
                {formatSize(attachment.file.size)}
              </div>
            </div>
            <button
              onClick={removeAttachment}
              className="p-1 rounded hover:bg-gray-200 text-gray-400 hover:text-gray-600"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="px-4 pb-4 pt-1">
        <div className="flex items-end gap-2 max-w-3xl mx-auto">
          {/* File upload button */}
          <button
            onClick={() => fileInputRef.current?.click()}
            className="flex-shrink-0 p-2 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            title="上传文件或图片"
            disabled={isUploading}
          >
            {isUploading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Paperclip className="h-5 w-5" />
            )}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_TYPES}
            onChange={handleFileSelect}
            className="hidden"
          />

          {/* Text input */}
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                handleInput();
              }}
              onKeyDown={handleKeyDown}
              placeholder={
                attachment ? "添加描述（可选）..." : "描述你的需求，或选择上方技能..."
              }
              rows={1}
              disabled={disabled}
              className="w-full resize-none rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:border-[#00D4FF] focus:ring-1 focus:ring-[#00D4FF]/30 disabled:opacity-50"
            />
          </div>

          {/* Send button */}
          <button
            onClick={handleSend}
            disabled={!canSend}
            className="flex-shrink-0 p-2.5 rounded-xl bg-[#1E3A5F] text-white hover:bg-[#2D5A8E] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
