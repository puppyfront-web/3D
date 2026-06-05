"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  FolderKanban,
  Package,
  BookOpen,
  GitBranch,
  FileText,
  MessageSquareCode,
  Palette,
  Cpu,
  ShieldCheck,
  ClipboardCheck,
  ChevronDown,
  ChevronRight,
  Sparkles,
} from "lucide-react";
import { useState } from "react";

interface SidebarLink {
  label: string;
  href: string;
  icon: React.ReactNode;
}

interface SidebarGroup {
  title: string;
  links: SidebarLink[];
}

const navGroups: SidebarGroup[] = [
  {
    title: "工作台",
    links: [
      {
        label: "项目列表",
        href: "/workspace/projects",
        icon: <FolderKanban className="h-4 w-4" />,
      },
    ],
  },
  {
    title: "管理",
    links: [
      {
        label: "资产管理",
        href: "/admin/assets",
        icon: <Package className="h-4 w-4" />,
      },
      {
        label: "案例库",
        href: "/admin/cases",
        icon: <BookOpen className="h-4 w-4" />,
      },
      {
        label: "SOP工作流",
        href: "/admin/sop-workflows",
        icon: <GitBranch className="h-4 w-4" />,
      },
      {
        label: "方案模板",
        href: "/admin/proposal-templates",
        icon: <FileText className="h-4 w-4" />,
      },
      {
        label: "提示词模板",
        href: "/admin/prompt-templates",
        icon: <MessageSquareCode className="h-4 w-4" />,
      },
      {
        label: "视觉风格库",
        href: "/admin/visual-styles",
        icon: <Palette className="h-4 w-4" />,
      },
      {
        label: "技术规则",
        href: "/admin/technical-rules",
        icon: <Cpu className="h-4 w-4" />,
      },
      {
        label: "质量标准",
        href: "/admin/quality-rules",
        icon: <ShieldCheck className="h-4 w-4" />,
      },
      {
        label: "评估记录",
        href: "/admin/evaluations",
        icon: <ClipboardCheck className="h-4 w-4" />,
      },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({
    "工作台": true,
    "管理": true,
  });

  const toggleGroup = (title: string) => {
    setExpandedGroups((prev) => ({ ...prev, [title]: !prev[title] }));
  };

  const isActive = (href: string) => {
    if (href === "/workspace/projects" && pathname.startsWith("/workspace")) return true;
    if (pathname.startsWith(href)) return true;
    return false;
  };

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-60 bg-[#1A1A2E] text-gray-300 flex flex-col">
      {/* Logo */}
      <div className="flex items-center gap-2 px-5 py-4 border-b border-white/10">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-[#00D4FF] text-[#1A1A2E]">
          <Sparkles className="h-5 w-5" />
        </div>
        <span className="text-lg font-semibold text-white tracking-tight">
          3D提案平台
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4 px-3">
        {navGroups.map((group) => (
          <div key={group.title} className="mb-4">
            <button
              onClick={() => toggleGroup(group.title)}
              className="flex items-center justify-between w-full px-2 py-2 text-xs font-medium uppercase tracking-wider text-gray-500 hover:text-gray-300 transition-colors"
            >
              <span>{group.title}</span>
              {expandedGroups[group.title] ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
            </button>
            {expandedGroups[group.title] && (
              <div className="space-y-0.5 mt-1">
                {group.links.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-all duration-150 ${
                      isActive(link.href)
                        ? "bg-[#2D5A8E] text-white shadow-sm"
                        : "text-gray-400 hover:bg-white/5 hover:text-gray-200"
                    }`}
                  >
                    {link.icon}
                    <span>{link.label}</span>
                  </Link>
                ))}
              </div>
            )}
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-3 border-t border-white/10 text-xs text-gray-600">
        v0.1.0 · 3D提案平台
      </div>
    </aside>
  );
}
