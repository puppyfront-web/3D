"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus, Search, Filter, LayoutGrid, List } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ProjectCard } from "@/components/workspace/project-card";
import { mockProjects } from "@/lib/mock-data";

export default function ProjectsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [filterStatus, setFilterStatus] = useState<string>("all");

  const filtered = mockProjects.filter((p) => {
    const matchesSearch =
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.client.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesFilter =
      filterStatus === "all" || p.status === filterStatus;
    return matchesSearch && matchesFilter;
  });

  const statusCounts = {
    all: mockProjects.length,
    in_progress: mockProjects.filter((p) => p.status === "in_progress").length,
    proposal_draft: mockProjects.filter((p) => p.status === "proposal_draft").length,
    review: mockProjects.filter((p) => p.status === "review").length,
    approved: mockProjects.filter((p) => p.status === "approved").length,
  };

  return (
    <div className="p-6">
      {/* Page Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#1A1A2E]">项目列表</h1>
          <p className="text-sm text-gray-500 mt-1">
            管理所有提案项目，跟踪进度与状态
          </p>
        </div>
        <Link href="/workspace/projects/new">
          <Button className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-2">
            <Plus className="h-4 w-4" />
            新建项目
          </Button>
        </Link>
      </div>

      {/* Stats Bar */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: "全部项目", count: statusCounts.all, color: "text-[#1E3A5F]" },
          { label: "进行中", count: statusCounts.in_progress, color: "text-[#3B82F6]" },
          { label: "审核中", count: statusCounts.review, color: "text-[#00D4FF]" },
          { label: "已通过", count: statusCounts.approved, color: "text-[#10B981]" },
        ].map((stat) => (
          <Card key={stat.label} className="border-gray-200">
            <CardContent className="p-4">
              <p className="text-xs text-gray-500 mb-1">{stat.label}</p>
              <p className={`text-2xl font-bold ${stat.color}`}>{stat.count}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            placeholder="搜索项目名称或客户..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 h-9"
          />
        </div>
        <div className="flex gap-1.5">
          {[
            { key: "all", label: "全部" },
            { key: "in_progress", label: "进行中" },
            { key: "proposal_draft", label: "方案撰写" },
            { key: "review", label: "审核中" },
            { key: "approved", label: "已通过" },
          ].map((f) => (
            <Button
              key={f.key}
              variant={filterStatus === f.key ? "default" : "outline"}
              size="sm"
              onClick={() => setFilterStatus(f.key)}
              className={
                filterStatus === f.key
                  ? "bg-[#1E3A5F] hover:bg-[#2D5A8E]"
                  : "border-gray-200"
              }
            >
              {f.label}
            </Button>
          ))}
        </div>
      </div>

      {/* Project Grid */}
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400">
          <p className="text-sm">没有找到匹配的项目</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}
    </div>
  );
}
