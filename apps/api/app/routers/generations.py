"""Generations router — generation task/output endpoints."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.exceptions import NotFoundException
from app.db.session import get_db
from app.models.generation import GenerationOutput, GenerationTask
from app.models.project import Project
from app.schemas.common import PaginatedResponse, Response
from app.schemas.generation import (
    GenerationOutputOut,
    GenerationTaskCreate,
    GenerationTaskOut,
    GenerationTaskUpdate,
    ProposalContentUpdate,
    ProposalSectionStatusUpdate,
)

router = APIRouter(prefix="/generations", tags=["generations"])


@router.get("/tasks", response_model=PaginatedResponse[GenerationTaskOut])
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    project_id: Optional[uuid.UUID] = Query(None),
    task_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
):
    """List generation tasks."""
    query = select(GenerationTask)
    count_query = select(func.count(GenerationTask.id))

    if project_id:
        query = query.where(GenerationTask.project_id == project_id)
        count_query = count_query.where(GenerationTask.project_id == project_id)
    if task_type:
        query = query.where(GenerationTask.type == task_type)
        count_query = count_query.where(GenerationTask.type == task_type)
    if status_filter:
        query = query.where(GenerationTask.status == status_filter)
        count_query = count_query.where(GenerationTask.status == status_filter)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(GenerationTask.created_at.desc())
    result = await db.execute(query)
    tasks = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=[GenerationTaskOut.model_validate(t) for t in tasks],
        total=total, page=page, page_size=page_size, total_pages=total_pages,
    )


@router.get("/tasks/{task_id}", response_model=Response[GenerationTaskOut])
async def get_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a generation task by ID, including its outputs."""
    task = await db.get(GenerationTask, task_id)
    if not task:
        raise NotFoundException("GenerationTask", str(task_id))
    return Response(data=GenerationTaskOut.model_validate(task))


@router.post("/tasks", response_model=Response[GenerationTaskOut], status_code=status.HTTP_201_CREATED)
async def create_task(body: GenerationTaskCreate, db: AsyncSession = Depends(get_db)):
    """Create a new generation task."""
    project = await db.get(Project, body.project_id)
    if not project:
        raise NotFoundException("Project", str(body.project_id))

    task = GenerationTask(
        project_id=body.project_id,
        type=body.type,
        prompt_used=body.prompt_used,
        status="pending",
        model_used="mock-v1",
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return Response(data=GenerationTaskOut.model_validate(task), message="Generation task created")


@router.patch("/tasks/{task_id}", response_model=Response[GenerationTaskOut])
async def update_task(
    task_id: uuid.UUID, body: GenerationTaskUpdate, db: AsyncSession = Depends(get_db)
):
    """Update a generation task status."""
    task = await db.get(GenerationTask, task_id)
    if not task:
        raise NotFoundException("GenerationTask", str(task_id))

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)

    if body.status == "completed":
        task.completed_at = datetime.now(timezone.utc)
    elif body.status == "running" and not task.started_at:
        task.started_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(task)
    return Response(data=GenerationTaskOut.model_validate(task), message="Task updated")


@router.get("/tasks/{task_id}/outputs", response_model=PaginatedResponse[GenerationOutputOut])
async def list_task_outputs(
    task_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List outputs for a generation task."""
    task = await db.get(GenerationTask, task_id)
    if not task:
        raise NotFoundException("GenerationTask", str(task_id))

    query = (
        select(GenerationOutput)
        .where(GenerationOutput.task_id == task_id)
        .order_by(GenerationOutput.created_at.desc())
    )
    count_query = select(func.count(GenerationOutput.id)).where(
        GenerationOutput.task_id == task_id
    )

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    outputs = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=[GenerationOutputOut.model_validate(o) for o in outputs],
        total=total, page=page, page_size=page_size, total_pages=total_pages,
    )


@router.get("/outputs/{output_id}", response_model=Response[GenerationOutputOut])
async def get_output(output_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a generation output by ID."""
    output = await db.get(GenerationOutput, output_id)
    if not output:
        raise NotFoundException("GenerationOutput", str(output_id))
    return Response(data=GenerationOutputOut.model_validate(output))


@router.delete("/tasks/{task_id}", response_model=Response)
async def delete_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a generation task and its outputs."""
    task = await db.get(GenerationTask, task_id)
    if not task:
        raise NotFoundException("GenerationTask", str(task_id))
    await db.delete(task)
    return Response(message="Generation task deleted")


@router.put("/outputs/{output_id}", response_model=Response[GenerationOutputOut])
async def update_output(
    output_id: uuid.UUID,
    body: ProposalContentUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update proposal content or sections metadata (human edit)."""
    output = await db.get(GenerationOutput, output_id)
    if not output:
        raise NotFoundException("GenerationOutput", str(output_id))

    if body.content is not None:
        output.content = body.content
    if body.sections_meta is not None:
        output.sections_meta = body.sections_meta

    await db.flush()
    await db.refresh(output)
    return Response(data=GenerationOutputOut.model_validate(output), message="Output updated")


@router.patch(
    "/outputs/{output_id}/sections/{section_order}/status",
    response_model=Response[GenerationOutputOut],
)
async def update_section_status(
    output_id: uuid.UUID,
    section_order: int,
    body: ProposalSectionStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a single section's review status."""
    output = await db.get(GenerationOutput, output_id)
    if not output:
        raise NotFoundException("GenerationOutput", str(output_id))

    sections_meta = output.sections_meta or []
    if section_order < 1 or section_order > len(sections_meta):
        raise HTTPException(
            status_code=400,
            detail=f"Section order {section_order} out of range (1-{len(sections_meta)})",
        )

    # Find and update the section (order is 1-based)
    for section in sections_meta:
        if section.get("order") == section_order:
            section["status"] = body.status
            if body.status == "approved":
                section["reviewed_by"] = body.reviewed_by or "unknown"
                section["reviewed_at"] = datetime.now(timezone.utc).isoformat()
                # Approving a HITL-gated section confirms it for export — flips
                # the export_gate check (routers/exports._check_export_eligibility)
                # from blocked to allowed for this section.
                section["human_confirmed"] = True
            else:
                section["reviewed_by"] = None
                section["reviewed_at"] = None
                section["human_confirmed"] = False
            break

    output.sections_meta = sections_meta
    flag_modified(output, "sections_meta")
    await db.flush()
    await db.refresh(output)
    return Response(data=GenerationOutputOut.model_validate(output), message="Section status updated")
