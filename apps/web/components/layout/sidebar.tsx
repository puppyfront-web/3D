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
  Settings,
  Pencil,
  Trash2,
  Check,
  X,
} from "lucide-react";
import { useState, useEffect, useCallback, useRef } from "react";
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
  { label: "系统设置", href: "/admin/settings", icon: Settings },
];

/* ─── Individual conversation item with hover edit/delete ────────── */

function ConversationItem({
  conv,
  isActive,
  onSelect,
  onRename,
  onDelete,
}: {
  conv: Conversation;
  isActive: boolean;
  onSelect: (id: string) => void;
  onRename: (id: string, title: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(conv.title);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Sync title when it changes externally
  useEffect(() => {
    if (!editing) setEditValue(conv.title);
  }, [conv.title, editing]);

  // Auto-focus on edit start
  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  const handleStartEdit = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      setEditing(true);
      setEditValue(conv.title);
    },
    [conv.title]
  );

  const handleSaveEdit = useCallback(async () => {
    const trimmed = editValue.trim();
    if (trimmed && trimmed !== conv.title) {
      await onRename(conv.id, trimmed);
    }
    setEditing(false);
  }, [editValue, conv.id, conv.title, onRename]);

  const handleCancelEdit = useCallback(() => {
    setEditing(false);
    setEditValue(conv.title);
  }, [conv.title]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleSaveEdit();
      } else if (e.key === "Escape") {
        e.preventDefault();
        handleCancelEdit();
      }
    },
    [handleSaveEdit, handleCancelEdit]
  );

  const handleStartDelete = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setConfirmDelete(true);
  }, []);

  const handleConfirmDelete = useCallback(
    async (e: React.MouseEvent) => {
      e.stopPropagation();
      await onDelete(conv.id);
      setConfirmDelete(false);
    },
    [conv.id, onDelete]
  );

  const handleCancelDelete = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setConfirmDelete(false);
  }, []);

  // Confirm delete overlay
  if (confirmDelete) {
    return (
      <div className="flex items-center gap-1.5 w-full px-3 py-2 rounded-lg bg-red-900/30 border border-red-500/30">
        <span className="text-xs text-red-300 flex-1 truncate">确认删除？</span>
        <button
          onClick={handleConfirmDelete}
          className="p-1 rounded hover:bg-red-500/30 text-red-400 hover:text-red-300 transition-colors"
          title="确认删除"
        >
          <Check className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={handleCancelDelete}
          className="p-1 rounded hover:bg-white/10 text-gray-400 hover:text-gray-300 transition-colors"
          title="取消"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    );
  }

  // Inline editing mode
  if (editing) {
    return (
      <div
        className="flex items-center gap-1.5 w-full px-3 py-2 rounded-lg bg-white/10"
        onClick={(e) => e.stopPropagation()}
      >
        <input
          ref={inputRef}
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleSaveEdit}
          className="flex-1 min-w-0 bg-transparent text-sm text-white border-b border-[#00D4FF]/50 focus:outline-none focus:border-[#00D4FF] py-0.5"
          maxLength={200}
        />
        <button
          onClick={handleSaveEdit}
          className="p-1 rounded hover:bg-white/10 text-[#00D4FF] transition-colors shrink-0"
          title="保存"
        >
          <Check className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={handleCancelEdit}
          className="p-1 rounded hover:bg-white/10 text-gray-400 hover:text-gray-300 transition-colors shrink-0"
          title="取消"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    );
  }

  // Normal display with hover actions
  return (
    <div
      onClick={() => onSelect(conv.id)}
      className={`group flex items-start gap-2.5 w-full px-3 py-2 rounded-lg text-left cursor-pointer transition-all duration-150 ${
        isActive
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
      {/* Hover action buttons — shown on hover, hidden on active state via opacity */}
      <div
        className={`shrink-0 flex items-center gap-0.5 transition-opacity ${
          isActive ? "opacity-0 group-hover:opacity-100" : "opacity-0 group-hover:opacity-100"
        }`}
      >
        <button
          onClick={handleStartEdit}
          className="p-1 rounded hover:bg-white/15 text-gray-400 hover:text-white transition-colors"
          title="重命名"
        >
          <Pencil className="h-3 w-3" />
        </button>
        <button
          onClick={handleStartDelete}
          className="p-1 rounded hover:bg-red-500/25 text-gray-400 hover:text-red-400 transition-colors"
          title="删除"
        >
          <Trash2 className="h-3 w-3" />
        </button>
      </div>
    </div>
  );
}

/* ─── Main Sidebar ─────────────────────────────────────────────── */

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const {
    state,
    loadConversations,
    selectConversation,
    createConversation,
    renameConversation,
    deleteConversation,
  } = useChat();
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

  const handleDelete = useCallback(
    async (id: string) => {
      // If deleting the active conversation, navigate away
      if (state.activeConversationId === id) {
        router.push("/workspace/chat");
      }
      await deleteConversation(id);
    },
    [deleteConversation, state.activeConversationId, router]
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
              花生ONE
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
              <ConversationItem
                key={conv.id}
                conv={conv}
                isActive={state.activeConversationId === conv.id}
                onSelect={handleSelectConv}
                onRename={renameConversation}
                onDelete={handleDelete}
              />
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
        {collapsed ? "v0.1" : "v0.1.0 · 花生ONE"}
      </div>
    </aside>
  );
}
