"""Lightweight token estimation without tiktoken dependency.

Uses a simple heuristic: ~1.5 chars per token for Chinese, ~4 chars per token
for English. Accuracy is ~80-90% which is sufficient for budget guardrails
(not billing).

This module intentionally avoids a hard dependency on `tiktoken` so the app
keeps working in minimal deployments. The estimates are deliberately
conservative (slightly over-count) so guardrails trip *before* a real overflow.
"""

from typing import Any, Dict, List


def estimate_tokens(text: str) -> int:
    """Estimate token count for a text string."""
    if not text:
        return 0
    # Count CJK characters (each ~1-2 tokens)
    cjk_count = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    # Non-CJK text (~4 chars per token)
    non_cjk_len = len(text) - cjk_count
    return int(cjk_count * 1.5 + non_cjk_len / 4)


def estimate_messages_tokens(messages: List[Dict[str, Any]]) -> int:
    """Estimate total tokens for a message list (includes overhead per message)."""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        else:
            # Non-string content (e.g. vision parts) — fall back to its repr.
            total += estimate_tokens(str(content))
        total += 4  # overhead per message (role + formatting)
    return total


def truncate_to_budget(text: str, max_tokens: int, from_end: bool = False) -> str:
    """Truncate text to fit within a token budget.

    If from_end=True, keep the tail (drop the beginning) — useful for keeping
    the most recent content while shedding older history.
    """
    est = estimate_tokens(text)
    if est <= max_tokens:
        return text
    # Scale length by the ratio of budgets, with a 5% safety margin.
    ratio = max_tokens / est
    target_len = int(len(text) * ratio * 0.95)
    if target_len < 1:
        target_len = 1
    if from_end:
        return "..." + text[-target_len:]
    return text[:target_len] + "..."
