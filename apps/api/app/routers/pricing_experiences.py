"""Pricing experiences router — 报价经验库 CRUD (PRD §12.7).

All figures here are historical reference ranges. They must never be
quoted verbatim to a client — always human-confirmed first.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import Response as RawResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.core.security import require_admin
from app.db.session import get_db
from app.models.pricing_experience import PricingExperience
from app.models.user import User
from app.schemas.common import ImportResponse, PaginatedResponse, Response
from app.schemas.knowledge_base import (
    PricingExperienceCreate,
    PricingExperienceOut,
    PricingExperienceUpdate,
)
from app.services.config_export_service import ConfigExportService
from app.services.import_service import ImportService

router = APIRouter(prefix="/pricing-experiences", tags=["pricing-experiences"])


@router.post("/import", response_model=Response[ImportResponse])
async def import_pricing_experiences(
    file: UploadFile = File(...),
    mode: str = Query("skip", pattern="^(skip|overwrite|rename)$"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    parsed = await ImportService.parse_file(file, "pricing_experience")
    applied = await ImportService.apply_items(db, "pricing_experience", parsed.items, mode)
    summary = ImportService.build_import_response(parsed, applied, "报价经验")
    return Response(data=ImportResponse(**summary), message=summary["message"])


@router.get("/export")
async def export_pricing_experiences(db: AsyncSession = Depends(get_db)):
    payload = await ConfigExportService.export_many(db, "pricing_experience")
    return RawResponse(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="pricing_experiences.json"'},
    )


@router.get("/{experience_id}/export")
async def export_pricing_experience(experience_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    payload = await ConfigExportService.export_one(db, "pricing_experience", experience_id)
    return RawResponse(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="pricing_experience.json"'},
    )


@router.get("", response_model=PaginatedResponse[PricingExperienceOut])
async def list_pricing_experiences(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    industry: Optional[str] = Query(None),
    project_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = select(PricingExperience)
    count_query = select(func.count(PricingExperience.id))

    if industry:
        query = query.where(PricingExperience.industry == industry)
        count_query = count_query.where(PricingExperience.industry == industry)
    if project_type:
        query = query.where(PricingExperience.project_type == project_type)
        count_query = count_query.where(PricingExperience.project_type == project_type)

    total = (await db.execute(count_query)).scalar_one()
    offset = (page - 1) * page_size
    rows = (
        (await db.execute(query.offset(offset).limit(page_size).order_by(PricingExperience.created_at.desc())))
        .scalars()
        .all()
    )
    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=[PricingExperienceOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size, total_pages=total_pages,
    )


@router.get("/{experience_id}", response_model=Response[PricingExperienceOut])
async def get_pricing_experience(experience_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    row = await db.get(PricingExperience, experience_id)
    if not row:
        raise NotFoundException("PricingExperience", str(experience_id))
    return Response(data=PricingExperienceOut.model_validate(row))


@router.post("", response_model=Response[PricingExperienceOut], status_code=status.HTTP_201_CREATED)
async def create_pricing_experience(
    body: PricingExperienceCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    row = PricingExperience(**body.model_dump())
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return Response(data=PricingExperienceOut.model_validate(row), message="报价经验已创建")


@router.put("/{experience_id}", response_model=Response[PricingExperienceOut])
async def update_pricing_experience(
    experience_id: uuid.UUID,
    body: PricingExperienceUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    row = await db.get(PricingExperience, experience_id)
    if not row:
        raise NotFoundException("PricingExperience", str(experience_id))
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.flush()
    await db.refresh(row)
    return Response(data=PricingExperienceOut.model_validate(row), message="报价经验已更新")


@router.delete("/{experience_id}", response_model=Response)
async def delete_pricing_experience(
    experience_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    row = await db.get(PricingExperience, experience_id)
    if not row:
        raise NotFoundException("PricingExperience", str(experience_id))
    await db.delete(row)
    return Response(message="报价经验已删除")
