"""KnowledgeAssetRevision model — version history for knowledge base assets."""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class KnowledgeAssetRevision(Base):
    """A revision snapshot of a knowledge-base asset (PRD §23.4.9)."""
    __tablename__ = "knowledge_asset_revisions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    asset_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    snapshot: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self):
        return f"<KnowledgeAssetRevision {self.asset_type}:{self.version_no}>"
