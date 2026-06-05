"use client";

import Link from "next/link";
import { usePathname, useParams } from "next/navigation";
import { Header } from "@/components/layout/header";
import { cn } from "@/lib/utils";

const projectTabs = [
  { label: "项目概览", href: "", key: "overview" },
  { label: "企业分析", href: "/company-analysis", key: "company-analysis" },
  { label: "方案编辑", href: "/proposal", key: "proposal" },
  { label: "视觉创作", href: "/visual", key: "visual" },
  { label: "审核校验", href: "/review", key: "review" },
  { label: "导出记录", href: "/exports", key: "exports" },
];

export default function ProjectDetailLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const params = useParams();
  const projectId = params.id as string;

  const activeTab = projectTabs.find((tab) => {
    if (tab.href === "") return pathname === `/workspace/projects/${projectId}`;
    return pathname.endsWith(tab.href);
  });

  return (
    <div className="flex flex-col h-screen">
      <Header
        breadcrumbs={[
          { label: "工作台", href: "/workspace/projects" },
          { label: "项目详情" },
        ]}
      />

      {/* Project Tabs */}
      <div className="bg-white border-b border-gray-200 px-6">
        <nav className="flex gap-0">
          {projectTabs.map((tab) => {
            const fullHref = `/workspace/projects/${projectId}${tab.href}`;
            const isActive = activeTab?.key === tab.key;
            return (
              <Link
                key={tab.key}
                href={fullHref}
                className={cn(
                  "px-4 py-3 text-sm font-medium border-b-2 transition-colors",
                  isActive
                    ? "border-[#1E3A5F] text-[#1E3A5F]"
                    : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                )}
              >
                {tab.label}
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="flex-1 overflow-y-auto">{children}</div>
    </div>
  );
}
