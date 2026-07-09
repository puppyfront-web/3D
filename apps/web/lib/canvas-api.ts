"use client";

// Canvas API client — wraps the backend canvas router (/api/v1/...).
// Mirrors the apiFetch pattern in lib/api.ts: same API_BASE_URL, same
// { success, data, message } envelope. Kept separate from lib/api.ts to
// avoid churning that large file during the canvas rollout.

import type {
  ApiResponse,
  Canvas,
  CanvasNode,
  NodeContent,
  NodeStatus,
  ProjectVersion,
  VersionRestoreResult,
} from "@/types/canvas";
import type { ConversationDetail } from "@/types";
import { getToken } from "@/lib/auth";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function canvasFetch<T>(
  endpoint: string,
  options?: RequestInit,
): Promise<ApiResponse<T>> {
  const url = `${API_BASE_URL}${endpoint}`;
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(url, { headers, ...options });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const message =
      (err && (err.detail || err.message)) || `请求失败 (${res.status})`;
    return { success: false, data: null as T, message };
  }
  const json = await res.json();
  if (json && typeof json === "object" && "data" in json) {
    return {
      data: json.data as T,
      success: json.success ?? true,
      message: json.message,
    };
  }
  return { data: json as T, success: true };
}

// ─── Versions ────────────────────────────────────────────────────────────────

export async function listVersions(
  projectId: string,
): Promise<ApiResponse<ProjectVersion[]>> {
  return canvasFetch<ProjectVersion[]>(
    `/api/v1/projects/${projectId}/versions`,
  );
}

export async function createVersion(
  projectId: string,
  body?: { versionName?: string; changeSummary?: string },
): Promise<ApiResponse<ProjectVersion>> {
  return canvasFetch<ProjectVersion>(
    `/api/v1/projects/${projectId}/versions`,
    { method: "POST", body: JSON.stringify(body ?? {}) },
  );
}

export async function getVersion(
  projectId: string,
  versionId: string,
): Promise<ApiResponse<ProjectVersion>> {
  return canvasFetch<ProjectVersion>(
    `/api/v1/projects/${projectId}/versions/${versionId}`,
  );
}

export async function restoreVersion(
  versionId: string,
): Promise<ApiResponse<VersionRestoreResult>> {
  return canvasFetch<VersionRestoreResult>(
    `/api/v1/versions/${versionId}/restore`,
    { method: "POST" },
  );
}

// ─── Canvas reads ────────────────────────────────────────────────────────────

export async function getCurrentCanvas(
  projectId: string,
): Promise<ApiResponse<Canvas>> {
  return canvasFetch<Canvas>(`/api/v1/projects/${projectId}/canvas`);
}

export async function getVersionCanvas(
  projectId: string,
  versionId: string,
): Promise<ApiResponse<Canvas>> {
  return canvasFetch<Canvas>(
    `/api/v1/projects/${projectId}/versions/${versionId}/canvas`,
  );
}

// ─── Project-scoped conversation (canvas left-rail chat) ─────────────────────

/**
 * Get-or-create the conversation bound to a project, with full history.
 * Backs the canvas workspace's left-rail chat panel — gives it a stable,
 * project-scoped conversation independent of the global sidebar chat list.
 *
 * Backend: GET /api/v1/projects/{id}/conversation (get-or-create semantics,
 * Conversation.project_id FK already exists — no migration needed).
 */
export async function getProjectConversation(
  projectId: string,
  nodeId?: string | null,
): Promise<ApiResponse<ConversationDetail>> {
  const params = new URLSearchParams();
  if (nodeId) params.set("node_id", nodeId);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return canvasFetch<ConversationDetail>(
    `/api/v1/projects/${projectId}/conversation${suffix}`,
  );
}

// ─── Node CRUD ───────────────────────────────────────────────────────────────

export async function getNode(
  nodeId: string,
): Promise<ApiResponse<CanvasNode>> {
  return canvasFetch<CanvasNode>(`/api/v1/nodes/${nodeId}`);
}

export interface NodeUpdateInput {
  title?: string;
  status?: NodeStatus | string;
  priority?: string;
  position?: { x: number; y: number };
  content?: NodeContent;
}

export async function updateNode(
  projectId: string,
  nodeId: string,
  body: NodeUpdateInput,
): Promise<ApiResponse<CanvasNode>> {
  return canvasFetch<CanvasNode>(`/api/v1/projects/${projectId}/nodes/${nodeId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

/** Adopt a node-edit draft (from the node-scoped conversation) into the node.
 * Backend: POST /api/v1/projects/{pid}/nodes/{nid}/adopt (Task 3). */
export interface NodeAdoptInput {
  planning: string[];
  pending_questions?: string[];
  extracted?: string[];
  sources?: Array<{ type: string; name?: string; quote?: string }>;
}

export async function adoptNode(
  projectId: string,
  nodeId: string,
  body: NodeAdoptInput,
): Promise<ApiResponse<CanvasNode>> {
  return canvasFetch<CanvasNode>(
    `/api/v1/projects/${projectId}/nodes/${nodeId}/adopt`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

/** Accept a canvas-fill proposal in ask mode (Task 5 backend): POST the
 * selected board→node→points selections to /canvas/fill-accept, which merges
 * them into the current canvas. The backend returns the whole updated canvas;
 * callers ignore the body and reload via loadCurrent() instead. */
export interface CanvasFillAcceptInput {
  boards: Array<{
    board_key: string;
    nodes: Array<{
      node_key: string;
      points: string[];
      citations?: Array<{ name?: string; url?: string; snippet?: string }>;
    }>;
  }>;
  change_summary?: string;
}

export async function acceptCanvasFill(
  projectId: string,
  body: CanvasFillAcceptInput,
): Promise<ApiResponse<Canvas>> {
  // 后端 /canvas/fill-accept 返回整份更新后的 CanvasOut(新版本的画布),非单个 node。
  return canvasFetch<Canvas>(
    `/api/v1/projects/${projectId}/canvas/fill-accept`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

/** Add a custom node under one of the three boards (PRD P1 #2: 节点新增). */
export async function addNode(
  projectId: string,
  body: { groupId: string; title: string; nodeKey?: string },
): Promise<ApiResponse<CanvasNode>> {
  return canvasFetch<CanvasNode>(`/api/v1/projects/${projectId}/nodes`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** Remove a module node and its edges (PRD P1 #2: 节点删除). */
export async function deleteNode(
  projectId: string,
  nodeId: string,
): Promise<ApiResponse<null>> {
  return canvasFetch<null>(`/api/v1/projects/${projectId}/nodes/${nodeId}`, {
    method: "DELETE",
  });
}

/**
 * Persist a batch of node positions to the current canvas without forcing a
 * new version. Used by the debounced drag-persistence in the canvas store so
 * that moved nodes survive a page refresh (PRD §10).
 *
 * Fires one PATCH per node — there is no bulk endpoint, but the calls are
 * coalesced on a debounce timer so this stays cheap.
 */
export async function persistNodePositions(
  projectId: string,
  positions: { nodeId: string; position: { x: number; y: number } }[],
): Promise<void> {
  await Promise.all(
    positions.map(({ nodeId, position }) =>
      updateNode(projectId, nodeId, { position }).catch(() => {
        // Swallow per-node failures — drag persistence is best-effort and
        // must not throw into the React Flow drag handler.
      }),
    ),
  );
}

// ─── Agent runs (AI fill) ────────────────────────────────────────────────────

export interface AgentRunStatus {
  execution_id: string;
  status: "running" | "succeeded" | "failed" | string;
  agent_role?: string;
  node_ids?: string[];
  output?: Record<string, unknown>;
  error?: string | null;
}

export type AgentRole =
  | "canvas_fill"
  | "planner"
  | "tone"
  | "ui_expert"
  | "consistency"
  | "requirement"
  | "document_parse";

export async function triggerAgentRun(
  projectId: string,
  agentRole?: AgentRole,
): Promise<ApiResponse<AgentRunStatus>> {
  // Backend reads agent_role as a QUERY param (FastAPI scalar param), so send
  // it on the URL — a JSON body would be ignored and the run would silently
  // fall back to the default canvas_fill/full stage.
  const qs = agentRole ? `?agent_role=${encodeURIComponent(agentRole)}` : "";
  return canvasFetch<AgentRunStatus>(
    `/api/v1/projects/${projectId}/agent-runs${qs}`,
    { method: "POST" },
  );
}

export async function getAgentRun(
  executionId: string,
): Promise<ApiResponse<AgentRunStatus>> {
  return canvasFetch<AgentRunStatus>(`/api/v1/agent-runs/${executionId}`);
}

// ─── Canvas-version document export (PRD §20) ────────────────────────────
//
// These hit the /exports/{word|pdf}/version/{version_id} endpoints, which
// return a binary file (FileResponse) — not the JSON envelope canvasFetch
// expects — so they use plain fetch + blob() and trigger a browser download.

export async function exportVersionDoc(
  versionId: string,
  format: "word" | "pdf",
): Promise<void> {
  const ext = format === "word" ? "docx" : "pdf";
  const token = getToken();
  const exportHeaders: Record<string, string> = {};
  if (token) exportHeaders["Authorization"] = `Bearer ${token}`;
  const res = await fetch(
    `${API_BASE_URL}/api/v1/exports/${format}/version/${versionId}`,
    { method: "POST", headers: exportHeaders },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail =
      (err?.detail && (err.detail.message || err.detail)) ||
      err?.message ||
      `导出失败 (${res.status})`;
    throw new Error(typeof detail === "string" ? detail : "导出失败");
  }
  const blob = await res.blob();
  // Derive a filename from the response, falling back to a sane default.
  const disp = res.headers.get("content-disposition") || "";
  const match = disp.match(/filename="?([^";]+)"?/i);
  const filename = match?.[1] || `proposal.${ext}`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
