import {
  Project,
  CompanyAnalysis,
  Proposal,
  VisualProject,
  ReviewChecklist,
  Asset,
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
} from "@/types";

// ============================================================
// API Configuration
// ============================================================

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Generic fetch wrapper for real API calls
// Backend wraps responses in { success: bool, data: T, message: string }
async function apiFetch<T>(endpoint: string, options?: RequestInit): Promise<ApiResponse<T>> {
  const url = `${API_BASE_URL}${endpoint}`;
  try {
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json", ...options?.headers },
      ...options,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      return { data: null as T, success: false, message: err.detail || "请求失败" };
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
    return { data: null as T, success: false, message: (error as Error).message };
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
  return apiFetch<Project>("/api/v1/projects", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ============================================================
// Company Analysis API
// ============================================================

export async function getCompanyAnalysis(projectId: string): Promise<ApiResponse<CompanyAnalysis>> {
  return apiFetch<CompanyAnalysis>(`/api/v1/company-profiles/by-company/${projectId}`);
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
  return apiFetch<Proposal>(`/api/v1/generations/tasks?project_id=${projectId}`);
}

export async function updateProposalSection(
  proposalId: string,
  sectionId: string,
  content: string
): Promise<ApiResponse<Proposal>> {
  return apiFetch<Proposal>(`/api/v1/generations/outputs/${proposalId}`, {
    method: "PUT",
    body: JSON.stringify({ section_id: sectionId, content }),
  });
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
  outputId: string,
  format: "word" | "pdf" | "pptx"
): Promise<Blob> {
  const res = await fetch(`${API_BASE_URL}/api/v1/exports/${format}/${outputId}`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Export failed" }));
    throw new Error(err.detail?.message || err.detail || "Export failed");
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
  return apiFetch<VisualProject[]>(`/api/v1/generations/tasks?project_id=${projectId}&type=visual`);
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
  return apiFetch<ReviewChecklist[]>(`/api/v1/generations/tasks?project_id=${projectId}&type=review`);
}

// ============================================================
// Exports API
// ============================================================

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
function mapDocumentToAsset(doc: any): Asset {
  return {
    id: doc.id,
    name: doc.original_filename || doc.filename,
    type: contentTypeToAssetType(doc.content_type || ""),
    category: "document",
    url: "",
    size: formatFileSize(doc.file_size || 0),
    file_size: doc.file_size || 0,
    project_id: doc.project_id || null,
    status: doc.status || "uploaded",
    chunk_count: doc.chunk_count || 0,
    uploadedAt: doc.created_at || new Date().toISOString(),
    uploadedBy: "",
    tags: [],
  };
}

// ============================================================
// Admin: Assets / Documents API
// ============================================================

export async function getAssets(page = 1, pageSize = 50): Promise<ApiResponse<Asset[]>> {
  const result = await apiFetch<{ items: unknown[]; total: number }>(
    `/api/v1/documents?page=${page}&page_size=${pageSize}`
  );
  if (result.success && result.data) {
    return {
      data: result.data.items.map(mapDocumentToAsset),
      success: true,
    };
  }
  return { data: [], success: false, message: result.message };
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
  const res = await fetch(
    `${API_BASE_URL}/api/v1/documents/upload?${params.toString()}`,
    { method: "POST", body: formData },
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

export async function indexDocument(documentId: string): Promise<ApiResponse<DocumentIndexResponse>> {
  return apiFetch<DocumentIndexResponse>(`/api/v1/documents/${documentId}/index`, {
    method: "POST",
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

export async function searchKnowledge(query: string, filters?: Record<string, string>): Promise<ApiResponse<unknown>> {
  return apiFetch("/api/v1/rag/search", {
    method: "POST",
    body: JSON.stringify({ query, filters }),
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
// Pipeline API
// ============================================================

export async function runPipeline(projectId: string): Promise<ApiResponse<Record<string, unknown>>> {
  return apiFetch<Record<string, unknown>>(`/api/v1/agents/pipeline/${projectId}`, {
    method: "POST",
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
    const res = await fetch(url, { method: "POST", body: formData });
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
// Admin: Import API
// ============================================================

export async function importCases(file: File, projectId?: string): Promise<ApiResponse<ImportResult>> {
  const params: Record<string, string> = {};
  if (projectId) params.project_id = projectId;
  return importFromFile("/api/v1/cases/import", file, params);
}

export async function importSOPWorkflows(file: File): Promise<ApiResponse<ImportResult>> {
  return importFromFile("/api/v1/workflows/import", file);
}

export async function importProposalTemplates(file: File): Promise<ApiResponse<ImportResult>> {
  return importFromFile("/api/v1/templates/proposals/import", file);
}

export async function importPromptTemplates(file: File): Promise<ApiResponse<ImportResult>> {
  return importFromFile("/api/v1/templates/prompts/import", file);
}

export async function importVisualStyles(file: File): Promise<ApiResponse<ImportResult>> {
  return importFromFile("/api/v1/visual-styles/import", file);
}

export async function importTechnicalRules(file: File): Promise<ApiResponse<ImportResult>> {
  return importFromFile("/api/v1/rules/technical/import", file);
}

export async function importQualityRules(file: File): Promise<ApiResponse<ImportResult>> {
  return importFromFile("/api/v1/rules/quality/import", file);
}

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
