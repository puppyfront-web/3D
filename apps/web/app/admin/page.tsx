"use client";

import { useState, useEffect } from "react";
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
  FolderKanban,
  Settings,
  Loader2,
  BookMarked,
  MessageSquareQuote,
  CircleDollarSign,
} from "lucide-react";
import Link from "next/link";
import {
  getProjects,
  getCases,
  getProposalTemplates,
  getAssetCount,
} from "@/lib/api";
import type { ApiResponse } from "@/types";

interface StatItem {
  label: string;
  value: string;
  loading: boolean;
  icon: React.ReactNode;
  color: string;
}

const KB_SKU = (process.env.NEXT_PUBLIC_KB_SKU || "standard").toLowerCase();

export default function AdminDashboardPage() {
  const [stats, setStats] = useState<StatItem[]>([
    { label: "活跃项目", value: "-", loading: true, icon: <FolderKanban className="h-5 w-5" />, color: "text-primary" },
    { label: "方案模板", value: "-", loading: true, icon: <FileText className="h-5 w-5" />, color: "text-primary" },
    { label: "案例库", value: "-", loading: true, icon: <BookOpen className="h-5 w-5" />, color: "text-[#00875a]" },
    { label: "资产总数", value: "-", loading: true, icon: <Package className="h-5 w-5" />, color: "text-[#e8740b]" },
  ]);

  useEffect(() => {
    async function loadStats() {
      const results = await Promise.allSettled([
        getProjects(),
        getProposalTemplates(),
        getCases(),
        getAssetCount(), // total count, not a 1-item page
      ]);

      const newStats = [...stats];
      // Count from a paginated ApiResponse<T[]> (items length); returns "?"
      // for rejected promises or non-array payloads.
      const extractCount = (
        r: PromiseSettledResult<ApiResponse<unknown[]>>,
      ) => {
        if (r.status === "fulfilled" && r.value.success) {
          const data = r.value.data;
          if (Array.isArray(data)) return String(data.length);
          return "0";
        }
        return "?";
      };

      newStats[0] = { ...newStats[0], value: extractCount(results[0] as PromiseSettledResult<ApiResponse<unknown[]>>), loading: false };
      newStats[1] = { ...newStats[1], value: extractCount(results[1] as PromiseSettledResult<ApiResponse<unknown[]>>), loading: false };
      newStats[2] = { ...newStats[2], value: extractCount(results[2] as PromiseSettledResult<ApiResponse<unknown[]>>), loading: false };
      // Assets stat uses the real total count (getAssetCount returns a number).
      const assetR = results[3];
      newStats[3] = {
        ...newStats[3],
        value: assetR.status === "fulfilled" ? String(assetR.value) : "?",
        loading: false,
      };
      setStats(newStats);
    }
    loadStats();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const kbQuickLinks = [
    { label: "资料上传", href: "/admin/assets", desc: "上传并入库企业文档" },
    { label: "检索实验室", href: "/admin/rag-test", desc: "验证混合检索与保存用例" },
    { label: "评测中心", href: "/admin/eval", desc: "Hit@k 回归与冒烟模板" },
    { label: "检索日志", href: "/admin/retrieval-logs", desc: "问答与 Eval 追溯" },
  ];

  const onboardingSteps = [
    { step: 1, title: "配置 LLM / Embedding", href: "/admin/settings" },
    { step: 2, title: "上传资料或导入 Pack", href: "/admin/assets" },
    { step: 3, title: "检索实验室测 1 条", href: "/admin/rag-test" },
    { step: 4, title: "创建项目并开始问答", href: "/workspace/projects/new" },
  ];

  const adminLinks = [
    { label: "资产管理", desc: "管理3D模型、图片、视频等素材资源", href: "/admin/assets", icon: <Package className="h-5 w-5 text-primary" /> },
    { label: "案例库", desc: "管理成功案例，用于方案参考和素材复用", href: "/admin/cases", icon: <BookOpen className="h-5 w-5 text-[#00875a]" /> },
    { label: "行业资料", desc: "行业趋势、政策解读、对标分析等参考资料", href: "/admin/industry-materials", icon: <BookMarked className="h-5 w-5 text-primary" /> },
    { label: "SOP工作流", desc: "配置方案生成的自动化工作流程", href: "/admin/sop-workflows", icon: <GitBranch className="h-5 w-5 text-[#8B5CF6]" /> },
    { label: "方案模板", desc: "管理方案文档模板和章节结构", href: "/admin/proposal-templates", icon: <FileText className="h-5 w-5 text-primary" /> },
    { label: "提示词模板", desc: "管理AI提示词模板和变量配置", href: "/admin/prompt-templates", icon: <MessageSquareCode className="h-5 w-5 text-surface-tint" /> },
    { label: "话术库", desc: "按场景沉淀售前话术，保持表达一致可追溯", href: "/admin/talking-points", icon: <MessageSquareQuote className="h-5 w-5 text-primary" /> },
    { label: "视觉风格库", desc: "管理视觉风格预设和参数配置", href: "/admin/visual-styles", icon: <Palette className="h-5 w-5 text-[#EC4899]" /> },
    { label: "技术规则", desc: "配置技术方案生成的约束规则", href: "/admin/technical-rules", icon: <Cpu className="h-5 w-5 text-[#e8740b]" /> },
    { label: "质量标准", desc: "管理方案质量评估标准和评分规则", href: "/admin/quality-rules", icon: <ShieldCheck className="h-5 w-5 text-error" /> },
    { label: "报价经验", desc: "历史报价参考，正式报价须人工确认", href: "/admin/pricing-experiences", icon: <CircleDollarSign className="h-5 w-5 text-primary" /> },
    { label: "评估记录", desc: "查看方案质量评估历史和报告", href: "/admin/evaluations", icon: <ClipboardCheck className="h-5 w-5 text-primary" /> },
    { label: "系统设置", desc: "配置AI服务提供商、模型参数和API密钥", href: "/admin/settings", icon: <Settings className="h-5 w-5 text-[#6B7280]" /> },
  ];

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-on-surface">系统管理</h1>
        <p className="text-sm text-gray-500 mt-1">管理平台配置、模板、规则和资产资源</p>
      </div>

      {KB_SKU !== "full" ? (
        <>
          <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-4">
            交付验收快捷入口
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            {kbQuickLinks.map((link) => (
              <Link key={link.href} href={link.href}>
                <Card className="border-primary/20 hover:border-primary/40 h-full">
                  <CardContent className="p-4">
                    <p className="text-sm font-medium text-on-surface">{link.label}</p>
                    <p className="text-xs text-gray-500 mt-1">{link.desc}</p>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
          <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3 mt-2">
            首次交付引导
          </h2>
          <ol className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-8">
            {onboardingSteps.map((s) => (
              <li key={s.step}>
                <Link href={s.href}>
                  <Card className="h-full hover:border-primary/30">
                    <CardContent className="p-4 flex gap-3 items-start">
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary text-sm font-semibold">
                        {s.step}
                      </span>
                      <span className="text-sm text-on-surface">{s.title}</span>
                    </CardContent>
                  </Card>
                </Link>
              </li>
            ))}
          </ol>
        </>
      ) : null}

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {stats.map((stat) => (
          <Card key={stat.label} className="border-gray-200">
            <CardContent className="p-5 flex items-center gap-4">
              <div className="w-12 h-12 rounded-lg bg-primary/5 flex items-center justify-center text-primary">
                {stat.icon}
              </div>
              <div>
                <p className="text-xs text-gray-500">{stat.label}</p>
                {stat.loading ? (
                  <Loader2 className="h-5 w-5 animate-spin text-gray-300 mt-1" />
                ) : (
                  <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
                )}
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
            <Card className="border-gray-200 hover:border-primary/30 hover:shadow-sm transition-all group cursor-pointer h-full">
              <CardContent className="p-5 flex items-start gap-4">
                <div className="w-10 h-10 rounded-lg bg-gray-50 flex items-center justify-center flex-shrink-0 group-hover:bg-primary/5 transition-colors">
                  {link.icon}
                </div>
                <div>
                  <p className="text-sm font-medium text-on-surface group-hover:text-primary transition-colors">
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
