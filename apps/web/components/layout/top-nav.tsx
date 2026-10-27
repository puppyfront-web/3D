"use client";

// TopNav — the unified top navigation bar shared by the marketing home page
// and the workspace. Two faces of the same system:
//   - "marketing": dark chrome (`.theme-dark` scope on the page root), nav
//     links + 登录 (secondary) + 创建团队任务 (primary lavender)
//   - "workspace": light chrome for the app (workspace + admin routes)
//
// Includes auth-aware user menu: shows login button when unauthenticated,
// user avatar + logout when authenticated.

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { BrainCircuit, LogOut, Settings as SettingsIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { isAuthenticated, getStoredUser, clearToken } from "@/lib/auth";
import { APP_NAME } from "@/lib/constants";
import { useEffect, useState } from "react";
import { toast } from "sonner";

const MARKETING_NAV = [
  { label: "首页", href: "/" },
  { label: "团队工作台", href: "/workspace/projects" },
  { label: "知识库", href: "/admin/assets" },
  { label: "案例库", href: "/admin/cases" },
];

const WORKSPACE_NAV = [
  { label: "首页", href: "/" },
  { label: "团队工作台", href: "/workspace/projects" },
  { label: "知识库", href: "/admin/assets" },
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
  const dark = variant === "marketing";

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
    <header
      className={cn(
        "sticky top-0 z-50 h-16 border-b w-full",
        dark
          ? "bg-surface/85 backdrop-blur-md border-outline-variant"
          : "bg-surface-container-lowest border-outline-variant shadow-sm",
      )}
    >
      <div className="flex justify-between items-center h-full px-margin-desktop max-w-container-max mx-auto">
        {/* Brand + primary nav */}
        <div className="flex items-center gap-8">
          <Link
            href="/"
            className="font-semibold text-primary flex items-center gap-2 text-xl"
          >
            <BrainCircuit className="h-6 w-6" />
            <span className="tracking-tight">{APP_NAME}</span>
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
                      ? "text-on-surface font-medium border-b-2 border-primary"
                      : "text-on-surface-variant hover:text-on-surface",
                  )}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Right cluster: actions + user */}
        <div className="flex items-center gap-3">
          {variant === "marketing" && !authed && (
            <>
              <Link
                href="/login"
                className="hidden sm:inline-flex bg-surface-container-lowest text-on-surface border border-outline-variant px-4 py-2 rounded-lg text-sm font-medium hover:bg-surface-container-low transition-colors"
              >
                登录
              </Link>
              <Link
                href="/workspace/projects/new"
                className="hidden sm:inline-flex bg-primary text-on-primary px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary-container active:scale-95 transition-all"
              >
                创建团队任务
              </Link>
            </>
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
              <div className="w-8 h-8 rounded-full bg-primary-fixed text-on-primary-fixed flex items-center justify-center text-sm font-medium">
                {userName.charAt(0).toUpperCase()}
              </div>
            </div>
          ) : (
            variant === "workspace" && (
              <Link
                href="/login"
                className="bg-primary text-on-primary px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary-container active:scale-95 transition-all"
              >
                登录
              </Link>
            )
          )}
        </div>
      </div>
    </header>
  );
}
