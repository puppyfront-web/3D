"""Projects router — CRUD with status management."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import Field
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

# Project-conversation linking (canvas workspace chat). Imported lazily-bound here
# because the endpoint lives under /projects/{id}/conversation, but the logic
# belongs to the conversation domain.
from app.services.conversation_service import ConversationService
from app.models.conversation import Message
from app.schemas.conversation import ConversationDetail, MessageOut

router = APIRouter(prefix="/projects", tags=["projects"])

_conv_service = ConversationService()


def _message_to_out(m: Message) -> MessageOut:
    """Convert a Message ORM object to MessageOut schema (mirrors conversations router)."""
    return MessageOut(
        id=str(m.id),
        conversation_id=str(m.conversation_id),
        thread_id=str(m.thread_id) if m.thread_id else None,
        role=m.role,
        content=m.content,
        content_type=m.content_type,
        rich_content=m.rich_content,
        skill_execution_id=str(m.skill_execution_id) if m.skill_execution_id else None,
        metadata=m.metadata_json,
        created_at=m.created_at,
    )

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


@router.get(
    "/{project_id}/conversation",
    response_model=Response[ConversationDetail],
)
async def get_project_conversation(
    project_id: uuid.UUID,
    node_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get-or-create the conversation bound to a project.

    Used by the canvas workspace to load its left-rail chat panel with a real,
    project-scoped conversation (history included). The underlying
    Conversation.project_id FK already exists; this endpoint just exposes the
    get-or-create path that the service already supports.
    """
    # Verify the project exists (404 if not).
    project = await db.get(Project, project_id)
    if not project:
        raise NotFoundException("Project", str(project_id))

    conv = await _conv_service.get_or_create_conversation(
        db, project_id=str(project_id)
    )
    thread = await _conv_service.get_or_create_thread(
        db,
        conv.id,
        scope_type="node" if node_id else "project",
        scope_ref_id=node_id,
    )
    messages = await _conv_service.get_thread_history(db, thread.id)

    # Backward compatibility: before thread-scoped persistence landed, node
    # turns lived in the project thread and were separated only by metadata.
    # Keep those histories visible during the migration window.
    project_thread = await _conv_service.get_or_create_thread(
        db,
        conv.id,
        scope_type="project",
    )
    project_messages = await _conv_service.get_thread_history(db, project_thread.id)
    legacy_messages = _conv_service.filter_messages_for_scope(
        project_messages,
        node_id=node_id,
    )

    if node_id:
        combined: list[Message] = []
        seen_ids: set[str] = set()
        for message in [*legacy_messages, *messages]:
            message_id = str(message.id)
            if message_id in seen_ids:
                continue
            seen_ids.add(message_id)
            combined.append(message)
        combined.sort(key=lambda msg: msg.created_at)
        scoped_messages = combined
    else:
        scoped_messages = legacy_messages

    msg_outs = [_message_to_out(m) for m in scoped_messages]

    detail = ConversationDetail(
        id=str(conv.id),
        thread_id=str(thread.id),
        project_id=str(conv.project_id) if conv.project_id else None,
        title=conv.title,
        status=conv.status,
        last_message=msg_outs[-1] if msg_outs else None,
        message_count=len(msg_outs),
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=msg_outs,
    )
    return Response(data=detail, message="Project conversation")


@router.get("/{project_id}/proposal-output", response_model=Response)
async def get_latest_proposal_output(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Return the latest proposal_generation output (设计 Brief) for a project.

    Used by the Canvas workspace's Proposal editor panel and the export
    dropdown to resolve the ``output_id`` + ``sections_meta`` that drive
    章节 review + 导出门控 (PRESALE_DELIVERY_SPEC §6.1 / §10.2).

    Returns 404 when no Brief exists yet — the frontend uses that to hide the
    Proposal entry until auto-fill has produced one.
    """
    from app.models.generation import GenerationOutput, GenerationTask
    from app.schemas.common import APIBaseModel
    from typing import Any, List, Optional
    from datetime import datetime

    class ProposalOutputOut(APIBaseModel):
        """Serializer for the latest Brief — camelCase on the wire."""

        output_id: str
        task_id: str
        sections_meta: List[Any] = Field(default_factory=list)
        used_cases: List[Any] = Field(default_factory=list)
        used_documents: List[Any] = Field(default_factory=list)
        used_chunks: List[Any] = Field(default_factory=list)
        used_external_sources: List[Any] = Field(default_factory=list)
        used_sop_version: Optional[str] = None
        created_at: Optional[str] = None

    project = await db.get(Project, project_id)
    if not project:
        raise NotFoundException("Project", str(project_id))

    result = await db.execute(
        select(GenerationOutput)
        .join(GenerationTask, GenerationTask.id == GenerationOutput.task_id)
        .where(
            GenerationTask.project_id == project_id,
            GenerationTask.type == "proposal_generation",
        )
        .order_by(GenerationOutput.created_at.desc())
        .limit(1)
    )
    output = result.scalar_one_or_none()
    if output is None:
        raise NotFoundException("GenerationOutput", f"project={project_id}")

    return Response(
        data=ProposalOutputOut(
            output_id=str(output.id),
            task_id=str(output.task_id),
            sections_meta=output.sections_meta or [],
            used_cases=output.used_cases or [],
            used_documents=output.used_documents or [],
            used_chunks=output.used_chunks or [],
            used_external_sources=output.used_external_sources or [],
            used_sop_version=output.used_sop_version,
            created_at=output.created_at.isoformat() if output.created_at else None,
        ),
        message="Latest proposal output",
    )
