"use client";

import { useEffect } from "react";
import { toast } from "sonner";

/**
 * Next.js Error Boundary for the app.
 * Catches runtime errors in any route segment below app/.
 * Shows a toast and a user-friendly fallback UI.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Show toast for the error
    toast.error("页面发生错误", {
      description: error.message || "未知错误",
      duration: 8000,
    });
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 p-8">
      <div className="text-center space-y-2">
        <h2 className="text-lg font-semibold text-gray-900">出了点问题</h2>
        <p className="text-sm text-gray-500 max-w-md">
          {error.message || "页面发生了意外错误，请重试。"}
        </p>
        {error.digest && (
          <p className="text-xs text-gray-400">错误ID: {error.digest}</p>
        )}
      </div>
      <button
        onClick={reset}
        className="px-4 py-2 text-sm bg-[#1A2B3C] text-white rounded-lg hover:bg-[#2A3B4C] transition-colors"
      >
        重试
      </button>
    </div>
  );
}
