"""RAG router — hybrid search endpoint.

Delegates all retrieval logic to HybridRetriever so that scoring weights
and retrieval strategy are defined in exactly one place.
"""

import time
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.rag.retriever import HybridRetriever
from app.schemas.common import Response

router = APIRouter(prefix="/rag", tags=["rag"])

# Single retriever instance — weights are configured here, centrally.
_retriever = HybridRetriever()


class RAGSearchResultItem(BaseModel):
    """Single search result from RAG retrieval."""

    chunk_id: str
    document_id: str
    content: str
    score: float
    page_number: Optional[int] = None
    source: Optional[str] = None
    title: Optional[str] = None


class RAGSearchResponse(BaseModel):
    """Response wrapper for RAG search results."""

    query: str
    results: List[RAGSearchResultItem]
    total: int
    latency_ms: int
    retrieval_type: str


@router.post("/search", response_model=Response[RAGSearchResponse])
async def hybrid_search(
    query: str = Query(..., min_length=1, description="Search query text"),
    top_k: int = Query(5, ge=1, le=50, description="Number of results to return"),
    project_id: Optional[uuid.UUID] = Query(None, description="Limit to a project"),
    retrieval_type: str = Query("hybrid", description="hybrid, keyword, or vector"),
    db: AsyncSession = Depends(get_db),
):
    """Perform hybrid search using the shared HybridRetriever.

    Scoring weights and retrieval logic live in app.rag.retriever.HybridRetriever.
    This router only handles HTTP request/response and logging.
    """
    start = time.monotonic()

    # Delegate to the centralised retriever (includes logging inside search())
    raw_results = await _retriever.search(
        query=query,
        top_k=top_k,
        project_id=project_id,
        retrieval_type=retrieval_type,
        db=db,
    )

    # Development fallback: return mock results when no real data is indexed.
    # This keeps the endpoint usable during early development without data.
    if not raw_results:
        raw_results = _retriever._mock_search(query, top_k, retrieval_type)

    results = [
        RAGSearchResultItem(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            content=r.content,
            score=r.score,
            page_number=r.page_number,
            source=r.source,
            title=r.title,
        )
        for r in raw_results
    ]

    elapsed_ms = int((time.monotonic() - start) * 1000)

    return Response(
        data=RAGSearchResponse(
            query=query,
            results=results,
            total=len(results),
            latency_ms=elapsed_ms,
            retrieval_type=retrieval_type,
        )
    )
