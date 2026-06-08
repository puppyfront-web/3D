"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useReducer,
  useRef,
} from "react";
import type {
  Conversation,
  ChatMessage,
  ContentBlock,
} from "@/types";
import {
  getConversations as fetchConversations,
  createConversation as apiCreateConversation,
  getConversation as apiGetConversation,
  streamChat,
  uploadChatFile,
  type StreamCallbacks,
} from "@/lib/chat-api";
import { VisualConceptProvider } from "@/lib/visual-concept-context";

// ─── State ────────────────────────────────────────────────────────

interface ChatState {
  conversations: Conversation[];
  activeConversationId: string | null;
  messages: ChatMessage[];
  isLoading: boolean;
  isStreaming: boolean;
  isUploading: boolean;
  streamingText: string;
  streamingBlocks: ContentBlock[];
  error: string | null;
}

type ChatAction =
  | { type: "SET_CONVERSATIONS"; payload: Conversation[] }
  | { type: "SET_ACTIVE"; payload: string | null }
  | { type: "SET_MESSAGES"; payload: ChatMessage[] }
  | { type: "ADD_USER_MESSAGE"; payload: ChatMessage }
  | { type: "START_STREAM" }
  | { type: "APPEND_TEXT_DELTA"; payload: string }
  | { type: "ADD_STREAM_BLOCK"; payload: ContentBlock }
  | { type: "COMPLETE_STREAM"; payload: ChatMessage }
  | { type: "STREAM_ERROR"; payload: string }
  | { type: "SET_LOADING"; payload: boolean }
  | { type: "SET_UPLOADING"; payload: boolean }
  | { type: "SET_ERROR"; payload: string | null }
  | { type: "UPDATE_CONVERSATION"; payload: { id: string; title: string } }
  | { type: "REMOVE_CONVERSATION"; payload: string };

const initialState: ChatState = {
  conversations: [],
  activeConversationId: null,
  messages: [],
  isLoading: false,
  isStreaming: false,
  isUploading: false,
  streamingText: "",
  streamingBlocks: [],
  error: null,
};

function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "SET_CONVERSATIONS":
      return { ...state, conversations: action.payload };

    case "SET_ACTIVE":
      return { ...state, activeConversationId: action.payload, messages: [] };

    case "SET_MESSAGES":
      return { ...state, messages: action.payload };

    case "ADD_USER_MESSAGE":
      return {
        ...state,
        messages: [...state.messages, action.payload],
      };

    case "START_STREAM":
      return {
        ...state,
        isStreaming: true,
        streamingText: "",
        streamingBlocks: [],
        error: null,
      };

    case "APPEND_TEXT_DELTA":
      return {
        ...state,
        streamingText: state.streamingText + action.payload,
      };

    case "ADD_STREAM_BLOCK":
      return {
        ...state,
        streamingBlocks: [...state.streamingBlocks, action.payload],
      };

    case "COMPLETE_STREAM": {
      // Avoid duplicate IDs (e.g. if stream fires onComplete twice)
      const existingIds = new Set(state.messages.map((m) => m.id));
      const msg = action.payload;
      const messages = existingIds.has(msg.id)
        ? state.messages
        : [...state.messages, msg];
      return {
        ...state,
        isStreaming: false,
        streamingText: "",
        streamingBlocks: [],
        messages,
      };
    }

    case "STREAM_ERROR":
      return {
        ...state,
        isStreaming: false,
        streamingText: "",
        streamingBlocks: [],
        error: action.payload,
      };

    case "SET_LOADING":
      return { ...state, isLoading: action.payload };

    case "SET_UPLOADING":
      return { ...state, isUploading: action.payload };

    case "SET_ERROR":
      return { ...state, error: action.payload };

    case "UPDATE_CONVERSATION":
      return {
        ...state,
        conversations: state.conversations.map((c) =>
          c.id === action.payload.id ? { ...c, title: action.payload.title } : c
        ),
      };

    case "REMOVE_CONVERSATION": {
      const isTarget = state.activeConversationId === action.payload;
      return {
        ...state,
        conversations: state.conversations.filter((c) => c.id !== action.payload),
        activeConversationId: isTarget ? null : state.activeConversationId,
        messages: isTarget ? [] : state.messages,
      };
    }

    default:
      return state;
  }
}

// ─── Context ──────────────────────────────────────────────────────

interface ChatContextValue {
  state: ChatState;
  loadConversations: () => Promise<void>;
  selectConversation: (id: string) => Promise<void>;
  createConversation: (data: {
    projectId?: string;
    title?: string;
  }) => Promise<string>;
  sendMessage: (content: string, overrideConversationId?: string) => void;
  uploadFile: (file: File, caption: string) => Promise<void>;
  abortStream: () => void;
  renameConversation: (id: string, title: string) => Promise<void>;
  deleteConversation: (id: string) => Promise<void>;
}

const ChatContext = createContext<ChatContextValue | null>(null);

// ─── Provider ─────────────────────────────────────────────────────

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(chatReducer, initialState);
  const abortRef = useRef<AbortController | null>(null);

  const loadConversations = useCallback(async () => {
    try {
      const res = await fetchConversations();
      dispatch({ type: "SET_CONVERSATIONS", payload: res.data || [] });
    } catch (err) {
      dispatch({
        type: "SET_ERROR",
        payload: err instanceof Error ? err.message : "Failed to load conversations",
      });
    }
  }, []);

  const selectConversation = useCallback(async (id: string) => {
    dispatch({ type: "SET_ACTIVE", payload: id });
    dispatch({ type: "SET_LOADING", payload: true });
    try {
      const res = await apiGetConversation(id);
      // Map snake_case fields from API to camelCase for frontend types
      const messages = (res.data?.messages || []).map((msg) => {
        const raw = msg as unknown as Record<string, unknown>;
        return {
          ...msg,
          createdAt: msg.createdAt || raw.created_at,
          richContent: msg.richContent || raw.rich_content,
        };
      }) as ChatMessage[];
      dispatch({ type: "SET_MESSAGES", payload: messages });
    } catch (err) {
      dispatch({
        type: "SET_ERROR",
        payload: err instanceof Error ? err.message : "Failed to load messages",
      });
    } finally {
      dispatch({ type: "SET_LOADING", payload: false });
    }
  }, []);

  const createConversation = useCallback(
    async (data: { projectId?: string; title?: string }) => {
      try {
        const res = await apiCreateConversation(data);
        const conv = res.data!;
        dispatch({
          type: "SET_CONVERSATIONS",
          payload: [conv, ...state.conversations],
        });
        dispatch({ type: "SET_ACTIVE", payload: conv.id });
        dispatch({ type: "SET_MESSAGES", payload: [] });
        return conv.id;
      } catch (err) {
        dispatch({
          type: "SET_ERROR",
          payload: err instanceof Error ? err.message : "Failed to create conversation",
        });
        throw err;
      }
    },
    [state.conversations]
  );

  const sendMessage = useCallback(
    (content: string, overrideConversationId?: string) => {
      const convId = overrideConversationId || state.activeConversationId;
      if (!convId || state.isStreaming) return;

      // Add user message immediately
      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        conversationId: convId,
        role: "user",
        content,
        contentType: "text",
        createdAt: new Date().toISOString(),
      };
      dispatch({ type: "ADD_USER_MESSAGE", payload: userMsg });

      // Start streaming
      dispatch({ type: "START_STREAM" });

      const callbacks: StreamCallbacks = {
        onTextDelta: (text) => {
          dispatch({ type: "APPEND_TEXT_DELTA", payload: text });
        },
        onContentBlockData: (data) => {
          if (data?.type) {
            dispatch({
              type: "ADD_STREAM_BLOCK",
              payload: data as unknown as ContentBlock,
            });
          }
        },
        onComplete: (message) => {
          dispatch({ type: "COMPLETE_STREAM", payload: message });
          // Reload conversations to update last message
          loadConversations();
        },
        onError: (error) => {
          dispatch({
            type: "STREAM_ERROR",
            payload: error.message,
          });
        },
      };

      const controller = streamChat(convId, content, callbacks);
      abortRef.current = controller;
    },
    [state.activeConversationId, state.isStreaming, loadConversations]
  );

  const abortStream = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    dispatch({ type: "STREAM_ERROR", payload: "Stream aborted" });
  }, []);

  const uploadFile = useCallback(
    async (file: File, caption: string) => {
      if (!state.activeConversationId) return;
      dispatch({ type: "SET_UPLOADING", payload: true });
      try {
        const res = await uploadChatFile(
          state.activeConversationId,
          file,
          caption
        );
        if (res.data) {
          dispatch({ type: "ADD_USER_MESSAGE", payload: res.data });
        }
        loadConversations();
      } catch (err) {
        dispatch({
          type: "SET_ERROR",
          payload: err instanceof Error ? err.message : "Upload failed",
        });
      } finally {
        dispatch({ type: "SET_UPLOADING", payload: false });
      }
    },
    [state.activeConversationId, loadConversations]
  );

  const renameConversation = useCallback(
    async (id: string, title: string) => {
      try {
        const { updateConversation } = await import("@/lib/chat-api");
        await updateConversation(id, { title });
        dispatch({ type: "UPDATE_CONVERSATION", payload: { id, title } });
      } catch (err) {
        dispatch({
          type: "SET_ERROR",
          payload: err instanceof Error ? err.message : "Rename failed",
        });
      }
    },
    []
  );

  const deleteConversation = useCallback(
    async (id: string) => {
      try {
        const { archiveConversation } = await import("@/lib/chat-api");
        await archiveConversation(id);
        dispatch({ type: "REMOVE_CONVERSATION", payload: id });
      } catch (err) {
        dispatch({
          type: "SET_ERROR",
          payload: err instanceof Error ? err.message : "Delete failed",
        });
      }
    },
    []
  );

  return (
    <VisualConceptProvider>
      <ChatContext.Provider
        value={{
          state,
          loadConversations,
          selectConversation,
          createConversation,
          sendMessage,
          uploadFile,
          abortStream,
          renameConversation,
          deleteConversation,
        }}
      >
        {children}
      </ChatContext.Provider>
    </VisualConceptProvider>
  );
}

// ─── Hook ─────────────────────────────────────────────────────────

export function useChat(): ChatContextValue {
  const ctx = useContext(ChatContext);
  if (!ctx) {
    throw new Error("useChat must be used within a ChatProvider");
  }
  return ctx;
}
