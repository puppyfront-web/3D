"""Projects router — CRUD with status management."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.db.session import get_db
from app.models.project import Project
from app.schemas.common import PaginatedResponse, Response
from app.schemas.project import (
    ProjectCreate,
    ProjectOut,
    ProjectStatusUpdate,
    ProjectUpdate,
    ProjectWizardCreate,
)
from app.services.project_service import project_service

router = APIRouter(prefix="/projects", tags=["projects"])

VALID_STATUSES = {"draft", "in_progress", "review", "completed", "archived"}


@router.get("", response_model=PaginatedResponse[ProjectOut])
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    company_id: Optional[uuid.UUID] = Query(None),
    priority: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List projects with pagination and filters."""
    query = select(Project)
    count_query = select(func.count(Project.id))

    if status_filter:
        query = query.where(Project.status == status_filter)
        count_query = count_query.where(Project.status == status_filter)
    if company_id:
        query = query.where(Project.company_id == company_id)
        count_query = count_query.where(Project.company_id == company_id)
    if priority:
        query = query.where(Project.priority == priority)
        count_query = count_query.where(Project.priority == priority)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(Project.created_at.desc())
    result = await db.execute(query)
    projects = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=[ProjectOut.model_validate(p) for p in projects],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{project_id}", response_model=Response[ProjectOut])
async def get_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a project by ID."""
    project = await db.get(Project, project_id)
    if not project:
        raise NotFoundException("Project", str(project_id))
    return Response(data=ProjectOut.model_validate(project))


@router.post("", response_model=Response[ProjectOut], status_code=status.HTTP_201_CREATED)
async def create_project(body: ProjectCreate, db: AsyncSession = Depends(get_db)):
    """Create a new project (raw CRUD — requires company_id/owner_id)."""
    project = Project(**body.model_dump())
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return Response(data=ProjectOut.model_validate(project), message="Project created")


@router.post(
    "/wizard",
    response_model=Response[ProjectOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_project_wizard(body: ProjectWizardCreate, db: AsyncSession = Depends(get_db)):
    """Create a project from the multi-step wizard payload.

    Resolves the owner (default seeded user) and create-or-gets the Company
    from step1/step2 — the frontend never has to supply company_id/owner_id.
    Accepts the frontend's nested camelCase payload via alias mapping.
    """
    project = await project_service.create_from_wizard(db, body)
    return Response(data=ProjectOut.model_validate(project), message="Project created")


@router.put("/{project_id}", response_model=Response[ProjectOut])
async def update_project(
    project_id: uuid.UUID, body: ProjectUpdate, db: AsyncSession = Depends(get_db)
):
    """Update a project."""
    project = await db.get(Project, project_id)
    if not project:
        raise NotFoundException("Project", str(project_id))

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    await db.flush()
    await db.refresh(project)
    return Response(data=ProjectOut.model_validate(project), message="Project updated")


@router.patch("/{project_id}/status", response_model=Response[ProjectOut])
async def update_project_status(
    project_id: uuid.UUID, body: ProjectStatusUpdate, db: AsyncSession = Depends(get_db)
):
    """Update the status of a project."""
    if body.status not in VALID_STATUSES:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(sorted(VALID_STATUSES))}",
        )

    project = await db.get(Project, project_id)
    if not project:
        raise NotFoundException("Project", str(project_id))

    project.status = body.status
    await db.flush()
    await db.refresh(project)
    return Response(data=ProjectOut.model_validate(project), message="Status updated")


@router.delete("/{project_id}", response_model=Response)
async def delete_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a project."""
    project = await db.get(Project, project_id)
    if not project:
        raise NotFoundException("Project", str(project_id))
    await db.delete(project)
    await db.flush()
    return Response(message="Project deleted")
