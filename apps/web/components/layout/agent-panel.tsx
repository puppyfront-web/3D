"use client";

import { useState, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import {
  Sparkles,
  X,
  Send,
  Lightbulb,
  FileText,
  BarChart3,
  ChevronRight,
  Loader2,
} from "lucide-react";
import { createConversation, streamChat } from "@/lib/chat-api";

interface AgentPanelProps {
  isOpen: boolean;
  onClose: () => void;
  projectId?: string;
}

interface AgentMessage {
  id: string;
  role: "assistant" | "user";
  content: string;
  timestamp: string;
  loading?: boolean;
}

const suggestions = [
  { icon: <FileText className="h-3.5 w-3.5" />, text: "优化当前章节内容", prompt: "请帮我优化当前方案的内容" },
  { icon: <BarChart3 className="h-3.5 w-3.5" />, text: "分析竞品数据", prompt: "请分析相关行业的竞品数据" },
  { icon: <Lightbulb className="h-3.5 w-3.5" />, text: "生成改进建议", prompt: "请针对当前方案生成改进建议" },
];

export function AgentPanel({ isOpen, onClose, projectId }: AgentPanelProps) {
  const [messages, setMessages] = useState<AgentMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "您好！我是AI助手，可以帮您优化方案内容、分析数据、生成建议。请问有什么需要帮助的吗？",
      timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
    },
  ]);
  const [inputValue, setInputValue] = useState("");
  const [sending, setSending] = useState(false);
  const conversationIdRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const ensureConversation = useCallback(async () => {
    if (conversationIdRef.current) return conversationIdRef.current;
    try {
      const res = await createConversation({
        projectId,
        title: "AI 助手对话",
      });
      if (res.success && res.data) {
        conversationIdRef.current = res.data.id;
        return res.data.id;
      }
    } catch {
      // fallback — will retry on next message
    }
    return null;
  }, [projectId]);

  const handleSend = async (text?: string) => {
    const content = text || inputValue.trim();
    if (!content || sending) return;

    const userMsg: AgentMessage = {
      id: `m-${Date.now()}`,
      role: "user",
      content,
      timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
    };

    const aiMsgId = `ai-${Date.now()}`;
    const aiMsg: AgentMessage = {
      id: aiMsgId,
      role: "assistant",
      content: "",
      timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
      loading: true,
    };

    setMessages((prev) => [...prev, userMsg, aiMsg]);
    setInputValue("");
    setSending(true);

    try {
      const convId = await ensureConversation();
      if (!convId) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === aiMsgId
              ? { ...m, loading: false, content: "暂时无法连接AI服务，请稍后再试。" }
              : m
          )
        );
        setSending(false);
        return;
      }

      let fullText = "";
      const ctrl = streamChat(convId, content, {
        onTextDelta: (text) => {
          fullText += text;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiMsgId ? { ...m, loading: false, content: fullText } : m
            )
          );
        },
        onComplete: () => {
          setSending(false);
        },
        onError: (err) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiMsgId
                ? { ...m, loading: false, content: fullText || `请求失败: ${err.message}` }
                : m
            )
          );
          setSending(false);
        },
      });
      abortRef.current = ctrl;
    } catch {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === aiMsgId
            ? { ...m, loading: false, content: "连接失败，请检查网络后重试。" }
            : m
        )
      );
      setSending(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="flex flex-col h-full w-80 bg-white border-l border-gray-200">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-[#00D4FF] flex items-center justify-center">
            <Sparkles className="h-3.5 w-3.5 text-white" />
          </div>
          <span className="text-sm font-medium text-[#1A1A2E]">AI 助手</span>
        </div>
        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}
          >
            <div
              className={`max-w-[90%] rounded-lg px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-[#1E3A5F] text-white"
                  : "bg-gray-50 text-gray-700 border border-gray-100"
              }`}
            >
              {msg.loading ? (
                <span className="flex items-center gap-1.5 text-gray-400">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> 思考中...
                </span>
              ) : (
                msg.content
              )}
            </div>
            <span className="text-xs text-gray-400 mt-1 px-1">{msg.timestamp}</span>
          </div>
        ))}
      </div>

      {/* Suggestions */}
      <div className="px-4 py-2 border-t border-gray-100">
        <p className="text-xs text-gray-400 mb-2">快捷操作</p>
        <div className="space-y-1">
          {suggestions.map((s, i) => (
            <button
              key={i}
              className="flex items-center gap-2 w-full px-2 py-1.5 text-xs text-gray-600 hover:bg-gray-50 rounded transition-colors"
              onClick={() => handleSend(s.prompt)}
              disabled={sending}
            >
              {s.icon}
              <span>{s.text}</span>
              <ChevronRight className="h-3 w-3 ml-auto text-gray-300" />
            </button>
          ))}
        </div>
      </div>

      <Separator />

      {/* Input */}
      <div className="p-3">
        <div className="flex gap-2">
          <Input
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
            placeholder="输入您的问题..."
            className="flex-1 h-8 text-sm"
            disabled={sending}
          />
          <Button
            onClick={() => handleSend()}
            size="icon"
            className="h-8 w-8 bg-[#1E3A5F] hover:bg-[#2D5A8E]"
            disabled={sending || !inputValue.trim()}
          >
            <Send className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}
