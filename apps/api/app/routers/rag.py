"""RAG router — hybrid search endpoint."""

import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.document import DocumentChunk
from app.models.retrieval import RetrievalLog
from app.schemas.common import Response

router = APIRouter(prefix="/rag", tags=["rag"])


class RAGSearchResultItem(BaseModel):
    """Single search result from RAG retrieval."""

    chunk_id: str
    document_id: str
    content: str
    score: float
    page_number: Optional[int] = None
    metadata: Optional[dict] = None


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
    """Perform hybrid search (keyword + vector mock) over document chunks.

    In mock mode, keyword search uses ILIKE matching.  Vector search
    returns simulated cosine-similarity scores.  Hybrid blends both.
    """
    start = time.monotonic()

    # Build keyword query
    keyword_query = select(DocumentChunk)
    conditions = []
    for word in query.split()[:5]:
        conditions.append(DocumentChunk.content.ilike(f"%{word}%"))

    base_filter = DocumentChunk.content != ""
    if conditions:
        base_filter = base_filter & or_(*conditions)

    keyword_query = keyword_query.where(base_filter)

    if project_id:
        from app.models.document import Document

        keyword_query = keyword_query.join(Document).where(
            Document.project_id == project_id
        )

    keyword_query = keyword_query.limit(top_k)
    result = await db.execute(keyword_query)
    chunks = result.scalars().all()

    # Build results with simulated scores
    results: List[RAGSearchResultItem] = []
    for idx, chunk in enumerate(chunks):
        base_score = 0.95 - (idx * 0.08)
        keyword_score = base_score if retrieval_type in ("hybrid", "keyword") else 0.0
        vector_score = base_score * 0.92 if retrieval_type in ("hybrid", "vector") else 0.0

        if retrieval_type == "hybrid":
            final_score = round(0.6 * keyword_score + 0.4 * vector_score, 3)
        elif retrieval_type == "keyword":
            final_score = round(keyword_score, 3)
        else:
            final_score = round(vector_score, 3)

        results.append(
            RAGSearchResultItem(
                chunk_id=str(chunk.id),
                document_id=str(chunk.document_id),
                content=chunk.content[:500],
                score=final_score,
                page_number=chunk.page_number,
            )
        )

    # If no real chunks found, return mock results for development
    if not results:
        results = _generate_mock_results(query, top_k)

    elapsed_ms = int((time.monotonic() - start) * 1000)

    # Log the retrieval
    log = RetrievalLog(
        query=query,
        retrieval_type=retrieval_type,
        results_count=len(results),
        top_scores=[r.score for r in results[:5]],
        document_ids=list({r.document_id for r in results}),
        latency_ms=elapsed_ms,
    )
    db.add(log)
    await db.flush()

    return Response(
        data=RAGSearchResponse(
            query=query,
            results=results,
            total=len(results),
            latency_ms=elapsed_ms,
            retrieval_type=retrieval_type,
        )
    )


def _generate_mock_results(query: str, top_k: int) -> List[RAGSearchResultItem]:
    """Return realistic mock search results for development."""
    mock_docs = [
        {
            "content": "Cloud migration best practices recommend a phased approach starting with non-critical workloads. Organizations should assess application dependencies, establish network connectivity, and implement monitoring before migrating production systems.",
            "doc_id": str(uuid.uuid4()),
        },
        {
            "content": "The company's digital transformation strategy focuses on three pillars: infrastructure modernization, data-driven decision making, and customer experience enhancement. Key initiatives include cloud adoption, AI integration, and omnichannel platform development.",
            "doc_id": str(uuid.uuid4()),
        },
        {
            "content": "Successful enterprise transformations require executive sponsorship, clear communication plans, and dedicated change management resources. Studies show that projects with formal change management are six times more likely to meet objectives.",
            "doc_id": str(uuid.uuid4()),
        },
        {
            "content": "Technology stack evaluation criteria should include scalability, security compliance, integration capabilities, total cost of ownership, and vendor support quality. Our assessment framework covers 47 distinct evaluation dimensions.",
            "doc_id": str(uuid.uuid4()),
        },
        {
            "content": "Implementation methodology follows agile principles with two-week sprints, daily standups, and regular stakeholder demos. Risk mitigation includes automated testing, blue-green deployments, and rollback procedures for all major releases.",
            "doc_id": str(uuid.uuid4()),
        },
    ]

    results = []
    for i, doc in enumerate(mock_docs[:top_k]):
        results.append(
            RAGSearchResultItem(
                chunk_id=str(uuid.uuid4()),
                document_id=doc["doc_id"],
                content=doc["content"],
                score=round(0.95 - i * 0.07, 3),
                page_number=i + 1,
            )
        )
    return results
