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

export type AssetStatus = "pending" | "uploaded" | "indexed" | "error";

export type SOPStepStatus = "pending" | "running" | "completed" | "skipped" | "failed";

// --- Project ---

export interface Project {
  id: string;
  name: string;
  client?: string;
  companyId?: string;
  industry?: string;
  status: ProjectStatus;
  priority?: Priority;
  createdAt: string;
  updatedAt: string;
  dueDate?: string;
  description?: string;
  progress?: number;
  assignee?: string;
  tags?: string[];
}

// --- Company Analysis ---

// ── Enterprise Six Views ──

export interface SixViews {
  backward_history?: Record<string, string>;
  forward_planning?: Record<string, string>;
  left_competitors?: { benchmark_companies?: string[]; differentiation?: string };
  right_industry?: Record<string, string>;
  upward_policy?: Record<string, string>;
  downward_niche?: Record<string, string>;
}

// ── Technology Architecture ──

export interface TechnologyLayer {
  name: string;
  level: "top" | "middle" | "bottom";
  description: string;
  metaphor: string;
}

export interface TechnologyArchitecture {
  layers: TechnologyLayer[];
  core_technology_summary: string;
  visual_metaphor: string;
}

// ── Project Background ──

export interface BackgroundLevel {
  title: string;
  content: string;
}

export interface ProjectBackground {
  national_policy?: BackgroundLevel;
  city_or_industry?: BackgroundLevel;
  project_positioning?: BackgroundLevel;
}

// ── Material & Lighting Specs ──

export interface MaterialCategory {
  name: string;
  description: string;
  coverage: string;
}

export interface MaterialSpec {
  style: string;
  categories: MaterialCategory[];
}

export interface ColorTemperature {
  range: string;
  description: string;
}

export interface LightingLayer {
  type: "ambient" | "task" | "accent";
  description: string;
}

export interface LightingSpec {
  overall_atmosphere: string;
  color_temperature?: ColorTemperature;
  lighting_layers: LightingLayer[];
  fixture_style: string;
}

// ── Reference Image ──

export interface ReferenceImage {
  url: string;
  caption: string;
  photo_type:
    | "product_experience"
    | "brand_exhibition"
    | "space_design"
    | "technology_showcase"
    | "outdoor_installation";
  style_label: string;
  description: string;
}

// ── Pipeline Stage ──

export interface PipelineStage {
  stage: string;
  name: string;
  description: string;
}

// ── SOP Step Rule & Prompt ──

export interface SOPStepRule {
  type: "general" | "custom";
  description: string;
}

export interface SOPStepPrompt {
  number: number;
  question: string;
  purpose: string;
}

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
  // Enriched structured data
  sixViews?: SixViews;
  technologyArch?: TechnologyArchitecture;
  projectBackground?: ProjectBackground;
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
  file_size: number;
  project_id: string | null;
  status: AssetStatus;
  chunk_count: number;
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
  referenceImages?: ReferenceImage[];
}

// --- Admin: SOP Workflow ---

export interface SOPWorkflow {
  id: string;
  name: string;
  description: string;
  steps: SOPStep[];
  pipelineStages?: PipelineStage[];
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
  stage?: string;
  rules?: SOPStepRule[];
  prompts?: SOPStepPrompt[];
  dependencies?: string[];
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
  materialSpec?: MaterialSpec;
  lightingSpec?: LightingSpec;
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

// --- Skill System ---

export interface SkillManifest {
  skill_id: string;
  name: string;
  description?: string;
  category: string;
  input_schema?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
  required_services?: string[];
  permissions?: string[];
  visibility: string;
  version: string;
}

export interface SkillExecution {
  id: string;
  skill_id: string;
  project_id?: string;
  user_id?: string;
  input_json?: Record<string, unknown>;
  output_json?: Record<string, unknown>;
  status: string;
  error_message?: string;
  duration_ms?: number;
  used_cases?: string[];
  used_documents?: string[];
  used_chunks?: string[];
  created_at?: string;
  completed_at?: string;
}

export interface Artifact {
  id: string;
  type: "report" | "document" | "image" | "prompt";
  title: string;
  content: string;
  mimeType: string;
  url?: string;
  createdAt: string;
}

// --- Chat / Conversation ---

export interface Conversation {
  id: string;
  projectId?: string;
  title: string;
  status: "active" | "archived";
  lastMessage?: ChatMessage;
  messageCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface ConversationDetail extends Conversation {
  messages: ChatMessage[];
}

export interface ChatMessage {
  id: string;
  conversationId: string;
  role: "user" | "assistant" | "system";
  content: string;
  contentType: "text" | "rich";
  richContent?: RichContent;
  skillExecutionId?: string;
  metadata?: Record<string, unknown>;
  createdAt: string;
}

export interface RichContent {
  blocks: ContentBlock[];
}

export interface ContentBlock {
  type:
    | "text"
    | "company_analysis_card"
    | "proposal_section"
    | "visual_result"
    | "visual_strategy"
    | "quality_check"
    | "skill_progress"
    | "skill_executing"
    | "artifact"
    | "attachment"
    | "form"
    | "action_buttons"
    | "context_card"
    | "parameter_card"
    | "stage_summary";
  content?: string;
  data?: Record<string, unknown>;
}

export interface StreamChunk {
  type:
    | "text_delta"
    | "content_block_start"
    | "content_block_data"
    | "content_block_end"
    | "done"
    | "error";
  text?: string;
  data?: Record<string, unknown>;
}

// ── Visual Concept ──────────────────────────────────────

export interface VisualRequirement {
  raw_input: string;
  scene?: string;
  screen_type?: string;
  brand_or_theme?: string;
  visual_style?: string;
  color_tone?: string;
  target_audience?: string;
  key_elements: string[];
  constraints?: string;
  reference_case_ids: string[];
}

export interface VersionNode {
  node_id: string;
  parent_id?: string;
  branch_id: string;
  version_label: string;
  requirement_snapshot: Record<string, unknown>;
  visual_strategy?: Record<string, unknown>;
  positive_prompt?: string;
  negative_prompt?: string;
  prompt_template_used?: string;
  image_url?: string;
  image_metadata?: Record<string, unknown>;
  quality_check?: QualityCheckItem[];
  rag_citations: Citation[];
  status: "completed" | "active" | "abandoned";
  children_ids: string[];
  trigger: "initial" | "modify" | "branch" | "rollback";
  user_instruction?: string;
  created_at: string;
  completed_at?: string;
}

export interface QualityCheckItem {
  item: string;
  status: "✅" | "⚠️";
  note: string;
}

export interface Citation {
  type: "case" | "document_chunk" | "prompt_template" | "technical_rule";
  id: string;
  title?: string;
  score?: number;
}

export interface BranchMeta {
  branch_id: string;
  branch_name: string;
  root_node_id: string;
  current_node_id: string;
  status: "active" | "merged" | "abandoned";
  created_at: string;
}

export interface VersionTree {
  nodes: Record<string, VersionNode>;
  root_id: string;
  active_branch: string;
  branches: Record<string, BranchMeta>;
}

export interface VisualConceptState {
  isActive: boolean;
  agentState: "COLLECTING" | "PLANNING" | "PROMPTING" | "GENERATING" | "REVIEWING" | "COMPLETED";
  requirement: VisualRequirement | null;
  versionTree: VersionTree | null;
  currentBranchId: string;
  currentNodeId: string | null;
  currentImageUrl: string | null;
  qualityCheck: QualityCheckItem[] | null;
}

// --- Document Indexing ---

export interface DocumentIndexResponse {
  document_id: string;
  status: string;
  chunk_count: number;
  message: string;
}

export interface DocumentBatchIndexResponse {
  total: number;
  indexed: number;
  failed: number;
  total_chunks: number;
  message: string;
}

// --- Import ---

export interface ImportResult {
  imported: number;
  failed: number;
  errors: string[];
  message: string;
}
