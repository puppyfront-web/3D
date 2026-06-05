"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { SkillManifest } from "@/types";

interface SkillCardProps {
  skill: SkillManifest;
  onExecute?: (skillId: string) => void;
  loading?: boolean;
}

const categoryColors: Record<string, string> = {
  analysis: "bg-blue-100 text-blue-800",
  retrieval: "bg-green-100 text-green-800",
  proposal: "bg-purple-100 text-purple-800",
  visual: "bg-pink-100 text-pink-800",
  export: "bg-amber-100 text-amber-800",
};

export function SkillCard({ skill, onExecute, loading }: SkillCardProps) {
  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">{skill.name}</CardTitle>
          <Badge variant="secondary" className={categoryColors[skill.category] || ""}>
            {skill.category}
          </Badge>
        </div>
        <CardDescription className="text-sm">{skill.description}</CardDescription>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500">v{skill.version}</span>
          {onExecute && (
            <Button
              size="sm"
              onClick={() => onExecute(skill.skill_id)}
              disabled={loading}
            >
              {loading ? "执行中..." : "使用"}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
