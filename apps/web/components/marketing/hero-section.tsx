"use client";

// HeroSection — split hero (Linear-style): left = display copy + CTAs,
// right = the REAL task-input panel (the product protagonist) with a live
// "AI 大脑调度预览" strip. The input flow is unchanged: upload asset (if any)
// → POST /projects/wizard → redirect to canvas with init_prompt.

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Loader2,
  Users,
  FileUp,
  CircleAlert,
  X,
  FileText,
  BrainCircuit,
  SearchCheck,
  PenLine,
  Palette,
  ArrowDown,
} from "lucide-react";
import { toast } from "sonner";

import { uploadAsset } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { Reveal } from "@/components/ui/reveal";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:13800";

const MAX_LEN = 1000;

function deriveProjectName(prompt: string, fileName?: string | null): string {
  const trimmed = prompt.trim();
  if (trimmed) {
    const firstLine = trimmed.split("\n")[0].trim();
    if (firstLine) return firstLine.slice(0, 40);
  }
  if (fileName) return fileName.replace(/\.[^.]+$/, "").slice(0, 40);
  return "新建任务";
}

// 调度预览 — 映射画布流水线中的真实 Agent 角色，仅作展示。
const DISPATCH_PREVIEW = [
  { Icon: SearchCheck, name: "调研专员", duty: "企业解析 · 联网检索", status: "进行中", active: true },
  { Icon: PenLine, name: "策划专家", duty: "方案生成 · 章节撰写", status: "排队中", active: false },
  { Icon: Palette, name: "视觉设计师", duty: "视觉策略 · 概念图", status: "排队中", active: false },
];

export function HeroSection() {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const canSubmit = prompt.trim().length > 0 || selectedFile !== null;

  function focusInput() {
    const el = document.getElementById("task-input");
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
    setTimeout(() => el?.focus(), 300);
  }

  async function handleStart() {
    if (!canSubmit) {
      setError("请输入企业名称、官网链接或需求描述，或上传企业资料");
      focusInput();
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
            projectType: "展厅·文旅数字化展示",
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
    <section className="relative pt-16 pb-20 lg:pt-24 lg:pb-28 overflow-hidden">
      <div className="relative z-10 max-w-container-max mx-auto px-margin-desktop">
        <div className="grid lg:grid-cols-12 gap-12 lg:gap-8 items-center">
          {/* Left — display copy */}
          <Reveal className="lg:col-span-6">
            <div className="inline-flex items-center gap-2 border border-outline-variant bg-surface-container-lowest text-on-surface-variant text-xs font-medium px-3 py-1.5 rounded-full mb-8">
              <BrainCircuit className="h-3.5 w-3.5 text-primary" />
              AI 团队平台 · 多 Agent 协作
            </div>
            <h1 className="text-4xl md:text-5xl lg:text-[56px] leading-[1.08] font-semibold text-on-background mb-6 tracking-tighter">
              组建你的 AI 团队
              <br />
              AI 大脑（CEO）统筹交付
            </h1>
            <p className="text-base md:text-lg text-on-surface-variant max-w-xl mb-10 leading-relaxed">
              把任务交给 AI 团队：AI 大脑负责拆解与调度，调研、策划、视觉等
              AI 员工基于 SOP 与企业知识并行执行，关键节点由你确认，产出全程可追溯。
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={focusInput}
                className="inline-flex items-center gap-2 bg-primary text-on-primary px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-primary-container active:scale-95 transition-all"
              >
                立即派发任务
                <ArrowDown className="h-4 w-4" />
              </button>
              <a
                href="#how-it-works"
                className="inline-flex items-center gap-2 bg-surface-container-lowest text-on-surface border border-outline-variant px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-surface-container-low transition-colors"
              >
                了解工作方式
              </a>
            </div>
          </Reveal>

          {/* Right — the product panel (real input + dispatch preview) */}
          <Reveal delay={150} className="lg:col-span-6">
            <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant p-5 md:p-6 shadow-2xl shadow-black/40">
              <textarea
                id="task-input"
                value={prompt}
                onChange={(e) => {
                  setPrompt(e.target.value.slice(0, MAX_LEN));
                  if (error) setError(null);
                }}
                className="w-full h-32 bg-surface-container-low border border-outline-variant rounded-lg p-4 text-sm leading-relaxed focus:ring-2 focus:ring-primary/60 focus:border-transparent transition-all outline-none resize-none placeholder:text-on-surface-variant/50"
                placeholder="描述你的任务，例如：为某制造企业规划企业展厅 3D 数字化展示方案…"
              />
              <div className="flex justify-between items-center mt-2 mb-4">
                <span className="text-xs text-outline">
                  资料优先 · 搜索补充 · 最小追问
                </span>
                <span className="text-xs text-outline">
                  {prompt.length} / {MAX_LEN}
                </span>
              </div>

              {/* Selected file chip */}
              {selectedFile && (
                <div className="mb-3 inline-flex items-center gap-2 bg-surface-container-low border border-outline-variant rounded-lg pl-3 pr-2 py-1.5 max-w-full">
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
                <div className="mb-3 text-sm text-error flex items-center gap-1.5">
                  <CircleAlert className="h-4 w-4 shrink-0" />
                  {error}
                </div>
              )}

              <div className="flex items-center gap-3">
                <button
                  onClick={handleStart}
                  disabled={submitting || uploading || !canSubmit}
                  className="flex-1 inline-flex items-center justify-center gap-2 bg-primary text-on-primary px-6 py-3 rounded-lg font-medium hover:bg-primary-container active:scale-[0.98] transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {submitting || uploading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Users className="h-4 w-4" />
                  )}
                  {uploading
                    ? "上传附件中…"
                    : submitting
                      ? "创建中…"
                      : "派发给 AI 团队"}
                </button>
                <label className="inline-flex items-center gap-2 bg-surface-container-lowest text-on-surface border border-outline-variant px-5 py-3 rounded-lg text-sm font-medium hover:bg-surface-container-low transition-colors cursor-pointer">
                  <FileUp className="h-4 w-4" />
                  <span className="hidden sm:inline">上传资料</span>
                  <input
                    type="file"
                    className="hidden"
                    onChange={handleFileChange}
                    accept=".pdf,.docx,.xlsx,.pptx,.txt,.md,image/*"
                  />
                </label>
              </div>

              {/* AI 大脑调度预览 — 展示派发后的团队分工 */}
              <div className="mt-5 pt-5 border-t border-outline-variant">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 text-xs font-medium text-on-surface-variant">
                    <BrainCircuit className="h-4 w-4 text-primary" />
                    AI 大脑 · CEO 自动派发
                  </div>
                  <span className="text-[10px] text-on-surface-variant bg-surface-container-low border border-outline-variant rounded-full px-2 py-0.5">
                    调度预览
                  </span>
                </div>
                <div className="space-y-1.5">
                  {DISPATCH_PREVIEW.map(
                    ({ Icon, name, duty, status, active }) => (
                      <div
                        key={name}
                        className="flex items-center gap-3 rounded-lg px-3 py-2 bg-surface-container-low border border-outline-variant"
                      >
                        <div
                          className={`w-7 h-7 rounded-md flex items-center justify-center shrink-0 ${
                            active
                              ? "bg-primary-fixed text-on-primary-fixed"
                              : "bg-surface-container-high text-on-surface-variant"
                          }`}
                        >
                          <Icon className="h-4 w-4" strokeWidth={1.75} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium text-on-surface truncate">
                            {name}
                          </p>
                          <p className="text-[11px] text-on-surface-variant truncate">
                            {duty}
                          </p>
                        </div>
                        <span
                          className={`text-[10px] rounded-full px-2 py-0.5 shrink-0 ${
                            active
                              ? "text-primary bg-primary-fixed"
                              : "text-on-surface-variant bg-surface-container-high"
                          }`}
                        >
                          {status}
                        </span>
                      </div>
                    ),
                  )}
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
