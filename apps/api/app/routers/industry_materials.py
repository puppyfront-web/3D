"""Industry materials router — 行业资料库 CRUD (PRD §12.5)."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import Response as RawResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.db.session import get_db
from app.models.industry_material import IndustryMaterial
from app.schemas.common import ImportResponse, PaginatedResponse, Response
from app.schemas.knowledge_base import (
    IndustryMaterialCreate,
    IndustryMaterialOut,
    IndustryMaterialUpdate,
)
from app.services.config_export_service import ConfigExportService
from app.services.import_service import ImportService

router = APIRouter(prefix="/industry-materials", tags=["industry-materials"])


@router.post("/import", response_model=Response[ImportResponse])
async def import_industry_materials(
    file: UploadFile = File(...),
    mode: str = Query("skip", pattern="^(skip|overwrite|rename)$"),
    db: AsyncSession = Depends(get_db),
):
    parsed = await ImportService.parse_file(file, "industry_material")
    applied = await ImportService.apply_items(db, "industry_material", parsed.items, mode)
    summary = ImportService.build_import_response(parsed, applied, "行业资料")
    return Response(data=ImportResponse(**summary), message=summary["message"])


@router.get("/export")
async def export_industry_materials(db: AsyncSession = Depends(get_db)):
    payload = await ConfigExportService.export_many(db, "industry_material")
    return RawResponse(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="industry_materials.json"'},
    )


@router.get("/{material_id}/export")
async def export_industry_material(material_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    payload = await ConfigExportService.export_one(db, "industry_material", material_id)
    return RawResponse(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="industry_material.json"'},
    )


@router.get("", response_model=PaginatedResponse[IndustryMaterialOut])
async def list_industry_materials(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    industry: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = select(IndustryMaterial)
    count_query = select(func.count(IndustryMaterial.id))

    if industry:
        query = query.where(IndustryMaterial.industry == industry)
        count_query = count_query.where(IndustryMaterial.industry == industry)
    if category:
        query = query.where(IndustryMaterial.category == category)
        count_query = count_query.where(IndustryMaterial.category == category)

    total = (await db.execute(count_query)).scalar_one()
    offset = (page - 1) * page_size
    rows = (
        (await db.execute(query.offset(offset).limit(page_size).order_by(IndustryMaterial.created_at.desc())))
        .scalars()
        .all()
    )
    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=[IndustryMaterialOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size, total_pages=total_pages,
    )


@router.get("/{material_id}", response_model=Response[IndustryMaterialOut])
async def get_industry_material(material_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    row = await db.get(IndustryMaterial, material_id)
    if not row:
        raise NotFoundException("IndustryMaterial", str(material_id))
    return Response(data=IndustryMaterialOut.model_validate(row))


@router.post("", response_model=Response[IndustryMaterialOut], status_code=status.HTTP_201_CREATED)
async def create_industry_material(body: IndustryMaterialCreate, db: AsyncSession = Depends(get_db)):
    row = IndustryMaterial(**body.model_dump())
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return Response(data=IndustryMaterialOut.model_validate(row), message="行业资料已创建")


@router.put("/{material_id}", response_model=Response[IndustryMaterialOut])
async def update_industry_material(
    material_id: uuid.UUID, body: IndustryMaterialUpdate, db: AsyncSession = Depends(get_db)
):
    row = await db.get(IndustryMaterial, material_id)
    if not row:
        raise NotFoundException("IndustryMaterial", str(material_id))
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.flush()
    await db.refresh(row)
    return Response(data=IndustryMaterialOut.model_validate(row), message="行业资料已更新")


@router.delete("/{material_id}", response_model=Response)
async def delete_industry_material(material_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    row = await db.get(IndustryMaterial, material_id)
    if not row:
        raise NotFoundException("IndustryMaterial", str(material_id))
    await db.delete(row)
    return Response(message="行业资料已删除")
