"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useState,
} from "react";
import type {
  VisualConceptState,
  VersionTree,
  QualityCheckItem,
} from "@/types";
import {
  getVersionTree as apiGetVersionTree,
  executeVisualConceptAction,
} from "@/lib/visual-concept-api";
import { toast } from "sonner";

// ─── State ────────────────────────────────────────────────────────

const initialState: VisualConceptState = {
  isActive: false,
  agentState: "COLLECTING",
  requirement: null,
  versionTree: null,
  currentBranchId: "",
  currentNodeId: null,
  currentImageUrl: null,
  qualityCheck: null,
};

// ─── Context ──────────────────────────────────────────────────────

interface VisualConceptContextValue {
  state: VisualConceptState;
  drawerOpen: boolean;
  toggleDrawer: () => void;
  refreshVersionTree: (conversationId: string) => Promise<void>;
  handleRollback: (conversationId: string, nodeId: string) => Promise<void>;
  handleBranch: (
    conversationId: string,
    nodeId: string,
    name: string
  ) => Promise<void>;
  handleSwitchBranch: (
    conversationId: string,
    branchId: string
  ) => Promise<void>;
  updateFromSSE: (data: Record<string, unknown>) => void;
}

const VisualConceptContext = createContext<VisualConceptContextValue | null>(
  null
);

// ─── Provider ─────────────────────────────────────────────────────

export function VisualConceptProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [state, setState] = useState<VisualConceptState>(initialState);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const toggleDrawer = useCallback(() => {
    setDrawerOpen((prev) => !prev);
  }, []);

  const refreshVersionTree = useCallback(
    async (conversationId: string) => {
      try {
        const res = await apiGetVersionTree(conversationId);
        const treeData = res.data as unknown as VersionTree;
        if (treeData) {
          setState((prev) => ({
            ...prev,
            isActive: true,
            versionTree: treeData,
            currentBranchId: treeData.active_branch || prev.currentBranchId,
          }));
        }
      } catch (error) {
        toast.error("版本树加载失败", {
          description: (error as Error).message || "请检查网络连接",
        });
      }
    },
    []
  );

  const handleRollback = useCallback(
    async (conversationId: string, nodeId: string) => {
      try {
        await executeVisualConceptAction(conversationId, "rollback", {
          target_node_id: nodeId,
        });
        await refreshVersionTree(conversationId);
      } catch (error) {
        toast.error("回滚失败", {
          description: (error as Error).message,
        });
      }
    },
    [refreshVersionTree]
  );

  const handleBranch = useCallback(
    async (conversationId: string, nodeId: string, name: string) => {
      try {
        await executeVisualConceptAction(conversationId, "branch", {
          source_node_id: nodeId,
          branch_name: name,
        });
        await refreshVersionTree(conversationId);
      } catch (error) {
        toast.error("分支创建失败", {
          description: (error as Error).message,
        });
      }
    },
    [refreshVersionTree]
  );

  const handleSwitchBranch = useCallback(
    async (conversationId: string, branchId: string) => {
      try {
        await executeVisualConceptAction(conversationId, "switch_branch", {
          target_branch_id: branchId,
        });
        await refreshVersionTree(conversationId);
      } catch (error) {
        toast.error("切换分支失败", {
          description: (error as Error).message,
        });
      }
    },
    [refreshVersionTree]
  );

  /**
   * Parse SSE content_block_data to update local visual concept state.
   * This is called from the chat streaming callback when visual concept
   * related blocks arrive.
   */
  const updateFromSSE = useCallback((data: Record<string, unknown>) => {
    const blockType = data.type as string | undefined;

    if (blockType === "visual_strategy") {
      setState((prev) => ({
        ...prev,
        isActive: true,
        agentState: "PROMPTING",
      }));
    }

    if (blockType === "visual_result" || blockType === "quality_check") {
      const agentState = blockType === "quality_check"
        ? "REVIEWING"
        : "GENERATING";
      setState((prev) => ({
        ...prev,
        isActive: true,
        agentState,
      }));
    }

    // Update from structured version tree data if present
    if (data.version_tree) {
      const treeData = data.version_tree as unknown as VersionTree;
      setState((prev) => ({
        ...prev,
        versionTree: treeData,
        currentBranchId: treeData.active_branch || prev.currentBranchId,
        currentNodeId: data.current_node_id
          ? String(data.current_node_id)
          : prev.currentNodeId,
        currentImageUrl: data.current_image_url
          ? String(data.current_image_url)
          : prev.currentImageUrl,
      }));
    }

    // Update quality check items
    if (data.quality_check_items) {
      setState((prev) => ({
        ...prev,
        qualityCheck: data.quality_check_items as QualityCheckItem[],
      }));
    }

    // Update agent state if provided
    if (data.agent_state) {
      setState((prev) => ({
        ...prev,
        agentState: data.agent_state as VisualConceptState["agentState"],
      }));
    }
  }, []);

  return (
    <VisualConceptContext.Provider
      value={{
        state,
        drawerOpen,
        toggleDrawer,
        refreshVersionTree,
        handleRollback,
        handleBranch,
        handleSwitchBranch,
        updateFromSSE,
      }}
    >
      {children}
    </VisualConceptContext.Provider>
  );
}

// ─── Hook ─────────────────────────────────────────────────────────

export function useVisualConcept(): VisualConceptContextValue {
  const ctx = useContext(VisualConceptContext);
  if (!ctx) {
    throw new Error(
      "useVisualConcept must be used within a VisualConceptProvider"
    );
  }
  return ctx;
}
