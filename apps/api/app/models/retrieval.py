"""RetrievalLog model."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RetrievalLog(Base):
    """Log record for RAG retrieval operations."""

    __tablename__ = "retrieval_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_type: Mapped[str] = mapped_column(String(50), nullable=False)
    results_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    top_scores: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    document_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<RetrievalLog query='{self.query[:50]}'>"
