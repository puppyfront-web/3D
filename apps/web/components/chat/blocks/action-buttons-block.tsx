"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";

interface ActionButtonsBlockProps {
  data: Record<string, unknown>;
  onAction?: (value: string, action: string) => void;
}

export function ActionButtonsBlock({ data, onAction }: ActionButtonsBlockProps) {
  const buttons = Array.isArray(data.buttons) ? data.buttons : [];
  const [clickedValue, setClickedValue] = useState<string | null>(null);

  if (buttons.length === 0) return null;

  const handleClick = (btn: Record<string, unknown>) => {
    const value = String(btn.value || btn.label || "");
    const action = String(btn.action || "quick_reply");
    setClickedValue(value);
    onAction?.(value, action);
  };

  return (
    <div className="flex flex-wrap gap-2">
      {buttons.map((btn: Record<string, unknown>, i: number) => {
        const isDisabled = clickedValue !== null;
        const isClicked = clickedValue === (btn.value || btn.label);
        return (
          <button
            key={i}
            onClick={() => handleClick(btn)}
            disabled={isDisabled}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              isClicked
                ? "bg-violet-600 text-white scale-95"
                : isDisabled
                  ? "bg-gray-200 text-gray-400 cursor-not-allowed"
                  : "bg-[#1E3A5F] text-white hover:bg-[#2D5A8E]"
            }`}
          >
            {isClicked && <Loader2 className="h-3 w-3 animate-spin mr-1 inline" />}
            {String(btn.label || "操作")}
          </button>
        );
      })}
    </div>
  );
}
