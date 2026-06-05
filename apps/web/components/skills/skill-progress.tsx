"use client";

import { CheckCircle, XCircle, Loader2, Clock } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface SkillProgressProps {
  status: "running" | "completed" | "failed";
  name?: string;
  durationMs?: number;
  errorMessage?: string;
}

export function SkillProgress({ status, name, durationMs, errorMessage }: SkillProgressProps) {
  const statusConfig = {
    running: { icon: Loader2, color: "text-blue-500", label: "执行中", animate: true },
    completed: { icon: CheckCircle, color: "text-green-500", label: "完成", animate: false },
    failed: { icon: XCircle, color: "text-red-500", label: "失败", animate: false },
  };

  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 border">
      <Icon className={`h-5 w-5 ${config.color} ${config.animate ? "animate-spin" : ""}`} />
      <div className="flex-1">
        <div className="flex items-center gap-2">
          {name && <span className="text-sm font-medium">{name}</span>}
          <Badge variant={status === "completed" ? "default" : status === "failed" ? "destructive" : "secondary"}>
            {config.label}
          </Badge>
        </div>
        {durationMs != null && (
          <span className="text-xs text-gray-500 flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {durationMs >= 1000 ? `${(durationMs / 1000).toFixed(1)}s` : `${durationMs}ms`}
          </span>
        )}
        {errorMessage && (
          <p className="text-xs text-red-500 mt-1">{errorMessage}</p>
        )}
      </div>
    </div>
  );
}
