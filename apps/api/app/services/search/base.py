"""Search service — external information retrieval with provider abstraction.

Precedence chain (orchestrated by SearchOrchestrator):
  1. Tavily provider (if API key configured) — dedicated search API
  2. LLM-native search (if configured LLM supports web_search tool)
  3. Degraded fallback — returns status="failed", never raises

All providers return a normalised WebSearchResult. Failures never raise out —
they surface as status="degraded"/"failed" so callers (WebSearchTool, skills)
can continue without blocking the pipeline. See
docs/superpowers/specs/2026-06-25-web-search-tool-boundary.md.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SearchHit:
    """A single normalised search result item."""

    title: str
    url: str
    snippet: str
    domain: str = ""
    published_at: Optional[str] = None
    source_type: str = "article"  # official | news | article
    confidence: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "domain": self.domain,
            "published_at": self.published_at,
            "source_type": self.source_type,
            "confidence": round(self.confidence, 3),
        }


@dataclass
class WebSearchResult:
    """Normalised output of any search provider.

    status:
      ok       — got usable results
      degraded — ran but results unusable (low confidence / partial failure)
      failed   — provider unavailable / errored entirely
    """

    query: str
    status: str = "failed"
    hits: List[SearchHit] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    provider: str = ""  # tavily | llm_native | none
    degraded_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "status": self.status,
            "results": [h.to_dict() for h in self.hits],
            "summary": self.summary,
            "provider": self.provider,
            "degraded_reason": self.degraded_reason,
        }


class SearchProvider(ABC):
    """Abstract base for a search backend."""

    name: str = ""

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 5,
        timeout: int = 15,
        min_confidence: float = 0.5,
    ) -> WebSearchResult:
        """Run a search. Must NOT raise — return status=failed on error."""
