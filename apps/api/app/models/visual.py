"""VisualStyle model."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VisualStyle(Base):
    """Visual style configuration for proposal presentations."""

    __tablename__ = "visual_styles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    primary_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#1a73e8")
    secondary_color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    accent_color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    background_color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    font_primary: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    font_secondary: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    layout: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    brand_guidelines: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Design specification fields
    material_spec: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="材质规范参数")
    lighting_spec: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="灯光规范参数")
    # Classification + lifecycle
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # UI 视觉资料子库区分: ui_spec / large_screen / 3d_ref / motion_ref (NULL = 颜色预设)
    sub_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<VisualStyle {self.name}>"
