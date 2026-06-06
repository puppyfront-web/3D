"use client";

import { useEffect, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { useChat } from "@/lib/chat-context";
import { MessageList } from "@/components/chat/message-bubble";
import { ChatInput } from "@/components/chat/chat-input";
import { WelcomeScreen } from "@/components/chat/welcome-screen";
import { Badge } from "@/components/ui/badge";
import { Settings, Loader2, AlertCircle } from "lucide-react";

export default function ChatPage() {
  const searchParams = useSearchParams();
  const {
    state,
    loadConversations,
    selectConversation,
    createConversation,
    sendMessage,
    uploadFile,
  } = useChat();

  // Load conversation from URL param
  useEffect(() => {
    const convId = searchParams.get("conv");
    if (convId && convId !== state.activeConversationId) {
      selectConversation(convId);
    }
  }, [searchParams, selectConversation, state.activeConversationId]);

  // Load conversations on mount
  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const handleSend = useCallback(
    async (message: string) => {
      // If no active conversation, create one first
      if (!state.activeConversationId) {
        const id = await createConversation({ title: message.slice(0, 50) });
        // Wait for context to update, then send
        // The sendMessage will be called after the conversation is created
        // We need to use a small delay to let state update
        setTimeout(() => {
          sendMessage(message);
        }, 100);
      } else {
        sendMessage(message);
      }
    },
    [state.activeConversationId, createConversation, sendMessage]
  );

  const hasMessages = state.messages.length > 0 || state.isStreaming;

  // Find active conversation for header
  const activeConv = state.conversations.find(
    (c) => c.id === state.activeConversationId
  );

  return (
    <div className="flex flex-col h-full">
      {/* Top Bar */}
      <header className="flex items-center justify-between px-6 h-12 border-b border-gray-200 bg-white shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-sm font-semibold text-gray-900">
            {activeConv?.title || "新对话"}
          </h1>
          {activeConv && (
            <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
              {activeConv.status === "active" ? "进行中" : "已归档"}
            </Badge>
          )}
          {state.isStreaming && (
            <div className="flex items-center gap-1 text-[#00D4FF]">
              <Loader2 className="h-3 w-3 animate-spin" />
              <span className="text-xs">生成中</span>
            </div>
          )}
        </div>
        <button className="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors">
          <Settings className="h-4 w-4" />
        </button>
      </header>

      {/* Error Banner */}
      {state.error && (
        <div className="flex items-center gap-2 px-4 py-2 bg-red-50 border-b border-red-100 text-red-700 text-xs">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          {state.error}
        </div>
      )}

      {/* Main Content */}
      {hasMessages ? (
        <MessageList
          messages={state.messages}
          streamingText={state.streamingText}
          streamingBlocks={state.streamingBlocks}
          isStreaming={state.isStreaming}
        />
      ) : (
        <WelcomeScreen onSendMessage={handleSend} />
      )}

      {/* Input */}
      <ChatInput
        onSend={handleSend}
        onFileUpload={uploadFile}
        disabled={state.isStreaming || state.isLoading}
        isUploading={state.isUploading}
      />
    </div>
  );
}
