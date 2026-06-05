"""Users router — CRUD operations for users."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.db.session import get_db
from app.models.user import Role, User
from app.schemas.common import PaginatedResponse, Response
from app.schemas.user import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=PaginatedResponse[UserOut])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all users with pagination and optional search."""
    query = select(User)
    count_query = select(func.count(User.id))

    if search:
        filter_clause = User.name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%")
        query = query.where(filter_clause)
        count_query = count_query.where(filter_clause)

    if role:
        query = query.join(Role).where(Role.name == role)
        count_query = count_query.join(Role).where(Role.name == role)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(User.created_at.desc())
    result = await db.execute(query)
    users = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=[UserOut.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{user_id}", response_model=Response[UserOut])
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single user by ID."""
    user = await db.get(User, user_id)
    if not user:
        raise NotFoundException("User", str(user_id))
    return Response(data=UserOut.model_validate(user))


@router.post("", response_model=Response[UserOut], status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, db: AsyncSession = Depends(get_db)):
    """Create a new user."""
    role = await db.get(Role, body.role_id)
    if not role:
        raise HTTPException(status_code=400, detail="Role not found")

    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(**body.model_dump())
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return Response(data=UserOut.model_validate(user), message="User created")


@router.put("/{user_id}", response_model=Response[UserOut])
async def update_user(
    user_id: uuid.UUID, body: UserUpdate, db: AsyncSession = Depends(get_db)
):
    """Update an existing user."""
    user = await db.get(User, user_id)
    if not user:
        raise NotFoundException("User", str(user_id))

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    await db.flush()
    await db.refresh(user)
    return Response(data=UserOut.model_validate(user), message="User updated")


@router.delete("/{user_id}", response_model=Response)
async def delete_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a user."""
    user = await db.get(User, user_id)
    if not user:
        raise NotFoundException("User", str(user_id))
    await db.delete(user)
    return Response(message="User deleted")
