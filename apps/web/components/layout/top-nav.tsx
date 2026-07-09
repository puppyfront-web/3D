"use client";

// TopNav — the unified top navigation bar shared by the marketing home page
// and the workspace. Supports two variants:
//   - "marketing": full nav (首页 / 方案中心 / 案例库 / 模板中心 / 帮助中心) + 工作台 CTA
//   - "workspace": workspace-focused nav
//
// Includes auth-aware user menu: shows login button when unauthenticated,
// user avatar + logout when authenticated.

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { CloudCog, LogOut, Settings as SettingsIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { isAuthenticated, getStoredUser, clearToken } from "@/lib/auth";
import { useEffect, useState } from "react";
import { toast } from "sonner";

const MARKETING_NAV = [
  { label: "首页", href: "/" },
  { label: "方案中心", href: "/workspace/projects" },
  { label: "案例库", href: "/admin/cases" },
  { label: "模板中心", href: "/admin/proposal-templates" },
];

const WORKSPACE_NAV = [
  { label: "首页", href: "/" },
  { label: "方案中心", href: "/workspace/projects" },
  { label: "案例库", href: "/admin/cases" },
];

export function TopNav({
  variant = "marketing",
  activeHref,
}: {
  variant?: "marketing" | "workspace";
  activeHref?: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const current = activeHref ?? pathname;
  const items = variant === "marketing" ? MARKETING_NAV : WORKSPACE_NAV;

  // Auth state — read on mount (client-only, avoids SSR hydration mismatch)
  const [authed, setAuthed] = useState(false);
  const [userName, setUserName] = useState<string>("");

  useEffect(() => {
    setAuthed(isAuthenticated());
    setUserName(getStoredUser()?.name || getStoredUser()?.email || "用户");
  }, [pathname]);

  function handleLogout() {
    clearToken();
    setAuthed(false);
    toast.success("已登出");
    router.push("/login");
  }

  return (
    <header className="bg-surface-container-lowest sticky top-0 z-50 h-16 border-b border-outline-variant shadow-sm w-full">
      <div className="flex justify-between items-center h-full px-margin-desktop max-w-container-max mx-auto">
        {/* Brand + primary nav */}
        <div className="flex items-center gap-8">
          <Link
            href="/"
            className="font-bold text-primary flex items-center gap-2 text-xl"
          >
            <CloudCog className="h-6 w-6 fill" />
            <span className="tracking-tight">花生ONE</span>
          </Link>
          <nav className="hidden md:flex gap-6 items-center">
            {items.map((item) => {
              const isActive =
                current === item.href ||
                (item.href !== "/" && current.startsWith(item.href));
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "text-sm transition-colors pb-1",
                    isActive
                      ? "text-primary font-bold border-b-2 border-primary"
                      : "text-on-surface-variant hover:text-primary",
                  )}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Right cluster: actions + user */}
        <div className="flex items-center gap-4">
          {variant === "marketing" && (
            <Link
              href="/workspace/projects/new"
              className="hidden sm:inline-flex bg-primary text-on-primary px-4 py-2 rounded-lg text-sm font-medium hover:opacity-90 active:scale-95 transition-all"
            >
              开始生成方案
            </Link>
          )}

          {/* Auth-aware user menu */}
          {authed ? (
            <div className="flex items-center gap-2 ml-2 pl-4 border-l border-outline-variant">
              <span className="text-sm hidden sm:inline text-on-surface-variant">
                {userName}
              </span>
              <Link
                href="/admin/settings"
                className="p-2 hover:bg-surface-container-low rounded-full transition-colors text-on-surface-variant"
                title="系统设置"
                aria-label="系统设置"
              >
                <SettingsIcon className="h-5 w-5" />
              </Link>
              <button
                onClick={handleLogout}
                className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg text-on-surface-variant hover:bg-surface-container-low hover:text-error transition-colors"
                title="登出"
                aria-label="登出"
              >
                <LogOut className="h-4 w-4" />
                <span className="hidden sm:inline">登出</span>
              </button>
              <div className="w-8 h-8 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center text-sm font-medium">
                {userName.charAt(0).toUpperCase()}
              </div>
            </div>
          ) : (
            <Link
              href="/login"
              className="bg-primary text-on-primary px-4 py-2 rounded-lg text-sm font-medium hover:opacity-90 active:scale-95 transition-all"
            >
              登录
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
