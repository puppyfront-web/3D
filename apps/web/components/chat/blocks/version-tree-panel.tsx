"use client";

import { useState } from "react";
import type { VersionTree, VersionNode } from "@/types";
import { BranchSwitcher } from "./branch-switcher";
import { VersionNodeCard } from "./version-node-card";
import { VersionCompareView } from "./version-compare-view";
import { BranchDialog } from "./branch-dialog";
import { ArtifactDetailModal } from "./artifact-detail-modal";
import { GitCompareArrows } from "lucide-react";

interface VersionTreePanelProps {
  versionTree: VersionTree | null;
  currentBranchId: string;
  currentNodeId: string | null;
  onRollback: (nodeId: string) => void;
  onBranch: (nodeId: string, name: string) => void;
  onSwitchBranch: (branchId: string) => void;
  onViewArtifact: (node: VersionNode) => void;
}

export function VersionTreePanel({
  versionTree,
  currentBranchId,
  currentNodeId,
  onRollback,
  onBranch,
  onSwitchBranch,
  onViewArtifact,
}: VersionTreePanelProps) {
  const [showCompare, setShowCompare] = useState(false);
  const [branchDialogOpen, setBranchDialogOpen] = useState(false);
  const [branchSourceNodeId, setBranchSourceNodeId] = useState<string | null>(null);
  const [artifactModalNode, setArtifactModalNode] = useState<VersionNode | null>(null);

  if (!versionTree) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-gray-400">
        暂无版本数据
      </div>
    );
  }

  // Get nodes for the current branch, ordered by creation time
  const branchNodes = Object.values(versionTree.nodes)
    .filter((n) => n.branch_id === currentBranchId)
    .sort(
      (a, b) =>
        new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    );

  const handleBranchFromCard = (nodeId: string) => {
    setBranchSourceNodeId(nodeId);
    setBranchDialogOpen(true);
  };

  const handleBranchConfirm = (name: string) => {
    if (branchSourceNodeId) {
      onBranch(branchSourceNodeId, name);
    }
  };

  const handleViewArtifact = (node: VersionNode) => {
    setArtifactModalNode(node);
    onViewArtifact(node);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Branch switcher */}
      <div className="px-3 py-2 border-b border-gray-100">
        <BranchSwitcher
          branches={versionTree.branches}
          activeBranchId={currentBranchId}
          onSwitch={onSwitchBranch}
          onCreateBranch={() => {
            setBranchSourceNodeId(currentNodeId);
            setBranchDialogOpen(true);
          }}
        />
      </div>

      {/* Version node list */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2">
        {branchNodes.map((node) => (
          <div key={node.node_id}>
            <VersionNodeCard
              node={node}
              isActive={node.node_id === currentNodeId}
              onRollback={onRollback}
              onBranch={handleBranchFromCard}
            />
            {/* Quick view artifact button */}
            {(node.visual_strategy || node.positive_prompt || node.image_url) && (
              <button
                onClick={() => handleViewArtifact(node)}
                className="mt-1 ml-2 text-[10px] text-[#00D4FF] hover:underline"
              >
                查看产物详情
              </button>
            )}
          </div>
        ))}

        {branchNodes.length === 0 && (
          <div className="text-xs text-gray-400 text-center py-6">
            该分支暂无版本
          </div>
        )}
      </div>

      {/* Compare toggle */}
      {branchNodes.length >= 2 && (
        <div className="px-3 py-2 border-t border-gray-100">
          <button
            onClick={() => setShowCompare(!showCompare)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              showCompare
                ? "bg-[#00D4FF]/20 text-[#00D4FF]"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            <GitCompareArrows className="h-3.5 w-3.5" />
            {showCompare ? "关闭对比" : "版本对比"}
          </button>

          {showCompare && (
            <div className="mt-2">
              <VersionCompareView
                nodes={versionTree.nodes}
                nodeIds={branchNodes.map((n) => n.node_id)}
              />
            </div>
          )}
        </div>
      )}

      {/* Branch dialog */}
      <BranchDialog
        open={branchDialogOpen}
        onClose={() => setBranchDialogOpen(false)}
        onConfirm={handleBranchConfirm}
      />

      {/* Artifact detail modal */}
      <ArtifactDetailModal
        open={!!artifactModalNode}
        onClose={() => setArtifactModalNode(null)}
        node={artifactModalNode}
      />
    </div>
  );
}
