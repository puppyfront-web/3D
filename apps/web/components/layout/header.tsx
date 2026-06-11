"use client";

import { Bell, Search, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface HeaderProps {
  title?: string;
  breadcrumbs?: { label: string; href?: string }[];
}

export function Header({ title, breadcrumbs }: HeaderProps) {
  return (
    <header className="sticky top-0 z-30 h-12 bg-white border-b border-gray-200 flex items-center justify-between px-6">
      <div className="flex items-center gap-2">
        {breadcrumbs && breadcrumbs.length > 0 ? (
          <nav className="flex items-center gap-1.5 text-sm">
            {breadcrumbs.map((crumb, i) => (
              <span key={i} className="flex items-center gap-1.5">
                {i > 0 && <span className="text-gray-400">/</span>}
                {crumb.href ? (
                  <a
                    href={crumb.href}
                    className="text-[#1E3A5F] hover:text-[#2D5A8E] transition-colors"
                  >
                    {crumb.label}
                  </a>
                ) : (
                  <span className="text-gray-600 font-medium">{crumb.label}</span>
                )}
              </span>
            ))}
          </nav>
        ) : (
          <h1 className="text-sm font-semibold text-[#1A1A2E]">
            {title || "花生ONE"}
          </h1>
        )}
      </div>

      <div className="flex items-center gap-3">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            placeholder="搜索项目、模板..."
            className="pl-9 w-56 h-8 text-sm bg-gray-50 border-gray-200 focus:bg-white"
          />
        </div>
        <Button variant="ghost" size="icon" className="relative h-8 w-8">
          <Bell className="h-4 w-4 text-gray-500" />
          <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-[#EF4444]" />
        </Button>
        <div className="h-6 w-px bg-gray-200" />
        <div className="flex items-center gap-2 cursor-pointer">
          <div className="w-7 h-7 rounded-full bg-[#1E3A5F] flex items-center justify-center">
            <User className="h-3.5 w-3.5 text-white" />
          </div>
        </div>
      </div>
    </header>
  );
}
