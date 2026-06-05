"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Artifact } from "@/types";

interface ArtifactViewerProps {
  artifact: Artifact;
}

const typeLabels: Record<Artifact["type"], string> = {
  report: "解析报告",
  document: "方案文档",
  image: "效果图",
  prompt: "视觉 Prompt",
};

const typeColors: Record<Artifact["type"], string> = {
  report: "bg-blue-100 text-blue-800",
  document: "bg-purple-100 text-purple-800",
  image: "bg-pink-100 text-pink-800",
  prompt: "bg-amber-100 text-amber-800",
};

export function ArtifactViewer({ artifact }: ArtifactViewerProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">{artifact.title}</CardTitle>
          <Badge variant="secondary" className={typeColors[artifact.type]}>
            {typeLabels[artifact.type]}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {artifact.type === "image" && artifact.url ? (
          <img
            src={artifact.url}
            alt={artifact.title}
            className="w-full rounded-md border"
          />
        ) : artifact.type === "prompt" ? (
          <pre className="bg-gray-900 text-green-400 p-3 rounded-md text-xs font-mono whitespace-pre-wrap overflow-x-auto">
            {artifact.content}
          </pre>
        ) : (
          <div className="prose prose-sm max-w-none text-gray-700">
            {artifact.content}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
