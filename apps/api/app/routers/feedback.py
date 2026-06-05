"""Feedback router — CRUD."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.db.session import get_db
from app.models.feedback import Feedback
from app.schemas.common import PaginatedResponse, Response
from app.schemas.feedback import FeedbackCreate, FeedbackOut, FeedbackUpdate

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.get("", response_model=PaginatedResponse[FeedbackOut])
async def list_feedback(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    project_id: Optional[uuid.UUID] = Query(None),
    user_id: Optional[uuid.UUID] = Query(None),
    min_rating: Optional[int] = Query(None, ge=1, le=5),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List feedback with pagination and filters."""
    query = select(Feedback)
    count_query = select(func.count(Feedback.id))

    if project_id:
        query = query.where(Feedback.project_id == project_id)
        count_query = count_query.where(Feedback.project_id == project_id)
    if user_id:
        query = query.where(Feedback.user_id == user_id)
        count_query = count_query.where(Feedback.user_id == user_id)
    if min_rating:
        query = query.where(Feedback.rating >= min_rating)
        count_query = count_query.where(Feedback.rating >= min_rating)
    if category:
        query = query.where(Feedback.category == category)
        count_query = count_query.where(Feedback.category == category)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(Feedback.created_at.desc())
    result = await db.execute(query)
    items = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=[FeedbackOut.model_validate(f) for f in items],
        total=total, page=page, page_size=page_size, total_pages=total_pages,
    )


@router.get("/{feedback_id}", response_model=Response[FeedbackOut])
async def get_feedback(feedback_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    fb = await db.get(Feedback, feedback_id)
    if not fb:
        raise NotFoundException("Feedback", str(feedback_id))
    return Response(data=FeedbackOut.model_validate(fb))


@router.post("", response_model=Response[FeedbackOut], status_code=status.HTTP_201_CREATED)
async def create_feedback(body: FeedbackCreate, db: AsyncSession = Depends(get_db)):
    """Create feedback. Uses the first admin user as the feedback author in mock mode."""
    from app.models.user import User
    result = await db.execute(select(User).limit(1))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundException("User", "No users found")

    fb = Feedback(
        project_id=body.project_id,
        user_id=user.id,
        generation_task_id=body.generation_task_id,
        rating=body.rating,
        comment=body.comment,
        category=body.category,
    )
    db.add(fb)
    await db.flush()
    await db.refresh(fb)
    return Response(data=FeedbackOut.model_validate(fb), message="Feedback created")


@router.put("/{feedback_id}", response_model=Response[FeedbackOut])
async def update_feedback(
    feedback_id: uuid.UUID, body: FeedbackUpdate, db: AsyncSession = Depends(get_db)
):
    fb = await db.get(Feedback, feedback_id)
    if not fb:
        raise NotFoundException("Feedback", str(feedback_id))
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(fb, field, value)
    await db.flush()
    await db.refresh(fb)
    return Response(data=FeedbackOut.model_validate(fb), message="Feedback updated")


@router.delete("/{feedback_id}", response_model=Response)
async def delete_feedback(feedback_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    fb = await db.get(Feedback, feedback_id)
    if not fb:
        raise NotFoundException("Feedback", str(feedback_id))
    await db.delete(fb)
    return Response(message="Feedback deleted")
