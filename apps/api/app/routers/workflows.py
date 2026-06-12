"""Workflows router — SOP workflow CRUD."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import Response as RawResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.db.session import get_db
from app.models.workflow import SOPWorkflow
from app.schemas.common import ImportResponse, PaginatedResponse, Response
from app.schemas.workflow import SOPWorkflowCreate, SOPWorkflowOut, SOPWorkflowUpdate
from app.services.config_export_service import ConfigExportService
from app.services.import_service import ImportService

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("/import", response_model=Response[ImportResponse])
async def import_workflows(
    file: UploadFile = File(...),
    mode: str = Query(
        "skip",
        pattern="^(skip|overwrite|rename)$",
        description="冲突策略: skip 跳过已存在 / overwrite 覆盖 / rename 建副本",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Import SOP workflows from JSON file."""
    parsed = await ImportService.parse_file(file, "sop_workflow")
    applied = await ImportService.apply_items(db, "sop_workflow", parsed.items, mode)
    summary = ImportService.build_import_response(parsed, applied, "工作流")
    return Response(data=ImportResponse(**summary), message=summary["message"])


@router.get("/export")
async def export_workflows(db: AsyncSession = Depends(get_db)):
    """Export all SOP workflows as a re-importable JSON download."""
    payload = await ConfigExportService.export_many(db, "sop_workflow")
    return RawResponse(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="sop_workflows.json"'},
    )


@router.get("/{workflow_id}/export")
async def export_workflow(workflow_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Export a single SOP workflow as a re-importable JSON download."""
    payload = await ConfigExportService.export_one(db, "sop_workflow", workflow_id)
    return RawResponse(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="sop_workflow.json"'},
    )


@router.get("", response_model=PaginatedResponse[SOPWorkflowOut])
async def list_workflows(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List SOP workflows with pagination."""
    query = select(SOPWorkflow)
    count_query = select(func.count(SOPWorkflow.id))

    if is_active is not None:
        query = query.where(SOPWorkflow.is_active == is_active)
        count_query = count_query.where(SOPWorkflow.is_active == is_active)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(SOPWorkflow.created_at.desc())
    result = await db.execute(query)
    workflows = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=[SOPWorkflowOut.model_validate(w) for w in workflows],
        total=total, page=page, page_size=page_size, total_pages=total_pages,
    )


@router.get("/{workflow_id}", response_model=Response[SOPWorkflowOut])
async def get_workflow(workflow_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a workflow by ID."""
    wf = await db.get(SOPWorkflow, workflow_id)
    if not wf:
        raise NotFoundException("SOPWorkflow", str(workflow_id))
    return Response(data=SOPWorkflowOut.model_validate(wf))


@router.post("", response_model=Response[SOPWorkflowOut], status_code=status.HTTP_201_CREATED)
async def create_workflow(body: SOPWorkflowCreate, db: AsyncSession = Depends(get_db)):
    """Create a new SOP workflow."""
    wf = SOPWorkflow(**body.model_dump())
    db.add(wf)
    await db.flush()
    await db.refresh(wf)
    return Response(data=SOPWorkflowOut.model_validate(wf), message="Workflow created")


@router.put("/{workflow_id}", response_model=Response[SOPWorkflowOut])
async def update_workflow(
    workflow_id: uuid.UUID, body: SOPWorkflowUpdate, db: AsyncSession = Depends(get_db)
):
    """Update a workflow."""
    wf = await db.get(SOPWorkflow, workflow_id)
    if not wf:
        raise NotFoundException("SOPWorkflow", str(workflow_id))
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(wf, field, value)
    await db.flush()
    await db.refresh(wf)
    return Response(data=SOPWorkflowOut.model_validate(wf), message="Workflow updated")


@router.delete("/{workflow_id}", response_model=Response)
async def delete_workflow(workflow_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a workflow."""
    wf = await db.get(SOPWorkflow, workflow_id)
    if not wf:
        raise NotFoundException("SOPWorkflow", str(workflow_id))
    await db.delete(wf)
    return Response(message="Workflow deleted")
