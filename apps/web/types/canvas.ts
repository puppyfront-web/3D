// Canvas workspace types — mirror the backend canvas schemas
// (app/schemas/canvas.py). Backend serializes snake_case → camelCase via
// APIBaseModel's alias_generator, so frontend fields are camelCase.

export type NodeStatus = "draft" | "filling" | "filled" | "pending_review";
export type SourceType =
  | "uploaded_file"
  | "conversation"
  | "internal_sop"
  | "internal_case"
  | "internal_template"
  | "internal_ui"
  | "web_search"
  | "ai_completed"
  | "pending_user";
export type Confidence = "high" | "medium" | "low";

// ─── Node sources (provenance) ───────────────────────────────────────────────

export interface NodeSource {
  id: string;
  sourceType: SourceType;
  sourceRefId?: string;
  sourceName?: string;
  confidence?: Confidence;
  quote?: string;
  metadataJson?: Record<string, unknown>;
  createdAt: string;
}

// ─── Node content skeleton (matches canvas_service default topology) ─────────

export interface NodeContent {
  extracted: string[];
  planning: string[];
  uiSuggestion: string[];
  pendingQuestions: string[];
}

// ─── Canvas nodes ────────────────────────────────────────────────────────────

export interface CanvasNode {
  id: string;
  canvasId: string;
  groupId?: string;
  nodeKey?: string;
  title: string;
  nodeType: string;
  status: NodeStatus | string;
  priority?: string;
  position?: { x: number; y: number };
  content?: NodeContent;
  sources?: NodeSource[];
  createdAt: string;
  updatedAt: string;
}

// ─── Canvas groups (the three boards) ────────────────────────────────────────

export interface CanvasGroup {
  id: string;
  canvasId: string;
  groupKey: string;
  title: string;
  description?: string;
  position?: { x: number; y: number };
  style?: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

// ─── Canvas edges ────────────────────────────────────────────────────────────

export interface CanvasEdge {
  id: string;
  canvasId: string;
  sourceNodeId: string;
  targetNodeId: string;
  edgeType?: string;
  label?: string;
  metadataJson?: Record<string, unknown>;
  createdAt: string;
}

// ─── Canvas aggregate ────────────────────────────────────────────────────────

export interface Canvas {
  id: string;
  projectVersionId: string;
  viewport?: { x: number; y: number; zoom?: number };
  layoutConfig?: Record<string, unknown>;
  groups: CanvasGroup[];
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  createdAt: string;
  isReadOnly: boolean;
}

// ─── Project versions ────────────────────────────────────────────────────────

export interface ProjectVersion {
  id: string;
  projectId: string;
  versionNo: number;
  versionName?: string;
  changeSummary?: string;
  basedOnVersionId?: string;
  isCurrent: boolean;
  createdBy?: string;
  createdAt: string;
  // Related knowledge assets used by this version (PRD §16.3 / §23.6).
  relatedMaterials?: string[];
  relatedInternalAssets?: {
    internal_sop?: string[];
    internal_case?: string[];
    internal_template?: string[];
    internal_ui?: string[];
  };
  /** Per-node diff vs the prior version (PRD §16.3 变更节点). */
  changedNodes?: Array<{
    nodeKey?: string;
    title?: string;
    change?: "added" | "removed" | "content" | "status" | "title";
  }>;
}

// ─── API response wrapper (matches backend Response[T]) ──────────────────────

export interface ApiResponse<T> {
  success: boolean;
  message?: string;
  data: T;
}

export interface VersionRestoreResult {
  newVersion: ProjectVersion;
  message: string;
}
