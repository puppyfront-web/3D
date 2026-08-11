"""RAG router — hybrid search endpoint + retrieval-log traceability.

Delegates all retrieval logic to HybridRetriever so that scoring weights
and retrieval strategy are defined in exactly one place.
"""

import time
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.retrieval import RetrievalLog
from app.rag.retrieval_orchestrator import retrieval_orchestrator
from app.schemas.common import APIBaseModel, Response
from app.services.knowledge_context_service import build_context_preview_text

router = APIRouter(prefix="/rag", tags=["rag"])


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
    log_id: Optional[str] = None
    context_preview_text: Optional[str] = None


@router.post("/search", response_model=Response[RAGSearchResponse])
async def hybrid_search(
    query: str = Query(..., min_length=1, description="Search query text"),
    top_k: int = Query(5, ge=1, le=50, description="Number of results to return"),
    project_id: Optional[uuid.UUID] = Query(None, description="Limit to a project"),
    retrieval_type: str = Query("hybrid", description="hybrid, keyword, or vector"),
    include_context_preview: bool = Query(
        False, description="Include Context Pack preview text (M2 Lab)"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Perform knowledge search via RetrievalOrchestrator (local / FastGPT / dual)."""
    start = time.monotonic()

    traced = await retrieval_orchestrator.search(
        db,
        query,
        top_k=top_k,
        project_id=project_id,
        triggered_by="rag_hit_test",
    )
    hits = traced.hits

    results = [
        RAGSearchResultItem(
            chunk_id=h.chunk_id,
            document_id=h.document_id,
            content=h.content,
            score=h.score,
            page_number=h.page_number,
            source=h.source,
            title=h.title,
        )
        for h in hits
    ]

    elapsed_ms = int((time.monotonic() - start) * 1000)
    preview = (
        build_context_preview_text(hits, top_k=top_k) if include_context_preview else None
    )
    log_id = str(traced.log_id) if traced.log_id else None

    return Response(
        data=RAGSearchResponse(
            query=query,
            results=results,
            total=len(results),
            latency_ms=elapsed_ms,
            retrieval_type=retrieval_type,
            log_id=log_id,
            context_preview_text=preview,
        )
    )


# ─── Retrieval logs (PRD §9.4 traceability) ──────────────────────────────────


class RetrievalLogOut(APIBaseModel):
    """One retrieval-log row, surfaced for the admin 检索日志 view.

    Inherits APIBaseModel so output serializes to camelCase (matching the
    frontend RetrievalLogItem type) instead of raw snake_case.
    """

    id: uuid.UUID
    query: str
    retrieval_type: str
    results_count: int
    top_scores: Optional[list] = None
    latency_ms: Optional[int] = None
    triggered_by: Optional[str] = None
    structured_query_json: Optional[dict] = None
    retrieved_items_json: Optional[list] = None
    selected_context_json: Optional[dict] = None
    final_output_id: Optional[str] = None
    project_id: Optional[uuid.UUID] = None
    conversation_id: Optional[uuid.UUID] = None
    message_id: Optional[uuid.UUID] = None
    eval_run_id: Optional[uuid.UUID] = None
    created_at: datetime


@router.get("/logs", response_model=Response[List[RetrievalLogOut]])
async def list_retrieval_logs(
    triggered_by: Optional[str] = Query(None, description="Filter by trigger source"),
    retrieval_type: Optional[str] = Query(None, description="Filter by retrieval type"),
    message_id: Optional[uuid.UUID] = Query(None),
    conversation_id: Optional[uuid.UUID] = Query(None),
    project_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List recent retrieval logs (PRD §9.4 / §12).

    Newest first. Optional filters by trigger source (knowledge_search /
    case_search / hybrid_retriever) and retrieval type, so the admin view can
    inspect what each agent actually retrieved.
    """
    stmt = select(RetrievalLog).order_by(RetrievalLog.created_at.desc()).limit(limit)
    if triggered_by:
        stmt = stmt.where(RetrievalLog.triggered_by == triggered_by)
    if retrieval_type:
        stmt = stmt.where(RetrievalLog.retrieval_type == retrieval_type)
    if message_id:
        stmt = stmt.where(RetrievalLog.message_id == message_id)
    if conversation_id:
        stmt = stmt.where(RetrievalLog.conversation_id == conversation_id)
    if project_id:
        stmt = stmt.where(RetrievalLog.project_id == project_id)

    rows = (await db.execute(stmt)).scalars().all()
    return Response(data=[RetrievalLogOut.model_validate(r, from_attributes=True) for r in rows])
