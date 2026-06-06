"use client";

/**
 * Visual concept API client — handles version tree and artifact endpoints.
 */

import type { ApiResponse } from "@/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── Version Tree ────────────────────────────────────────────────

export async function getVersionTree(
  conversationId: string
): Promise<ApiResponse<Record<string, unknown>>> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/conversations/${conversationId}/version-tree`
  );
  if (!res.ok)
    throw new Error(`Failed to fetch version tree: ${res.status}`);
  return res.json();
}

// ─── Artifacts ───────────────────────────────────────────────────

export async function getArtifact(
  conversationId: string,
  nodeId: string
): Promise<ApiResponse<Record<string, unknown>>> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/conversations/${conversationId}/artifacts/${nodeId}`
  );
  if (!res.ok)
    throw new Error(`Failed to fetch artifact: ${res.status}`);
  return res.json();
}

export async function compareArtifacts(
  conversationId: string,
  nodeA: string,
  nodeB: string
): Promise<ApiResponse<Record<string, unknown>>> {
  const params = new URLSearchParams({ node_a: nodeA, node_b: nodeB });
  const res = await fetch(
    `${API_BASE_URL}/api/v1/conversations/${conversationId}/artifacts/compare?${params.toString()}`
  );
  if (!res.ok)
    throw new Error(`Failed to compare artifacts: ${res.status}`);
  return res.json();
}

// ─── Actions ─────────────────────────────────────────────────────

export async function executeVisualConceptAction(
  conversationId: string,
  action: string,
  formData?: Record<string, unknown>
): Promise<ApiResponse<Record<string, unknown>>> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/conversations/${conversationId}/visual-concept-actions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action,
        form_data: formData,
      }),
    }
  );
  if (!res.ok)
    throw new Error(`Visual concept action failed: ${res.status}`);
  return res.json();
}
