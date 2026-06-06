"use client";

import { Plus, GitBranch } from "lucide-react";
import type { BranchMeta } from "@/types";

interface BranchSwitcherProps {
  branches: Record<string, BranchMeta>;
  activeBranchId: string;
  onSwitch: (branchId: string) => void;
  onCreateBranch: () => void;
}

export function BranchSwitcher({
  branches,
  activeBranchId,
  onSwitch,
  onCreateBranch,
}: BranchSwitcherProps) {
  const branchList = Object.values(branches).filter(
    (b) => b.status === "active"
  );

  return (
    <div className="flex items-center gap-1 overflow-x-auto pb-1 scrollbar-hide">
      {branchList.map((branch) => (
        <button
          key={branch.branch_id}
          onClick={() => onSwitch(branch.branch_id)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
            branch.branch_id === activeBranchId
              ? "bg-[#00D4FF]/20 text-[#00D4FF] border border-[#00D4FF]/30"
              : "bg-gray-100 text-gray-600 hover:bg-gray-200 border border-transparent"
          }`}
        >
          <GitBranch className="h-3 w-3" />
          {branch.branch_name}
          {branch.branch_id === activeBranchId && (
            <span className="w-1.5 h-1.5 rounded-full bg-[#00D4FF] animate-pulse" />
          )}
        </button>
      ))}

      <button
        onClick={onCreateBranch}
        className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors border border-dashed border-gray-300"
      >
        <Plus className="h-3 w-3" />
        新分支
      </button>
    </div>
  );
}
