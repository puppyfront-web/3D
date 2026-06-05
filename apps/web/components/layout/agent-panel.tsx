"use client";

import { useState } from "react";
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
} from "lucide-react";

interface AgentPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

interface AgentMessage {
  id: string;
  role: "assistant" | "user";
  content: string;
  timestamp: string;
}

const initialMessages: AgentMessage[] = [
  {
    id: "m1",
    role: "assistant",
    content:
      "您好！我是AI助手，可以帮您优化方案内容、分析数据、生成建议。请问有什么需要帮助的吗？",
    timestamp: "14:30",
  },
];

const suggestions = [
  { icon: <FileText className="h-3.5 w-3.5" />, text: "优化当前章节内容" },
  { icon: <BarChart3 className="h-3.5 w-3.5" />, text: "分析竞品数据" },
  { icon: <Lightbulb className="h-3.5 w-3.5" />, text: "生成改进建议" },
];

export function AgentPanel({ isOpen, onClose }: AgentPanelProps) {
  const [messages, setMessages] = useState<AgentMessage[]>(initialMessages);
  const [inputValue, setInputValue] = useState("");

  const handleSend = () => {
    if (!inputValue.trim()) return;

    const userMsg: AgentMessage = {
      id: `m-${Date.now()}`,
      role: "user",
      content: inputValue,
      timestamp: new Date().toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
      }),
    };

    setMessages((prev) => [...prev, userMsg]);

    setTimeout(() => {
      const aiMsg: AgentMessage = {
        id: `m-${Date.now() + 1}`,
        role: "assistant",
        content:
          "收到您的需求，我正在分析相关内容。基于当前方案的数据，我建议从以下几个方面进行优化：\n\n1. 技术架构部分可以增加容灾设计说明\n2. 投资概算建议增加10%的风险储备金\n3. 实施计划中第二阶段与第三阶段之间建议增加联调缓冲期",
        timestamp: new Date().toLocaleTimeString("zh-CN", {
          hour: "2-digit",
          minute: "2-digit",
        }),
      };
      setMessages((prev) => [...prev, aiMsg]);
    }, 1000);

    setInputValue("");
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
              {msg.content}
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
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="输入您的问题..."
            className="flex-1 h-8 text-sm"
          />
          <Button
            onClick={handleSend}
            size="icon"
            className="h-8 w-8 bg-[#1E3A5F] hover:bg-[#2D5A8E]"
          >
            <Send className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}
