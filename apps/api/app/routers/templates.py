"""Templates router — Prompt + Proposal template CRUD."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.db.session import get_db
from app.models.template import PromptTemplate, ProposalTemplate
from app.schemas.common import ImportResponse, PaginatedResponse, Response
from app.schemas.template import (
    PromptTemplateCreate,
    PromptTemplateOut,
    PromptTemplateUpdate,
    ProposalTemplateCreate,
    ProposalTemplateOut,
    ProposalTemplateUpdate,
)
from app.services.import_service import ImportService

router = APIRouter(prefix="/templates", tags=["templates"])


# ---------------------------------------------------------------------------
# Prompt Templates
# ---------------------------------------------------------------------------

@router.post("/prompts/import", response_model=Response[ImportResponse])
async def import_prompt_templates(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Import prompt templates from JSON, TXT, or MD file."""
    result = await ImportService.parse_file(file, "prompt_template")
    for item in result.items:
        tmpl = PromptTemplate(**item)
        db.add(tmpl)
    await db.flush()
    return Response(
        data=ImportResponse(
            imported=result.imported,
            failed=result.failed,
            errors=result.errors,
            message=f"成功导入 {result.imported} 条 Prompt 模板",
        ),
        message=f"导入完成: {result.imported} 成功, {result.failed} 失败",
    )


@router.get("/prompts", response_model=PaginatedResponse[PromptTemplateOut])
async def list_prompt_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List prompt templates."""
    query = select(PromptTemplate)
    count_query = select(func.count(PromptTemplate.id))

    if category:
        query = query.where(PromptTemplate.category == category)
        count_query = count_query.where(PromptTemplate.category == category)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(PromptTemplate.created_at.desc())
    result = await db.execute(query)
    items = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=[PromptTemplateOut.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size, total_pages=total_pages,
    )


@router.get("/prompts/{template_id}", response_model=Response[PromptTemplateOut])
async def get_prompt_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    tmpl = await db.get(PromptTemplate, template_id)
    if not tmpl:
        raise NotFoundException("PromptTemplate", str(template_id))
    return Response(data=PromptTemplateOut.model_validate(tmpl))


@router.post("/prompts", response_model=Response[PromptTemplateOut], status_code=status.HTTP_201_CREATED)
async def create_prompt_template(body: PromptTemplateCreate, db: AsyncSession = Depends(get_db)):
    tmpl = PromptTemplate(**body.model_dump())
    db.add(tmpl)
    await db.flush()
    await db.refresh(tmpl)
    return Response(data=PromptTemplateOut.model_validate(tmpl), message="Prompt template created")


@router.put("/prompts/{template_id}", response_model=Response[PromptTemplateOut])
async def update_prompt_template(
    template_id: uuid.UUID, body: PromptTemplateUpdate, db: AsyncSession = Depends(get_db)
):
    tmpl = await db.get(PromptTemplate, template_id)
    if not tmpl:
        raise NotFoundException("PromptTemplate", str(template_id))
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(tmpl, field, value)
    await db.flush()
    await db.refresh(tmpl)
    return Response(data=PromptTemplateOut.model_validate(tmpl), message="Prompt template updated")


@router.delete("/prompts/{template_id}", response_model=Response)
async def delete_prompt_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    tmpl = await db.get(PromptTemplate, template_id)
    if not tmpl:
        raise NotFoundException("PromptTemplate", str(template_id))
    await db.delete(tmpl)
    return Response(message="Prompt template deleted")


# ---------------------------------------------------------------------------
# Proposal Templates
# ---------------------------------------------------------------------------

@router.post("/proposals/import", response_model=Response[ImportResponse])
async def import_proposal_templates(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Import proposal templates from JSON file."""
    result = await ImportService.parse_file(file, "proposal_template")
    for item in result.items:
        tmpl = ProposalTemplate(**item)
        db.add(tmpl)
    await db.flush()
    return Response(
        data=ImportResponse(
            imported=result.imported,
            failed=result.failed,
            errors=result.errors,
            message=f"成功导入 {result.imported} 条策划案模板",
        ),
        message=f"导入完成: {result.imported} 成功, {result.failed} 失败",
    )


@router.get("/proposals", response_model=PaginatedResponse[ProposalTemplateOut])
async def list_proposal_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List proposal templates."""
    query = select(ProposalTemplate)
    count_query = select(func.count(ProposalTemplate.id))

    if category:
        query = query.where(ProposalTemplate.category == category)
        count_query = count_query.where(ProposalTemplate.category == category)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(ProposalTemplate.created_at.desc())
    result = await db.execute(query)
    items = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=[ProposalTemplateOut.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size, total_pages=total_pages,
    )


@router.get("/proposals/{template_id}", response_model=Response[ProposalTemplateOut])
async def get_proposal_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    tmpl = await db.get(ProposalTemplate, template_id)
    if not tmpl:
        raise NotFoundException("ProposalTemplate", str(template_id))
    return Response(data=ProposalTemplateOut.model_validate(tmpl))


@router.post("/proposals", response_model=Response[ProposalTemplateOut], status_code=status.HTTP_201_CREATED)
async def create_proposal_template(body: ProposalTemplateCreate, db: AsyncSession = Depends(get_db)):
    tmpl = ProposalTemplate(**body.model_dump())
    db.add(tmpl)
    await db.flush()
    await db.refresh(tmpl)
    return Response(data=ProposalTemplateOut.model_validate(tmpl), message="Proposal template created")


@router.put("/proposals/{template_id}", response_model=Response[ProposalTemplateOut])
async def update_proposal_template(
    template_id: uuid.UUID, body: ProposalTemplateUpdate, db: AsyncSession = Depends(get_db)
):
    tmpl = await db.get(ProposalTemplate, template_id)
    if not tmpl:
        raise NotFoundException("ProposalTemplate", str(template_id))
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(tmpl, field, value)
    await db.flush()
    await db.refresh(tmpl)
    return Response(data=ProposalTemplateOut.model_validate(tmpl), message="Proposal template updated")


@router.delete("/proposals/{template_id}", response_model=Response)
async def delete_proposal_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    tmpl = await db.get(ProposalTemplate, template_id)
    if not tmpl:
        raise NotFoundException("ProposalTemplate", str(template_id))
    await db.delete(tmpl)
    return Response(message="Proposal template deleted")
