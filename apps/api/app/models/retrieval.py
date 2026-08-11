"""RetrievalLog model."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RetrievalLog(Base):
    """Log record for RAG retrieval operations.

    Per PRD §9.4 every retrieval must be traceable: the raw user query, the
    structured query the retriever ran, the items it surfaced, the context
    pack actually selected for generation, and (later) the generation output
    that consumed it. The legacy ``results_count`` / ``top_scores`` /
    ``document_ids`` fields are kept for back-compat; the JSON fields carry
    the richer PRD payload.
    """

    __tablename__ = "retrieval_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_type: Mapped[str] = mapped_column(String(50), nullable=False)
    results_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    top_scores: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    document_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ── PRD §9.4 traceability payload ──────────────────────────────────────
    # The structured query the retriever ran (filters, intent, rewritten q).
    structured_query_json: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, default=dict
    )
    # The raw retrieved items (id + score + source), capped to avoid bloat.
    retrieved_items_json: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, default=list
    )
    # The context pack slice actually selected for generation.
    selected_context_json: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, default=dict
    )
    # Soft FK to the generation output that consumed this retrieval; set
    # after the Agent produces its artefact.
    final_output_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    # Which agent / tool triggered the retrieval (knowledge_search,
    # case_search, planner, …) for filtering the admin log view.
    triggered_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(), nullable=True, index=True)
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(), nullable=True, index=True)
    message_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(), nullable=True, index=True)
    eval_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<RetrievalLog query='{self.query[:50]}'>"
