"""Talking points router — 话术库 CRUD (PRD §12.6)."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import Response as RawResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.db.session import get_db
from app.models.talking_point import TalkingPoint
from app.schemas.common import ImportResponse, PaginatedResponse, Response
from app.schemas.knowledge_base import TalkingPointCreate, TalkingPointOut, TalkingPointUpdate
from app.services.config_export_service import ConfigExportService
from app.services.import_service import ImportService

router = APIRouter(prefix="/talking-points", tags=["talking-points"])


@router.post("/import", response_model=Response[ImportResponse])
async def import_talking_points(
    file: UploadFile = File(...),
    mode: str = Query("skip", pattern="^(skip|overwrite|rename)$"),
    db: AsyncSession = Depends(get_db),
):
    parsed = await ImportService.parse_file(file, "talking_point")
    applied = await ImportService.apply_items(db, "talking_point", parsed.items, mode)
    summary = ImportService.build_import_response(parsed, applied, "话术")
    return Response(data=ImportResponse(**summary), message=summary["message"])


@router.get("/export")
async def export_talking_points(db: AsyncSession = Depends(get_db)):
    payload = await ConfigExportService.export_many(db, "talking_point")
    return RawResponse(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="talking_points.json"'},
    )


@router.get("/{point_id}/export")
async def export_talking_point(point_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    payload = await ConfigExportService.export_one(db, "talking_point", point_id)
    return RawResponse(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="talking_point.json"'},
    )


@router.get("", response_model=PaginatedResponse[TalkingPointOut])
async def list_talking_points(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    scenario: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = select(TalkingPoint)
    count_query = select(func.count(TalkingPoint.id))

    if scenario:
        query = query.where(TalkingPoint.scenario == scenario)
        count_query = count_query.where(TalkingPoint.scenario == scenario)
    if industry:
        query = query.where(TalkingPoint.industry == industry)
        count_query = count_query.where(TalkingPoint.industry == industry)

    total = (await db.execute(count_query)).scalar_one()
    offset = (page - 1) * page_size
    rows = (
        (await db.execute(query.offset(offset).limit(page_size).order_by(TalkingPoint.created_at.desc())))
        .scalars()
        .all()
    )
    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=[TalkingPointOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size, total_pages=total_pages,
    )


@router.get("/{point_id}", response_model=Response[TalkingPointOut])
async def get_talking_point(point_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    row = await db.get(TalkingPoint, point_id)
    if not row:
        raise NotFoundException("TalkingPoint", str(point_id))
    return Response(data=TalkingPointOut.model_validate(row))


@router.post("", response_model=Response[TalkingPointOut], status_code=status.HTTP_201_CREATED)
async def create_talking_point(body: TalkingPointCreate, db: AsyncSession = Depends(get_db)):
    row = TalkingPoint(**body.model_dump())
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return Response(data=TalkingPointOut.model_validate(row), message="话术已创建")


@router.put("/{point_id}", response_model=Response[TalkingPointOut])
async def update_talking_point(
    point_id: uuid.UUID, body: TalkingPointUpdate, db: AsyncSession = Depends(get_db)
):
    row = await db.get(TalkingPoint, point_id)
    if not row:
        raise NotFoundException("TalkingPoint", str(point_id))
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.flush()
    await db.refresh(row)
    return Response(data=TalkingPointOut.model_validate(row), message="话术已更新")


@router.delete("/{point_id}", response_model=Response)
async def delete_talking_point(point_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    row = await db.get(TalkingPoint, point_id)
    if not row:
        raise NotFoundException("TalkingPoint", str(point_id))
    await db.delete(row)
    return Response(message="话术已删除")
