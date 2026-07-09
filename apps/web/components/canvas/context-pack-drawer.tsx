"use client";

// ContextPackDrawer — the traceability drawer (PRD §9.3).
//
// Surfaces the structured Context Pack the orchestrator assembled for the
// current version: enterprise profile, project requirement, matched cases,
// referenced docs/chunks, SOP, web + uploaded material. Lets the user (and
// the reviewer) see EXACTLY what fed the AI generation — no black box.
//
// Reads from the canvas's layoutConfig.context_pack, which the orchestrator
// populates on every fill and the version snapshot captures.

import { X, FileSearch, Building2, Briefcase, BookOpen, FileText, GitBranch, Globe, Upload, Database, AlertCircle } from "lucide-react";
import type { ReactNode } from "react";

/** Shape mirrors the backend _build_context_pack dict (snake_case keys). */
interface ContextPack {
  enterprise_profile?: Record<string, string>;
  project_requirement?: Record<string, unknown>;
  matched_cases?: Array<{ name?: string; quote?: string }>;
  sop_checklist?: Array<{ name?: string; quote?: string }>;
  referenced_chunks?: Array<{ name?: string; quote?: string; document_id?: string }>;
  prompt_templates?: Array<{ name?: string; quote?: string }>;
  web_references?: Array<{ title?: string; url?: string; snippet?: string }>;
  uploaded_materials?: Array<{ title?: string; filename?: string; excerpt?: string; document_id?: string; category?: string }>;
  document_analyses?: Array<{ title?: string; filename?: string; category?: string; summary?: string; document_id?: string }>;
  pending_info?: string[];
  summary?: Record<string, number>;
}

interface Entry {
  name?: string;
  quote?: string;
  title?: string;
  url?: string;
  snippet?: string;
  excerpt?: string;
  filename?: string;
  document_id?: string;
  category?: string;
  summary?: string;
}

function Section({
  icon,
  title,
  count,
  children,
  emptyHint,
}: {
  icon: ReactNode;
  title: string;
  count: number;
  children: ReactNode;
  emptyHint: string;
}) {
  return (
    <section className="space-y-1.5">
      <div className="flex items-center gap-2 text-on-surface">
        <span className="text-primary">{icon}</span>
        <h3 className="text-sm font-semibold">{title}</h3>
        {count > 0 && (
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary-fixed text-primary font-medium">
            {count}
          </span>
        )}
      </div>
      {count === 0 ? (
        <p className="text-xs text-outline italic pl-6">{emptyHint}</p>
      ) : (
        <div className="pl-6 space-y-1.5">{children}</div>
      )}
    </section>
  );
}

function EntryRow({ label, sub, quote }: { label: string; sub?: string; quote?: string }) {
  return (
    <div className="text-xs rounded-md border border-outline-variant bg-surface-container p-2">
      <div className="font-medium text-on-surface truncate">{label}</div>
      {sub && <div className="text-outline truncate">{sub}</div>}
      {quote && (
        <div className="text-on-surface-variant italic line-clamp-3 mt-1">{quote}</div>
      )}
    </div>
  );
}

export function ContextPackDrawer({
  pack,
  onClose,
}: {
  pack: ContextPack | null;
  onClose: () => void;
}) {
  const cases = pack?.matched_cases ?? [];
  const sop = pack?.sop_checklist ?? [];
  const chunks = pack?.referenced_chunks ?? [];
  const templates = pack?.prompt_templates ?? [];
  const web = pack?.web_references ?? [];
  const uploads = pack?.uploaded_materials ?? [];
  const analyses = pack?.document_analyses ?? [];
  const ep = pack?.enterprise_profile ?? {};
  const pr = pack?.project_requirement ?? {};
  const pending = pack?.pending_info ?? [];

  const isEmpty =
    !pack ||
    (!Object.keys(ep).length &&
      !Object.keys(pr).length &&
      !cases.length &&
      !sop.length &&
      !chunks.length &&
      !templates.length &&
      !web.length &&
      !uploads.length &&
      !analyses.length &&
      !pending.length);

  return (
    <>
      <div className="absolute inset-0 z-30 bg-black/30" onClick={onClose} aria-hidden />
      <aside className="absolute right-0 top-0 bottom-0 w-[420px] z-40 shadow-xl border-l border-outline-variant bg-surface-container-lowest flex flex-col overflow-y-auto scrollbar-thin animate-in slide-in-from-right duration-200">
        <div className="p-4 border-b border-outline-variant flex items-center justify-between sticky top-0 bg-surface-container-lowest z-10">
          <h2 className="font-semibold text-on-surface flex items-center gap-2">
            <FileSearch className="h-4 w-4 text-primary" />
            上下文追溯
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-surface-container-high text-on-surface-variant"
            aria-label="关闭"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-4 space-y-5">
          <p className="text-xs text-on-surface-variant leading-relaxed">
            本版本生成时，AI 所依据的全部上下文资料（PRD §9.3）。每个节点详情中也可查看该节点专属引用。
          </p>

          {isEmpty ? (
            <div className="text-center py-12 text-outline text-sm">
              <Database className="h-10 w-10 mx-auto mb-3 opacity-40" />
              当前版本尚无上下文记录。
              <br />
              点击「生成新版本」后此处将展示 AI 依据的全部资料。
            </div>
          ) : (
            <>
              {/* Enterprise profile */}
              <Section
                icon={<Building2 className="h-4 w-4" />}
                title="企业画像"
                count={Object.keys(ep).length}
                emptyHint="未提取到企业信息"
              >
                <div className="text-xs rounded-md border border-outline-variant bg-surface-container p-2 space-y-0.5">
                  {Object.entries(ep).map(([k, v]) => (
                    <div key={k} className="flex gap-2">
                      <span className="text-outline shrink-0">{k}：</span>
                      <span className="text-on-surface-variant truncate">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </Section>

              {/* Project requirement (LLM-extracted: scene/goal/audience/key_asks) */}
              <Section
                icon={<Briefcase className="h-4 w-4" />}
                title="项目需求"
                count={Object.keys(pr).length}
                emptyHint="未提取到项目需求"
              >
                <div className="text-xs rounded-md border border-outline-variant bg-surface-container p-2 space-y-0.5">
                  {Object.entries(pr).map(([k, v]) => {
                    const display = Array.isArray(v)
                      ? v.join("、")
                      : String(v).slice(0, 200);
                    return (
                      <div key={k} className="flex gap-2">
                        <span className="text-outline shrink-0">{k}：</span>
                        <span className="text-on-surface-variant break-words">{display || "—"}</span>
                      </div>
                    );
                  })}
                </div>
              </Section>

              {/* Pending info (PRD §3.5 / §4.4 — 需求采集 flagged missing items) */}
              <Section
                icon={<AlertCircle className="h-4 w-4" />}
                title="待确认信息"
                count={pending.length}
                emptyHint="无待确认项"
              >
                <ul className="text-xs space-y-1 text-amber-700 bg-amber-50 border border-amber-300 rounded-md p-2">
                  {pending.map((p, i) => (
                    <li key={i} className="flex gap-1.5">
                      <span className="shrink-0">•</span>
                      <span>{p}</span>
                    </li>
                  ))}
                </ul>
              </Section>

              {/* Matched cases */}
              <Section
                icon={<BookOpen className="h-4 w-4" />}
                title="匹配案例"
                count={cases.length}
                emptyHint="未检索到同行业案例"
              >
                {cases.map((c: Entry, i: number) => (
                  <EntryRow key={i} label={c.name ?? "案例"} quote={c.quote} />
                ))}
              </Section>

              {/* Referenced chunks */}
              <Section
                icon={<FileText className="h-4 w-4" />}
                title="知识库片段"
                count={chunks.length}
                emptyHint="未检索到相关知识库片段"
              >
                {chunks.map((c: Entry, i: number) => (
                  <EntryRow
                    key={i}
                    label={c.name ?? "知识片段"}
                    sub={c.document_id}
                    quote={c.quote}
                  />
                ))}
              </Section>

              {/* SOP */}
              <Section
                icon={<GitBranch className="h-4 w-4" />}
                title="参考 SOP"
                count={sop.length}
                emptyHint="未匹配到 SOP 流程"
              >
                {sop.map((s: Entry, i: number) => (
                  <EntryRow key={i} label={s.name ?? "SOP"} quote={s.quote} />
                ))}
              </Section>

              {/* Templates */}
              <Section
                icon={<FileText className="h-4 w-4" />}
                title="方案模板"
                count={templates.length}
                emptyHint="未引用模板"
              >
                {templates.map((t: Entry, i: number) => (
                  <EntryRow key={i} label={t.name ?? "模板"} quote={t.quote} />
                ))}
              </Section>

              {/* Web references */}
              <Section
                icon={<Globe className="h-4 w-4" />}
                title="网络参考"
                count={web.length}
                emptyHint="未检索到公开网络信息"
              >
                {web.map((w: Entry, i: number) => (
                  <EntryRow
                    key={i}
                    label={w.title ?? w.url ?? "网络参考"}
                    sub={w.url}
                    quote={w.snippet}
                  />
                ))}
              </Section>

              {/* Uploaded materials */}
              <Section
                icon={<Upload className="h-4 w-4" />}
                title="上传资料"
                count={uploads.length}
                emptyHint="未上传资料"
              >
                {uploads.map((u: Entry, i: number) => (
                  <EntryRow
                    key={i}
                    label={u.title ?? u.filename ?? "资料"}
                    sub={u.filename}
                    quote={u.excerpt}
                  />
                ))}
              </Section>

              {/* Document analyses (资料解析 Agent — PRD §13.2 step 2) */}
              <Section
                icon={<FileText className="h-4 w-4" />}
                title="资料解析（自动分类）"
                count={analyses.length}
                emptyHint="尚未解析上传资料"
              >
                {analyses.map((a: Entry, i: number) => (
                  <EntryRow
                    key={i}
                    label={a.title ?? a.filename ?? "资料"}
                    sub={a.category ? `分类：${a.category}` : undefined}
                    quote={a.summary}
                  />
                ))}
              </Section>
            </>
          )}
        </div>
      </aside>
    </>
  );
}
