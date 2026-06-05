"use client";

import Link from "next/link";
import { Calendar, User, Tag } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { StatusTag, PriorityTag } from "./status-tag";
import type { Project } from "@/types";

interface ProjectCardProps {
  project: Project;
}

export function ProjectCard({ project }: ProjectCardProps) {
  return (
    <Link href={`/workspace/projects/${project.id}`}>
      <Card className="group hover:shadow-md hover:border-[#2D5A8E]/30 transition-all duration-200 cursor-pointer border-gray-200">
        <CardContent className="p-5">
          <div className="flex items-start justify-between mb-3">
            <div className="flex-1 min-w-0 mr-3">
              <h3 className="text-sm font-semibold text-[#1A1A2E] truncate group-hover:text-[#2D5A8E] transition-colors">
                {project.name}
              </h3>
              <p className="text-xs text-gray-500 mt-0.5">{project.client}</p>
            </div>
            <div className="flex items-center gap-2">
              <PriorityTag priority={project.priority} />
              <StatusTag status={project.status} />
            </div>
          </div>

          <p className="text-xs text-gray-500 line-clamp-2 mb-4 leading-relaxed">
            {project.description}
          </p>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-400">项目进度</span>
              <span className="text-xs font-medium text-[#1E3A5F]">
                {project.progress}%
              </span>
            </div>
            <Progress value={project.progress} className="h-1.5" />
          </div>

          <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-100">
            <div className="flex items-center gap-4 text-xs text-gray-400">
              <span className="flex items-center gap-1">
                <User className="h-3 w-3" />
                {project.assignee}
              </span>
              <span className="flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                截止 {project.dueDate}
              </span>
            </div>
            {project.tags.length > 0 && (
              <div className="flex items-center gap-1">
                <Tag className="h-3 w-3 text-gray-300" />
                <span className="text-xs text-gray-400">{project.tags.length}个标签</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
