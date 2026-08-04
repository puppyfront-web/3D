"use client";

// HeroSection — the landing hero with the prompt input card.
// Aligns with Stitch code_home.html "Hero & Input Section".
// Preserves the existing project-creation flow (POST /projects/wizard → canvas),
// and wires the "上传资料" button to the real uploadAsset API.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Sparkles, FileUp, Info, CircleAlert, X, FileText } from "lucide-react";
import { toast } from "sonner";

import { uploadAsset } from "@/lib/api";
import { getToken } from "@/lib/auth";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const MAX_LEN = 1000;

function deriveProjectName(prompt: string, fileName?: string | null): string {
  const trimmed = prompt.trim();
  if (trimmed) {
    const firstLine = trimmed.split("\n")[0].trim();
    if (firstLine) return firstLine.slice(0, 40);
  }
  if (fileName) return fileName.replace(/\.[^.]+$/, "").slice(0, 40);
  return "知识问答";
}

export function HeroSection() {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const canSubmit = prompt.trim().length > 0 || selectedFile !== null;

  async function handleStart() {
    if (!canSubmit) {
      setError("请输入问题或需求描述，或上传相关资料");
      return;
    }
    setError(null);
    setSubmitting(true);

    // If a file is attached, upload it first to seed the project with context.
    // Failure here is non-fatal — fall back to prompt-only creation.
    let attachmentHint = prompt.trim();
    let uploadedDocId: string | null = null;
    if (selectedFile) {
      setUploading(true);
      try {
        const upRes = await uploadAsset(selectedFile);
        if (upRes.success && upRes.data) {
          uploadedDocId = (upRes.data as { id?: string }).id ?? null;
          attachmentHint = `${prompt.trim()}\n\n[附件:${selectedFile.name}]`.trim();
        } else {
          toast.warning("附件上传失败，将仅用文字创建项目");
        }
      } catch {
        toast.warning("附件上传失败，将仅用文字创建项目");
      } finally {
        setUploading(false);
      }
    }

    // Compose the initial message that the canvas conversation will auto-send
    // once the project conversation resolves. Kept in sync with the project
    // description so backend IntentDetector / ProposalAgent can pick up the
    // `[ref_doc:...]` reference for RAG.
    const refDocTag = uploadedDocId ? `\n[ref_doc:${uploadedDocId}]` : "";
    const initialMessage = attachmentHint + refDocTag;

    try {
      const token = getToken();
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const res = await fetch(`${API_BASE_URL}/api/v1/projects/wizard`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          step1: {
            projectName: deriveProjectName(attachmentHint, selectedFile?.name),
            clientName: "",
            industry: null,
            projectType: "知识库问答",
            description: initialMessage,
          },
          screen: { screenType: null },
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(
          err.detail || err.message || `创建失败 (${res.status})`,
        );
      }
      const json = await res.json();
      const projectId = json?.data?.id;
      if (!projectId) throw new Error("未返回项目 ID");
      // Carry the original prompt to the canvas; the left-rail conversation
      // panel will auto-send it as the first message.
      const target = initialMessage.trim()
        ? `/workspace/chat/${projectId}?init_prompt=${encodeURIComponent(initialMessage.trim())}`
        : `/workspace/chat/${projectId}`;
      router.push(target);
    } catch (e) {
      setError(e instanceof Error ? e.message : "创建项目失败");
    } finally {
      setSubmitting(false);
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) {
      setSelectedFile(f);
      if (error) setError(null);
    }
    // Reset input value so the same file can be re-picked after removal.
    e.target.value = "";
  }

  return (
    <section className="relative pt-16 pb-24 overflow-hidden bg-surface-bright">
      <div
        aria-hidden
        className="absolute inset-0 hero-radial opacity-60 pointer-events-none"
      />
      <div className="relative z-10 max-w-container-max mx-auto px-margin-desktop text-center">
        <h1 className="text-4xl md:text-[32px] leading-tight font-bold text-on-background mb-4 tracking-tight">
          企业知识库与方案问答助手
        </h1>
        <p className="text-base md:text-lg text-on-surface-variant max-w-2xl mx-auto mb-12 leading-relaxed">
          上传资料、自动入库检索，基于内部知识库提问并获得可追溯引用的专业回答与方案建议。
        </p>

        <div className="max-w-4xl mx-auto bg-surface-container-lowest rounded-xl shadow-xl border border-outline-variant p-6 text-left">
          <div className="relative group">
            <textarea
              value={prompt}
              onChange={(e) => {
                setPrompt(e.target.value.slice(0, MAX_LEN));
                if (error) setError(null);
              }}
              className="w-full h-40 bg-surface-container-low border border-outline-variant rounded-lg p-6 text-sm leading-relaxed focus:ring-2 focus:ring-primary focus:border-transparent transition-all outline-none resize-none placeholder:text-outline"
              placeholder="请输入问题、需求描述，或上传相关资料…"
            />
            <div className="absolute bottom-4 right-4 text-xs text-outline">
              {prompt.length} / {MAX_LEN}
            </div>
          </div>

          {/* Selected file chip */}
          {selectedFile && (
            <div className="mt-3 inline-flex items-center gap-2 bg-surface-container-low border border-outline-variant rounded-lg pl-3 pr-2 py-1.5 max-w-full">
              <FileText className="h-4 w-4 text-primary shrink-0" />
              <span className="text-xs truncate max-w-[240px]">
                {selectedFile.name}
              </span>
              <span className="text-[10px] text-outline shrink-0">
                {(selectedFile.size / 1024).toFixed(0)}KB
              </span>
              <button
                type="button"
                onClick={() => setSelectedFile(null)}
                className="p-0.5 hover:bg-surface-container-high rounded text-on-surface-variant"
                aria-label="移除附件"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          )}

          {error && (
            <div className="mt-3 text-sm text-error flex items-center gap-1.5">
              <CircleAlert className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          <div className="flex flex-col md:flex-row items-center justify-center gap-4 mt-6">
            <button
              onClick={handleStart}
              disabled={submitting || uploading || !canSubmit}
              className="w-full md:w-auto bg-primary text-on-primary px-10 py-4 rounded-lg font-medium shadow-lg shadow-primary-container/20 hover:opacity-90 active:scale-95 transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting || uploading ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <Sparkles className="h-5 w-5" />
              )}
              {uploading
                ? "上传附件中…"
                : submitting
                  ? "创建中…"
                  : "开始问答"}
            </button>
            <label className="w-full md:w-auto border-2 border-primary text-primary px-10 py-4 rounded-lg font-medium hover:bg-primary/5 active:scale-95 transition-all flex items-center justify-center gap-2 cursor-pointer">
              <FileUp className="h-5 w-5" />
              上传资料
              <input
                type="file"
                className="hidden"
                onChange={handleFileChange}
                accept=".pdf,.docx,.xlsx,.pptx,.txt,.md,image/*"
              />
            </label>
          </div>

          <p className="mt-4 text-xs text-outline flex items-center justify-center gap-1">
            <Info className="h-4 w-4" />
            支持资料优先、搜索补充、最小追问模式
          </p>
        </div>
      </div>
    </section>
  );
}
