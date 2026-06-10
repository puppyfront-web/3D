"use client";

import { useRef, useEffect, useCallback } from "react";
import type { ChatMessage, ContentBlock } from "@/types";
import { BlockRenderer } from "@/components/chat/blocks/block-renderer";
import { MarkdownRenderer } from "@/components/chat/markdown-renderer";
import { VersionTreeDrawer } from "@/components/chat/version-tree-drawer";
import { useVisualConcept } from "@/lib/visual-concept-context";
import { useChat } from "@/lib/chat-context";
import { Bot, User } from "lucide-react";

interface MessageBubbleProps {
  message: ChatMessage;
  onAction?: (value: string, action: string) => void;
}

export function MessageBubble({ message, onAction }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";

  // Visual concept: check if any block is visual-related
  const hasVisualBlocks =
    isAssistant &&
    message.richContent?.blocks?.some(
      (b) => b.type === "visual_result" || b.type === "visual_strategy"
    );

  const visualConceptContext = useVisualConcept();

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
      {/* Avatar */}
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
          isUser
            ? "bg-[#1E3A5F] text-white"
            : "bg-[#00D4FF]/20 text-[#00D4FF]"
        }`}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Content */}
      <div className={`max-w-[75%] min-w-0 ${isUser ? "items-end" : "items-start"}`}>
        {/* Text content */}
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? "bg-[#1E3A5F] text-white rounded-tr-sm"
              : "bg-white text-gray-800 rounded-tl-sm shadow-sm border border-gray-100"
          }`}
        >
          {isUser ? (
            message.content
          ) : (
            <MarkdownRenderer content={message.content} />
          )}
        </div>

        {/* Rich content blocks */}
        {message.richContent?.blocks && isAssistant && (() => {
          const LOADING_TYPES = ["skill_executing"];
          const RESULT_TYPES = [
            "visual_result",
            "company_analysis_card",
            "proposal_section",
            "artifact",
          ];
          const hasResult = message.richContent.blocks.some((b) =>
            RESULT_TYPES.includes(b.type)
          );
          // When a result block exists, also hide skill_progress with status=running
          const filteredBlocks = message.richContent.blocks.filter((b) => {
            if (LOADING_TYPES.includes(b.type)) return false;
            if (hasResult && b.type === "skill_progress" && (b.data as Record<string, unknown>)?.status === "running") return false;
            return true;
          });
          return (
            <div className="mt-2 space-y-2">
              {filteredBlocks.map((block, i) => (
                <BlockRenderer key={i} block={block} onAction={onAction} />
              ))}

              {/* Version tree drawer trigger for visual concept messages */}
              {hasVisualBlocks && (
                <VersionTreeDrawer
                  versionTree={visualConceptContext.state.versionTree}
                  currentBranchId={visualConceptContext.state.currentBranchId}
                  currentNodeId={visualConceptContext.state.currentNodeId}
                  conversationId={message.conversationId}
                  onRollback={(nodeId) =>
                    visualConceptContext.handleRollback(
                      message.conversationId,
                      nodeId
                    )
                  }
                  onBranch={(nodeId, name) =>
                    visualConceptContext.handleBranch(
                      message.conversationId,
                      nodeId,
                      name
                    )
                  }
                  onSwitchBranch={(branchId) =>
                    visualConceptContext.handleSwitchBranch(
                      message.conversationId,
                      branchId
                    )
                  }
                />
              )}
            </div>
          );
        })()}

        {/* Timestamp */}
        <div
          className={`text-[10px] text-gray-400 mt-1 px-1 ${
            isUser ? "text-right" : "text-left"
          }`}
        >
          {new Date(message.createdAt).toLocaleTimeString("zh-CN", {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </div>
      </div>
    </div>
  );
}

// Streaming message bubble (shown while AI is generating)
interface StreamingBubbleProps {
  text: string;
  blocks: ContentBlock[];
  onAction?: (value: string, action: string) => void;
}

export function StreamingBubble({ text, blocks, onAction }: StreamingBubbleProps) {
  // During streaming: hide skill_executing (redundant with streaming text) and skill_progress (running)
  // After completion: MessageBubble hides skill_executing entirely
  const displayBlocks = blocks.filter((b) => {
    if (b.type === "skill_executing") return false;
    if (b.type === "skill_progress" && (b.data as Record<string, unknown>)?.status === "running") return false;
    return true;
  });

  return (
    <div className="flex gap-3 flex-row">
      <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-[#00D4FF]/20 text-[#00D4FF]">
        <Bot className="h-4 w-4" />
      </div>
      <div className="max-w-[75%] min-w-0">
        <div className="rounded-2xl rounded-tl-sm px-4 py-3 bg-white text-gray-800 shadow-sm border border-gray-100 text-sm leading-relaxed">
          <MarkdownRenderer content={text} />
          <span className="inline-block w-1.5 h-4 bg-[#00D4FF] ml-0.5 animate-pulse rounded-sm" />
        </div>
        {displayBlocks.length > 0 && (
          <div className="mt-2 space-y-2">
            {displayBlocks.map((block, i) => (
              <BlockRenderer key={i} block={block} onAction={onAction} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// Message list container
interface MessageListProps {
  messages: ChatMessage[];
  streamingText: string;
  streamingBlocks: ContentBlock[];
  isStreaming: boolean;
}

export function MessageList({
  messages,
  streamingText,
  streamingBlocks,
  isStreaming,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const { sendMessage, state } = useChat();

  const onBlockAction = useCallback((value: string) => {
    if (state.isStreaming) return;
    sendMessage(value);
  }, [sendMessage, state.isStreaming]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: isStreaming ? "auto" : "smooth" });
  }, [isStreaming, messages, streamingText]);

  return (
    <div className="flex-1 min-h-0 overflow-y-auto px-4 py-6">
      <div className="max-w-3xl mx-auto space-y-4">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} onAction={onBlockAction} />
        ))}
        {isStreaming && (
          <StreamingBubble text={streamingText} blocks={streamingBlocks} onAction={onBlockAction} />
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
