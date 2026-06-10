"use client";

import { useState } from "react";
import Image from "next/image";
import {
  X,
  Copy,
  Check,
  Maximize2,
  FileText,
  Eye,
  CheckSquare,
} from "lucide-react";
import type { VersionNode } from "@/types";

type ArtifactTab = "strategy" | "prompt" | "image" | "quality";

interface ArtifactDetailModalProps {
  open: boolean;
  onClose: () => void;
  node: VersionNode | null;
}

export function ArtifactDetailModal({
  open,
  onClose,
  node,
}: ArtifactDetailModalProps) {
  const [activeTab, setActiveTab] = useState<ArtifactTab>("strategy");
  const [copied, setCopied] = useState(false);

  if (!open || !node) return null;

  const tabs: { key: ArtifactTab; label: string; icon: React.ReactNode; available: boolean }[] = [
    {
      key: "strategy",
      label: "视觉策略",
      icon: <Eye className="h-3.5 w-3.5" />,
      available: !!node.visual_strategy,
    },
    {
      key: "prompt",
      label: "Prompt",
      icon: <FileText className="h-3.5 w-3.5" />,
      available: !!node.positive_prompt,
    },
    {
      key: "image",
      label: "图片",
      icon: <Maximize2 className="h-3.5 w-3.5" />,
      available: !!node.image_url,
    },
    {
      key: "quality",
      label: "质量检查",
      icon: <CheckSquare className="h-3.5 w-3.5" />,
      available: !!node.quality_check && node.quality_check.length > 0,
    },
  ];

  const availableTabs = tabs.filter((t) => t.available);

  const handleCopy = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-2xl mx-4 max-h-[80vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200">
          <div>
            <h3 className="text-sm font-semibold text-gray-800">
              {node.version_label} — 产物详情
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Tab bar */}
        <div className="flex border-b border-gray-100 px-5">
          {availableTabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? "border-[#00D4FF] text-[#00D4FF]"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5">
          {/* Strategy tab */}
          {activeTab === "strategy" && node.visual_strategy && (
            <div className="relative">
              <pre className="text-xs text-gray-700 bg-gray-50 rounded-lg p-4 whitespace-pre-wrap font-mono">
                {JSON.stringify(node.visual_strategy, null, 2)}
              </pre>
            </div>
          )}

          {/* Prompt tab */}
          {activeTab === "prompt" && node.positive_prompt && (
            <div className="space-y-4">
              {/* Positive prompt */}
              <div className="relative">
                <div className="text-xs text-gray-500 mb-1">正向 Prompt</div>
                <pre className="text-xs text-gray-700 bg-gray-900 text-green-400 rounded-lg p-4 whitespace-pre-wrap font-mono">
                  {node.positive_prompt}
                </pre>
                <button
                  onClick={() => handleCopy(node.positive_prompt!)}
                  className="absolute top-7 right-2 p-1.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors"
                >
                  {copied ? (
                    <Check className="h-3 w-3 text-green-400" />
                  ) : (
                    <Copy className="h-3 w-3" />
                  )}
                </button>
              </div>

              {/* Negative prompt */}
              {node.negative_prompt && (
                <div className="relative">
                  <div className="text-xs text-gray-500 mb-1">负向 Prompt</div>
                  <pre className="text-xs text-gray-700 bg-gray-900 text-red-400 rounded-lg p-4 whitespace-pre-wrap font-mono">
                    {node.negative_prompt}
                  </pre>
                  <button
                    onClick={() => handleCopy(node.negative_prompt!)}
                    className="absolute top-7 right-2 p-1.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors"
                  >
                    <Copy className="h-3 w-3" />
                  </button>
                </div>
              )}

              {node.prompt_template_used && (
                <div className="text-[10px] text-gray-400">
                  使用模板: {node.prompt_template_used}
                </div>
              )}
            </div>
          )}

          {/* Image tab */}
          {activeTab === "image" && node.image_url && (
            <div className="flex items-center justify-center">
              <div className="relative h-[60vh] w-full">
                <Image
                  src={node.image_url}
                  alt={node.version_label}
                  fill
                  unoptimized
                  className="rounded-lg object-contain"
                />
              </div>
            </div>
          )}

          {/* Quality tab */}
          {activeTab === "quality" && node.quality_check && (
            <ul className="space-y-2">
              {node.quality_check.map((item, i) => {
                const isPass = item.status === "✅";
                return (
                  <li
                    key={i}
                    className="flex items-start gap-2 p-2 rounded-lg bg-gray-50"
                  >
                    <span className="text-base leading-none mt-0.5">
                      {item.status}
                    </span>
                    <div className="min-w-0">
                      <div
                        className={`text-sm ${
                          isPass ? "text-gray-800" : "text-amber-700 font-medium"
                        }`}
                      >
                        {item.item}
                      </div>
                      {item.note && (
                        <div className="text-xs text-gray-500 mt-0.5">
                          {item.note}
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
