"use client";

/**
 * Chat API client — SSE streaming + file upload for the canvas left-rail
 * conversation. Conversation CRUD used to live here for the legacy global
 * chat workspace; that page was removed and the canvas now talks to the
 * project-scoped conversation via lib/canvas-api.ts, so only the streaming
 * and upload primitives remain.
 */

import type {
  ChatMessage,
  ContentBlock,
  StreamChunk,
  ApiResponse,
} from "@/types";
import { toast } from "sonner";
import { getToken } from "@/lib/auth";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── SSE Streaming Chat ─────────────────────────────────────────

export interface StreamCallbacks {
  onTextDelta: (text: string) => void;
  onThinkingDelta?: (text: string) => void;
  onContentBlockStart?: (data: Record<string, unknown>) => void;
  onContentBlockData?: (data: Record<string, unknown>) => void;
  onContentBlockEnd?: () => void;
  onComplete: (message: ChatMessage) => void;
  onError: (error: Error) => void;
}

/**
 * Stream a chat message via SSE. Returns an AbortController to cancel.
 *
 * Usage:
 *   const ctrl = streamChat(convId, "Hello", callbacks);
 *   // later: ctrl.abort();
 */
// Unique counter to avoid key collisions from Date.now()
let _streamSeq = 0;

export function streamChat(
  conversationId: string,
  message: string,
  callbacks: StreamCallbacks,
  extraBody?: Record<string, unknown>
): AbortController {
  const controller = new AbortController();
  let fullText = "";
  const collectedBlocks: ContentBlock[] = [];
  const streamId = `stream-${Date.now()}-${++_streamSeq}`;

  // Inject JWT as Bearer token if available.
  const token = getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  fetch(
    `${API_BASE_URL}/api/v1/conversations/${conversationId}/chat/stream`,
    {
      method: "POST",
      headers,
      body: JSON.stringify({ message, ...(extraBody ?? {}) }),
      signal: controller.signal,
    }
  )
    .then(async (response) => {
      if (!response.ok) {
        const errText = await response.text().catch(() => "");
        const errMsg = `Stream failed: ${response.status}`;
        toast.error(`对话流错误 (${response.status})`, {
          description: errText ? errText.slice(0, 200) : errMsg,
        });
        throw new Error(errMsg);
      }
      if (!response.body) {
        throw new Error("No response body for streaming");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parse SSE lines
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;

          try {
            const chunk: StreamChunk = JSON.parse(line.slice(6));

            switch (chunk.type) {
              case "text_delta":
                fullText += chunk.text || "";
                callbacks.onTextDelta(chunk.text || "");
                break;

              case "thinking_delta":
                callbacks.onThinkingDelta?.(chunk.text || "");
                break;

              case "content_block_start":
                callbacks.onContentBlockStart?.(chunk.data || {});
                break;

              case "content_block_data":
                if (chunk.data?.type) {
                  collectedBlocks.push(chunk.data as unknown as ContentBlock);
                }
                callbacks.onContentBlockData?.(chunk.data || {});
                break;

              case "content_block_end":
                callbacks.onContentBlockEnd?.();
                break;

              case "done": {
                // Create a synthetic ChatMessage with collected rich content
                const assistantMsg: ChatMessage = {
                  id: streamId,
                  conversationId,
                  role: "assistant",
                  content: fullText,
                  contentType: collectedBlocks.length > 0 ? "rich" : "text",
                  richContent: collectedBlocks.length > 0
                    ? { blocks: collectedBlocks }
                    : undefined,
                  createdAt: new Date().toISOString(),
                };
                callbacks.onComplete(assistantMsg);
                break;
              }

              case "error":
                callbacks.onError(
                  new Error(
                    (chunk.data?.error as string) || "Stream error"
                  )
                );
                break;

              default:
                // Visual concept agent sends raw block types (visual_result, visual_strategy,
                // skill_progress, action_buttons, quality_check, etc.) — collect them too.
                if (chunk.data) {
                  collectedBlocks.push({ type: chunk.type, data: chunk.data } as unknown as ContentBlock);
                  callbacks.onContentBlockData?.({ type: chunk.type, data: chunk.data });
                } else if (chunk.text) {
                  // text-only non-standard chunks (e.g. error messages)
                  fullText += chunk.text;
                  callbacks.onTextDelta(chunk.text);
                }
                break;
            }
          } catch {
            // Ignore malformed JSON in SSE
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        toast.error("对话连接失败", {
          description: err.message || "未知错误",
        });
        callbacks.onError(err);
      }
    });

  return controller;
}

// ─── File Upload ─────────────────────────────────────────────────

export async function uploadChatFile(
  conversationId: string,
  file: File,
  caption?: string
): Promise<ApiResponse<ChatMessage>> {
  const formData = new FormData();
  formData.append("file", file);

  const params = new URLSearchParams();
  if (caption) params.set("caption", caption);

  // Inject JWT as Bearer token if available. Do NOT set Content-Type — the
  // browser sets the multipart boundary automatically.
  const token = getToken();
  const reqHeaders: Record<string, string> = {};
  if (token) reqHeaders["Authorization"] = `Bearer ${token}`;

  const res = await fetch(
    `${API_BASE_URL}/api/v1/conversations/${conversationId}/upload?${params.toString()}`,
    {
      method: "POST",
      headers: reqHeaders,
      body: formData,
    }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(
      (err as Record<string, unknown>).detail
        ? String((err as Record<string, unknown>).detail)
        : `Upload failed: ${res.status}`
    );
  }
  return res.json();
}
