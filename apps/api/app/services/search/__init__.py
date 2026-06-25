"""Search service package — external web search with provider abstraction."""

from app.services.search.base import SearchHit, SearchProvider, WebSearchResult
from app.services.search.factory import search
from app.services.search.orchestrator import SearchOrchestrator

__all__ = [
    "SearchHit",
    "SearchProvider",
    "WebSearchResult",
    "SearchOrchestrator",
    "search",
]
