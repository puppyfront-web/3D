"use client";

// Canvas workspace — the three-column infinite-canvas workbench (PRD §9),
// aligned with Stitch code_workspace_typewriter.html.
//
// Layout (the global TopNav is rendered by the workspace layout):
//   ┌──────────────────────────────────────────────────────────────────┐
//   │ 顶栏（workspace/layout.tsx 渲染的 TopNav）                          │
//   ├────────────┬──────────────────────────────┬──────────────────────┤
//   │ 左 320px    │      中：React Flow 画布       │  右 320px            │
//   │ 对话助教+附件 │      三大板块拓扑            │  版本管理（常驻）      │
//   │             │  顶部浮层：项目名 · 缩放       │                      │
//   │             │  底部浮层：保存 · 导出 · 生成   │                      │
//   └────────────┴──────────────────────────────┴──────────────────────┘
//
// On first mount: loads the current canvas. If the project has no version
// yet, creates V1 (which lays out the default 20-node topology).

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { Loader2, Save, Sparkles, Download, Palette, History, Target, X, FileText, FileType, LayoutGrid, FileSearch } from "lucide-react";
import { toPng } from "html-to-image";
import { toast } from "sonner";

import { useCanvasStore } from "@/lib/canvas-store";
import type { ProjectTone } from "@/lib/canvas-store";
import {
  addNode,
  createVersion,
  exportVersionDoc,
  getAgentRun,
  getCurrentCanvas,
  getVersionCanvas,
  listVersions,
  triggerAgentRun,
} from "@/lib/canvas-api";
import { getProjectById } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { ProjectVersion, CanvasGroup } from "@/types/canvas";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CanvasViewport } from "@/components/canvas/canvas-viewport";
import { ConversationPanel } from "@/components/canvas/conversation-panel";
import { NodeDetailDrawer } from "@/components/canvas/node-detail-drawer";
import { VersionPanel } from "@/components/canvas/version-panel";
import { VisualDrawer } from "@/components/canvas/visual-drawer";
import { ToneCard } from "@/components/canvas/tone-card";
import { ContextPackDrawer } from "@/components/canvas/context-pack-drawer";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

// 方案定调 is stored on the canvas's layoutConfig.tone in snake_case (raw JSON
// dict, not alias-converted). Map it to the camelCase ProjectTone the UI uses.
function extractTone(layoutConfig: unknown): ProjectTone | null {
  if (!layoutConfig || typeof layoutConfig !== "object") return null;
  const raw = (layoutConfig as Record<string, unknown>).tone;
  if (!raw || typeof raw !== "object") return null;
  const t = raw as Record<string, unknown>;
  const asList = (v: unknown): string[] =>
    Array.isArray(v) ? v.map((x) => String(x)).filter(Boolean) : [];
  const tone: ProjectTone = {};
  if (typeof t.theme_name === "string") tone.themeName = t.theme_name;
  if (typeof t.narrative_spine === "string") tone.narrativeSpine = t.narrative_spine;
  if (typeof t.visual_tone === "string") tone.visualTone = t.visual_tone;
  if (typeof t.presentation_rhythm === "string")
    tone.presentationRhythm = t.presentation_rhythm;
  if (t.style_keywords) tone.styleKeywords = asList(t.style_keywords);
  if (t.info_hierarchy) tone.infoHierarchy = asList(t.info_hierarchy);
  if (t.key_modules) tone.keyModules = asList(t.key_modules);
  if (t.ui_principles) tone.uiPrinciples = asList(t.ui_principles);
  return tone.themeName || tone.styleKeywords?.length ? tone : null;
}

export default function CanvasWorkspacePage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center h-full bg-surface">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      }
    >
      <CanvasWorkspaceInner />
    </Suspense>
  );
}

function CanvasWorkspaceInner() {
  const params = useParams();
  const projectId = params.projectId as string;
  // Initial prompt carried from the landing hero — when present, the left-rail
  // conversation auto-sends it as the first message once the project
  // conversation resolves. Read once on mount; subsequent navigation within
  // the canvas (e.g. switching versions) must NOT re-send it.
  const searchParams = useSearchParams();
  const initialPrompt = searchParams.get("init_prompt") ?? "";

  const hydrate = useCanvasStore((s) => s.hydrate);
  const reset = useCanvasStore((s) => s.reset);
  const currentVersionId = useCanvasStore((s) => s.currentVersionId);
  const isReadOnly = useCanvasStore((s) => s.isReadOnly);
  // Node-scope conversation state. selectedNodeId opens the detail drawer;
  // conversationNodeId binds the left-rail chat to a single node. Clicking a
  // node sets both, and the user can exit the node chat independently (clears
  // conversationNodeId only, leaves the drawer open).
  const selectedNodeId = useCanvasStore((s) => s.selectedNodeId);
  const conversationNodeId = useCanvasStore((s) => s.conversationNodeId);
  const setConversationNode = useCanvasStore((s) => s.setConversationNode);
  const canvasNodes = useCanvasStore((s) => s.canvasNodes);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [projectName, setProjectName] = useState("");
  const [versions, setVersions] = useState<ProjectVersion[]>([]);
  const [visualOpen, setVisualOpen] = useState(false);
  const [versionOpen, setVersionOpen] = useState(false);
  const [toneOpen, setToneOpen] = useState(false);
  const [addNodeOpen, setAddNodeOpen] = useState(false);
  const [addingNode, setAddingNode] = useState(false);
  const [contextPackOpen, setContextPackOpen] = useState(false);
  // Context pack (PRD §9.3) — pulled from canvas.layoutConfig.context_pack
  // on every load so the traceability drawer stays in sync with the version.
  const [contextPack, setContextPack] = useState<Record<string, unknown> | null>(null);
  const [saving, setSaving] = useState(false);
  const [aiFilling, setAiFilling] = useState(false);
  const [aiFillStatus, setAiFillStatus] = useState<string>("");
  const lastAutoScopedNodeIdRef = useRef<string | null>(null);

  const tone = useCanvasStore((s) => s.tone);
  const canvasGroups = useCanvasStore((s) => s.groups);

  // Display title for the active node breadcrumb.
  const activeNodeTitle = useMemo(() => {
    if (!conversationNodeId) return undefined;
    const n = canvasNodes.find((x) => x.id === conversationNodeId);
    return n?.title;
  }, [conversationNodeId, canvasNodes]);

  // When the user selects a node on the canvas, scope the chat to it exactly
  // once for that selection. If the user explicitly exits node chat, keep the
  // drawer selection but do not auto-bind the chat back to the same node.
  useEffect(() => {
    if (!selectedNodeId) {
      lastAutoScopedNodeIdRef.current = null;
      return;
    }
    if (
      selectedNodeId !== lastAutoScopedNodeIdRef.current &&
      selectedNodeId !== conversationNodeId
    ) {
      lastAutoScopedNodeIdRef.current = selectedNodeId;
      setConversationNode(selectedNodeId);
    }
  }, [selectedNodeId, conversationNodeId, setConversationNode]);

  // Switching to a read-only historical version ends any node-scoped chat —
  // historical nodes are immutable, so editing suggestions make no sense.
  useEffect(() => {
    if (isReadOnly && conversationNodeId) setConversationNode(null);
  }, [isReadOnly, conversationNodeId, setConversationNode]);

  const loadCurrent = useCallback(async (opts?: { keepSelection?: boolean }) => {
    setLoading(true);
    setError(null);
    // 1. ensure versions exist; create V1 if none.
    let vlist = (await listVersions(projectId).then((r) => r.data)) ?? [];
    if (vlist.length === 0) {
      const created = await createVersion(projectId);
      if (!created.success) {
        setError(created.message ?? "创建初始版本失败");
        setLoading(false);
        return;
      }
      vlist = (await listVersions(projectId).then((r) => r.data)) ?? [];
    }
    setVersions(vlist);

    const current = vlist.find((v) => v.isCurrent) ?? vlist[0];
    if (!current) {
      setError("未找到任何版本");
      setLoading(false);
      return;
    }
    setProjectName(`项目 #${projectId.slice(0, 8)}`);
    // Resolve a human-readable name from the project record (falls back to the
    // short-id placeholder above if the fetch fails). PRD §9.4 wants the real
    // project / enterprise name in the toolbar, not a raw uuid.
    getProjectById(projectId)
      .then((res) => {
        if (res.success && res.data) {
          const p = res.data;
          // Prefer client enterprise name, then project name; trim the
          // generic default the wizard stamps on prompt-only creations.
          const candidate = (p.client || p.name || "").trim();
          if (
            candidate &&
            candidate !== "待补充企业" &&
            candidate !== "企业3D数字化展示方案"
          ) {
            setProjectName(candidate);
          } else if (p.name && p.name !== "企业3D数字化展示方案") {
            setProjectName(p.name);
          }
        }
      })
      .catch(() => {
        /* keep placeholder */
      });

    // 2. load the canvas of the current version.
    const canvasRes = await getCurrentCanvas(projectId);
    if (!canvasRes.success || !canvasRes.data) {
      setError(canvasRes.message ?? "加载画布失败");
      setLoading(false);
      return;
    }
    const c = canvasRes.data;
    hydrate({
      projectId,
      versionId: c.projectVersionId,
      groups: c.groups,
      nodes: c.nodes,
      edges: c.edges,
      isReadOnly: false,
      tone: extractTone(c.layoutConfig),
      keepSelection: opts?.keepSelection,
    });
    // Context pack lives on canvas.layoutConfig.context_pack (snake_case raw
    // JSON). Mirror it into page state for the traceability drawer.
    const lc = (c.layoutConfig ?? {}) as Record<string, unknown>;
    setContextPack((lc.context_pack as Record<string, unknown> | undefined) ?? null);
    setLoading(false);
  }, [projectId, hydrate]);

  useEffect(() => {
    loadCurrent();
    return () => reset();
  }, [loadCurrent, reset]);

  async function handleSelectVersion(versionId: string) {
    const v = versions.find((x) => x.id === versionId);
    const readOnly = v ? !v.isCurrent : true;
    const res = await getVersionCanvas(projectId, versionId);
    if (res.success && res.data) {
      hydrate({
        projectId,
        versionId: res.data.projectVersionId,
        groups: res.data.groups,
        nodes: res.data.nodes,
        edges: res.data.edges,
        isReadOnly: readOnly,
        tone: extractTone(res.data.layoutConfig),
      });
    }
  }

  // PRD §15.3-6 / §16: every confirmed node edit must produce a new version.
  // The backend PATCH mutates the current version's canvas in place (by design
  // — see canvas.py:216-218); we then snapshot it into a new version and reload
  // while keeping the drawer open.
  async function handleNodeContentSaved(nodeId: string, nodeTitle: string) {
    const summary = `编辑节点：${nodeTitle}`;
    const res = await createVersion(projectId, {
      versionName: `V${versions.length + 1}`,
      changeSummary: summary,
    });
    if (res.success) {
      const vlist = (await listVersions(projectId).then((r) => r.data)) ?? [];
      setVersions(vlist);
      await loadCurrent({ keepSelection: true });
      toast.success(`已生成新版本 V${vlist.length}`);
    } else {
      toast.error(res.message ?? "生成版本失败");
    }
  }

  // One-click auto-relayout (PRD §10 / §23.3): re-runs the fixed three-column
  // layout client-side and persists positions so a chaotic canvas can be reset.
  async function handleRelayout() {
    // Trigger the backend relayout endpoint which recomputes and persists
    // node positions for the current version, then reload.
    try {
      const token = getToken();
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/projects/${projectId}/canvas/relayout`,
        { method: "POST", headers },
      );
      if (!res.ok) throw new Error(`重排失败 (${res.status})`);
      await loadCurrent({ keepSelection: true });
      toast.success("已自动重排画布");
    } catch (e) {
      toast.error(`重排失败：${e instanceof Error ? e.message : "未知错误"}`);
    }
  }

  // After the UI 专家 pass completes, snapshot the updated content into a new
  // version (PRD §16: content changes produce a new version) and reload.
  async function handleUiRegenerated() {
    const res = await createVersion(projectId, {
      versionName: `V${versions.length + 1}`,
      changeSummary: "UI 专家重新生成 UI 建议",
    });
    if (res.success) {
      const vlist = (await listVersions(projectId).then((r) => r.data)) ?? [];
      setVersions(vlist);
    }
    await loadCurrent({ keepSelection: true });
  }

  // PRD P1 #2: add a custom module node under one of the three boards.
  async function handleAddNode(groupId: string, title: string) {
    if (!groupId || !title.trim() || addingNode) return;
    setAddingNode(true);
    try {
      const res = await addNode(projectId, { groupId, title: title.trim() });
      if (res.success) {
        toast.success(`已新增节点：${title.trim()}`);
        setAddNodeOpen(false);
        await loadCurrent({ keepSelection: true });
      } else {
        toast.error(res.message ?? "新增失败");
      }
    } catch (e) {
      toast.error(`新增失败：${e instanceof Error ? e.message : "未知"}`);
    } finally {
      setAddingNode(false);
    }
  }

  async function handleSaveVersion() {
    setSaving(true);
    // No explicit changeSummary → the backend 版本总结 Agent derives a
    // data-grounded summary (node fill rate + referenced assets) so the
    // version-detail panel shows something useful (PRD §16.1).
    const res = await createVersion(projectId, {
      versionName: `V${versions.length + 1}`,
    });
    setSaving(false);
    if (res.success) {
      const vlist = (await listVersions(projectId).then((r) => r.data)) ?? [];
      setVersions(vlist);
      await loadCurrent({ keepSelection: true });
      toast.success(`已保存为 V${vlist.length}`);
    } else {
      toast.error(res.message ?? "保存失败");
    }
  }

  async function handleAiFill() {
    if (aiFilling) return;
    setAiFilling(true);
    setAiFillStatus("启动 AI 填充…");
    try {
      const start = await triggerAgentRun(projectId);
      if (!start.success || !start.data?.execution_id) {
        setAiFillStatus(`启动失败：${start.message ?? "未知错误"}`);
        setAiFilling(false);
        return;
      }
      const execId = start.data.execution_id;
      // Poll until terminal status.
      for (let i = 0; i < 60; i++) {
        await new Promise((r) => setTimeout(r, 1500));
        const poll = await getAgentRun(execId);
        const st = poll.data?.status;
        if (st === "succeeded") {
          setAiFillStatus("填充完成，刷新画布…");
          await loadCurrent();
          setAiFilling(false);
          setAiFillStatus("");
          return;
        }
        if (st === "failed") {
          setAiFillStatus(`填充失败：${poll.data?.error ?? "未知错误"}`);
          setAiFilling(false);
          return;
        }
        setAiFillStatus(`AI 填充中… (${i + 1}/60)`);
      }
      setAiFillStatus("超时，请稍后查看画布");
      setAiFilling(false);
    } catch (e) {
      setAiFillStatus(`异常：${e instanceof Error ? e.message : "未知"}`);
      setAiFilling(false);
    }
  }

  async function handleExport() {
    // Capture the FULL canvas (all boards, all nodes), not just the visible
    // viewport. ReactFlow renders nodes inside `.react-flow__viewport`, which
    // carries a pan/zoom transform, and `.react-flow` itself clips to the
    // visible area — so a plain toPng() truncates anything scrolled off-screen.
    //
    // Strategy: temporarily reset the viewport transform to identity so every
    // node is laid out from the canvas origin in document space, compute the
    // bounding box of all nodes from the store positions, then capture with an
    // explicit width/height covering the whole content area. The viewport is
    // restored afterwards (ReactFlow re-applies its own transform on next
    // interaction / fitView).
    const rfElement = document.querySelector(".react-flow") as HTMLElement | null;
    const viewport = document.querySelector(
      ".react-flow__viewport",
    ) as HTMLElement | null;
    if (!rfElement) return;

    const nodes = useCanvasStore.getState().rfNodes;
    if (nodes.length === 0) return;

    // Compute the bounding box of all nodes. Module nodes render at a fixed
    // 200px width (see module-node.tsx `w-[200px]`); section-header pills are
    // inline-flow but we give them a generous 280px so the title isn't cut.
    // Heights are upper-bound estimates — the padding below absorbs variance.
    const bounds = nodes.reduce(
      (acc, node) => {
        const isSection = node.type === "sectionHeader";
        const w = isSection ? 280 : 200;
        const h = isSection ? 48 : 96;
        return {
          minX: Math.min(acc.minX, node.position.x),
          minY: Math.min(acc.minY, node.position.y),
          maxX: Math.max(acc.maxX, node.position.x + w),
          maxY: Math.max(acc.maxY, node.position.y + h),
        };
      },
      {
        minX: Infinity,
        minY: Infinity,
        maxX: -Infinity,
        maxY: -Infinity,
      },
    );

    const PAD = 48;
    const width = Math.max(bounds.maxX - bounds.minX + PAD * 2, 1200);
    const height = Math.max(bounds.maxY - bounds.minY + PAD * 2, 800);

    // Save the current viewport transform so we can restore it exactly.
    const prevTransform = viewport?.style.transform ?? null;

    try {
      // Reset pan/zoom to identity so nodes are positioned in raw document
      // coordinates from the canvas origin. Also nudge the viewport container
      // so the capture origin aligns with the canvas top-left (bounds.minX/Y).
      if (viewport) {
        viewport.style.transform = "translate(0px, 0px) scale(1)";
      }
      rfElement.scrollLeft = 0;
      rfElement.scrollTop = 0;

      // Let the browser paint the reset transform before we capture.
      await new Promise((r) =>
        requestAnimationFrame(() => requestAnimationFrame(r)),
      );

      const dataUrl = await toPng(rfElement, {
        backgroundColor: "#ffffff",
        width,
        height,
        // Offset the capture window so it begins at the canvas content origin
        // (top-left node minus padding) rather than the (0,0) corner of the
        // viewport element, which may be empty space.
        style: {
          width: `${width}px`,
          height: `${height}px`,
          transform: `translate(${-(bounds.minX - PAD)}px, ${-(bounds.minY - PAD)}px)`,
        },
        filter: (domNode) => {
          const cls =
            typeof domNode?.className === "string" ? domNode.className : "";
          return (
            !cls.includes("react-flow__minimap") &&
            !cls.includes("react-flow__controls") &&
            !cls.includes("react-flow__attribution")
          );
        },
        pixelRatio: 2,
      });

      const a = document.createElement("a");
      a.href = dataUrl;
      a.download = `${projectName}-canvas.png`;
      a.click();
      toast.success("画布图片已导出");
    } catch (e) {
      toast.error(`导出失败：${e instanceof Error ? e.message : "未知错误"}`);
    } finally {
      // Restore the viewport so the user's pan/zoom is preserved. Clearing the
      // inline transform lets ReactFlow re-assert its own (it re-renders the
      // viewport on the next interaction / fitView pass).
      if (viewport) {
        viewport.style.transform = prevTransform ?? "";
      }
    }
  }

  async function handleExportVersionDoc(format: "word" | "pdf") {
    if (!currentVersionId) {
      toast.error("当前没有可导出的版本");
      return;
    }
    try {
      await exportVersionDoc(currentVersionId, format);
      toast.success(`已导出 ${format === "word" ? "Word" : "PDF"} 文档`);
    } catch (e) {
      toast.error(`导出失败：${e instanceof Error ? e.message : "未知错误"}`);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full bg-surface">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-error bg-surface">
        ⚠️ {error}
      </div>
    );
  }

  const currentVersionLabel =
    versions.find((v) => v.isCurrent)?.versionName ?? "V1";

  return (
    <div className="h-full flex bg-surface">
      {/* Body: left chat rail + canvas. The global TopNav (workspace/layout.tsx)
          sits above this page, so this container fills the remaining viewport.
          The version panel is now an on-demand drawer (no longer a third rail)
          so the canvas gets full width by default. */}
      <ConversationPanel
        projectId={projectId}
        initialPrompt={initialPrompt}
        activeNodeId={conversationNodeId}
        activeNodeTitle={activeNodeTitle}
        onClearNode={() => setConversationNode(null)}
        onNodeAdopted={() => loadCurrent()}
        onCanvasAccepted={() => loadCurrent()}
      />

      <section className="flex-1 flex flex-col relative bg-surface-bright overflow-hidden">
        {/* Unified top toolbar (PRD §9): project name · version · actions.
            Replaces the prior split (floating top label + floating bottom bar). */}
        <div className="flex items-center gap-2 px-4 h-14 border-b border-outline-variant bg-surface-container-lowest shrink-0 z-20">
          <div className="flex items-center gap-2 min-w-0">
            <span className="font-medium text-on-surface truncate">{projectName}</span>
            <span className="text-xs text-outline whitespace-nowrap">
              · 方案 {currentVersionLabel}{isReadOnly && " · 只读"}
            </span>
            {conversationNodeId && (
              <span className="bg-primary-fixed text-primary border border-primary-fixed px-2 py-0.5 rounded-md flex items-center gap-1 text-xs">
                <Target className="h-3 w-3" />
                节点对话
              </span>
            )}
          </div>

          <div className="flex-1" />

          {/* Action group — single toolbar per PRD §9 */}
          <button
            onClick={handleSaveVersion}
            disabled={saving || isReadOnly}
            className="border border-outline-variant px-3 h-9 rounded-lg font-medium text-sm text-primary hover:bg-primary-fixed hover:text-primary disabled:opacity-50 transition-all flex items-center gap-1.5"
            title="保存当前画布为新版本"
          >
            <Save className="h-4 w-4" />
            <span className="hidden sm:inline">{saving ? "保存中…" : "保存"}</span>
          </button>
          <button
            onClick={handleRelayout}
            disabled={isReadOnly}
            className="border border-outline-variant px-3 h-9 rounded-lg font-medium text-sm text-on-surface-variant hover:bg-surface-container-low disabled:opacity-50 transition-all flex items-center gap-1.5"
            title="自动重排画布节点"
          >
            <LayoutGrid className="h-4 w-4" />
            <span className="hidden md:inline">自动布局</span>
          </button>
          <button
            onClick={() => setVisualOpen(true)}
            className="border border-outline-variant px-3 h-9 rounded-lg font-medium text-sm text-on-surface-variant hover:bg-surface-container-low transition-all flex items-center gap-1.5"
            title="查看视觉概念版本树"
          >
            <Palette className="h-4 w-4" />
            <span className="hidden md:inline">视觉创作</span>
          </button>

          {/* Export dropdown: PNG canvas image + Word/PDF document (PRD §20) */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                className="border border-outline-variant px-3 h-9 rounded-lg font-medium text-sm text-on-surface-variant hover:bg-surface-container-low transition-all flex items-center gap-1.5"
                title="导出"
              >
                <Download className="h-4 w-4" />
                <span className="hidden sm:inline">导出</span>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-44">
              <DropdownMenuItem onClick={handleExport} className="gap-2">
                <Download className="h-4 w-4" /> 画布图片 (PNG)
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExportVersionDoc("word")} className="gap-2">
                <FileText className="h-4 w-4" /> 方案文档 (Word)
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExportVersionDoc("pdf")} className="gap-2">
                <FileType className="h-4 w-4" /> 方案文档 (PDF)
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <button
            onClick={() => setVersionOpen(true)}
            className="border border-outline-variant px-3 h-9 rounded-lg font-medium text-sm text-on-surface-variant hover:bg-surface-container-low transition-all flex items-center gap-1.5"
            title="版本管理"
          >
            <History className="h-4 w-4 text-primary" />
            <span className="hidden sm:inline">版本管理</span>
          </button>
          <button
            onClick={() => setAddNodeOpen(true)}
            disabled={isReadOnly}
            className="border border-outline-variant px-3 h-9 rounded-lg font-medium text-sm text-on-surface-variant hover:bg-surface-container-low transition-all flex items-center gap-1.5 disabled:opacity-50"
            title="在某个板块下新增节点"
          >
            <LayoutGrid className="h-4 w-4 text-primary" />
            <span className="hidden sm:inline">新增节点</span>
          </button>
          <button
            onClick={() => setContextPackOpen(true)}
            className="border border-outline-variant px-3 h-9 rounded-lg font-medium text-sm text-on-surface-variant hover:bg-surface-container-low transition-all flex items-center gap-1.5"
            title="查看本版本 AI 依据的全部上下文资料（PRD §9.3）"
          >
            <FileSearch className="h-4 w-4 text-primary" />
            <span className="hidden lg:inline">上下文追溯</span>
          </button>
          {tone && (
            <button
              onClick={() => setToneOpen(true)}
              className="border border-outline-variant px-3 h-9 rounded-lg font-medium text-sm text-on-surface-variant hover:bg-surface-container-low transition-all flex items-center gap-1.5"
              title="查看方案定调详情"
            >
              <Sparkles className="h-4 w-4 text-primary" />
              <span className="hidden lg:inline">定调</span>
            </button>
          )}

          <button
            onClick={handleAiFill}
            disabled={aiFilling || isReadOnly}
            className="bg-primary text-on-primary px-4 h-9 rounded-lg font-medium text-sm hover:opacity-90 disabled:opacity-50 transition-all flex items-center gap-1.5 ml-1"
            title="基于企业资料 + SOP + 网络搜索填充画布节点"
          >
            {aiFilling ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            <span className="hidden sm:inline">{aiFilling ? "AI 填充中…" : "生成新版本"}</span>
          </button>
        </div>

        {tone && (
          <div className="px-4 py-2 border-b border-outline-variant bg-surface-container-low shrink-0">
            <ToneCard tone={tone} compact />
          </div>
        )}

        {aiFillStatus && (
          <div className="px-4 py-1.5 border-b border-outline-variant bg-primary-fixed text-xs text-primary shrink-0">
            {aiFillStatus}
          </div>
        )}

        {/* Canvas surface */}
        <div className="flex-1 canvas-grid relative overflow-auto">
          <CanvasViewport />
        </div>

        <NodeDetailDrawer
          projectId={projectId}
          onSaved={handleNodeContentSaved}
          onUiRegenerated={handleUiRegenerated}
          onNodeDeleted={() => loadCurrent({ keepSelection: true })}
        />

        {/* Version management drawer — slides in over the canvas on demand. */}
        <VersionPanel
          projectId={projectId}
          currentVersionId={currentVersionId}
          onSelectVersion={handleSelectVersion}
          onRestored={loadCurrent}
          open={versionOpen}
          onClose={() => setVersionOpen(false)}
          onExport={handleExportVersionDoc}
        />

        {/* 方案定调 drawer (PRD §13.4) — full tone detail. Compact chip lives
            in the top overlay; this expands it. */}
        {toneOpen && tone && (
          <div className="absolute top-0 right-0 h-full w-[360px] z-20 p-4 overflow-auto">
            <div className="relative">
              <button
                onClick={() => setToneOpen(false)}
                className="absolute -top-1 -right-1 z-10 p-1.5 rounded-full bg-surface-container-lowest border border-outline-variant shadow-sm hover:bg-surface-container-low"
                aria-label="关闭"
              >
                <X className="h-4 w-4 text-on-surface-variant" />
              </button>
              <ToneCard tone={tone} />
            </div>
          </div>
        )}

        <AddNodeDialog
          open={addNodeOpen}
          onClose={() => setAddNodeOpen(false)}
          groups={canvasGroups}
          submitting={addingNode}
          onSubmit={handleAddNode}
        />

        {contextPackOpen && (
          <ContextPackDrawer
            pack={contextPack as Record<string, unknown> | null}
            onClose={() => setContextPackOpen(false)}
          />
        )}
      </section>

      <VisualDrawer
        projectId={projectId}
        open={visualOpen}
        onClose={() => setVisualOpen(false)}
      />
    </div>
  );
}

/** Add-node dialog (PRD P1 #2): pick a board + name the new module node. */
function AddNodeDialog({
  open,
  onClose,
  groups,
  submitting,
  onSubmit,
}: {
  open: boolean;
  onClose: () => void;
  groups: CanvasGroup[];
  submitting: boolean;
  onSubmit: (groupId: string, title: string) => void;
}) {
  const [groupId, setGroupId] = useState<string>("");
  const [title, setTitle] = useState<string>("");

  // Default to the first board once groups load.
  useEffect(() => {
    if (open && !groupId && groups.length > 0) setGroupId(groups[0].id);
    if (!open) {
      setGroupId("");
      setTitle("");
    }
  }, [open, groupId, groups]);

  const sortedGroups = [...groups].sort(
    (a, b) => (a.position?.x ?? 0) - (b.position?.x ?? 0),
  );

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新增节点</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label htmlFor="add-node-group">所属板块</Label>
            <Select value={groupId} onValueChange={setGroupId}>
              <SelectTrigger id="add-node-group">
                <SelectValue placeholder="选择板块" />
              </SelectTrigger>
              <SelectContent>
                {sortedGroups.map((g) => (
                  <SelectItem key={g.id} value={g.id}>
                    {g.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="add-node-title">节点标题</Label>
            <Input
              id="add-node-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="如：国际合作、产学研平台"
              maxLength={80}
              onKeyDown={(e) => {
                if (e.key === "Enter" && groupId && title.trim()) {
                  onSubmit(groupId, title);
                }
              }}
            />
          </div>
        </div>
        <DialogFooter className="gap-2">
          <DialogClose asChild>
            <Button variant="outline">取消</Button>
          </DialogClose>
          <Button
            disabled={!groupId || !title.trim() || submitting}
            onClick={() => onSubmit(groupId, title)}
          >
            {submitting ? "新增中…" : "新增节点"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
