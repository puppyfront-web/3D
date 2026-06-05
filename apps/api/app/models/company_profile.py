"""CompanyProfile model."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CompanyProfile(Base):
    """AI-generated company analysis profile."""

    __tablename__ = "company_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id"), unique=True, nullable=False, index=True
    )
    strengths: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    weaknesses: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    market_position: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_products: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    competitors: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recent_news: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    culture: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    financials: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="profile", lazy="selectin")

    def __repr__(self) -> str:
        return f"<CompanyProfile for {self.company_id}>"
