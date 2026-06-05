"use client";

import { Card, CardContent } from "@/components/ui/card";
import {
  Package,
  BookOpen,
  GitBranch,
  FileText,
  MessageSquareCode,
  Palette,
  Cpu,
  ShieldCheck,
  ClipboardCheck,
  TrendingUp,
  FolderKanban,
  Users,
} from "lucide-react";
import Link from "next/link";

const stats = [
  { label: "活跃项目", value: "12", change: "+3 本月", icon: <FolderKanban className="h-5 w-5" />, color: "text-[#1E3A5F]" },
  { label: "方案模板", value: "8", change: "+2 本月", icon: <FileText className="h-5 w-5" />, color: "text-[#3B82F6]" },
  { label: "案例库", value: "45", change: "+5 本月", icon: <BookOpen className="h-5 w-5" />, color: "text-[#10B981]" },
  { label: "资产总数", value: "326", change: "+28 本月", icon: <Package className="h-5 w-5" />, color: "text-[#F59E0B]" },
];

const adminLinks = [
  { label: "资产管理", desc: "管理3D模型、图片、视频等素材资源", href: "/admin/assets", icon: <Package className="h-5 w-5 text-[#1E3A5F]" /> },
  { label: "案例库", desc: "管理成功案例，用于方案参考和素材复用", href: "/admin/cases", icon: <BookOpen className="h-5 w-5 text-[#10B981]" /> },
  { label: "SOP工作流", desc: "配置方案生成的自动化工作流程", href: "/admin/sop-workflows", icon: <GitBranch className="h-5 w-5 text-[#8B5CF6]" /> },
  { label: "方案模板", desc: "管理方案文档模板和章节结构", href: "/admin/proposal-templates", icon: <FileText className="h-5 w-5 text-[#3B82F6]" /> },
  { label: "提示词模板", desc: "管理AI提示词模板和变量配置", href: "/admin/prompt-templates", icon: <MessageSquareCode className="h-5 w-5 text-[#00D4FF]" /> },
  { label: "视觉风格库", desc: "管理视觉风格预设和参数配置", href: "/admin/visual-styles", icon: <Palette className="h-5 w-5 text-[#EC4899]" /> },
  { label: "技术规则", desc: "配置技术方案生成的约束规则", href: "/admin/technical-rules", icon: <Cpu className="h-5 w-5 text-[#F59E0B]" /> },
  { label: "质量标准", desc: "管理方案质量评估标准和评分规则", href: "/admin/quality-rules", icon: <ShieldCheck className="h-5 w-5 text-[#EF4444]" /> },
  { label: "评估记录", desc: "查看方案质量评估历史和报告", href: "/admin/evaluations", icon: <ClipboardCheck className="h-5 w-5 text-[#1E3A5F]" /> },
];

export default function AdminDashboardPage() {
  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-[#1A1A2E]">系统管理</h1>
        <p className="text-sm text-gray-500 mt-1">管理平台配置、模板、规则和资产资源</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {stats.map((stat) => (
          <Card key={stat.label} className="border-gray-200">
            <CardContent className="p-5 flex items-center gap-4">
              <div className="w-12 h-12 rounded-lg bg-[#1E3A5F]/5 flex items-center justify-center text-[#1E3A5F]">
                {stat.icon}
              </div>
              <div>
                <p className="text-xs text-gray-500">{stat.label}</p>
                <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
                <p className="text-xs text-[#10B981]">{stat.change}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Admin Links Grid */}
      <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-4">管理模块</h2>
      <div className="grid grid-cols-3 gap-4">
        {adminLinks.map((link) => (
          <Link key={link.href} href={link.href}>
            <Card className="border-gray-200 hover:border-[#2D5A8E]/30 hover:shadow-sm transition-all group cursor-pointer h-full">
              <CardContent className="p-5 flex items-start gap-4">
                <div className="w-10 h-10 rounded-lg bg-gray-50 flex items-center justify-center flex-shrink-0 group-hover:bg-[#1E3A5F]/5 transition-colors">
                  {link.icon}
                </div>
                <div>
                  <p className="text-sm font-medium text-[#1A1A2E] group-hover:text-[#2D5A8E] transition-colors">
                    {link.label}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">{link.desc}</p>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
