"""Project and Company models."""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Company(Base):
    """Client company record."""

    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    projects: Mapped[List["Project"]] = relationship(back_populates="company", lazy="selectin")
    profile: Mapped[Optional["CompanyProfile"]] = relationship(
        back_populates="company", uselist=False, lazy="selectin"
    )


class Project(Base):
    """Project record linking a company to a proposal effort."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id"), nullable=False, index=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(50), default="draft", nullable=False
    )
    priority: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="projects", lazy="selectin")
    owner: Mapped["User"] = relationship(lazy="selectin")
    documents: Mapped[List["Document"]] = relationship(back_populates="project", lazy="selectin")
    cases: Mapped[List["Case"]] = relationship(back_populates="project", lazy="selectin")
    generation_tasks: Mapped[List["GenerationTask"]] = relationship(
        back_populates="project", lazy="selectin"
    )
    feedback: Mapped[List["Feedback"]] = relationship(back_populates="project", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Project {self.name}>"
