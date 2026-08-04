"""PricingExperience model — 报价经验库."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PricingExperience(Base):
    """Reusable pricing / quotation reference (报价经验库).

    Captures historical pricing experience per industry / project type so
    future quotes can be grounded in real prior engagements. All figures
    are reference ranges and must be human-confirmed before use — never
    quoted verbatim to a client.
    """

    __tablename__ = "pricing_experiences"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    project_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    budget_range: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    duration: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<PricingExperience {self.title}>"
