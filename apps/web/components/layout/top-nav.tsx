"use client";

// TopNav — the unified top navigation bar shared by the marketing home page
// and the workspace. Two faces of the same system:
//   - "marketing": dark chrome (`.theme-dark` scope on the page root), nav
//     links + 登录 (secondary) + 创建团队任务 (primary lavender)
//   - "workspace": light chrome for the app (workspace + admin routes)
//
// Mobile (<md): nav links move into a left drawer (radix Dialog gets us
// focus trap, Esc, scroll lock, and aria wiring for free). Touch targets
// in the drawer are 44px tall.

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { BrainCircuit, LogOut, Menu, Settings as SettingsIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { isAuthenticated, getStoredUser, clearToken } from "@/lib/auth";
import { APP_NAME } from "@/lib/constants";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

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
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    setAuthed(isAuthenticated());
    setUserName(getStoredUser()?.name || getStoredUser()?.email || "用户");
  }, [pathname]);

  function handleLogout() {
    clearToken();
    setAuthed(false);
    setMenuOpen(false);
    toast.success("已登出");
    router.push("/login");
  }

  const isActive = (href: string) =>
    current === href || (href !== "/" && current.startsWith(href));

  return (
    <header
      className={cn(
        "sticky top-0 z-50 h-16 border-b w-full",
        dark
          ? "bg-surface/85 backdrop-blur-md border-outline-variant"
          : "bg-surface-container-lowest border-outline-variant shadow-sm",
      )}
    >
      <div className="flex justify-between items-center h-full px-4 sm:px-margin-desktop max-w-container-max mx-auto">
        {/* Brand + primary nav */}
        <div className="flex items-center gap-8">
          <Link
            href="/"
            className="font-semibold text-primary flex items-center gap-2 text-xl"
          >
            <BrainCircuit className="h-6 w-6" />
            <span className="tracking-tight">{APP_NAME}</span>
          </Link>
          <nav className="hidden md:flex gap-6 items-center" aria-label="主导航">
            {items.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive(item.href) ? "page" : undefined}
                className={cn(
                  "text-sm transition-colors pb-1",
                  isActive(item.href)
                    ? "text-on-surface font-medium border-b-2 border-primary"
                    : "text-on-surface-variant hover:text-on-surface",
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>

        {/* Right cluster: actions + user + mobile menu */}
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
              <span className="text-sm hidden lg:inline text-on-surface-variant">
                {userName}
              </span>
              <Link
                href="/admin/settings"
                className="hidden md:inline-flex p-2 hover:bg-surface-container-low rounded-full transition-colors text-on-surface-variant"
                title="系统设置"
                aria-label="系统设置"
              >
                <SettingsIcon className="h-5 w-5" />
              </Link>
              <button
                onClick={handleLogout}
                className="hidden md:inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg text-on-surface-variant hover:bg-surface-container-low hover:text-error transition-colors"
                title="登出"
                aria-label="登出"
              >
                <LogOut className="h-4 w-4" />
                <span className="hidden lg:inline">登出</span>
              </button>
              <div
                className="w-8 h-8 rounded-full bg-primary-fixed text-on-primary-fixed flex items-center justify-center text-sm font-medium"
                aria-label={userName}
              >
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

          {/* Mobile drawer trigger */}
          <Dialog open={menuOpen} onOpenChange={setMenuOpen}>
            <DialogTrigger asChild>
              <button
                type="button"
                className="md:hidden -mr-2 flex h-11 w-11 items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-container-low transition-colors"
                aria-label="打开导航菜单"
              >
                <Menu className="h-5 w-5" />
              </button>
            </DialogTrigger>
            <DialogContent
              // Drawer mounts through a portal to <body>, outside the page's
              // `.theme-dark` scope — re-apply it here for the marketing variant.
              className={cn(
                "top-0 left-0 right-auto bottom-auto translate-x-0 translate-y-0 h-full w-[280px] max-w-[85vw] rounded-none border-r border-outline-variant p-0 gap-0 bg-surface-container-lowest text-on-surface data-open:zoom-in-100 data-closed:zoom-out-100 data-open:duration-200",
                dark && "theme-dark",
              )}
              aria-describedby={undefined}
            >
              <DialogTitle className="sr-only">导航菜单</DialogTitle>
              <div className="flex items-center gap-2 px-4 h-16 border-b border-outline-variant">
                <BrainCircuit className="h-6 w-6 text-primary" />
                <span className="font-semibold text-primary text-lg tracking-tight">
                  {APP_NAME}
                </span>
              </div>
              <nav className="p-2 space-y-1" aria-label="移动端导航">
                {items.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMenuOpen(false)}
                    aria-current={isActive(item.href) ? "page" : undefined}
                    className={cn(
                      "flex items-center h-11 px-4 rounded-lg text-base transition-colors",
                      isActive(item.href)
                        ? "bg-primary-fixed text-on-primary-fixed font-medium"
                        : "text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface",
                    )}
                  >
                    {item.label}
                  </Link>
                ))}
              </nav>
              <div className="absolute inset-x-0 bottom-0 border-t border-outline-variant p-4 space-y-2">
                {authed ? (
                  <>
                    <div className="flex items-center gap-3 px-1 pb-1">
                      <div className="w-8 h-8 rounded-full bg-primary-fixed text-on-primary-fixed flex items-center justify-center text-sm font-medium">
                        {userName.charAt(0).toUpperCase()}
                      </div>
                      <span className="text-sm text-on-surface-variant truncate">
                        {userName}
                      </span>
                    </div>
                    <Link
                      href="/admin/settings"
                      onClick={() => setMenuOpen(false)}
                      className="flex items-center h-11 px-4 rounded-lg text-base text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface transition-colors"
                    >
                      系统设置
                    </Link>
                    <button
                      type="button"
                      onClick={handleLogout}
                      className="flex w-full items-center h-11 px-4 rounded-lg text-base text-error hover:bg-error-container/40 transition-colors"
                    >
                      登出
                    </button>
                  </>
                ) : (
                  <>
                    {variant === "marketing" && (
                      <Link
                        href="/workspace/projects/new"
                        onClick={() => setMenuOpen(false)}
                        className="flex items-center justify-center h-11 rounded-lg bg-primary text-on-primary text-base font-medium hover:bg-primary-container transition-colors"
                      >
                        创建团队任务
                      </Link>
                    )}
                    <Link
                      href="/login"
                      onClick={() => setMenuOpen(false)}
                      className="flex items-center justify-center h-11 rounded-lg border border-outline-variant text-on-surface text-base font-medium hover:bg-surface-container-low transition-colors"
                    >
                      登录
                    </Link>
                  </>
                )}
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>
    </header>
  );
}
