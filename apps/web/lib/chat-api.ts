"use client";

/**
 * Chat API client — handles SSE streaming and conversation CRUD.
 * Separate from the main api.ts to keep concerns isolated.
 */

import type {
  Conversation,
  ConversationDetail,
  ChatMessage,
  ContentBlock,
  StreamChunk,
  ApiResponse,
} from "@/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── Conversation CRUD ──────────────────────────────────────────

export async function getConversations(
  status?: string
): Promise<ApiResponse<Conversation[]>> {
  const params = status ? `?status=${status}` : "";
  const res = await fetch(`${API_BASE_URL}/api/v1/conversations${params}`);
  if (!res.ok) throw new Error(`Failed to fetch conversations: ${res.status}`);
  return res.json();
}

export async function createConversation(data: {
  projectId?: string;
  title?: string;
}): Promise<ApiResponse<Conversation>> {
  const res = await fetch(`${API_BASE_URL}/api/v1/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok)
    throw new Error(`Failed to create conversation: ${res.status}`);
  return res.json();
}

export async function getConversation(
  id: string
): Promise<ApiResponse<ConversationDetail>> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/conversations/${id}`
  );
  if (!res.ok) throw new Error(`Conversation not found: ${res.status}`);
  return res.json();
}

export async function archiveConversation(
  id: string
): Promise<ApiResponse<null>> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/conversations/${id}`,
    { method: "DELETE" }
  );
  if (!res.ok) throw new Error(`Failed to archive: ${res.status}`);
  return res.json();
}

export async function updateConversation(
  id: string,
  data: { title?: string }
): Promise<ApiResponse<Conversation>> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/conversations/${id}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }
  );
  if (!res.ok) throw new Error(`Failed to update: ${res.status}`);
  return res.json();
}

// ─── SSE Streaming Chat ─────────────────────────────────────────

export interface StreamCallbacks {
  onTextDelta: (text: string) => void;
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
  callbacks: StreamCallbacks
): AbortController {
  const controller = new AbortController();
  let fullText = "";
  const collectedBlocks: ContentBlock[] = [];
  const streamId = `stream-${Date.now()}-${++_streamSeq}`;

  fetch(
    `${API_BASE_URL}/api/v1/conversations/${conversationId}/chat/stream`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
      signal: controller.signal,
    }
  )
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`Stream failed: ${response.status}`);
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
        callbacks.onError(err);
      }
    });

  return controller;
}

// ─── Actions ─────────────────────────────────────────────────────

export async function executeAction(
  conversationId: string,
  action: string,
  data?: {
    skillId?: string;
    formData?: Record<string, unknown>;
    targetMessageId?: string;
  }
): Promise<ApiResponse<ChatMessage>> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/conversations/${conversationId}/actions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action,
        skill_id: data?.skillId,
        form_data: data?.formData,
        target_message_id: data?.targetMessageId,
      }),
    }
  );
  if (!res.ok) throw new Error(`Action failed: ${res.status}`);
  return res.json();
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

  const res = await fetch(
    `${API_BASE_URL}/api/v1/conversations/${conversationId}/upload?${params.toString()}`,
    {
      method: "POST",
      body: formData,
      // Do NOT set Content-Type — browser sets multipart boundary automatically
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
