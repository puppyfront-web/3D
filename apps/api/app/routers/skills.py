"""Skills router — list, inspect, and execute skills."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.db.session import get_db
from app.models.skill import Skill, SkillExecution
from app.schemas.common import Response
from app.schemas.skill import SkillExecuteRequest, SkillExecutionOut, SkillOut, SkillManifestOut
from app.services.llm_service import get_llm_service
from app.services.embedding_service import get_embedding_service
from app.services.image_service import get_image_service
from app.skills.base import SkillContext
from app.skills.registry import SkillRegistry
from app.skills.runner import SkillRunner

router = APIRouter(prefix="/skills", tags=["skills"])

# Ensure built-in skills are registered on module load
_registry = SkillRegistry.get_instance()
_registry.auto_register()


@router.get("", response_model=Response)
async def list_skills():
    """List all registered skills with their manifests."""
    manifests = _registry.list_skills()
    return Response(
        data=[SkillManifestOut(
            skill_id=m.skill_id,
            name=m.name,
            description=m.description,
            category=m.category,
            input_schema=m.input_schema,
            output_schema=m.output_schema,
            required_services=m.required_services,
            permissions=m.permissions,
            visibility=m.visibility,
            version=m.version,
        ).model_dump() for m in manifests],
        message="Skills listed",
    )


@router.get("/executions", response_model=Response)
async def list_executions(
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List skill execution history."""
    query = select(SkillExecution).order_by(SkillExecution.created_at.desc())
    if project_id:
        query = query.where(SkillExecution.project_id == uuid.UUID(project_id))
    if status:
        query = query.where(SkillExecution.status == status)

    # Count
    from sqlalchemy import func
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    executions = result.scalars().all()

    items = [SkillExecutionOut(
        id=str(e.id),
        skill_id=str(e.skill_id),
        project_id=str(e.project_id) if e.project_id else None,
        user_id=str(e.user_id) if e.user_id else None,
        input_json=e.input_json,
        output_json=e.output_json,
        status=e.status,
        error_message=e.error_message,
        duration_ms=e.duration_ms,
        used_cases=e.used_cases,
        used_documents=e.used_documents,
        used_chunks=e.used_chunks,
        created_at=e.created_at.isoformat() if e.created_at else None,
        completed_at=e.completed_at.isoformat() if e.completed_at else None,
    ).model_dump() for e in executions]

    return Response(data={"items": items, "total": total, "page": page, "page_size": page_size})


@router.get("/executions/{execution_id}", response_model=Response)
async def get_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single skill execution detail."""
    execution = await db.get(SkillExecution, uuid.UUID(execution_id))
    if not execution:
        raise NotFoundException("SkillExecution", execution_id)

    return Response(data=SkillExecutionOut(
        id=str(execution.id),
        skill_id=str(execution.skill_id),
        project_id=str(execution.project_id) if execution.project_id else None,
        user_id=str(execution.user_id) if execution.user_id else None,
        input_json=execution.input_json,
        output_json=execution.output_json,
        status=execution.status,
        error_message=execution.error_message,
        duration_ms=execution.duration_ms,
        used_cases=execution.used_cases,
        used_documents=execution.used_documents,
        used_chunks=execution.used_chunks,
        created_at=execution.created_at.isoformat() if execution.created_at else None,
        completed_at=execution.completed_at.isoformat() if execution.completed_at else None,
    ).model_dump())


@router.get("/{skill_id}", response_model=Response)
async def get_skill(skill_id: str):
    """Get a single skill manifest."""
    skill = _registry.get(skill_id)
    if not skill:
        raise NotFoundException("Skill", skill_id)

    m = skill.manifest
    return Response(data=SkillManifestOut(
        skill_id=m.skill_id,
        name=m.name,
        description=m.description,
        category=m.category,
        input_schema=m.input_schema,
        output_schema=m.output_schema,
        required_services=m.required_services,
        permissions=m.permissions,
        visibility=m.visibility,
        version=m.version,
    ).model_dump())


@router.post("/{skill_id}/execute", response_model=Response)
async def execute_skill(
    skill_id: str,
    body: SkillExecuteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Execute a skill by ID."""
    skill = _registry.get(skill_id)
    if not skill:
        raise NotFoundException("Skill", skill_id)

    context = SkillContext(
        project_id=body.project_id,
        user_id=body.user_id,
        db=db,
        llm_service=await get_llm_service(db),
        embedding_service=await get_embedding_service(db),
        image_service=await get_image_service(db),
    )

    runner = SkillRunner(registry=_registry)
    result = await runner.run(skill_id, body.input_data, context)

    return Response(data=result, message="Skill executed")
