"""Companies router — CRUD operations."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.db.session import get_db
from app.models.project import Company
from app.schemas.common import PaginatedResponse, Response
from app.schemas.company import CompanyCreate, CompanyOut, CompanyUpdate

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=PaginatedResponse[CompanyOut])
async def list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List companies with pagination and filters."""
    query = select(Company)
    count_query = select(func.count(Company.id))

    if search:
        clause = Company.name.ilike(f"%{search}%")
        query = query.where(clause)
        count_query = count_query.where(clause)
    if industry:
        query = query.where(Company.industry == industry)
        count_query = count_query.where(Company.industry == industry)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(Company.created_at.desc())
    result = await db.execute(query)
    companies = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=[CompanyOut.model_validate(c) for c in companies],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{company_id}", response_model=Response[CompanyOut])
async def get_company(company_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a company by ID."""
    company = await db.get(Company, company_id)
    if not company:
        raise NotFoundException("Company", str(company_id))
    return Response(data=CompanyOut.model_validate(company))


@router.post("", response_model=Response[CompanyOut], status_code=status.HTTP_201_CREATED)
async def create_company(body: CompanyCreate, db: AsyncSession = Depends(get_db)):
    """Create a new company."""
    company = Company(**body.model_dump())
    db.add(company)
    await db.flush()
    await db.refresh(company)
    return Response(data=CompanyOut.model_validate(company), message="Company created")


@router.put("/{company_id}", response_model=Response[CompanyOut])
async def update_company(
    company_id: uuid.UUID, body: CompanyUpdate, db: AsyncSession = Depends(get_db)
):
    """Update a company."""
    company = await db.get(Company, company_id)
    if not company:
        raise NotFoundException("Company", str(company_id))

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(company, field, value)

    await db.flush()
    await db.refresh(company)
    return Response(data=CompanyOut.model_validate(company), message="Company updated")


@router.delete("/{company_id}", response_model=Response)
async def delete_company(company_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a company."""
    company = await db.get(Company, company_id)
    if not company:
        raise NotFoundException("Company", str(company_id))
    await db.delete(company)
    return Response(message="Company deleted")
