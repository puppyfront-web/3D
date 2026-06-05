import {
  Project,
  CompanyAnalysis,
  Proposal,
  VisualProject,
  ReviewChecklist,
  Asset,
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
} from "@/types";
import {
  mockProjects,
  mockCompanyAnalysis,
  mockProposal,
  mockVisualProjects,
  mockReviewChecklists,
  mockAssets,
  mockCases,
  mockSOPWorkflows,
  mockProposalTemplates,
  mockPromptTemplates,
  mockVisualStyles,
  mockTechnicalRules,
  mockQualityRules,
  mockEvaluations,
} from "./mock-data";

// ============================================================
// API Configuration
// ============================================================

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
// Default to real API; set NEXT_PUBLIC_USE_MOCK=true for offline development
const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === "true";

// Simulated API delay for mock mode
const delay = (ms: number = 300) => new Promise((resolve) => setTimeout(resolve, ms));

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
  if (USE_MOCK) {
    await delay();
    return { data: mockProjects, success: true };
  }
  return apiFetch<Project[]>("/api/v1/projects");
}

export async function getProjectById(id: string): Promise<ApiResponse<Project | undefined>> {
  if (USE_MOCK) {
    await delay();
    const project = mockProjects.find((p) => p.id === id);
    return { data: project, success: !!project };
  }
  return apiFetch<Project>(`/api/v1/projects/${id}`);
}

export async function createProject(data: ProjectWizardData): Promise<ApiResponse<Project>> {
  if (USE_MOCK) {
    await delay(500);
    const newProject: Project = {
      id: `proj-${String(mockProjects.length + 1).padStart(3, "0")}`,
      name: data.step1.projectName,
      client: data.step1.clientName,
      industry: data.step1.industry,
      status: "draft",
      priority: data.step1.priority,
      createdAt: new Date().toISOString().split("T")[0],
      updatedAt: new Date().toISOString().split("T")[0],
      dueDate: data.step1.dueDate,
      description: data.step1.description,
      progress: 0,
      assignee: "当前用户",
      tags: [],
    };
    return { data: newProject, success: true, message: "项目创建成功" };
  }
  return apiFetch<Project>("/api/v1/projects", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ============================================================
// Company Analysis API
// ============================================================

export async function getCompanyAnalysis(projectId: string): Promise<ApiResponse<CompanyAnalysis>> {
  if (USE_MOCK) {
    await delay();
    return { data: mockCompanyAnalysis, success: true };
  }
  return apiFetch<CompanyAnalysis>(`/api/v1/company-profiles/by-company/${projectId}`);
}

export async function updateCompanyAnalysis(
  projectId: string,
  data: Partial<CompanyAnalysis>
): Promise<ApiResponse<CompanyAnalysis>> {
  if (USE_MOCK) {
    await delay();
    return { data: { ...mockCompanyAnalysis, ...data }, success: true, message: "企业分析更新成功" };
  }
  return apiFetch<CompanyAnalysis>(`/api/v1/company-profiles/${projectId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function generateCompanyAnalysis(companyId: string): Promise<ApiResponse<CompanyAnalysis>> {
  if (USE_MOCK) {
    await delay(2000);
    return { data: mockCompanyAnalysis, success: true, message: "企业分析生成成功" };
  }
  return apiFetch<CompanyAnalysis>(`/api/v1/agents/company-analysis/${companyId}`, {
    method: "POST",
  });
}

// ============================================================
// Proposal API
// ============================================================

export async function getProposal(projectId: string): Promise<ApiResponse<Proposal>> {
  if (USE_MOCK) {
    await delay();
    return { data: mockProposal, success: true };
  }
  return apiFetch<Proposal>(`/api/v1/generations/tasks?project_id=${projectId}`);
}

export async function updateProposalSection(
  proposalId: string,
  sectionId: string,
  content: string
): Promise<ApiResponse<Proposal>> {
  if (USE_MOCK) {
    await delay();
    const updated = {
      ...mockProposal,
      sections: mockProposal.sections.map((s) =>
        s.id === sectionId ? { ...s, content } : s
      ),
    };
    return { data: updated, success: true, message: "章节内容已更新" };
  }
  return apiFetch<Proposal>(`/api/v1/generations/outputs/${proposalId}`, {
    method: "PUT",
    body: JSON.stringify({ section_id: sectionId, content }),
  });
}

export async function generateProposal(projectId: string): Promise<ApiResponse<Proposal>> {
  if (USE_MOCK) {
    await delay(3000);
    return { data: mockProposal, success: true, message: "策划案生成成功" };
  }
  return apiFetch<Proposal>("/api/v1/agents/proposal", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId }),
  });
}

// ============================================================
// Visual API
// ============================================================

export async function getVisualProjects(projectId: string): Promise<ApiResponse<VisualProject[]>> {
  if (USE_MOCK) {
    await delay();
    return { data: mockVisualProjects, success: true };
  }
  return apiFetch<VisualProject[]>(`/api/v1/generations/tasks?project_id=${projectId}&type=visual`);
}

export async function generateVisualImage(
  projectId: string,
  prompt: string,
  style: string
): Promise<ApiResponse<VisualProject>> {
  if (USE_MOCK) {
    await delay(2000);
    const newProject: VisualProject = {
      id: `vp-${Date.now()}`,
      projectId,
      name: "新生成任务",
      prompt,
      style,
      size: "1920x1080",
      images: [
        {
          id: `img-${Date.now()}`,
          url: "/placeholder-visual-new.jpg",
          prompt,
          status: "completed",
          createdAt: new Date().toISOString(),
        },
      ],
      createdAt: new Date().toISOString(),
    };
    return { data: newProject, success: true, message: "图片生成成功" };
  }
  return apiFetch<VisualProject>("/api/v1/agents/visual-prompt", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, prompt, style }),
  });
}

// ============================================================
// Review API
// ============================================================

export async function getReviewChecklists(projectId: string): Promise<ApiResponse<ReviewChecklist[]>> {
  if (USE_MOCK) {
    await delay();
    return { data: mockReviewChecklists, success: true };
  }
  return apiFetch<ReviewChecklist[]>(`/api/v1/generations/tasks?project_id=${projectId}&type=review`);
}

// ============================================================
// Exports API
// ============================================================

export async function exportToWord(taskId: string): Promise<ApiResponse<{ file_path: string }>> {
  if (USE_MOCK) {
    await delay(1000);
    return { data: { file_path: `/exports/proposal-${taskId}.docx` }, success: true, message: "Word 导出成功" };
  }
  return apiFetch<{ file_path: string }>(`/api/v1/exports/word/${taskId}`, { method: "POST" });
}

export async function exportToPdf(taskId: string): Promise<ApiResponse<{ file_path: string }>> {
  if (USE_MOCK) {
    await delay(1000);
    return { data: { file_path: `/exports/proposal-${taskId}.pdf` }, success: true, message: "PDF 导出成功" };
  }
  return apiFetch<{ file_path: string }>(`/api/v1/exports/pdf/${taskId}`, { method: "POST" });
}

// ============================================================
// Admin: Assets API
// ============================================================

export async function getAssets(): Promise<ApiResponse<Asset[]>> {
  if (USE_MOCK) {
    await delay();
    return { data: mockAssets, success: true };
  }
  return apiFetch<Asset[]>("/api/v1/documents");
}

export async function uploadAsset(file: File): Promise<ApiResponse<Asset>> {
  if (USE_MOCK) {
    await delay(1000);
    return { data: { id: `asset-${Date.now()}`, name: file.name, type: file.type, size: `${(file.size / 1024).toFixed(1)} KB`, uploadedAt: new Date().toISOString(), status: "ready", category: "document", url: "", uploadedBy: "当前用户", tags: [] } as Asset, success: true, message: "文件上传成功" };
  }
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE_URL}/api/v1/documents/upload`, { method: "POST", body: formData });
  const json = await res.json();
  return { data: json, success: res.ok };
}

export async function deleteAsset(id: string): Promise<ApiResponse<null>> {
  if (USE_MOCK) {
    await delay();
    return { data: null, success: true, message: "资产已删除" };
  }
  return apiFetch<null>(`/api/v1/documents/${id}`, { method: "DELETE" });
}

// ============================================================
// Admin: Cases API
// ============================================================

export async function getCases(): Promise<ApiResponse<CaseItem[]>> {
  if (USE_MOCK) {
    await delay();
    return { data: mockCases, success: true };
  }
  return apiFetch<CaseItem[]>("/api/v1/cases");
}

export async function createCase(data: Partial<CaseItem>): Promise<ApiResponse<CaseItem>> {
  if (USE_MOCK) {
    await delay();
    return { data: data as CaseItem, success: true, message: "案例创建成功" };
  }
  return apiFetch<CaseItem>("/api/v1/cases", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateCase(id: string, data: Partial<CaseItem>): Promise<ApiResponse<CaseItem>> {
  if (USE_MOCK) {
    await delay();
    return { data: { ...data, id } as CaseItem, success: true, message: "案例更新成功" };
  }
  return apiFetch<CaseItem>(`/api/v1/cases/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteCase(id: string): Promise<ApiResponse<null>> {
  if (USE_MOCK) {
    await delay();
    return { data: null, success: true, message: "案例已删除" };
  }
  return apiFetch<null>(`/api/v1/cases/${id}`, { method: "DELETE" });
}

// ============================================================
// Admin: SOP Workflows API
// ============================================================

export async function getSOPWorkflows(): Promise<ApiResponse<SOPWorkflow[]>> {
  if (USE_MOCK) {
    await delay();
    return { data: mockSOPWorkflows, success: true };
  }
  return apiFetch<SOPWorkflow[]>("/api/v1/workflows");
}

export async function createSOPWorkflow(data: Partial<SOPWorkflow>): Promise<ApiResponse<SOPWorkflow>> {
  if (USE_MOCK) {
    await delay();
    return { data: data as SOPWorkflow, success: true, message: "SOP 创建成功" };
  }
  return apiFetch<SOPWorkflow>("/api/v1/workflows", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ============================================================
// Admin: Templates API
// ============================================================

export async function getProposalTemplates(): Promise<ApiResponse<ProposalTemplate[]>> {
  if (USE_MOCK) {
    await delay();
    return { data: mockProposalTemplates, success: true };
  }
  return apiFetch<ProposalTemplate[]>("/api/v1/templates/proposals");
}

export async function getPromptTemplates(): Promise<ApiResponse<PromptTemplate[]>> {
  if (USE_MOCK) {
    await delay();
    return { data: mockPromptTemplates, success: true };
  }
  return apiFetch<PromptTemplate[]>("/api/v1/templates/prompts");
}

export async function createPromptTemplate(data: Partial<PromptTemplate>): Promise<ApiResponse<PromptTemplate>> {
  if (USE_MOCK) {
    await delay();
    return { data: data as PromptTemplate, success: true, message: "Prompt 模板创建成功" };
  }
  return apiFetch<PromptTemplate>("/api/v1/templates/prompts", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ============================================================
// Admin: Visual Styles API
// ============================================================

export async function getVisualStyles(): Promise<ApiResponse<VisualStyle[]>> {
  if (USE_MOCK) {
    await delay();
    return { data: mockVisualStyles, success: true };
  }
  return apiFetch<VisualStyle[]>("/api/v1/visual-styles");
}

// ============================================================
// Admin: Rules API
// ============================================================

export async function getTechnicalRules(): Promise<ApiResponse<TechnicalRule[]>> {
  if (USE_MOCK) {
    await delay();
    return { data: mockTechnicalRules, success: true };
  }
  return apiFetch<TechnicalRule[]>("/api/v1/rules/technical");
}

export async function getQualityRules(): Promise<ApiResponse<QualityRule[]>> {
  if (USE_MOCK) {
    await delay();
    return { data: mockQualityRules, success: true };
  }
  return apiFetch<QualityRule[]>("/api/v1/rules/quality");
}

// ============================================================
// Admin: Evaluations API
// ============================================================

export async function getEvaluations(): Promise<ApiResponse<Evaluation[]>> {
  if (USE_MOCK) {
    await delay();
    return { data: mockEvaluations, success: true };
  }
  return apiFetch<Evaluation[]>("/api/v1/generations/tasks?type=evaluation");
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
  if (USE_MOCK) {
    await delay();
    return { data: null, success: true, message: "反馈已提交" };
  }
  return apiFetch<null>("/api/v1/feedback", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ============================================================
// RAG Search API
// ============================================================

export async function searchKnowledge(query: string, filters?: Record<string, string>): Promise<ApiResponse<unknown>> {
  if (USE_MOCK) {
    await delay(500);
    return { data: { results: mockCases.slice(0, 3), total: 3 }, success: true };
  }
  return apiFetch("/api/v1/rag/search", {
    method: "POST",
    body: JSON.stringify({ query, filters }),
  });
}

// ============================================================
// Skills API
// ============================================================

export async function getSkills(): Promise<ApiResponse<SkillManifest[]>> {
  if (USE_MOCK) {
    await delay();
    return {
      data: [
        { skill_id: "company_analysis", name: "企业解析", description: "分析企业画像", category: "analysis", visibility: "internal", version: "1.0.0" },
        { skill_id: "case_retrieval", name: "案例检索", description: "检索匹配案例", category: "retrieval", visibility: "internal", version: "1.0.0" },
        { skill_id: "proposal_generation", name: "策划案生成", description: "生成策划案初稿", category: "proposal", visibility: "internal", version: "1.0.0" },
        { skill_id: "visual_prompt", name: "视觉 Prompt", description: "生成视觉策略和 Prompt", category: "visual", visibility: "internal", version: "1.0.0" },
        { skill_id: "image_generation", name: "图片生成", description: "调用图片生成服务", category: "visual", visibility: "internal", version: "1.0.0" },
        { skill_id: "export", name: "方案导出", description: "导出为 Word/PDF", category: "export", visibility: "internal", version: "1.0.0" },
      ],
      success: true,
    };
  }
  return apiFetch<SkillManifest[]>("/api/v1/skills");
}

export async function executeSkill(
  skillId: string,
  inputData: Record<string, unknown>,
  projectId?: string,
): Promise<ApiResponse<Record<string, unknown>>> {
  if (USE_MOCK) {
    await delay(2000);
    return { data: { success: true, output: {} }, success: true, message: "Skill 执行完成" };
  }
  return apiFetch<Record<string, unknown>>(`/api/v1/skills/${skillId}/execute`, {
    method: "POST",
    body: JSON.stringify({ input_data: inputData, project_id: projectId }),
  });
}

// ============================================================
// Pipeline API
// ============================================================

export async function runPipeline(projectId: string): Promise<ApiResponse<Record<string, unknown>>> {
  if (USE_MOCK) {
    await delay(5000);
    return {
      data: {
        company_analysis: { success: true },
        proposal_generation: { success: true },
        visual_prompt: { success: true },
      },
      success: true,
      message: "Pipeline completed",
    };
  }
  return apiFetch<Record<string, unknown>>(`/api/v1/agents/pipeline/${projectId}`, {
    method: "POST",
  });
}
