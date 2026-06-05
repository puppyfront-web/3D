// ============================================================
// Core type definitions for the 3D proposal platform
// ============================================================

// --- Enums & Status ---

export type ProjectStatus =
  | "draft"
  | "in_progress"
  | "company_analysis"
  | "proposal_draft"
  | "visual_design"
  | "review"
  | "approved"
  | "exported"
  | "archived";

export type Priority = "high" | "medium" | "low";

export type ReviewStatus = "pass" | "warning" | "fail" | "pending";

export type AssetType = "image" | "video" | "document" | "template" | "model";

export type SOPStepStatus = "pending" | "running" | "completed" | "skipped" | "failed";

// --- Project ---

export interface Project {
  id: string;
  name: string;
  client: string;
  industry: string;
  status: ProjectStatus;
  priority: Priority;
  createdAt: string;
  updatedAt: string;
  dueDate: string;
  description: string;
  progress: number;
  assignee: string;
  tags: string[];
}

// --- Company Analysis ---

export interface CompanyAnalysis {
  companyId: string;
  projectName: string;
  companyName: string;
  industry: string;
  overview: string;
  businessModel: string;
  competitiveAnalysis: CompetitiveItem[];
  financialHighlights: FinancialItem[];
  technologyAssessment: string;
  risks: RiskItem[];
  recommendations: string[];
  generatedAt: string;
}

export interface CompetitiveItem {
  competitor: string;
  strength: string;
  weakness: string;
  marketShare: string;
}

export interface FinancialItem {
  metric: string;
  value: string;
  trend: "up" | "down" | "stable";
  year: string;
}

export interface RiskItem {
  category: string;
  description: string;
  severity: "high" | "medium" | "low";
  mitigation: string;
}

// --- Proposal ---

export interface ProposalSection {
  id: string;
  title: string;
  content: string;
  order: number;
  status: "draft" | "review" | "approved";
}

export interface Proposal {
  id: string;
  projectId: string;
  title: string;
  sections: ProposalSection[];
  totalWords: number;
  lastEditedAt: string;
  version: number;
}

// --- Visual ---

export interface VisualProject {
  id: string;
  projectId: string;
  name: string;
  prompt: string;
  style: string;
  size: string;
  images: VisualImage[];
  createdAt: string;
}

export interface VisualImage {
  id: string;
  url: string;
  prompt: string;
  status: "generating" | "completed" | "failed";
  createdAt: string;
}

// --- Review ---

export interface ReviewChecklist {
  id: string;
  category: string;
  items: ReviewChecklistItem[];
}

export interface ReviewChecklistItem {
  id: string;
  description: string;
  status: ReviewStatus;
  comment: string;
}

// --- Admin: Asset ---

export interface Asset {
  id: string;
  name: string;
  type: AssetType;
  category: string;
  url: string;
  size: string;
  uploadedAt: string;
  uploadedBy: string;
  tags: string[];
}

// --- Admin: Case ---

export interface CaseItem {
  id: string;
  title: string;
  client: string;
  industry: string;
  outcome: string;
  highlights: string[];
  createdAt: string;
  status: "published" | "draft" | "archived";
}

// --- Admin: SOP Workflow ---

export interface SOPWorkflow {
  id: string;
  name: string;
  description: string;
  steps: SOPStep[];
  category: string;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface SOPStep {
  id: string;
  name: string;
  description: string;
  order: number;
  agentType: string;
  estimatedTime: string;
  requiredInputs: string[];
  outputs: string[];
}

// --- Admin: Template ---

export interface ProposalTemplate {
  id: string;
  name: string;
  category: string;
  industry: string;
  sections: TemplateSection[];
  description: string;
  usageCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface TemplateSection {
  id: string;
  title: string;
  defaultContent: string;
  required: boolean;
}

export interface PromptTemplate {
  id: string;
  name: string;
  category: string;
  prompt: string;
  variables: PromptVariable[];
  description: string;
  usageCount: number;
  createdAt: string;
}

export interface PromptVariable {
  name: string;
  description: string;
  defaultValue: string;
  required: boolean;
}

// --- Admin: Visual Style ---

export interface VisualStyle {
  id: string;
  name: string;
  description: string;
  previewUrl: string;
  parameters: Record<string, string>;
  category: string;
  isActive: boolean;
  createdAt: string;
}

// --- Admin: Rules ---

export interface TechnicalRule {
  id: string;
  name: string;
  category: string;
  description: string;
  rule: string;
  severity: "critical" | "warning" | "info";
  isActive: boolean;
  createdAt: string;
}

export interface QualityRule {
  id: string;
  name: string;
  category: string;
  description: string;
  criteria: QualityCriteria[];
  passingScore: number;
  isActive: boolean;
  createdAt: string;
}

export interface QualityCriteria {
  id: string;
  description: string;
  weight: number;
  scoringGuide: string;
}

// --- Admin: Evaluation ---

export interface Evaluation {
  id: string;
  projectId: string;
  projectName: string;
  evaluatedAt: string;
  evaluator: string;
  overallScore: number;
  categories: EvaluationCategory[];
  status: "pending" | "completed" | "disputed";
}

export interface EvaluationCategory {
  name: string;
  score: number;
  maxScore: number;
  comments: string;
}

// --- Wizard ---

export interface ProjectWizardData {
  step1: {
    projectName: string;
    clientName: string;
    industry: string;
    projectType: string;
    description: string;
    priority: Priority;
    dueDate: string;
  };
  step2: {
    companyWebsite: string;
    companyDescription: string;
    competitors: string;
    targetMarket: string;
    existingMaterials: boolean;
    materialLinks: string;
  };
  step3: {
    proposalStyle: string;
    language: string;
    toneOfVoice: string;
    keySellingPoints: string;
    requiredSections: string[];
    additionalRequirements: string;
  };
  step4: {
    visualStyle: string;
    colorScheme: string;
    imageStyle: string;
    brandGuidelines: string;
    numberOfImages: number;
    resolutions: string[];
  };
  step5: {
    qualityLevel: string;
    reviewCriteria: string[];
    autoExport: boolean;
    exportFormats: string[];
    notifyEmail: string;
  };
}

// --- API Response ---

export interface ApiResponse<T> {
  data: T;
  success: boolean;
  message?: string;
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  total: number;
  page: number;
  pageSize: number;
}

// --- Navigation ---

export interface NavItem {
  label: string;
  href: string;
  icon: string;
  badge?: string;
  children?: NavItem[];
}
