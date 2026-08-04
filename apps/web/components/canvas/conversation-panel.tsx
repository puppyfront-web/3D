"use client";

// ConversationPanel — left sidebar of the canvas workspace (Stitch
// code_workspace.html "Left Sidebar: Chat & Assets").
//
// Layout (top → bottom):
//   - Header: 对话助教 + 清空对话
//   - Message list: AI bubbles (left, surface-container-lowest + border) and
//     user bubbles (right, primary bg). Real streaming via useProjectChat.
//   - Assets section: uploaded attachments (file rows).
//   - Composer: textarea + send + upload.
//
// Wired to the real backend: useProjectChat gives this panel its own
// project-scoped conversation (get-or-create) + SSE streaming, isolated from
// the global ChatProvider so the canvas and the standalone chat page don't
// clobber each other.

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import {
  Upload,
  Send,
  FileText,
  Loader2,
  Bot,
  User,
  Paperclip,
  BrainCircuit,
  ChevronDown,
  X,
  Target,
  RotateCw,
  Trash2,
  FolderInput,
} from "lucide-react";
import { toast } from "sonner";
import { useProjectChat } from "@/lib/use-project-chat";
import { cn } from "@/lib/utils";
import { deleteAsset, indexDocument, updateAssetCategory } from "@/lib/api";
import type { ChatMessage, ContentBlock } from "@/types";
import ReactMarkdown from "react-markdown";
import { CompanyAnalysisCard } from "@/components/canvas/company-analysis-card";
import { NodeDraftBlock, type NodeDraftData } from "@/components/canvas/node-draft-block";
import {
  CanvasFillProposalBlock,
  type CanvasFillProposalData,
} from "@/components/canvas/canvas-fill-proposal-block";
import {
  KnowledgeCitationsBlock,
  type KnowledgeCitationsData,
} from "@/components/canvas/knowledge-citations-block";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface AttachmentMeta {
  filename: string;
  file_size: number;
  is_image: boolean;
  url: string;
  // The following are populated when the backend created a Document row for
  // this attachment (parseable text types). Missing for images / archives.
  document_id?: string;
  parse_status?: string;
  category?: string;
  chunk_count?: number;
}

// PRD §11.2 attachment categories.
const ATTACHMENT_CATEGORIES = [
  "企业介绍",
  "产品资料",
  "技术资料",
  "荣誉资质",
  "案例资料",
  "发展历程",
  "社会责任",
  "参考案例",
  "其他资料",
] as const;

// Mirrors _CHAT_ALLOWED_EXTENSIONS in the conversations router.
const UPLOAD_ACCEPT =
  ".pdf,.pptx,.docx,.xlsx,.xls,.csv,.txt,.md,.png,.jpg,.jpeg,.gif,.webp,.svg,.mp4,.mov,.avi,.zip,.rar";

const PARSE_STATUS_META: Record<
  string,
  { label: string; className: string }
> = {
  uploaded: { label: "待解析", className: "text-outline bg-surface-container" },
  parsing: { label: "解析中", className: "text-primary bg-primary-fixed" },
  parsed: { label: "已解析", className: "text-primary-container bg-primary/15" },
  parse_failed: { label: "解析失败", className: "text-error bg-error-container/40" },
  classified: { label: "已归类", className: "text-tertiary-container bg-tertiary/15" },
  pending_confirm: { label: "待确认", className: "text-secondary bg-secondary-container/40" },
  indexed: { label: "已解析", className: "text-primary-container bg-primary/15" },
  error: { label: "解析失败", className: "text-error bg-error-container/40" },
};

function fmtTime(ts: string) {
  return new Date(ts).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtSize(bytes: number) {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)}KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
}

/** Extract attachment metadata from a user message's rich_content blocks. */
function extractAttachments(msg: {
  richContent?: { blocks?: Array<{ type: string; data?: Record<string, unknown> }> };
}): AttachmentMeta[] {
  const blocks = msg.richContent?.blocks ?? [];
  return blocks
    .filter((b) => b.type === "attachment" && b.data)
    .map((b) => b.data as unknown as AttachmentMeta);
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item)).filter(Boolean);
}

function renderContentBlock(
  block: ContentBlock,
  key: string,
  ctx?: {
    projectId?: string;
    activeNodeId?: string | null;
    onNodeAdopted?: () => void;
    onCanvasAccepted?: () => void;
  },
) {
  const data = block.data ?? {};
  if (block.type === "skill_executing") {
    return (
      <div key={key} className="rounded-lg border border-outline-variant bg-surface px-3 py-2 text-xs text-on-surface-variant">
        正在执行技能：{String(data.name ?? data.skill_id ?? "未知技能")}
      </div>
    );
  }

  if (block.type === "visual_result") {
    const imageUrl = typeof data.image_url === "string" ? data.image_url : "";
    const prompt = typeof data.prompt === "string" ? data.prompt : "";
    return (
      <div key={key} className="rounded-lg border border-outline-variant bg-surface p-2 space-y-2">
        {imageUrl ? (
          <Image
            src={imageUrl}
            alt="生成结果"
            width={1200}
            height={675}
            unoptimized
            className="w-full h-auto rounded-md border border-outline-variant object-cover"
          />
        ) : null}
        {prompt ? (
          <p className="text-xs text-on-surface-variant whitespace-pre-wrap">{prompt}</p>
        ) : null}
      </div>
    );
  }

  if (block.type === "company_analysis_card") {
    return <CompanyAnalysisCard key={key} data={data} />;
  }

  if (block.type === "artifact") {
    const title = typeof data.title === "string" ? data.title : "结构化产物";
    const summary = typeof data.summary === "string" ? data.summary : "";
    const missing = asStringList(data.missing_info);
    return (
      <div key={key} className="rounded-lg border border-outline-variant bg-surface p-3 space-y-2">
        <div className="text-xs font-semibold text-on-surface">{title}</div>
        {summary ? <p className="text-xs text-on-surface-variant whitespace-pre-wrap">{summary}</p> : null}
        {missing.length > 0 ? (
          <ul className="text-xs text-tertiary space-y-1">
            {missing.map((item, index) => (
              <li key={`${key}-missing-${index}`}>⚠️ {item}</li>
            ))}
          </ul>
        ) : null}
      </div>
    );
  }

  if (block.type === "plan_progress") {
    const steps = Array.isArray(data.steps) ? data.steps : [];
    return (
      <div key={key} className="rounded-lg border border-outline-variant bg-surface p-3">
        <div className="text-xs font-semibold text-on-surface mb-2">执行进度</div>
        <ul className="space-y-1 text-xs text-on-surface-variant">
          {steps.map((step, index) => {
            const label =
              step && typeof step === "object" && "label" in step
                ? String((step as Record<string, unknown>).label)
                : String(step);
            return <li key={`${key}-step-${index}`}>• {label}</li>;
          })}
        </ul>
      </div>
    );
  }

  if (block.type === "node_draft") {
    const draft = (block.data ?? {}) as unknown as NodeDraftData;
    if (ctx?.projectId && ctx?.activeNodeId) {
      return (
        <NodeDraftBlock
          key={key}
          projectId={ctx.projectId}
          nodeId={ctx.activeNodeId}
          data={draft}
          onAdopted={ctx.onNodeAdopted}
        />
      );
    }
    return null;
  }

  if (block.type === "canvas_fill_proposal") {
    const proposal = (block.data ?? {}) as unknown as CanvasFillProposalData;
    return (
      <CanvasFillProposalBlock
        key={key}
        data={proposal}
        projectId={ctx?.projectId}
        onAccepted={ctx?.onCanvasAccepted}
      />
    );
  }

  if (block.type === "knowledge_citations") {
    return (
      <KnowledgeCitationsBlock
        key={key}
        data={(block.data ?? {}) as KnowledgeCitationsData}
      />
    );
  }

  if (block.type === "proposal_section") {
    // proposal_generation 输出(真实形状):{ content(markdown), content_type, used_cases, … },
    // missing_info 在 SkillResult 顶层。防御性兼容 proposal_sections:[{title,content}] /
    // citations / missing_info 形状。用 ReactMarkdown + 与助手正文一致的 prose 样式渲染,
    // 让设计 Brief 可读(此前无渲染器会落到 JSON dump)。
    const content = typeof data.content === "string" ? data.content : "";
    const sections = Array.isArray(data.proposal_sections) ? data.proposal_sections : [];
    const citations = Array.isArray(data.citations) ? data.citations : [];
    const missing = asStringList(data.missing_info);
    const proseClass =
      "prose prose-sm max-w-none text-on-surface [&_h1]:text-base [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:mt-3 [&_h3]:text-sm [&_p]:my-1.5 [&_ul]:my-1.5 [&_li]:my-0 [&_a]:text-primary [&_a]:underline [&_strong]:text-on-surface [&_blockquote]:border-l-2 [&_blockquote]:border-outline-variant [&_blockquote]:pl-2 [&_blockquote]:text-on-surface-variant [&_blockquote]:text-xs";
    return (
      <div key={key} className="rounded-lg border border-primary/30 bg-surface p-3 space-y-2">
        <div className="flex items-center gap-1.5 text-[10px] text-primary font-semibold uppercase tracking-wider">
          <FileText className="h-3 w-3" />
          设计 Brief
        </div>
        {content ? (
          <div className={proseClass}>
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        ) : sections.length > 0 ? (
          <div className="space-y-2">
            {sections.map((sec, i) => {
              const t =
                sec && typeof sec === "object" && "title" in sec
                  ? String((sec as Record<string, unknown>).title)
                  : "";
              const c =
                sec && typeof sec === "object" && "content" in sec
                  ? String((sec as Record<string, unknown>).content)
                  : "";
              return (
                <div key={`${key}-sec-${i}`} className="space-y-0.5">
                  {t ? <div className="text-xs font-semibold text-on-surface">{t}</div> : null}
                  {c ? (
                    <div className={proseClass}>
                      <ReactMarkdown>{c}</ReactMarkdown>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-xs text-outline whitespace-pre-wrap">
            {JSON.stringify(data, null, 2)}
          </div>
        )}
        {missing.length > 0 ? (
          <ul className="text-xs text-tertiary space-y-0.5">
            {missing.map((item, i) => (
              <li key={`${key}-missing-${i}`}>⚠️ {item}</li>
            ))}
          </ul>
        ) : null}
        {citations.length > 0 ? (
          <div className="text-[10px] text-outline">
            来源：
            {citations.map((c, i) => {
              const name =
                c && typeof c === "object" && "name" in c
                  ? String((c as Record<string, unknown>).name || "")
                  : "";
              const url =
                c && typeof c === "object" && "url" in c
                  ? String((c as Record<string, unknown>).url || "")
                  : "";
              return (
                <span key={`${key}-cite-${i}`}>
                  {i > 0 ? "、" : ""}
                  {url ? (
                    <a href={url} target="_blank" rel="noreferrer" className="underline">
                      {name || url}
                    </a>
                  ) : (
                    name || "网络来源"
                  )}
                </span>
              );
            })}
          </div>
        ) : null}
      </div>
    );
  }

  const fallbackText =
    block.content ||
    (typeof data.content === "string" ? data.content : "") ||
    (typeof data.text === "string" ? data.text : "");
  return (
    <div key={key} className="rounded-lg border border-dashed border-outline-variant bg-surface px-3 py-2 text-xs text-on-surface-variant whitespace-pre-wrap">
      {fallbackText || JSON.stringify(data, null, 2)}
    </div>
  );
}

function AssistantMessage({
  message,
  ctx,
}: {
  message: ChatMessage;
  ctx?: {
    projectId?: string;
    activeNodeId?: string | null;
    onNodeAdopted?: () => void;
    onCanvasAccepted?: () => void;
  };
}) {
  const blocks = message.richContent?.blocks ?? [];
  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 rounded-lg bg-primary-fixed flex items-center justify-center shrink-0">
        <Bot className="h-4 w-4 text-primary fill" />
      </div>
      <div className="bg-surface-container-lowest p-3 rounded-xl rounded-tl-none border border-outline-variant text-sm text-on-surface shadow-sm max-w-[85%] space-y-2">
        {message.content ? (
          <div className="prose prose-sm max-w-none text-on-surface [&_h1]:text-base [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:mt-3 [&_h3]:text-sm [&_p]:my-1.5 [&_ul]:my-1.5 [&_li]:my-0 [&_a]:text-primary [&_a]:underline [&_strong]:text-on-surface [&_blockquote]:border-l-2 [&_blockquote]:border-outline-variant [&_blockquote]:pl-2 [&_blockquote]:text-on-surface-variant [&_blockquote]:text-xs">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        ) : null}
        {blocks.map((block, index) => renderContentBlock(block, `${message.id}-${index}`, ctx))}
        <span className="block text-[10px] text-outline mt-2">
          {fmtTime(message.createdAt)}
        </span>
      </div>
    </div>
  );
}

function UserMessage({ message }: { message: ChatMessage }) {
  const attachments = extractAttachments(message);
  return (
    <div className="flex gap-3 flex-row-reverse">
      <div className="w-8 h-8 rounded-lg bg-surface-variant flex items-center justify-center shrink-0">
        <User className="h-4 w-4 text-on-surface-variant" />
      </div>
      <div className="bg-primary text-on-primary p-3 rounded-xl rounded-tr-none text-sm shadow-sm max-w-[85%] space-y-2">
        {message.content ? <p className="whitespace-pre-wrap">{message.content}</p> : null}
        {attachments.length > 0 ? (
          <div className="space-y-1.5 pt-1 border-t border-on-primary/20">
            {attachments.map((a, i) => (
              <div
                key={`${message.id}-att-${i}`}
                className="flex items-center gap-2 text-xs bg-on-primary/10 rounded-md px-2 py-1.5"
              >
                {a.is_image ? (
                  <Paperclip className="h-3.5 w-3.5 shrink-0" />
                ) : (
                  <FileText className="h-3.5 w-3.5 shrink-0" />
                )}
                <span className="truncate">{a.filename}</span>
                <span className="opacity-70 shrink-0">{fmtSize(a.file_size)}</span>
              </div>
            ))}
          </div>
        ) : null}
        <span className="block text-[10px] opacity-70 mt-1 text-right">
          {fmtTime(message.createdAt)}
        </span>
      </div>
    </div>
  );
}

export function ConversationPanel({
  projectId,
  initialPrompt,
  activeNodeId,
  activeNodeTitle,
  onClearNode,
  onNodeAdopted,
  onCanvasAccepted,
  layout = "sidebar",
}: {
  projectId: string;
  initialPrompt?: string;
  /** When set, the chat is scoped to this single canvas node. */
  activeNodeId?: string | null;
  /** Display title for the active node breadcrumb. */
  activeNodeTitle?: string;
  /** Exit node-scoped chat and return to the project-global conversation. */
  onClearNode?: () => void;
  /** Called after a node draft is adopted, so the canvas can reload. */
  onNodeAdopted?: () => void;
  /** Called after a canvas-fill proposal is accepted, so the canvas reloads. */
  onCanvasAccepted?: () => void;
  /** sidebar: fixed 320px rail; page: full-width chat workspace */
  layout?: "sidebar" | "page";
}) {
  const {
    messages,
    isStreaming,
    streamingText,
    streamingThinkingText,
    streamingBlocks,
    isUploading,
    error,
    send,
    upload,
    clear,
  } = useProjectChat(projectId, initialPrompt, activeNodeId);

  const [input, setInput] = useState("");
  // Whether the live thinking panel is expanded. While the model is still
  // reasoning (no body text yet) it stays open; the moment body text starts,
  // we auto-collapse it. The user can still toggle it back open.
  const [thinkingOpen, setThinkingOpen] = useState(true);
  // Category applied to files uploaded from the composer ("" = let the backend
  // auto-classify).
  const [uploadCategory, setUploadCategory] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages / streaming.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, streamingText, streamingThinkingText, isStreaming]);

  // Auto-collapse the thinking panel once real body text starts arriving,
  // but only if it was open (don't fight a user who manually opened it).
  useEffect(() => {
    if (streamingText && thinkingOpen) setThinkingOpen(false);
  }, [streamingText, thinkingOpen]);

  // Gather all attachments across user messages (newest first).
  const attachments = messages
    .filter((m) => m.role === "user")
    .flatMap(extractAttachments)
    .reverse();

  // Local overrides for parse_status / category / removal so the tray reflects
  // the user's actions immediately without waiting for a message re-fetch.
  const [statusOverride, setStatusOverride] = useState<Record<string, string>>({});
  const [categoryOverride, setCategoryOverride] = useState<Record<string, string>>({});
  const [removedIds, setRemovedIds] = useState<Set<string>>(new Set());

  async function handleReparse(a: AttachmentMeta) {
    if (!a.document_id) return;
    setStatusOverride((s) => ({ ...s, [a.document_id!]: "parsing" }));
    const res = await indexDocument(a.document_id);
    if (res.success) {
      setStatusOverride((s) => ({ ...s, [a.document_id!]: "parsed" }));
      toast.success(`已重新解析：${a.filename}`);
    } else {
      setStatusOverride((s) => ({ ...s, [a.document_id!]: "parse_failed" }));
      toast.error(res.message ?? "重新解析失败");
    }
  }

  async function handleSetCategory(a: AttachmentMeta, category: string) {
    if (!a.document_id) return;
    const res = await updateAssetCategory(a.document_id, category);
    if (res.success) {
      setCategoryOverride((s) => ({ ...s, [a.document_id!]: category }));
      toast.success(`${a.filename} 已归类为「${category}」`);
    } else {
      toast.error(res.message ?? "归类失败");
    }
  }

  async function handleDelete(a: AttachmentMeta, idx: number) {
    // Images / archives have no Document row — only remove from the local list.
    if (!a.document_id) {
      setRemovedIds((s) => new Set(s).add(`idx-${idx}-${a.filename}`));
      toast.success(`已移除：${a.filename}`);
      return;
    }
    const res = await deleteAsset(a.document_id);
    if (res.success) {
      setRemovedIds((s) => new Set(s).add(`idx-${idx}-${a.filename}`));
      toast.success(`已删除：${a.filename}`);
    } else {
      toast.error(res.message ?? "删除失败");
    }
  }

  function handleSubmit() {
    const text = input.trim();
    if (!text || isStreaming) return;
    send(text);
    setInput("");
  }

  // Sequential rather than parallel: each upload parses + indexes server-side,
  // and the tray reads the settled status from the response.
  async function handleUpload(files: FileList) {
    for (const file of Array.from(files)) {
      await upload(file, undefined, uploadCategory || undefined);
    }
  }

  return (
    <div
      className={cn(
        "flex flex-col bg-surface-container-low h-full",
        layout === "sidebar"
          ? "w-80 shrink-0 border-r border-outline-variant"
          : "w-full max-w-4xl mx-auto border-x border-outline-variant",
      )}
    >
      {/* Header — switches between project-global chat and node-scoped chat. */}
      <div className="p-4 border-b border-outline-variant flex justify-between items-center bg-surface-container-lowest">
        {activeNodeId ? (
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 text-[10px] text-primary font-semibold uppercase tracking-wider">
              <Target className="h-3 w-3" />
              节点对话
            </div>
            <div className="flex items-center gap-1 mt-0.5 min-w-0">
              <span className="font-semibold text-on-surface truncate text-sm">
                {activeNodeTitle ?? "节点"}
              </span>
              {onClearNode && (
                <button
                  onClick={onClearNode}
                  className="p-0.5 rounded hover:bg-surface-container-high text-on-surface-variant shrink-0"
                  aria-label="退出节点对话"
                  title="退出节点对话"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          </div>
        ) : (
          <>
            <h2 className="font-semibold text-on-surface">知识问答助手</h2>
            <div className="flex items-center gap-2">
              {!activeNodeId && messages.length > 0 ? (
                <button
                  type="button"
                  onClick={() => void clear()}
                  disabled={isStreaming}
                  className="text-xs text-outline hover:text-error flex items-center gap-1 px-2 py-1 rounded hover:bg-surface-container-high disabled:opacity-50"
                  title="清空对话"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  清空
                </button>
              ) : null}
              <span className="text-xs text-outline flex items-center gap-1">
                <Bot className="h-4 w-4" />
                项目会话
              </span>
            </div>
          </>
        )}
      </div>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin"
      >
        {messages.length === 0 && !isStreaming && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-lg bg-primary-fixed flex items-center justify-center shrink-0">
              <Bot className="h-4 w-4 text-primary fill" />
            </div>
            <div className="bg-surface-container-lowest p-3 rounded-xl rounded-tl-none border border-outline-variant text-sm shadow-sm text-on-surface-variant">
              你好！我是企业知识问答助手。你可以直接提问；上传资料后我会基于内部知识库给出<strong className="text-on-surface font-medium">结论、方案建议与引用来源</strong>。
            </div>
          </div>
        )}

        {messages.map((m) =>
          m.role === "assistant" ? (
            <AssistantMessage key={m.id} message={m} ctx={{ projectId, activeNodeId, onNodeAdopted, onCanvasAccepted }} />
          ) : (
            <UserMessage key={m.id} message={m} />
          ),
        )}

        {/* Live streaming response: a collapsible thinking block followed by
            the typewriter bubble.
            - The thinking panel is ALWAYS shown while streaming, so the user
              sees a visible "thinking" state even before any token arrives.
              With no thinking text yet, it renders a pulsing "深度思考中…".
            - Once body text starts: panel auto-collapses to "已深度思考",
              still toggleable to review the trace.
            - The response bubble is only rendered once there is body text,
              avoiding an empty "正在生成…" box that feels stuck. */}
        {isStreaming && (
          <div className="flex gap-3 animate-in fade-in duration-500">
            <div className="w-8 h-8 rounded-lg bg-primary-fixed flex items-center justify-center shrink-0">
              <Bot className="h-4 w-4 text-primary fill" />
            </div>
            <div className="max-w-full space-y-2">
              {/* Thinking panel — always visible while streaming. */}
              <div
                className={cn(
                  "bg-surface-container-lowest border border-outline-variant rounded-lg p-2 text-xs shadow-sm overflow-hidden transition-all",
                  thinkingOpen && "open",
                )}
              >
                <button
                  onClick={() => setThinkingOpen((v) => !v)}
                  className="flex items-center justify-between w-full text-on-surface-variant font-medium hover:text-primary transition-colors"
                >
                  <span className="flex items-center gap-1.5">
                    <BrainCircuit className="h-3.5 w-3.5" />
                    {streamingText ? "已深度思考" : "深度思考中…"}
                    {!streamingText && (
                      <span className="inline-flex gap-0.5 ml-1">
                        <span className="w-1 h-1 rounded-full bg-primary animate-pulse" />
                        <span className="w-1 h-1 rounded-full bg-primary animate-pulse [animation-delay:150ms]" />
                        <span className="w-1 h-1 rounded-full bg-primary animate-pulse [animation-delay:300ms]" />
                      </span>
                    )}
                  </span>
                  <ChevronDown
                    className={cn(
                      "h-3.5 w-3.5 transition-transform",
                      thinkingOpen && "rotate-180",
                    )}
                  />
                </button>
                <div
                  className={cn(
                    "grid transition-all duration-300",
                    thinkingOpen
                      ? "grid-rows-[1fr] opacity-100 pt-2"
                      : "grid-rows-[0fr] opacity-0",
                  )}
                >
                  <div className="overflow-hidden text-outline italic leading-relaxed whitespace-pre-wrap break-words">
                    {streamingThinkingText || "正在分析你的需求并组织回复…"}
                    {!streamingText && (
                      <span className="typewriter-cursor text-primary" />
                    )}
                  </div>
                </div>
              </div>

              {streamingBlocks.map((block, index) =>
                renderContentBlock(block, `streaming-${index}`, { projectId, activeNodeId, onNodeAdopted, onCanvasAccepted }),
              )}

              {/* Response text with typewriter cursor — only once body starts. */}
              {streamingText && (
                <div className="bg-surface-container-lowest p-3 rounded-xl rounded-tl-none border border-outline-variant text-sm text-on-surface shadow-sm max-w-[85%]">
                  {streamingText}
                  {isStreaming && (
                    <span className="typewriter-cursor text-primary" />
                  )}
                  <span className="block text-[10px] text-outline mt-2">刚刚</span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="px-4 py-2 bg-error-container/40 border-t border-error/30 text-error text-xs">
          {error}
        </div>
      )}

      {/* Assets (PRD §11) — attachment tray with parse-status badge + actions. */}
      {attachments.filter((a, i) => !removedIds.has(`idx-${i}-${a.filename}`)).length > 0 && (
        <div className="max-h-1/3 border-t border-outline-variant flex flex-col bg-surface-container">
          <div className="p-3 flex justify-between items-center">
            <h3 className="text-xs font-semibold flex items-center gap-2 text-on-surface">
              <Paperclip className="h-3.5 w-3.5" />
              附件 ({attachments.filter((a, i) => !removedIds.has(`idx-${i}-${a.filename}`)).length})
            </h3>
          </div>
          <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-2 scrollbar-thin">
            {attachments.map((a, i) => {
              if (removedIds.has(`idx-${i}-${a.filename}`)) return null;
              const docId = a.document_id;
              const rawStatus = docId
                ? (statusOverride[docId] ?? a.parse_status ?? "uploaded")
                : null;
              const statusMeta = rawStatus
                ? PARSE_STATUS_META[rawStatus] ?? PARSE_STATUS_META.uploaded
                : null;
              const category = docId
                ? (categoryOverride[docId] ?? a.category ?? null)
                : null;
              return (
                <div
                  key={`idx-${i}-${a.filename}`}
                  className="p-2 bg-surface-container-lowest border border-outline-variant rounded-lg flex items-center justify-between"
                >
                  <div className="flex items-center gap-2 overflow-hidden min-w-0">
                    <FileText className="h-4 w-4 text-primary shrink-0" />
                    <div className="truncate min-w-0">
                      <p className="text-xs font-medium truncate text-on-surface">
                        {a.filename}
                      </p>
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-[10px] text-outline">{fmtSize(a.file_size)}</span>
                        {statusMeta && (
                          <span
                            className={cn(
                              "text-[10px] px-1.5 py-0.5 rounded-full inline-flex items-center gap-1",
                              statusMeta.className,
                            )}
                          >
                            {rawStatus === "parsing" && (
                              <Loader2 className="h-2.5 w-2.5 animate-spin" />
                            )}
                            {statusMeta.label}
                          </span>
                        )}
                        {category && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-tertiary-fixed text-tertiary-container">
                            {category}
                          </span>
                        )}
                        {a.chunk_count ? (
                          <span className="text-[10px] text-outline">
                            {a.chunk_count} 片段
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button
                        className="p-1 rounded hover:bg-surface-container-high text-outline shrink-0"
                        aria-label="附件操作"
                      >
                        <ChevronDown className="h-3.5 w-3.5" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-44">
                      {docId && (
                        <>
                          <DropdownMenuItem
                            onClick={() => handleReparse(a)}
                            disabled={rawStatus === "parsing"}
                            className="gap-2"
                          >
                            <RotateCw className="h-3.5 w-3.5" /> 重新解析
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuLabel className="text-[10px] text-outline">
                            <FolderInput className="h-3 w-3 inline mr-1" />
                            分类
                          </DropdownMenuLabel>
                          {ATTACHMENT_CATEGORIES.map((cat) => (
                            <DropdownMenuItem
                              key={cat}
                              onClick={() => handleSetCategory(a, cat)}
                              className={cn("gap-2", category === cat && "font-semibold text-primary")}
                            >
                              {cat}
                            </DropdownMenuItem>
                          ))}
                          <DropdownMenuSeparator />
                        </>
                      )}
                      <DropdownMenuItem
                        onClick={() => handleDelete(a, i)}
                        className="gap-2 text-error focus:text-error"
                      >
                        <Trash2 className="h-3.5 w-3.5" /> 删除
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Composer */}
      <div className="p-4 bg-surface-container-lowest border-t border-outline-variant">
        <div className="relative">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
            placeholder="输入问题，例如：公司有哪些核心产品？"
            className="w-full h-24 p-3 pr-12 border border-outline-variant rounded-xl resize-none text-sm focus:ring-2 focus:ring-primary focus:border-transparent outline-none placeholder:text-outline bg-surface-container-low"
          />
          <button
            onClick={handleSubmit}
            disabled={!input.trim() || isStreaming}
            className={cn(
              "absolute bottom-3 right-3 p-2 rounded-lg shadow-md transition-all flex items-center justify-center",
              input.trim() && !isStreaming
                ? "bg-primary text-on-primary hover:opacity-90"
                : "bg-surface-container-high text-outline cursor-not-allowed",
            )}
            aria-label="发送"
          >
            {isStreaming ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </div>
        <div className="flex gap-2 mt-2">
          <label
            className={cn(
              "flex-1 flex items-center justify-center gap-1 text-xs border border-outline-variant text-on-surface-variant px-3 py-1.5 rounded-lg hover:bg-surface-container-low",
              isUploading ? "cursor-wait opacity-70" : "cursor-pointer",
            )}
          >
            {isUploading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Upload className="h-3.5 w-3.5" />
            )}
            {isUploading ? "上传并入库中…" : "上传资料"}
            <input
              type="file"
              multiple
              disabled={isUploading}
              accept={UPLOAD_ACCEPT}
              className="hidden"
              onChange={(e) => {
                const files = e.target.files;
                if (files?.length) void handleUpload(files);
                e.target.value = "";
              }}
            />
          </label>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="text-xs border border-outline-variant text-on-surface-variant px-3 py-1.5 rounded-lg hover:bg-surface-container-low flex items-center gap-1"
                title="设置上传资料的分类"
              >
                <FolderInput className="h-3.5 w-3.5" />
                {uploadCategory || "自动分类"}
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-44">
              <DropdownMenuLabel className="text-[10px] text-outline">
                上传时归类
              </DropdownMenuLabel>
              <DropdownMenuItem onClick={() => setUploadCategory("")}>
                自动分类
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              {ATTACHMENT_CATEGORIES.map((cat) => (
                <DropdownMenuItem
                  key={`upload-${cat}`}
                  onClick={() => setUploadCategory(cat)}
                  className={cn(uploadCategory === cat && "font-semibold text-primary")}
                >
                  {cat}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <p className="text-[10px] text-outline mt-1.5">
          上传的资料会自动解析入库并绑定当前项目，可在「知识库资料管理」统一维护。
        </p>
      </div>
    </div>
  );
}
