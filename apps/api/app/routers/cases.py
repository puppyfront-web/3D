"""Cases router — CRUD with quality scoring."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.db.session import get_db
from app.models.case import Case
from app.schemas.case import CaseCreate, CaseOut, CaseQualityScore, CaseUpdate
from app.schemas.common import ImportResponse, PaginatedResponse, Response
from app.services.import_service import ImportService

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("/import", response_model=Response[ImportResponse])
async def import_cases(
    file: UploadFile = File(...),
    project_id: uuid.UUID = Query(..., description="Required: project to associate imported cases with"),
    db: AsyncSession = Depends(get_db),
):
    """Import cases from JSON or CSV file."""
    result = await ImportService.parse_file(file, "case")
    for item in result.items:
        item["project_id"] = project_id
        case = Case(**item)
        db.add(case)
    await db.flush()
    return Response(
        data=ImportResponse(
            imported=result.imported,
            failed=result.failed,
            errors=result.errors,
            message=f"成功导入 {result.imported} 条案例",
        ),
        message=f"导入完成: {result.imported} 成功, {result.failed} 失败",
    )


@router.get("", response_model=PaginatedResponse[CaseOut])
async def list_cases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    project_id: Optional[uuid.UUID] = Query(None),
    industry: Optional[str] = Query(None),
    published_only: Optional[bool] = Query(None),
    min_score: Optional[float] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List cases with pagination and filters."""
    query = select(Case)
    count_query = select(func.count(Case.id))

    if project_id:
        query = query.where(Case.project_id == project_id)
        count_query = count_query.where(Case.project_id == project_id)
    if industry:
        query = query.where(Case.industry == industry)
        count_query = count_query.where(Case.industry == industry)
    if published_only:
        query = query.where(Case.is_published == True)
        count_query = count_query.where(Case.is_published == True)
    if min_score is not None:
        query = query.where(Case.quality_score >= min_score)
        count_query = count_query.where(Case.quality_score >= min_score)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(Case.created_at.desc())
    result = await db.execute(query)
    cases = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=[CaseOut.model_validate(c) for c in cases],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{case_id}", response_model=Response[CaseOut])
async def get_case(case_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a case by ID."""
    case = await db.get(Case, case_id)
    if not case:
        raise NotFoundException("Case", str(case_id))
    return Response(data=CaseOut.model_validate(case))


@router.post("", response_model=Response[CaseOut], status_code=status.HTTP_201_CREATED)
async def create_case(body: CaseCreate, db: AsyncSession = Depends(get_db)):
    """Create a new case study."""
    case = Case(**body.model_dump())
    db.add(case)
    await db.flush()
    await db.refresh(case)
    return Response(data=CaseOut.model_validate(case), message="Case created")


@router.put("/{case_id}", response_model=Response[CaseOut])
async def update_case(
    case_id: uuid.UUID, body: CaseUpdate, db: AsyncSession = Depends(get_db)
):
    """Update a case study."""
    case = await db.get(Case, case_id)
    if not case:
        raise NotFoundException("Case", str(case_id))

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(case, field, value)

    await db.flush()
    await db.refresh(case)
    return Response(data=CaseOut.model_validate(case), message="Case updated")


@router.patch("/{case_id}/quality-score", response_model=Response[CaseOut])
async def update_quality_score(
    case_id: uuid.UUID, body: CaseQualityScore, db: AsyncSession = Depends(get_db)
):
    """Update the quality score of a case study."""
    case = await db.get(Case, case_id)
    if not case:
        raise NotFoundException("Case", str(case_id))

    case.quality_score = body.score
    await db.flush()
    await db.refresh(case)
    return Response(data=CaseOut.model_validate(case), message="Quality score updated")


@router.delete("/{case_id}", response_model=Response)
async def delete_case(case_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a case study."""
    case = await db.get(Case, case_id)
    if not case:
        raise NotFoundException("Case", str(case_id))
    await db.delete(case)
    await db.flush()
    return Response(message="Case deleted")
