"""Visual styles router — CRUD."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.db.session import get_db
from app.models.visual import VisualStyle
from app.schemas.common import PaginatedResponse, Response
from app.schemas.visual import VisualStyleCreate, VisualStyleOut, VisualStyleUpdate

router = APIRouter(prefix="/visual-styles", tags=["visual-styles"])


@router.get("", response_model=PaginatedResponse[VisualStyleOut])
async def list_visual_styles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    layout: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List visual styles with pagination."""
    query = select(VisualStyle)
    count_query = select(func.count(VisualStyle.id))

    if layout:
        query = query.where(VisualStyle.layout == layout)
        count_query = count_query.where(VisualStyle.layout == layout)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(VisualStyle.created_at.desc())
    result = await db.execute(query)
    styles = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=[VisualStyleOut.model_validate(s) for s in styles],
        total=total, page=page, page_size=page_size, total_pages=total_pages,
    )


@router.get("/{style_id}", response_model=Response[VisualStyleOut])
async def get_visual_style(style_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a visual style by ID."""
    style = await db.get(VisualStyle, style_id)
    if not style:
        raise NotFoundException("VisualStyle", str(style_id))
    return Response(data=VisualStyleOut.model_validate(style))


@router.post("", response_model=Response[VisualStyleOut], status_code=status.HTTP_201_CREATED)
async def create_visual_style(body: VisualStyleCreate, db: AsyncSession = Depends(get_db)):
    """Create a new visual style."""
    style = VisualStyle(**body.model_dump())
    db.add(style)
    await db.flush()
    await db.refresh(style)
    return Response(data=VisualStyleOut.model_validate(style), message="Visual style created")


@router.put("/{style_id}", response_model=Response[VisualStyleOut])
async def update_visual_style(
    style_id: uuid.UUID, body: VisualStyleUpdate, db: AsyncSession = Depends(get_db)
):
    """Update a visual style."""
    style = await db.get(VisualStyle, style_id)
    if not style:
        raise NotFoundException("VisualStyle", str(style_id))
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(style, field, value)
    await db.flush()
    await db.refresh(style)
    return Response(data=VisualStyleOut.model_validate(style), message="Visual style updated")


@router.delete("/{style_id}", response_model=Response)
async def delete_visual_style(style_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a visual style."""
    style = await db.get(VisualStyle, style_id)
    if not style:
        raise NotFoundException("VisualStyle", str(style_id))
    await db.delete(style)
    return Response(message="Visual style deleted")
