import {
  Project,
  CompanyAnalysis,
  Proposal,
  VisualProject,
  VisualImage,
  ReviewChecklist,
  Asset,
  PaginatedAssets,
  AssetStatus,
  AssetType,
  CaseItem,
  SOPWorkflow,
  ProposalTemplate,
  PromptTemplate,
  VisualStyle,
  TechnicalRule,
  QualityRule,
  Evaluation,
  ProjectWizardData,
  ApiResponse,
  SkillManifest,
  DocumentIndexResponse,
  DocumentBatchIndexResponse,
  ImportResult,
  ImportMode,
  IndustryMaterial,
  TalkingPoint,
  PricingExperience,
} from "@/types";
import { toast } from "sonner";
import { getToken } from "@/lib/auth";

// ============================================================
// API Configuration
// ============================================================

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ============================================================
// Auth API
// ============================================================

export async function login(email: string, password: string): Promise<{ token: string; user: { name?: string; email?: string; id?: string } }> {
  const res = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "登录失败" }));
    throw new Error(err.detail || "登录失败");
  }
  const json = await res.json();
  return {
    token: json.data?.accessToken ?? json.data?.access_token,
    user: json.data?.user,
  };
}

// Generic fetch wrapper for real API calls
// Backend wraps responses in { success: bool, data: T, message: string }
async function apiFetch<T>(endpoint: string, options?: RequestInit): Promise<ApiResponse<T>> {
  const url = `${API_BASE_URL}${endpoint}`;
  // Inject the JWT (if present) as a Bearer token on every call.
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  try {
    const res = await fetch(url, {
      headers,
      ...options,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      const message = err.detail || err.message || "请求失败";
      toast.error(`API 错误 (${res.status})`, {
        description: `${options?.method || "GET"} ${endpoint}\n${message}`,
      });
      return { data: null as T, success: false, message };
    }
    const json = await res.json();
    // Backend wraps in { success, data, message }
    if (json && typeof json === "object" && "data" in json) {
      return {
        data: json.data as T,
        success: json.success ?? true,
        message: json.message,
      };
    }
    // Direct response (no wrapper)
    return { data: json as T, success: true };
  } catch (error) {
    const message = (error as Error).message;
    toast.error("网络请求失败", {
      description: `${options?.method || "GET"} ${endpoint}\n${message}`,
    });
    return { data: null as T, success: false, message };
  }
}

// ============================================================
// Projects API
// ============================================================

export async function getProjects(): Promise<ApiResponse<Project[]>> {
  return unwrapPaginated<Project>("/api/v1/projects");
}

export async function getProjectById(id: string): Promise<ApiResponse<Project | undefined>> {
  return apiFetch<Project>(`/api/v1/projects/${id}`);
}

export async function createProject(data: ProjectWizardData): Promise<ApiResponse<Project>> {
  // POST /projects/wizard resolves owner + create-or-gets the Company from the
  // nested payload, so the frontend never supplies company_id/owner_id.
  return apiFetch<Project>("/api/v1/projects/wizard", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ============================================================
// Company Analysis API
// ============================================================

export async function getCompanyAnalysis(projectId: string): Promise<ApiResponse<CompanyAnalysis>> {
  return apiFetch<CompanyAnalysis>(`/api/v1/company-profiles/by-project/${projectId}`);
}

export async function updateCompanyAnalysis(
  projectId: string,
  data: Partial<CompanyAnalysis>
): Promise<ApiResponse<CompanyAnalysis>> {
  return apiFetch<CompanyAnalysis>(`/api/v1/company-profiles/${projectId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function generateCompanyAnalysis(companyId: string): Promise<ApiResponse<CompanyAnalysis>> {
  return apiFetch<CompanyAnalysis>(`/api/v1/agents/company-analysis/${companyId}`, {
    method: "POST",
  });
}

// ============================================================
// Proposal API
// ============================================================

export async function getProposal(projectId: string): Promise<ApiResponse<Proposal>> {
  // Backend returns paginated GenerationTask list; find the latest proposal task
  const res = await apiFetch<{ items: Record<string, unknown>[]; total: number }>(
    `/api/v1/generations/tasks?project_id=${projectId}&task_type=proposal&page_size=5`
  );
  if (!res.success || !res.data?.items?.length) {
    return { data: null as unknown as Proposal, success: false, message: res.message || "暂无策划案" };
  }
  const task = res.data.items[0] as Record<string, unknown>;
  const outputs = (task.outputs as Record<string, unknown>[]) || [];
  if (!outputs.length) {
    return { data: null as unknown as Proposal, success: false, message: "策划案尚未生成完成" };
  }
  const output = outputs[0] as Record<string, unknown>;
  const sectionsMeta =
    (output.sections_meta as Record<string, unknown>[]) ||
    (output.sectionsMeta as Record<string, unknown>[]) ||
    [];
  const content = (output.content as string) || "";

  // Parse sections from content + sections_meta
  const sections: Proposal["sections"] = sectionsMeta.map((m) => {
    const order = m.order as number;
    const sectionContent = extractSectionContent(content, order);
    return {
      id: (m.id as string) || `s-${order}`,
      title: m.title as string,
      content: sectionContent,
      order,
      status: (m.status as "draft" | "review" | "approved") || "draft",
    };
  });

  const proposal: Proposal = {
    id: output.id as string,
    taskId: task.id as string,
    title: `${(task.type as string) || "策划案"} — ${(task.created_at as string || "").slice(0, 10)}`,
    version: (output.version as number) || 1,
    lastEditedAt: (output.updated_at as string) || (output.updatedAt as string) || new Date().toISOString(),
    totalWords: content.length,
    sections,
    usedCases: (output.used_cases as string[]) || [],
    usedDocuments: (output.used_documents as string[]) || [],
  };
  return { data: proposal, success: true };
}

function extractSectionContent(
  fullContent: string,
  order: number
): string {
  // Split content by ## N. patterns
  const regex = /^##\s*\d+[\.\s]+/m;
  const parts = fullContent.split(/(?=^##\s*\d+[\.\s]+)/m);
  // parts[0] may be preamble; sections start at index where ## appears
  const sectionParts = parts.filter((p) => regex.test(p));
  if (order >= 1 && order <= sectionParts.length) {
    // Remove the header line, return body
    return sectionParts[order - 1].replace(/^##[^\n]*\n?/, "").trim();
  }
  return "";
}

export async function updateProposalSection(
  outputId: string,
  sectionId: string,
  content: string
): Promise<ApiResponse<Proposal>> {
  // Backend PUT updates full content; returns GenerationOutputOut
  const res = await apiFetch<Record<string, unknown>>(`/api/v1/generations/outputs/${outputId}`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
  if (!res.success || !res.data) {
    return { data: null as unknown as Proposal, success: false, message: res.message };
  }
  // Re-parse the updated output into a Proposal
  const output = res.data;
  const sectionsMeta =
    (output.sections_meta as Record<string, unknown>[]) ||
    (output.sectionsMeta as Record<string, unknown>[]) ||
    [];
  const fullContent = (output.content as string) || content;
  const sections: Proposal["sections"] = sectionsMeta.map((m) => {
    const order = m.order as number;
    const sectionContent = extractSectionContent(fullContent, order);
    return {
      id: (m.id as string) || `s-${order}`,
      title: m.title as string,
      content: sectionContent,
      order,
      status: (m.status as "draft" | "review" | "approved") || "draft",
    };
  });
  const proposal: Proposal = {
    id: output.id as string,
    taskId: (output.task_id as string) || (output.taskId as string),
    title: `策划案`,
    version: (output.version as number) || 1,
    lastEditedAt: (output.updated_at as string) || (output.updatedAt as string) || new Date().toISOString(),
    totalWords: fullContent.length,
    sections,
  };
  return { data: proposal, success: true };
}

export async function updateSectionStatus(
  outputId: string,
  sectionOrder: number,
  reviewStatus: "draft" | "review" | "approved"
): Promise<ApiResponse<Record<string, unknown>>> {
  return apiFetch<Record<string, unknown>>(
    `/api/v1/generations/outputs/${outputId}/sections/${sectionOrder}/status`,
    {
      method: "PATCH",
      body: JSON.stringify({ status: reviewStatus }),
    }
  );
}

export async function exportProposal(
  taskId: string,
  format: "word" | "pdf" | "pptx"
): Promise<Blob> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE_URL}/api/v1/exports/${format}/${taskId}`, {
    method: "POST",
    headers,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Export failed" }));
    throw new Error(err.detail?.message || err.detail || "Export failed");
  }
  return res.blob();
}

/**
 * Fetch a config-entity export endpoint and return the JSON as a Blob for
 * download. The backend serves a bare JSON array (snake_case, auto-managed
 * fields stripped) that feeds straight back into the matching /import.
 */
export async function exportConfig(endpoint: string): Promise<Blob> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE_URL}${endpoint}`, { headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "导出失败" }));
    throw new Error(err.detail?.message || err.detail || "导出失败");
  }
  return res.blob();
}

export async function generateProposal(projectId: string): Promise<ApiResponse<Proposal>> {
  return apiFetch<Proposal>("/api/v1/agents/proposal", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId }),
  });
}

// ============================================================
// Visual API
// ============================================================

export async function getVisualProjects(projectId: string): Promise<ApiResponse<VisualProject[]>> {
  const res = await apiFetch<{ items: Record<string, unknown>[]; total: number }>(
    `/api/v1/generations/tasks?project_id=${projectId}&task_type=visual_prompt&page_size=20`
  );
  if (!res.success || !res.data) return { data: [], success: true };
  const projects: VisualProject[] = res.data.items.map((task) => {
    const outputs = (task.outputs as Record<string, unknown>[]) || [];
    const images: VisualImage[] = outputs
      .filter((o) => {
        try {
          const parsed = JSON.parse(o.content as string);
          return parsed?.url;
        } catch { return false; }
      })
      .map((o) => {
        const parsed = JSON.parse(o.content as string);
        return {
          id: o.id as string,
          url: parsed.url as string,
          prompt: parsed.prompt as string || "",
          status: "completed" as const,
          createdAt: o.created_at as string || new Date().toISOString(),
        };
      });
    return {
      id: task.id as string,
      name: `视觉方案 ${(task.created_at as string || "").slice(0, 10)}`,
      prompt: (task.prompt_used as string) || "",
      style: "",
      images,
      createdAt: task.created_at as string || new Date().toISOString(),
    };
  });
  return { data: projects, success: true };
}

export async function generateVisualImage(
  projectId: string,
  prompt: string,
  style: string,
  width?: number,
  height?: number
): Promise<ApiResponse<VisualProject>> {
  return apiFetch<VisualProject>("/api/v1/agents/visual-prompt", {
    method: "POST",
    body: JSON.stringify({
      project_id: projectId,
      style_preferences: style,
      width,
      height,
    }),
  });
}

/**
 * Directly generate an image from a prompt — no project required.
 * Returns { image_url, prompt, width, height }.
 */
export async function directGenerateImage(
  prompt: string,
  options?: {
    negative_prompt?: string;
    width?: number;
    height?: number;
  }
): Promise<ApiResponse<{ image_url: string; prompt: string; width: number; height: number }>> {
  return apiFetch("/api/v1/agents/generate-image", {
    method: "POST",
    body: JSON.stringify({
      prompt,
      negative_prompt: options?.negative_prompt,
      width: options?.width,
      height: options?.height,
    }),
  });
}

// ============================================================
// Review API
// ============================================================

export async function getReviewChecklists(projectId: string): Promise<ApiResponse<ReviewChecklist[]>> {
  return apiFetch<ReviewChecklist[]>(`/api/v1/agents/quality-check/${projectId}`, {
    method: "POST",
  });
}

// ============================================================
// Exports API
// ============================================================

export async function getProposalTasksForExport(projectId: string): Promise<{
  success: boolean;
  records: { id: string; outputId: string; filename: string; exportedAt: string; status: string }[];
  latestTaskId: string | null;
}> {
  const res = await apiFetch<{ items: Record<string, unknown>[]; total: number }>(
    `/api/v1/generations/tasks?project_id=${projectId}&task_type=proposal&page_size=5`
  );
  if (!res.success || !res.data) return { success: false, records: [], latestTaskId: null };

  const records: { id: string; outputId: string; filename: string; exportedAt: string; status: string }[] = [];
  let latestTaskId: string | null = null;

  for (const task of res.data.items) {
    const outputs = (task.outputs as Record<string, unknown>[]) || [];
    if (outputs.length > 0) {
      const out = outputs[0];
      const outputId = out.id as string;
      const taskId = task.id as string;
      if (!latestTaskId) latestTaskId = taskId;
      records.push({
        id: taskId,
        outputId,
        filename: `策划案_${(task.created_at as string || "").slice(0, 10)}`,
        exportedAt: out.updated_at as string || task.created_at as string || "",
        status: task.status as string || "completed",
      });
    }
  }
  return { success: true, records, latestTaskId };
}

export async function exportToWord(taskId: string): Promise<ApiResponse<{ file_path: string }>> {
  return apiFetch<{ file_path: string }>(`/api/v1/exports/word/${taskId}`, { method: "POST" });
}

export async function exportToPdf(taskId: string): Promise<ApiResponse<{ file_path: string }>> {
  return apiFetch<{ file_path: string }>(`/api/v1/exports/pdf/${taskId}`, { method: "POST" });
}

export async function exportToPptx(taskId: string): Promise<ApiResponse<{ file_path: string }>> {
  return apiFetch<{ file_path: string }>(`/api/v1/exports/pptx/${taskId}`, { method: "POST" });
}

export async function getGenerationOutputs(
  projectId: string,
): Promise<ApiResponse<Record<string, unknown>[]>> {
  return unwrapPaginated<Record<string, unknown>>(`/api/v1/generations/tasks?project_id=${projectId}`);
}

// ============================================================
// Helpers
// ============================================================

function contentTypeToAssetType(contentType: string): AssetType {
  if (contentType.startsWith("image/")) return "image";
  if (contentType.startsWith("video/")) return "video";
  return "document";
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function pickField(obj: any, ...keys: string[]): unknown {
  for (const k of keys) {
    if (obj != null && obj[k] !== undefined && obj[k] !== null) return obj[k];
  }
  return undefined;
}

const ASSET_STATUSES: readonly AssetStatus[] = ["pending", "uploaded", "indexed", "error"];

/** Narrow the backend's indexer status to the badge states the UI renders. */
function toAssetStatus(raw: unknown): AssetStatus {
  const value = String(raw ?? "");
  if ((ASSET_STATUSES as readonly string[]).includes(value)) return value as AssetStatus;
  return value === "parsing" ? "pending" : "uploaded";
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapDocumentToAsset(doc: any): Asset {
  const fileSize = Number(pickField(doc, "fileSize", "file_size") ?? 0);
  const chunkCount = Number(pickField(doc, "chunkCount", "chunk_count") ?? 0);
  const created = pickField(doc, "createdAt", "created_at") as string | undefined;
  return {
    id: String(doc.id),
    name: String(pickField(doc, "originalFilename", "original_filename", "filename") ?? "未命名"),
    type: contentTypeToAssetType(String(pickField(doc, "contentType", "content_type") ?? "")),
    category: String(pickField(doc, "category") ?? "document"),
    url: "",
    size: formatFileSize(fileSize),
    file_size: fileSize,
    project_id: (pickField(doc, "projectId", "project_id") as string | null) ?? null,
    status: toAssetStatus(pickField(doc, "status")),
    parse_status: String(pickField(doc, "parseStatus", "parse_status") ?? ""),
    chunk_count: chunkCount,
    uploadedAt: created ?? new Date().toISOString(),
    uploadedBy: "",
    tags: [],
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function normalizeRetrievalLog(raw: any): RetrievalLogItem {
  return {
    id: String(raw.id),
    query: String(raw.query ?? ""),
    retrieval_type: String(pickField(raw, "retrievalType", "retrieval_type") ?? ""),
    results_count: Number(pickField(raw, "resultsCount", "results_count") ?? 0),
    top_scores: (pickField(raw, "topScores", "top_scores") as number[]) ?? [],
    latency_ms: Number(pickField(raw, "latencyMs", "latency_ms") ?? 0),
    triggered_by: String(pickField(raw, "triggeredBy", "triggered_by") ?? ""),
    structured_query_json: (pickField(raw, "structuredQueryJson", "structured_query_json") as Record<string, unknown>) ?? {},
    retrieved_items_json: (pickField(raw, "retrievedItemsJson", "retrieved_items_json") as Array<Record<string, unknown>>) ?? [],
    selected_context_json: (pickField(raw, "selectedContextJson", "selected_context_json") as Record<string, unknown>) ?? {},
    final_output_id: pickField(raw, "finalOutputId", "final_output_id") as string | undefined,
    message_id: pickField(raw, "messageId", "message_id") as string | undefined,
    conversation_id: pickField(raw, "conversationId", "conversation_id") as string | undefined,
    project_id: pickField(raw, "projectId", "project_id") as string | undefined,
    created_at: String(pickField(raw, "createdAt", "created_at") ?? new Date().toISOString()),
  };
}

// ============================================================
// Admin: Assets / Documents API
// ============================================================

export async function getAssets(options?: {
  page?: number;
  pageSize?: number;
  status?: string;
  parseStatus?: string;
  category?: string;
  q?: string;
}): Promise<ApiResponse<PaginatedAssets>> {
  const params = new URLSearchParams();
  params.set("page", String(options?.page ?? 1));
  params.set("page_size", String(options?.pageSize ?? 20));
  if (options?.status) params.set("status", options.status);
  if (options?.parseStatus) params.set("parse_status", options.parseStatus);
  if (options?.category) params.set("category", options.category);
  if (options?.q?.trim()) params.set("q", options.q.trim());

  const result = await apiFetch<{
    items: unknown[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
  }>(`/api/v1/documents?${params.toString()}`);

  if (result.success && result.data) {
    return {
      success: true,
      data: {
        items: result.data.items.map(mapDocumentToAsset),
        total: result.data.total,
        page: result.data.page,
        pageSize: result.data.page_size,
        totalPages: result.data.total_pages,
      },
    };
  }
  return {
    success: false,
    data: { items: [], total: 0, page: 1, pageSize: 20, totalPages: 0 },
    message: result.message,
  };
}

export async function getDocument(id: string): Promise<ApiResponse<Asset>> {
  const result = await apiFetch<unknown>(`/api/v1/documents/${id}`);
  if (result.success && result.data) {
    return { success: true, data: mapDocumentToAsset(result.data) };
  }
  return { success: false, data: null as unknown as Asset, message: result.message };
}

export interface DocumentChunkItem {
  id: string;
  chunk_index: number;
  chunkIndex?: number;
  page_number?: number | null;
  token_count: number;
  content_preview: string;
  contentPreview?: string;
}

export async function getDocumentChunks(
  documentId: string
): Promise<ApiResponse<DocumentChunkItem[]>> {
  return apiFetch<DocumentChunkItem[]>(
    `/api/v1/documents/${documentId}/chunks?page_size=50`
  );
}

export async function importKnowledgePack(
  file: File,
  options?: { force?: boolean; projectId?: string }
): Promise<
  ApiResponse<{
    pack_name: string;
    documents_imported: number;
    talking_points_imported: number;
    eval_set_id?: string | null;
    skipped: boolean;
    errors: string[];
  }>
> {
  const formData = new FormData();
  formData.append("file", file);
  const params = new URLSearchParams();
  if (options?.force) params.set("force", "true");
  if (options?.projectId) params.set("project_id", options.projectId);
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const qs = params.toString();
  const res = await fetch(
    `${API_BASE_URL}/api/v1/knowledge/packs/import${qs ? `?${qs}` : ""}`,
    { method: "POST", headers, body: formData }
  );
  const json = await res.json();
  if (res.ok && json.data) {
    return { success: true, data: json.data, message: json.message };
  }
  return {
    success: false,
    data: null as unknown as {
      pack_name: string;
      documents_imported: number;
      talking_points_imported: number;
      skipped: boolean;
      errors: string[];
    },
    message: json.message ?? json.detail ?? "导入失败",
  };
}

/**
 * Fetch only the total document count (for dashboard stat cards). Avoids the
 * previous bug where getAssets(1,1) returned at most 1 item and `.length`
 * always read 0/1 regardless of the true total.
 */
export async function getAssetCount(): Promise<number> {
  const result = await apiFetch<{ items: unknown[]; total: number }>(
    `/api/v1/documents?page=1&page_size=1`
  );
  return result.success && result.data ? result.data.total : 0;
}

export async function uploadAsset(
  file: File,
  projectId?: string,
  autoIndex: boolean = true,
): Promise<ApiResponse<Asset>> {
  const formData = new FormData();
  formData.append("file", file);
  const params = new URLSearchParams();
  if (projectId) params.set("project_id", projectId);
  params.set("auto_index", String(autoIndex));
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(
    `${API_BASE_URL}/api/v1/documents/upload?${params.toString()}`,
    { method: "POST", headers, body: formData },
  );
  const json = await res.json();
  if (res.ok && json.data) {
    return { data: mapDocumentToAsset(json.data), success: true, message: json.message };
  }
  return { data: null as unknown as Asset, success: false, message: json.detail || "上传失败" };
}

export async function deleteAsset(id: string): Promise<ApiResponse<null>> {
  return apiFetch<null>(`/api/v1/documents/${id}`, { method: "DELETE" });
}

export interface BatchDeleteResult {
  total: number;
  deleted: number;
  notFound: number;
}

export async function deleteAssetsBatch(
  documentIds: string[],
): Promise<ApiResponse<BatchDeleteResult>> {
  return apiFetch<BatchDeleteResult>("/api/v1/documents/delete-batch", {
    method: "POST",
    body: JSON.stringify({ document_ids: documentIds }),
  });
}

/**
 * Download the 资料清单 as CSV — either an explicit selection or the current
 * filter set. Metadata only; document contents never leave the system.
 */
export async function exportAssets(options?: {
  documentIds?: string[];
  status?: string;
  parseStatus?: string;
  category?: string;
  q?: string;
}): Promise<Blob> {
  const params = new URLSearchParams();
  options?.documentIds?.forEach((id) => params.append("document_ids", id));
  if (options?.status) params.set("status", options.status);
  if (options?.parseStatus) params.set("parse_status", options.parseStatus);
  if (options?.category) params.set("category", options.category);
  if (options?.q?.trim()) params.set("q", options.q.trim());

  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(
    `${API_BASE_URL}/api/v1/documents/export?${params.toString()}`,
    { headers },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "导出失败" }));
    throw new Error(err.detail?.message || err.detail || "导出失败");
  }
  return res.blob();
}

export async function indexDocument(documentId: string): Promise<ApiResponse<DocumentIndexResponse>> {
  return apiFetch<DocumentIndexResponse>(`/api/v1/documents/${documentId}/index`, {
    method: "POST",
  });
}

/** Update a document's attachment category (PRD §11.2) / parse status. */
export async function updateAssetCategory(
  id: string,
  category: string,
): Promise<ApiResponse<unknown>> {
  return apiFetch<unknown>(`/api/v1/documents/${id}`, {
    method: "PUT",
    body: JSON.stringify({ category }),
  });
}

export async function indexBatchDocuments(
  documentIds?: string[],
  projectId?: string,
): Promise<ApiResponse<DocumentBatchIndexResponse>> {
  return apiFetch<DocumentBatchIndexResponse>("/api/v1/documents/index-batch", {
    method: "POST",
    body: JSON.stringify({
      document_ids: documentIds || null,
      project_id: projectId || null,
    }),
  });
}

// Helper: unwrap paginated {items, total} responses
async function unwrapPaginated<T>(endpoint: string): Promise<ApiResponse<T[]>> {
  const result = await apiFetch<{ items: T[]; total: number }>(endpoint);
  if (result.success && result.data) {
    return { data: result.data.items, success: true };
  }
  return { data: [] as T[], success: false, message: result.message };
}

// ============================================================
// Admin: Cases API
// ============================================================

export async function getCases(): Promise<ApiResponse<CaseItem[]>> {
  return unwrapPaginated<CaseItem>("/api/v1/cases");
}

export async function createCase(data: Partial<CaseItem>): Promise<ApiResponse<CaseItem>> {
  return apiFetch<CaseItem>("/api/v1/cases", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateCase(id: string, data: Partial<CaseItem>): Promise<ApiResponse<CaseItem>> {
  return apiFetch<CaseItem>(`/api/v1/cases/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteCase(id: string): Promise<ApiResponse<null>> {
  return apiFetch<null>(`/api/v1/cases/${id}`, { method: "DELETE" });
}

// ============================================================
// Admin: SOP Workflows API
// ============================================================

export async function getSOPWorkflows(): Promise<ApiResponse<SOPWorkflow[]>> {
  return unwrapPaginated<SOPWorkflow>("/api/v1/workflows");
}

export async function createSOPWorkflow(data: Partial<SOPWorkflow>): Promise<ApiResponse<SOPWorkflow>> {
  return apiFetch<SOPWorkflow>("/api/v1/workflows", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateSOPWorkflow(id: string, data: Partial<SOPWorkflow>): Promise<ApiResponse<SOPWorkflow>> {
  return apiFetch<SOPWorkflow>(`/api/v1/workflows/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteSOPWorkflow(id: string): Promise<ApiResponse<null>> {
  return apiFetch<null>(`/api/v1/workflows/${id}`, { method: "DELETE" });
}

// ============================================================
// Admin: Templates API
// ============================================================

export async function getProposalTemplates(): Promise<ApiResponse<ProposalTemplate[]>> {
  return unwrapPaginated<ProposalTemplate>("/api/v1/templates/proposals");
}

export async function createProposalTemplate(
  data: Partial<ProposalTemplate>,
): Promise<ApiResponse<ProposalTemplate>> {
  return apiFetch<ProposalTemplate>("/api/v1/templates/proposals", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updateProposalTemplate(
  id: string,
  data: Partial<ProposalTemplate>,
): Promise<ApiResponse<ProposalTemplate>> {
  return apiFetch<ProposalTemplate>(`/api/v1/templates/proposals/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function deleteProposalTemplate(id: string): Promise<ApiResponse<null>> {
  return apiFetch<null>(`/api/v1/templates/proposals/${id}`, { method: "DELETE" });
}

export async function getPromptTemplates(): Promise<ApiResponse<PromptTemplate[]>> {
  return unwrapPaginated<PromptTemplate>("/api/v1/templates/prompts");
}

export async function createPromptTemplate(data: Partial<PromptTemplate>): Promise<ApiResponse<PromptTemplate>> {
  return apiFetch<PromptTemplate>("/api/v1/templates/prompts", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updatePromptTemplate(id: string, data: Partial<PromptTemplate>): Promise<ApiResponse<PromptTemplate>> {
  return apiFetch<PromptTemplate>(`/api/v1/templates/prompts/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deletePromptTemplate(id: string): Promise<ApiResponse<null>> {
  return apiFetch<null>(`/api/v1/templates/prompts/${id}`, { method: "DELETE" });
}

// ============================================================
// Admin: Visual Styles API
// ============================================================

export async function getVisualStyles(): Promise<ApiResponse<VisualStyle[]>> {
  return unwrapPaginated<VisualStyle>("/api/v1/visual-styles");
}

export async function createVisualStyle(data: Partial<VisualStyle>): Promise<ApiResponse<VisualStyle>> {
  return apiFetch<VisualStyle>("/api/v1/visual-styles", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateVisualStyle(id: string, data: Partial<VisualStyle>): Promise<ApiResponse<VisualStyle>> {
  return apiFetch<VisualStyle>(`/api/v1/visual-styles/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteVisualStyle(id: string): Promise<ApiResponse<null>> {
  return apiFetch<null>(`/api/v1/visual-styles/${id}`, { method: "DELETE" });
}

// ============================================================
// Admin: Rules API
// ============================================================

export async function getTechnicalRules(): Promise<ApiResponse<TechnicalRule[]>> {
  return unwrapPaginated<TechnicalRule>("/api/v1/rules/technical");
}

export async function createTechnicalRule(data: Partial<TechnicalRule>): Promise<ApiResponse<TechnicalRule>> {
  return apiFetch<TechnicalRule>("/api/v1/rules/technical", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateTechnicalRule(id: string, data: Partial<TechnicalRule>): Promise<ApiResponse<TechnicalRule>> {
  return apiFetch<TechnicalRule>(`/api/v1/rules/technical/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteTechnicalRule(id: string): Promise<ApiResponse<null>> {
  return apiFetch<null>(`/api/v1/rules/technical/${id}`, { method: "DELETE" });
}

export async function getQualityRules(): Promise<ApiResponse<QualityRule[]>> {
  return unwrapPaginated<QualityRule>("/api/v1/rules/quality");
}

export async function createQualityRule(data: Partial<QualityRule>): Promise<ApiResponse<QualityRule>> {
  return apiFetch<QualityRule>("/api/v1/rules/quality", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateQualityRule(id: string, data: Partial<QualityRule>): Promise<ApiResponse<QualityRule>> {
  return apiFetch<QualityRule>(`/api/v1/rules/quality/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteQualityRule(id: string): Promise<ApiResponse<null>> {
  return apiFetch<null>(`/api/v1/rules/quality/${id}`, { method: "DELETE" });
}

// ============================================================
// Admin: Evaluations API
// ============================================================

export async function getEvaluations(): Promise<ApiResponse<Evaluation[]>> {
  return unwrapPaginated<Evaluation>("/api/v1/generations/tasks?type=evaluation");
}

// ============================================================
// Eval Center API
// ============================================================

export interface EvalSetItem {
  id: string;
  name: string;
  status: string;
  project_id?: string | null;
}

export interface EvalRunItem {
  id: string;
  set_id: string;
  setId?: string;
  status: string;
  metrics_json?: {
    hit_at_k_rate?: number;
    passed?: number;
    total?: number;
    empty_rate?: number;
    latency_ms_p50?: number;
    latency_ms_p95?: number;
  };
  metricsJson?: Record<string, unknown>;
  per_case_results_json?: Array<{
    case_id: string;
    pass: boolean;
    reason?: string;
    latency_ms?: number;
  }>;
  perCaseResultsJson?: Array<{
    caseId?: string;
    case_id?: string;
    pass: boolean;
    reason?: string;
  }>;
  created_at: string;
  createdAt?: string;
}

function evalRunMetrics(r: EvalRunItem) {
  const m = r.metrics_json ?? r.metricsJson;
  if (!m) return null;
  const rate =
    (m as { hit_at_k_rate?: number }).hit_at_k_rate ??
    (m as { hitAtKRate?: number }).hitAtKRate;
  return { ...m, hit_at_k_rate: rate };
}

export { evalRunMetrics };

export interface EvalCaseItem {
  id: string;
  set_id: string;
  setId?: string;
  query: string;
  expected_keywords?: string[];
  expectedKeywords?: string[];
  expected_chunk_ids?: string[];
  notes?: string | null;
  source: string;
}

export async function listEvalCases(
  setId: string
): Promise<ApiResponse<EvalCaseItem[]>> {
  return apiFetch<EvalCaseItem[]>(`/api/v1/eval/sets/${setId}/cases`);
}

export async function createEvalCase(
  setId: string,
  body: {
    query: string;
    expected_keywords?: string[];
    expected_chunk_ids?: string[];
    notes?: string;
  }
): Promise<ApiResponse<EvalCaseItem>> {
  return apiFetch<EvalCaseItem>(`/api/v1/eval/sets/${setId}/cases`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function deleteEvalCase(
  caseId: string
): Promise<ApiResponse<{ deleted: boolean; id: string }>> {
  return apiFetch<{ deleted: boolean; id: string }>(
    `/api/v1/eval/cases/${caseId}`,
    { method: "DELETE" }
  );
}

export async function saveEvalCaseFromLab(body: {
  set_id: string;
  query: string;
  pick_rank?: number;
  top_k_snapshot: Array<Record<string, unknown>>;
}): Promise<ApiResponse<EvalCaseItem>> {
  return apiFetch<EvalCaseItem>("/api/v1/eval/cases/from-lab", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function importEvalSmokeTemplate(body?: {
  template_id?: string;
  name?: string;
  project_id?: string | null;
}): Promise<ApiResponse<EvalSetItem>> {
  return apiFetch<EvalSetItem>("/api/v1/eval/import-template", {
    method: "POST",
    body: JSON.stringify({
      template_id: body?.template_id ?? "b2b-smoke-v1",
      name: body?.name,
      project_id: body?.project_id ?? undefined,
    }),
  });
}

export async function listEvalSets(): Promise<
  ApiResponse<{ items: EvalSetItem[]; total: number }>
> {
  return apiFetch<{ items: EvalSetItem[]; total: number }>("/api/v1/eval/sets");
}

export async function createEvalSet(body: {
  name: string;
  project_id?: string | null;
}): Promise<ApiResponse<EvalSetItem>> {
  return apiFetch<EvalSetItem>("/api/v1/eval/sets", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function runEvalSet(
  setId: string
): Promise<ApiResponse<EvalRunItem>> {
  return apiFetch<EvalRunItem>("/api/v1/eval/runs", {
    method: "POST",
    body: JSON.stringify({ set_id: setId }),
  });
}

export async function listEvalRuns(
  setId?: string
): Promise<ApiResponse<EvalRunItem[]>> {
  const q = setId ? `?set_id=${setId}` : "";
  return apiFetch<EvalRunItem[]>(`/api/v1/eval/runs${q}`);
}

export async function getEvalRun(runId: string): Promise<ApiResponse<EvalRunItem>> {
  return apiFetch<EvalRunItem>(`/api/v1/eval/runs/${runId}`);
}

// ============================================================
// Retrieval logs API (PRD §9.4 traceability)
// ============================================================

export interface RetrievalLogItem {
  id: string;
  query: string;
  retrieval_type: string;
  results_count: number;
  top_scores?: number[];
  latency_ms?: number;
  triggered_by?: string;
  structured_query_json?: Record<string, unknown>;
  retrieved_items_json?: Array<Record<string, unknown>>;
  selected_context_json?: Record<string, unknown>;
  final_output_id?: string;
  message_id?: string;
  conversation_id?: string;
  project_id?: string;
  created_at: string;
}

export async function getRetrievalLogs(params?: {
  triggered_by?: string;
  retrieval_type?: string;
  message_id?: string;
  conversation_id?: string;
  limit?: number;
}): Promise<ApiResponse<RetrievalLogItem[]>> {
  const qs = new URLSearchParams();
  if (params?.triggered_by) qs.set("triggered_by", params.triggered_by);
  if (params?.retrieval_type) qs.set("retrieval_type", params.retrieval_type);
  if (params?.message_id) qs.set("message_id", params.message_id);
  if (params?.conversation_id) qs.set("conversation_id", params.conversation_id);
  if (params?.limit) qs.set("limit", String(params.limit));
  const tail = qs.toString();
  return apiFetch<RetrievalLogItem[]>(`/api/v1/rag/logs${tail ? `?${tail}` : ""}`).then((res) => {
    if (res.success && res.data) {
      return { ...res, data: res.data.map(normalizeRetrievalLog) };
    }
    return res;
  });
}

// ============================================================
// Feedback API
// ============================================================

export async function submitFeedback(data: {
  output_id: string;
  rating: number;
  comment: string;
  feedback_type: string;
}): Promise<ApiResponse<null>> {
  return apiFetch<null>("/api/v1/feedback", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ============================================================
// RAG Search API
// ============================================================

export interface RAGSearchHit {
  chunkId: string;
  documentId: string;
  content: string;
  score: number;
  pageNumber?: number | null;
  source?: string | null;
  title?: string | null;
}

export interface RAGSearchResponse {
  query: string;
  results: RAGSearchHit[];
  total: number;
  latencyMs: number;
  retrievalType: string;
  logId?: string | null;
  contextPreviewText?: string | null;
}

export async function searchKnowledge(
  query: string,
  options?: {
    topK?: number;
    projectId?: string;
    retrievalType?: string;
    includeContextPreview?: boolean;
  },
): Promise<ApiResponse<RAGSearchResponse>> {
  const params = new URLSearchParams({
    query,
    top_k: String(options?.topK ?? 5),
    retrieval_type: options?.retrievalType ?? "hybrid",
  });
  if (options?.projectId) params.set("project_id", options.projectId);
  if (options?.includeContextPreview) params.set("include_context_preview", "true");
  return apiFetch<RAGSearchResponse>(`/api/v1/rag/search?${params.toString()}`, {
    method: "POST",
  });
}

// ============================================================
// Skills API
// ============================================================

export async function getSkills(): Promise<ApiResponse<SkillManifest[]>> {
  return apiFetch<SkillManifest[]>("/api/v1/skills");
}

export async function executeSkill(
  skillId: string,
  inputData: Record<string, unknown>,
  projectId?: string,
): Promise<ApiResponse<Record<string, unknown>>> {
  return apiFetch<Record<string, unknown>>(`/api/v1/skills/${skillId}/execute`, {
    method: "POST",
    body: JSON.stringify({ input_data: inputData, project_id: projectId }),
  });
}

// ============================================================
// Generic Import Helper
// ============================================================

async function importFromFile(
  endpoint: string,
  file: File,
  extraParams?: Record<string, string>,
): Promise<ApiResponse<ImportResult>> {
  const formData = new FormData();
  formData.append("file", file);
  const params = new URLSearchParams(extraParams);
  const url = `${API_BASE_URL}${endpoint}${params.toString() ? "?" + params.toString() : ""}`;
  try {
    const token = getToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(url, { method: "POST", headers, body: formData });
    const json = await res.json();
    if (res.ok) {
      const data = json.data || json;
      return { data: data as ImportResult, success: true, message: json.message };
    }
    return { data: null as unknown as ImportResult, success: false, message: json.detail || "导入失败" };
  } catch (error) {
    return { data: null as unknown as ImportResult, success: false, message: (error as Error).message };
  }
}

// ============================================================
// Admin: Import + Export API
// ============================================================

export async function importCases(
  file: File,
  projectId?: string,
  mode: ImportMode = "skip"
): Promise<ApiResponse<ImportResult>> {
  const params: Record<string, string> = { mode };
  if (projectId) params.project_id = projectId;
  return importFromFile("/api/v1/cases/import", file, params);
}

export async function importSOPWorkflows(
  file: File,
  mode: ImportMode = "skip"
): Promise<ApiResponse<ImportResult>> {
  return importFromFile("/api/v1/workflows/import", file, { mode });
}

export async function importProposalTemplates(
  file: File,
  mode: ImportMode = "skip"
): Promise<ApiResponse<ImportResult>> {
  return importFromFile("/api/v1/templates/proposals/import", file, { mode });
}

export async function importPromptTemplates(
  file: File,
  mode: ImportMode = "skip"
): Promise<ApiResponse<ImportResult>> {
  return importFromFile("/api/v1/templates/prompts/import", file, { mode });
}

export async function importVisualStyles(
  file: File,
  mode: ImportMode = "skip"
): Promise<ApiResponse<ImportResult>> {
  return importFromFile("/api/v1/visual-styles/import", file, { mode });
}

export async function importTechnicalRules(
  file: File,
  mode: ImportMode = "skip"
): Promise<ApiResponse<ImportResult>> {
  return importFromFile("/api/v1/rules/technical/import", file, { mode });
}

export async function importQualityRules(
  file: File,
  mode: ImportMode = "skip"
): Promise<ApiResponse<ImportResult>> {
  return importFromFile("/api/v1/rules/quality/import", file, { mode });
}

// --- Config export (all / single) -> JSON Blob for download ---

export const exportSOPWorkflows = () => exportConfig("/api/v1/workflows/export");
export const exportSOPWorkflow = (id: string) => exportConfig(`/api/v1/workflows/${id}/export`);
export const exportCases = () => exportConfig("/api/v1/cases/export");
export const exportCase = (id: string) => exportConfig(`/api/v1/cases/${id}/export`);
export const exportProposalTemplates = () => exportConfig("/api/v1/templates/proposals/export");
export const exportProposalTemplate = (id: string) =>
  exportConfig(`/api/v1/templates/proposals/${id}/export`);
export const exportPromptTemplates = () => exportConfig("/api/v1/templates/prompts/export");
export const exportPromptTemplate = (id: string) =>
  exportConfig(`/api/v1/templates/prompts/${id}/export`);
export const exportVisualStyles = () => exportConfig("/api/v1/visual-styles/export");
export const exportVisualStyle = (id: string) => exportConfig(`/api/v1/visual-styles/${id}/export`);
export const exportTechnicalRules = () => exportConfig("/api/v1/rules/technical/export");
export const exportTechnicalRule = (id: string) =>
  exportConfig(`/api/v1/rules/technical/${id}/export`);
export const exportQualityRules = () => exportConfig("/api/v1/rules/quality/export");
export const exportQualityRule = (id: string) => exportConfig(`/api/v1/rules/quality/${id}/export`);

// ============================================================
// Admin: Industry materials (行业资料库 — PRD §12.5)
// ============================================================

export async function getIndustryMaterials(): Promise<ApiResponse<IndustryMaterial[]>> {
  return unwrapPaginated<IndustryMaterial>("/api/v1/industry-materials");
}

export async function createIndustryMaterial(data: Partial<IndustryMaterial>): Promise<ApiResponse<IndustryMaterial>> {
  return apiFetch<IndustryMaterial>("/api/v1/industry-materials", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateIndustryMaterial(id: string, data: Partial<IndustryMaterial>): Promise<ApiResponse<IndustryMaterial>> {
  return apiFetch<IndustryMaterial>(`/api/v1/industry-materials/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteIndustryMaterial(id: string): Promise<ApiResponse<null>> {
  return apiFetch<null>(`/api/v1/industry-materials/${id}`, { method: "DELETE" });
}

export async function importIndustryMaterials(file: File, mode: ImportMode = "skip"): Promise<ApiResponse<ImportResult>> {
  return importFromFile("/api/v1/industry-materials/import", file, { mode });
}

export const exportIndustryMaterials = () => exportConfig("/api/v1/industry-materials/export");
export const exportIndustryMaterial = (id: string) => exportConfig(`/api/v1/industry-materials/${id}/export`);

// ============================================================
// Admin: Talking points (话术库 — PRD §12.6)
// ============================================================

export async function getTalkingPoints(): Promise<ApiResponse<TalkingPoint[]>> {
  return unwrapPaginated<TalkingPoint>("/api/v1/talking-points");
}

export async function createTalkingPoint(data: Partial<TalkingPoint>): Promise<ApiResponse<TalkingPoint>> {
  return apiFetch<TalkingPoint>("/api/v1/talking-points", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateTalkingPoint(id: string, data: Partial<TalkingPoint>): Promise<ApiResponse<TalkingPoint>> {
  return apiFetch<TalkingPoint>(`/api/v1/talking-points/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteTalkingPoint(id: string): Promise<ApiResponse<null>> {
  return apiFetch<null>(`/api/v1/talking-points/${id}`, { method: "DELETE" });
}

export async function importTalkingPoints(file: File, mode: ImportMode = "skip"): Promise<ApiResponse<ImportResult>> {
  return importFromFile("/api/v1/talking-points/import", file, { mode });
}

export const exportTalkingPoints = () => exportConfig("/api/v1/talking-points/export");
export const exportTalkingPoint = (id: string) => exportConfig(`/api/v1/talking-points/${id}/export`);

// ============================================================
// Admin: Pricing experiences (报价经验库 — PRD §12.7)
// ============================================================

export async function getPricingExperiences(): Promise<ApiResponse<PricingExperience[]>> {
  return unwrapPaginated<PricingExperience>("/api/v1/pricing-experiences");
}

export async function createPricingExperience(data: Partial<PricingExperience>): Promise<ApiResponse<PricingExperience>> {
  return apiFetch<PricingExperience>("/api/v1/pricing-experiences", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updatePricingExperience(id: string, data: Partial<PricingExperience>): Promise<ApiResponse<PricingExperience>> {
  return apiFetch<PricingExperience>(`/api/v1/pricing-experiences/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deletePricingExperience(id: string): Promise<ApiResponse<null>> {
  return apiFetch<null>(`/api/v1/pricing-experiences/${id}`, { method: "DELETE" });
}

export async function importPricingExperiences(file: File, mode: ImportMode = "skip"): Promise<ApiResponse<ImportResult>> {
  return importFromFile("/api/v1/pricing-experiences/import", file, { mode });
}

export const exportPricingExperiences = () => exportConfig("/api/v1/pricing-experiences/export");
export const exportPricingExperience = (id: string) => exportConfig(`/api/v1/pricing-experiences/${id}/export`);

// ============================================================
// Settings
// ============================================================

export async function getAppSettings(): Promise<ApiResponse<Record<string, string>>> {
  return apiFetch<Record<string, string>>("/api/v1/settings");
}

export async function updateAppSettings(data: Record<string, string>): Promise<ApiResponse<Record<string, string>>> {
  return apiFetch<Record<string, string>>("/api/v1/settings", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}
