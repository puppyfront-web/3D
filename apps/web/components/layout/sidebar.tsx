"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
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
  ChevronDown,
  ChevronRight,
  Sparkles,
  Plus,
  Search,
  MessageSquare,
  PanelLeftClose,
  PanelLeft,
} from "lucide-react";
import { useState, useEffect, useCallback } from "react";
import { useChat } from "@/lib/chat-context";
import type { Conversation } from "@/types";

const adminLinks = [
  { label: "资产管理", href: "/admin/assets", icon: Package },
  { label: "案例库", href: "/admin/cases", icon: BookOpen },
  { label: "SOP工作流", href: "/admin/sop-workflows", icon: GitBranch },
  { label: "方案模板", href: "/admin/proposal-templates", icon: FileText },
  { label: "提示词模板", href: "/admin/prompt-templates", icon: MessageSquareCode },
  { label: "视觉风格库", href: "/admin/visual-styles", icon: Palette },
  { label: "技术规则", href: "/admin/technical-rules", icon: Cpu },
  { label: "质量标准", href: "/admin/quality-rules", icon: ShieldCheck },
  { label: "评估记录", href: "/admin/evaluations", icon: ClipboardCheck },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { state, loadConversations, selectConversation, createConversation } =
    useChat();
  const [collapsed, setCollapsed] = useState(false);
  const [adminOpen, setAdminOpen] = useState(false);
  const [search, setSearch] = useState("");

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const handleNewChat = useCallback(async () => {
    try {
      const id = await createConversation({ title: "新对话" });
      router.push(`/workspace/chat?conv=${id}`);
    } catch {
      // error handled in context
    }
  }, [createConversation, router]);

  const handleSelectConv = useCallback(
    (id: string) => {
      selectConversation(id);
      router.push(`/workspace/chat?conv=${id}`);
    },
    [selectConversation, router]
  );

  const filtered = state.conversations.filter((c) =>
    c.title.toLowerCase().includes(search.toLowerCase())
  );

  const isActive = (href: string) => pathname.startsWith(href);

  return (
    <aside
      className={`h-full bg-[#1A1A2E] text-gray-300 flex flex-col transition-all duration-200 shrink-0 ${
        collapsed ? "w-16" : "w-[280px]"
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-3 border-b border-white/10">
        {!collapsed && (
          <div className="flex items-center gap-2">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-[#00D4FF] text-[#1A1A2E]">
              <Sparkles className="h-5 w-5" />
            </div>
            <span className="text-base font-semibold text-white tracking-tight">
              3D提案平台
            </span>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1.5 rounded-md hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
        >
          {collapsed ? (
            <PanelLeft className="h-4 w-4" />
          ) : (
            <PanelLeftClose className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* New Chat Button */}
      <div className="px-3 py-2">
        <button
          onClick={handleNewChat}
          className={`flex items-center gap-2 w-full rounded-lg bg-[#2D5A8E] hover:bg-[#3A6EA5] text-white transition-colors ${
            collapsed ? "justify-center p-2" : "px-3 py-2.5"
          }`}
        >
          <Plus className="h-4 w-4 shrink-0" />
          {!collapsed && <span className="text-sm font-medium">新建对话</span>}
        </button>
      </div>

      {/* Search */}
      {!collapsed && (
        <div className="px-3 pb-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-500" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索对话..."
              className="w-full pl-8 pr-3 py-1.5 bg-white/5 border border-white/10 rounded-md text-sm text-gray-300 placeholder-gray-600 focus:outline-none focus:border-[#00D4FF]/50"
            />
          </div>
        </div>
      )}

      {/* Conversation List */}
      <nav className="flex-1 overflow-y-auto px-2 py-1">
        {collapsed ? (
          <div className="flex flex-col items-center gap-1">
            {filtered.slice(0, 10).map((conv) => (
              <button
                key={conv.id}
                onClick={() => handleSelectConv(conv.id)}
                className={`p-2 rounded-md transition-colors ${
                  state.activeConversationId === conv.id
                    ? "bg-[#2D5A8E] text-white"
                    : "text-gray-500 hover:bg-white/5 hover:text-gray-300"
                }`}
                title={conv.title}
              >
                <MessageSquare className="h-4 w-4" />
              </button>
            ))}
          </div>
        ) : (
          <div className="space-y-0.5">
            {filtered.map((conv) => (
              <button
                key={conv.id}
                onClick={() => handleSelectConv(conv.id)}
                className={`flex items-start gap-2.5 w-full px-3 py-2 rounded-lg text-left transition-all duration-150 ${
                  state.activeConversationId === conv.id
                    ? "bg-[#2D5A8E] text-white shadow-sm"
                    : "text-gray-400 hover:bg-white/5 hover:text-gray-200"
                }`}
              >
                <MessageSquare className="h-4 w-4 mt-0.5 shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="text-sm truncate">{conv.title}</div>
                  {conv.lastMessage && (
                    <div className="text-xs text-gray-500 truncate mt-0.5">
                      {conv.lastMessage.content.slice(0, 40)}
                    </div>
                  )}
                </div>
              </button>
            ))}
            {filtered.length === 0 && (
              <div className="px-3 py-8 text-center text-xs text-gray-600">
                {search ? "没有找到对话" : "暂无对话，点击上方开始"}
              </div>
            )}
          </div>
        )}
      </nav>

      {/* Admin Links */}
      <div className="border-t border-white/10 shrink-0 overflow-y-auto max-h-[40vh]">
        <button
          onClick={() => setAdminOpen(!adminOpen)}
          className={`flex items-center justify-between w-full px-3 py-2 text-xs font-medium uppercase tracking-wider text-gray-500 hover:text-gray-300 transition-colors ${
            collapsed ? "justify-center" : ""
          }`}
        >
          {collapsed ? (
            <Package className="h-4 w-4" />
          ) : (
            <>
              <span>系统管理</span>
              {adminOpen ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
            </>
          )}
        </button>
        {adminOpen && !collapsed && (
          <div className="px-2 pb-2 space-y-0.5">
            {adminLinks.map((link) => {
              const Icon = link.icon;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`flex items-center gap-2.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
                    isActive(link.href)
                      ? "bg-[#2D5A8E] text-white"
                      : "text-gray-500 hover:bg-white/5 hover:text-gray-300"
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  <span>{link.label}</span>
                </Link>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="shrink-0 px-3 py-2 border-t border-white/10 text-xs text-gray-600">
        {collapsed ? "v0.1" : "v0.1.0 · 3D提案平台"}
      </div>
    </aside>
  );
}
