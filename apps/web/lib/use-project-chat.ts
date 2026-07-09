"use client";

// useProjectChat — a self-contained, project-scoped chat hook for the canvas
// workspace's left-rail conversation panel.
//
// Why a separate hook (and not the global ChatProvider)?
//   The global ChatProvider in lib/chat-context.tsx is a single-active-
//   conversation store (one messages[] + one streamingText). If the canvas
//   panel shared it with the sidebar, two concurrent streams would clobber
//   each other. This hook keeps its own messages/streaming state keyed to the
//   project's conversation, fully isolated.
//
// Backend contract:
//   - GET /api/v1/projects/{id}/conversation → get-or-create + history
//   - POST /api/v1/conversations/{id}/chat/stream → SSE streaming
//   - POST /api/v1/conversations/{id}/upload → attachment

import { useCallback, useEffect, useRef, useState } from "react";
import { streamChat, uploadChatFile } from "@/lib/chat-api";
import { getProjectConversation } from "@/lib/canvas-api";
import type { ChatMessage, ContentBlock } from "@/types";
import { toast } from "sonner";

export interface ProjectChatState {
  /** Loaded conversation id (null until the project conversation resolves). */
  conversationId: string | null;
  threadId: string | null;
  messages: ChatMessage[];
  isStreaming: boolean;
  streamingText: string;
  streamingThinkingText: string;
  streamingBlocks: ContentBlock[];
  isUploading: boolean;
  error: string | null;
}

export interface UseProjectChat extends ProjectChatState {
  /** Send a message; streams the assistant reply into local state.
   *  opts.nodeId, when set, scopes the AI reply to a single canvas node
   *  (node-scoped conversation). Falls back to the hook's activeNodeId. */
  send: (text: string, opts?: { nodeId?: string | null }) => void;
  /** Upload a file as a chat attachment to the project conversation. */
  upload: (file: File, caption?: string) => Promise<void>;
  /** Abort an in-flight stream. */
  abort: () => void;
}

/**
 * Strip internal markup from a message before showing it to the user.
 * The backend stores references like `[ref_doc:abc]` and `[附件:x.pdf]` inside
 * message bodies for routing/RAG; these are not meant to be displayed.
 */
function sanitizeDisplay(text: string): string {
  return text
    .replace(/\n*\[ref_doc:[^\]]*\]\n*/g, "\n")
    .replace(/\[附件:[^\]]*\]/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function useProjectChat(
  projectId: string,
  initialPrompt?: string,
  activeNodeId?: string | null,
): UseProjectChat {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [streamingThinkingText, setStreamingThinkingText] = useState("");
  const [streamingBlocks, setStreamingBlocks] = useState<ContentBlock[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const loadSeqRef = useRef(0);
  const activeStreamTokenRef = useRef<number | null>(null);
  const streamSeqRef = useRef(0);
  // Guards the one-shot auto-send of `initialPrompt`. Tri-flipped to true the
  // first time we attempt to send it (whether the send succeeds or not), so a
  // remount/refresh or version switch can never re-fire it.
  const autoSentRef = useRef(false);
  // Latest messages snapshot for the auto-send effect, so we can detect
  // "fresh conversation with no history" without races.
  const messagesLenRef = useRef(0);

  // Load (get-or-create) the project conversation + history for the current
  // scope. Scope switches are hard boundaries: stop the old stream, clear the
  // transient UI state, and fetch only the messages relevant to the new scope.
  useEffect(() => {
    const seq = ++loadSeqRef.current;
    activeStreamTokenRef.current = null;
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
    setStreamingText("");
    setStreamingThinkingText("");
    setStreamingBlocks([]);
    setConversationId(null);
    setThreadId(null);
    setMessages([]);
    messagesLenRef.current = 0;
    setError(null);

    getProjectConversation(projectId, activeNodeId)
      .then((res) => {
        if (seq !== loadSeqRef.current) return;
        if (!res.success || !res.data) {
          setError(res.message ?? "加载项目会话失败");
          return;
        }
        setConversationId(res.data.id);
        setThreadId(res.data.threadId ?? null);
        const history = res.data.messages ?? [];
        setMessages(history);
        messagesLenRef.current = history.length;
      })
      .catch((e) => {
        if (seq === loadSeqRef.current) {
          setError(e instanceof Error ? e.message : "加载项目会话失败");
        }
      });
  }, [projectId, activeNodeId]);

  const send = useCallback(
    (text: string, opts?: { nodeId?: string | null }) => {
      const trimmed = text.trim();
      if (!trimmed || !conversationId || isStreaming) return;
      // Node-scoped conversation: when a nodeId is in play, the backend routes
      // the message through the node-edit handler instead of IntentDetector.
      const nodeId = opts?.nodeId !== undefined ? opts.nodeId : activeNodeId;
      const streamToken = ++streamSeqRef.current;
      activeStreamTokenRef.current = streamToken;

      // Optimistic user message — show the cleaned text, but send the raw
      // (with [ref_doc:...] tags intact) to the backend so RAG routing works.
      const userMsg: ChatMessage = {
        id: `local-${Date.now()}`,
        conversationId,
        threadId: threadId ?? undefined,
        role: "user",
        content: sanitizeDisplay(trimmed),
        contentType: "text",
        metadata: nodeId ? { node_id: nodeId } : undefined,
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);
      messagesLenRef.current += 1;
      setStreamingText("");
      setStreamingThinkingText("");
      setStreamingBlocks([]);
      setIsStreaming(true);
      setError(null);

      abortRef.current = streamChat(
        conversationId,
        trimmed,
        {
          onTextDelta: (delta) =>
            activeStreamTokenRef.current === streamToken &&
            setStreamingText((prev) => prev + delta),
          onThinkingDelta: (delta) =>
            activeStreamTokenRef.current === streamToken &&
            setStreamingThinkingText((prev) => prev + delta),
          onContentBlockStart: (data) => {
            if (activeStreamTokenRef.current !== streamToken) return;
            const blockType = data.block_type as string | undefined;
            if (blockType) {
              setStreamingBlocks((prev) => [
                ...prev,
                { type: blockType as ContentBlock["type"] } as ContentBlock,
              ]);
            }
          },
          onContentBlockData: (data) => {
            if (activeStreamTokenRef.current !== streamToken) return;
            // Replace the last block of the same type with its payload.
            setStreamingBlocks((prev) => {
              const next = [...prev];
              const type = data.type as string | undefined;
              if (type) {
                const idx = next.map((b) => b.type).lastIndexOf(
                  type as ContentBlock["type"],
                );
                if (idx >= 0) {
                  next[idx] = {
                    type: type as ContentBlock["type"],
                    data: data.data as Record<string, unknown> | undefined,
                    content: data.content as string | undefined,
                  };
                } else {
                  next.push({
                    type: type as ContentBlock["type"],
                    data: data.data as Record<string, unknown> | undefined,
                  });
                }
              }
              return next;
            });
          },
          onComplete: (assistantMsg) => {
            if (activeStreamTokenRef.current !== streamToken) return;
            setMessages((prev) => [
              ...prev,
              {
                ...assistantMsg,
                threadId: threadId ?? assistantMsg.threadId,
                metadata: nodeId ? { node_id: nodeId, intent: "node_edit" } : assistantMsg.metadata,
              },
            ]);
            activeStreamTokenRef.current = null;
            abortRef.current = null;
            messagesLenRef.current += 1;
            setStreamingText("");
            setStreamingThinkingText("");
            setStreamingBlocks([]);
            setIsStreaming(false);
          },
          onError: (err) => {
            if (activeStreamTokenRef.current !== streamToken) return;
            activeStreamTokenRef.current = null;
            abortRef.current = null;
            setError(err.message);
            setIsStreaming(false);
            setStreamingText("");
            setStreamingThinkingText("");
            setStreamingBlocks([]);
            toast.error(`对话出错：${err.message}`);
          },
        },
        {
          ...(nodeId ? { node_id: nodeId } : {}),
          ...(threadId ? { thread_id: threadId } : {}),
        },
      );
    },
    [conversationId, isStreaming, activeNodeId, threadId],
  );

  // One-shot auto-send of the initial prompt carried from the landing hero.
  // Fires only when: an initialPrompt exists, the conversation has just been
  // loaded with NO history (fresh project), we haven't sent it yet, AND the
  // chat is NOT bound to a node context (node conversations are user-driven).
  useEffect(() => {
    if (
      initialPrompt &&
      initialPrompt.trim() &&
      conversationId &&
      messagesLenRef.current === 0 &&
      !isStreaming &&
      !autoSentRef.current &&
      !activeNodeId
    ) {
      autoSentRef.current = true;
      send(initialPrompt);
    }
  }, [initialPrompt, conversationId, isStreaming, activeNodeId, send]);

  const upload = useCallback(
    async (file: File, caption?: string) => {
      if (!conversationId) return;
      setIsUploading(true);
      setError(null);
      try {
        const res = await uploadChatFile(conversationId, file, caption);
        if (res.success && res.data) {
          setMessages((prev) => [...prev, res.data!]);
        } else {
          toast.error(res.message ?? "上传失败");
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : "上传失败";
        setError(msg);
        toast.error(msg);
      } finally {
        setIsUploading(false);
      }
    },
    [conversationId],
  );

  const abort = useCallback(() => {
    activeStreamTokenRef.current = null;
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
    setStreamingText("");
    setStreamingThinkingText("");
    setStreamingBlocks([]);
  }, []);

  return {
    conversationId,
    threadId,
    messages,
    isStreaming,
    streamingText,
    streamingThinkingText,
    streamingBlocks,
    isUploading,
    error,
    send,
    upload,
    abort,
  };
}
