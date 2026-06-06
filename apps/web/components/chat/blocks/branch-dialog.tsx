"use client";

import { useState } from "react";
import { X, GitBranch } from "lucide-react";

interface BranchDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (name: string) => void;
}

export function BranchDialog({ open, onClose, onConfirm }: BranchDialogProps) {
  const [name, setName] = useState("");

  if (!open) return null;

  const handleSubmit = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    onConfirm(trimmed);
    setName("");
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />

      {/* Dialog */}
      <div className="relative bg-white rounded-xl shadow-xl w-full max-w-sm mx-4 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <GitBranch className="h-5 w-5 text-[#00D4FF]" />
            <h3 className="text-sm font-semibold text-gray-800">创建新分支</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-gray-100 text-gray-400 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">
              分支名称
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSubmit();
              }}
              placeholder="例如：方案B、暖色调尝试..."
              autoFocus
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:border-[#00D4FF] focus:ring-1 focus:ring-[#00D4FF]/30"
            />
          </div>

          <div className="flex justify-end gap-2">
            <button
              onClick={onClose}
              className="px-3 py-1.5 text-sm rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors"
            >
              取消
            </button>
            <button
              onClick={handleSubmit}
              disabled={!name.trim()}
              className="px-3 py-1.5 text-sm rounded-lg bg-[#1E3A5F] text-white hover:bg-[#2D5A8E] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              创建
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
