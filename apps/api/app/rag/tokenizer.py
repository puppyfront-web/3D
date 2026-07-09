"""Shared CJK-aware tokenizer for RAG keyword search."""

import re
from typing import List

_CJK_PATTERN = re.compile(r"[一-鿿\s]+|[A-Za-z0-9]+")


def tokenize_query(
    query: str, max_tokens: int = 8, min_ascii_len: int = 2
) -> List[str]:
    """Tokenize a query into CJK-aware tokens.

    CJK text is split per-character (each char is a meaningful search unit).
    ASCII alphanumeric runs are kept as whole words.
    Drops ASCII tokens shorter than min_ascii_len. CJK single chars are kept.
    Caps at max_tokens.
    """
    if not query:
        return []
    tokens: List[str] = []
    for match in _CJK_PATTERN.finditer(query):
        raw = match.group().strip()
        if not raw:
            continue
        if re.search(r"[一-鿿]", raw):
            # CJK segment: split per character
            for ch in raw:
                if "\u4e00" <= ch <= "\u9fff":
                    tokens.append(ch)
        else:
            # ASCII: keep whole, filter short
            if len(raw) >= min_ascii_len:
                tokens.append(raw)
        if len(tokens) >= max_tokens:
            break
    return tokens[:max_tokens]
