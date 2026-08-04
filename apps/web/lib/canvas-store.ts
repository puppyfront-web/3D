"use client";

// Canvas store — zustand store for local canvas editing state.
//
// Holds the React-Flow-compatible nodes/edges plus the originating domain
// objects (groups, canvasNodes) so the workspace can render board sections
// and route node clicks to detail drawers. Server state is fetched via
// lib/canvas-api (react-query in phase 2); this store owns the optimistic
// in-memory edits (drag, fold) that haven't been promoted to a version yet.
//
// React Flow v12 (@xyflow/react) uses { id, type, position, data } nodes and
// { id, source, target } edges — we adapt our domain CanvasNode into that
// shape via RFNode / RFEdge.

import { create } from "zustand";
import type {
  Connection,
  Edge,
  EdgeChange,
  Node,
  NodeChange,
} from "@xyflow/react";

import type { CanvasGroup, CanvasNode } from "@/types/canvas";
import { SECTION_HEADER_STYLE } from "@/lib/design-tokens";
import { persistNodePositions } from "@/lib/canvas-api";
import type { SectionHeaderRFNode } from "@/components/canvas/section-header-node";

// Debounced drag persistence — node ids whose positions changed and need to be
// flushed to the backend. Coalesces rapid drag events into a single batch.
let _dirtyNodeIds = new Set<string>();
let _persistTimer: ReturnType<typeof setTimeout> | null = null;

// ─── 方案定调 (PRD §13.4) — synthesised by the 方案定调 Agent and stored on
// the canvas's layoutConfig.tone. Optional: present only after the AI-fill
// chain has produced a tone; the ToneCard hides itself otherwise.
export interface ProjectTone {
  themeName?: string;
  styleKeywords?: string[];
  narrativeSpine?: string;
  visualTone?: string;
  infoHierarchy?: string[];
  presentationRhythm?: string;
  keyModules?: string[];
  uiPrinciples?: string[];
}

// ─── React-Flow-shaped adapters ──────────────────────────────────────────────

export type RFNode = Node<{
  /** Domain canvas node id (UUID) — preserved so detail drawers can query. */
  domainId: string;
  title: string;
  status: string;
  nodeKey?: string;
  groupId?: string;
  /** Board group key — drives the three-colour palette (blue/green/orange). */
  groupKey?: string;
  sourceCount: number;
  /** First planning item, truncated — shown as a content preview on the card
      so users can see at a glance whether a node has been filled. */
  preview?: string;
  /** Number of planning items — "N 条内容" indicator. */
  planningCount?: number;
}>;

export type RFEdge = Edge;

interface CanvasStoreState {
  // Domain layer (for rendering board sections + detail drawers)
  groups: CanvasGroup[];
  canvasNodes: CanvasNode[];

  // React Flow layer (what <ReactFlow/> actually renders). Includes both module
  // nodes and synthesised section-header label nodes.
  rfNodes: (RFNode | SectionHeaderRFNode)[];
  rfEdges: RFEdge[];

  // Loading / read-only flags
  isLoading: boolean;
  isReadOnly: boolean;
  activeProjectId: string | null;
  currentVersionId: string | null;

  // Selected node (drives NodeDetailDrawer)
  selectedNodeId: string | null;

  // The node the left-rail conversation is currently bound to. null = project-
  // level global conversation; non-null = node-scoped conversation whose AI
  // replies are constrained to that single node. Decoupled from selectedNodeId
  // (clicking a node opens the drawer but does NOT force-switch the chat) —
  // the page wires the two together based on UX intent.
  conversationNodeId: string | null;

  // 方案定调 (project tone) — from layoutConfig.tone. null when the AI-fill
  // chain hasn't produced a tone yet (or for read-only historical versions
  // that predate the tone agent).
  tone: ProjectTone | null;

  // ─── actions ───
  hydrate: (input: {
    projectId: string;
    versionId: string;
    groups: CanvasGroup[];
    nodes: CanvasNode[];
    edges: { id: string; sourceNodeId: string; targetNodeId: string }[];
    isReadOnly: boolean;
    tone?: ProjectTone | null;
    /** When true, preserve selectedNodeId/conversationNodeId across the hydrate
     *  (used after a node-content save that promotes a new version, so the
     *  detail drawer stays open instead of snapping shut). */
    keepSelection?: boolean;
  }) => void;
  selectNode: (id: string | null) => void;
  setConversationNode: (id: string | null) => void;
  onNodesChange: (changes: NodeChange[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;
  reset: () => void;
}

function toRFEdge(e: {
  id: string;
  sourceNodeId: string;
  targetNodeId: string;
}): RFEdge {
  return {
    id: e.id,
    source: e.sourceNodeId,
    target: e.targetNodeId,
    type: "smoothstep",
  };
}

export const useCanvasStore = create<CanvasStoreState>((set, get) => ({
  groups: [],
  canvasNodes: [],
  rfNodes: [],
  rfEdges: [],
  isLoading: false,
  isReadOnly: false,
  activeProjectId: null,
  currentVersionId: null,
  selectedNodeId: null,
  conversationNodeId: null,
  tone: null,

  hydrate: ({ projectId, versionId, groups, nodes, edges, isReadOnly, tone, keepSelection }) => {
    // Build groupId → groupKey lookup so each node carries its board colour.
    const groupKeyById = new Map<string, string>();
    for (const g of groups) groupKeyById.set(g.id, g.groupKey);

    const buildRFNode = (n: CanvasNode): RFNode => {
      const groupKey = n.groupId ? groupKeyById.get(n.groupId) : undefined;
      // Build a short preview from the planning slot so the card shows whether
      // the node has been filled (and with what), not just the title.
      const planning = n.content?.planning ?? [];
      const firstPlanning = planning[0];
      const preview =
        typeof firstPlanning === "string"
          ? firstPlanning
          : firstPlanning && typeof firstPlanning === "object"
            ? String(
                (firstPlanning as { text?: string; detail?: string; title?: string }).text ??
                (firstPlanning as { detail?: string }).detail ??
                (firstPlanning as { title?: string }).title ??
                "",
              )
            : "";
      return {
        id: n.id,
        type: "moduleNode",
        position: n.position ?? { x: 0, y: 0 },
        data: {
          domainId: n.id,
          title: n.title,
          status: n.status,
          nodeKey: n.nodeKey,
          groupId: n.groupId,
          groupKey,
          sourceCount: n.sources?.length ?? 0,
          preview: preview || undefined,
          planningCount: planning.length || undefined,
        },
      };
    };

    // Synthesise one section-header RF node per board group, positioned at the
    // group's own position (the backend lays these out above the group's nodes).
    // These are visual anchors matching the Stitch design section pills and are
    // excluded from drag/select (draggable:false, selectable:false).
    const sectionHeaders: SectionHeaderRFNode[] = groups
      .map((g): SectionHeaderRFNode | null => {
        const style = SECTION_HEADER_STYLE[g.groupKey];
        if (!style) return null;
        return {
          id: `section-${g.id}`,
          type: "sectionHeader",
          position: g.position ?? { x: 0, y: 0 },
          draggable: false,
          selectable: false,
          data: {
            groupKey: g.groupKey,
            title: g.title,
            index: style.index,
            Icon: style.Icon,
            accent: style.accent,
            tintClass: style.tintClass,
            borderClass: style.borderClass,
          },
        };
      })
      .filter((n): n is SectionHeaderRFNode => n !== null);

    set({
      activeProjectId: projectId,
      currentVersionId: versionId,
      groups,
      canvasNodes: nodes,
      rfNodes: [...sectionHeaders, ...nodes.map(buildRFNode)],
      rfEdges: edges.map(toRFEdge),
      isReadOnly,
      isLoading: false,
      selectedNodeId: keepSelection ? get().selectedNodeId : null,
      conversationNodeId: keepSelection ? get().conversationNodeId : null,
      tone: tone ?? null,
    });
  },

  selectNode: (id) => set({ selectedNodeId: id }),

  setConversationNode: (id) => set({ conversationNodeId: id }),

  onNodesChange: (changes) => {
    // Apply position drag changes to both the RF layer and the domain layer
    // (so a subsequent version snapshot captures the new positions).
    set({
      rfNodes: applyNodeChanges(changes, get().rfNodes),
      canvasNodes: applyDomainNodePositions(changes, get().canvasNodes),
    });
    // Track drag-end position changes and schedule a debounced persist so
    // moved nodes survive a page refresh without forcing a new version.
    if (!get().isReadOnly && !get().isLoading) {
      const moved = changes.filter(
        (c): c is Extract<NodeChange, { type: "position" }> =>
          c.type === "position" && !!c.position,
      );
      if (moved.length) {
        for (const m of moved) _dirtyNodeIds.add(m.id);
        const projectId = get().activeProjectId;
        if (projectId) schedulePersist(projectId, get);
      }
    }
  },

  onEdgesChange: (changes) => {
    set({ rfEdges: applyEdgeChanges(changes, get().rfEdges) });
  },

  onConnect: (connection) => {
    if (!connection.source || !connection.target) return;
    const newEdge: RFEdge = {
      id: `e-${connection.source}-${connection.target}-${Date.now()}`,
      source: connection.source,
      target: connection.target,
      type: "smoothstep",
    };
    set({ rfEdges: [...get().rfEdges, newEdge] });
  },

  reset: () =>
    set({
      groups: [],
      canvasNodes: [],
      rfNodes: [],
      rfEdges: [],
      isLoading: false,
      isReadOnly: false,
      activeProjectId: null,
      currentVersionId: null,
      selectedNodeId: null,
      conversationNodeId: null,
      tone: null,
    }),
}));

// ─── React Flow change appliers (inlined to avoid pulling reactflow internals) ─

/**
 * Schedule a debounced flush of dirty node positions to the backend. Each new
 * drag event resets the timer so we only persist once the user stops dragging
 * for ~1.5s. Best-effort: per-node failures are swallowed inside
 * persistNodePositions. Position changes are also captured by the next version
 * snapshot, so a missed persist here is not data-loss.
 */
function schedulePersist(
  projectId: string,
  getState: () => CanvasStoreState,
): void {
  if (_persistTimer) clearTimeout(_persistTimer);
  _persistTimer = setTimeout(async () => {
    const dirty = Array.from(_dirtyNodeIds);
    _dirtyNodeIds = new Set<string>();
    _persistTimer = null;
    if (!dirty.length) return;
    const positions = dirty
      .map((id) => {
        const node = getState().canvasNodes.find((n) => n.id === id);
        if (!node?.position) return null;
        return { nodeId: id, position: node.position };
      })
      .filter((p): p is { nodeId: string; position: { x: number; y: number } } => p !== null);
    if (positions.length) {
      await persistNodePositions(projectId, positions);
    }
  }, 1500);
}


function applyNodeChanges(
  changes: NodeChange[],
  nodes: (RFNode | SectionHeaderRFNode)[],
): (RFNode | SectionHeaderRFNode)[] {
  // Only position + remove are relevant for the domain side; dimensions/layout
  // measured by RF are ignored. Section-header nodes are non-draggable so RF
  // never emits position changes for them, but they pass through this filter
  // unchanged.
  return nodes.map((n) => {
    const change = changes.find(
      (c): c is Extract<NodeChange, { type: "position" }> =>
        c.type === "position" && c.id === n.id,
    );
    if (change && change.position) {
      return { ...n, position: change.position };
    }
    return n;
  }).filter(
    (n) => !changes.some((c) => c.type === "remove" && c.id === n.id),
  );
}

function applyEdgeChanges(changes: EdgeChange[], edges: RFEdge[]): RFEdge[] {
  return edges.filter(
    (e) => !changes.some((c) => c.type === "remove" && c.id === e.id),
  );
}

function applyDomainNodePositions(
  changes: NodeChange[],
  nodes: CanvasNode[],
): CanvasNode[] {
  return nodes.map((n) => {
    const change = changes.find(
      (c): c is Extract<NodeChange, { type: "position" }> =>
        c.type === "position" && c.id === n.id,
    );
    if (change && change.position) {
      return { ...n, position: change.position };
    }
    return n;
  });
}
