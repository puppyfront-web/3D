"use client";

// AdminShell — dedicated chrome for the /admin/* area.
// TopNav (workspace variant, compact) + a left sub-nav grouping all 10 admin
// modules. Solves the current gap where admin pages have no navigation between
// modules (only the dashboard grid linked them).

import Link from "next/link";
import { usePathname } from "next/navigation";
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
  Settings,
  LayoutDashboard,
  CloudCog,
  BookMarked,
  MessageSquareQuote,
  CircleDollarSign,
  Search,
  FlaskConical,
} from "lucide-react";
import { cn } from "@/lib/utils";

const KB_SKU = (process.env.NEXT_PUBLIC_KB_SKU || "standard").toLowerCase();

const ADMIN_LINKS_FULL = [
  { label: "概览", href: "/admin", icon: LayoutDashboard, sku: "standard" as const },
  { label: "资产管理", href: "/admin/assets", icon: Package, sku: "standard" as const },
  { label: "检索测试", href: "/admin/rag-test", icon: FlaskConical, sku: "standard" as const },
  { label: "评测中心", href: "/admin/eval", icon: ClipboardCheck, sku: "standard" as const },
  { label: "案例库", href: "/admin/cases", icon: BookOpen, sku: "standard" as const },
  { label: "话术库", href: "/admin/talking-points", icon: MessageSquareQuote, sku: "standard" as const },
  { label: "检索日志", href: "/admin/retrieval-logs", icon: Search, sku: "standard" as const },
  { label: "系统设置", href: "/admin/settings", icon: Settings, sku: "standard" as const },
  { label: "行业资料", href: "/admin/industry-materials", icon: BookMarked, sku: "full" as const },
  { label: "SOP 工作流", href: "/admin/sop-workflows", icon: GitBranch, sku: "full" as const },
  { label: "方案模板", href: "/admin/proposal-templates", icon: FileText, sku: "full" as const },
  { label: "提示词模板", href: "/admin/prompt-templates", icon: MessageSquareCode, sku: "full" as const },
  { label: "视觉风格库", href: "/admin/visual-styles", icon: Palette, sku: "full" as const },
  { label: "技术规则", href: "/admin/technical-rules", icon: Cpu, sku: "full" as const },
  { label: "质量标准", href: "/admin/quality-rules", icon: ShieldCheck, sku: "full" as const },
  { label: "报价经验", href: "/admin/pricing-experiences", icon: CircleDollarSign, sku: "full" as const },
  { label: "评估记录", href: "/admin/evaluations", icon: ClipboardCheck, sku: "full" as const },
];

const ADMIN_LINKS =
  KB_SKU === "full"
    ? ADMIN_LINKS_FULL
    : ADMIN_LINKS_FULL.filter((l) => l.sku === "standard");

export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex flex-col h-screen">
      {/* Compact top bar */}
      <header className="h-14 bg-surface-container-lowest border-b border-outline-variant flex items-center px-margin-desktop shrink-0">
        <Link
          href="/"
          className="font-bold text-primary flex items-center gap-2"
        >
          <CloudCog className="h-5 w-5 fill" />
          <span>企业知识助手</span>
        </Link>
        <span className="mx-3 text-outline-variant">/</span>
        <span className="text-sm text-on-surface-variant font-medium">
          系统管理
        </span>
        <Link
          href="/workspace/projects"
          className="ml-auto text-sm text-primary hover:underline"
        >
          返回工作台
        </Link>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sub-nav */}
        <aside className="w-60 shrink-0 border-r border-outline-variant bg-surface-container-lowest overflow-y-auto scrollbar-thin">
          <nav className="p-3 space-y-0.5">
            {ADMIN_LINKS.map((link) => {
              const Icon = link.icon;
              const isActive =
                link.href === "/admin"
                  ? pathname === "/admin"
                  : pathname.startsWith(link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={cn(
                    "flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors",
                    isActive
                      ? "bg-primary-fixed text-on-primary-fixed font-medium"
                      : "text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface",
                  )}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  <span>{link.label}</span>
                </Link>
              );
            })}
          </nav>
        </aside>

        {/* Content */}
        <main className="flex-1 overflow-y-auto bg-surface scrollbar-thin">
          {children}
        </main>
      </div>
    </div>
  );
}
