"use client";

interface ActionButtonsBlockProps {
  data: Record<string, unknown>;
}

export function ActionButtonsBlock({ data }: ActionButtonsBlockProps) {
  const buttons = Array.isArray(data.buttons) ? data.buttons : [];

  if (buttons.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {buttons.map(
        (btn: Record<string, unknown>, i: number) => (
          <button
            key={i}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-[#1E3A5F] text-white hover:bg-[#2D5A8E] transition-colors"
          >
            {String(btn.label || "操作")}
          </button>
        )
      )}
    </div>
  );
}
