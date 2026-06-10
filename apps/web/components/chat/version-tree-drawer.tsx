"use client";

import { useState, useCallback } from "react";
import { GitBranch, X } from "lucide-react";
import type { VersionTree } from "@/types";
import { VersionTreePanel } from "./blocks/version-tree-panel";

interface VersionTreeDrawerProps {
  versionTree: VersionTree | null;
  currentBranchId: string;
  currentNodeId: string | null;
  conversationId?: string;
  onRollback?: (nodeId: string) => void;
  onBranch?: (nodeId: string, name: string) => void;
  onSwitchBranch?: (branchId: string) => void;
}

export function VersionTreeDrawer({
  versionTree,
  currentBranchId,
  currentNodeId,
  onRollback,
  onBranch,
  onSwitchBranch,
}: VersionTreeDrawerProps) {
  const [open, setOpen] = useState(false);

  const handleRollback = useCallback(
    (nodeId: string) => {
      onRollback?.(nodeId);
    },
    [onRollback]
  );

  const handleBranch = useCallback(
    (nodeId: string, name: string) => {
      onBranch?.(nodeId, name);
    },
    [onBranch]
  );

  const handleSwitchBranch = useCallback(
    (branchId: string) => {
      onSwitchBranch?.(branchId);
    },
    [onSwitchBranch]
  );

  const handleViewArtifact = useCallback(() => {
    // Artifact viewing is handled internally by VersionTreePanel
  }, []);

  return (
    <>
      {/* Trigger button */}
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-violet-50 text-violet-700 hover:bg-violet-100 border border-violet-200 transition-colors"
      >
        <GitBranch className="h-3.5 w-3.5" />
        版本树
      </button>

      {/* Drawer */}
      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40 bg-black/20"
            onClick={() => setOpen(false)}
          />

          {/* Drawer panel */}
          <div className="fixed right-0 top-0 z-50 h-full w-[420px] bg-white shadow-xl border-l border-gray-200 flex flex-col">
            {/* Drawer header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
              <div className="flex items-center gap-2">
                <GitBranch className="h-4 w-4 text-[#00D4FF]" />
                <h2 className="text-sm font-semibold text-gray-800">
                  版本树
                </h2>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Panel content */}
            <VersionTreePanel
              versionTree={versionTree}
              currentBranchId={currentBranchId}
              currentNodeId={currentNodeId}
              onRollback={handleRollback}
              onBranch={handleBranch}
              onSwitchBranch={handleSwitchBranch}
              onViewArtifact={handleViewArtifact}
            />
          </div>
        </>
      )}
    </>
  );
}
