"""Company profiles router — CRUD + AI generation endpoint."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.db.session import get_db
from app.models.company_profile import CompanyProfile
from app.models.project import Company
from app.schemas.common import PaginatedResponse, Response
from app.schemas.company_profile import (
    CompanyAnalysisRequest,
    CompanyProfileCreate,
    CompanyProfileOut,
    CompanyProfileUpdate,
)

router = APIRouter(prefix="/company-profiles", tags=["company-profiles"])


@router.get("", response_model=PaginatedResponse[CompanyProfileOut])
async def list_profiles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    company_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List company profiles with pagination."""
    query = select(CompanyProfile)
    count_query = select(func.count(CompanyProfile.id))

    if company_id:
        query = query.where(CompanyProfile.company_id == company_id)
        count_query = count_query.where(CompanyProfile.company_id == company_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(CompanyProfile.created_at.desc())
    result = await db.execute(query)
    profiles = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=[CompanyProfileOut.model_validate(p) for p in profiles],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{profile_id}", response_model=Response[CompanyProfileOut])
async def get_profile(profile_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a company profile by ID."""
    profile = await db.get(CompanyProfile, profile_id)
    if not profile:
        raise NotFoundException("CompanyProfile", str(profile_id))
    return Response(data=CompanyProfileOut.model_validate(profile))


@router.get("/by-company/{company_id}", response_model=Response[CompanyProfileOut])
async def get_profile_by_company(company_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get the profile for a specific company."""
    result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.company_id == company_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise NotFoundException("CompanyProfile for company", str(company_id))
    return Response(data=CompanyProfileOut.model_validate(profile))


@router.get("/by-project/{project_id}", response_model=Response[CompanyProfileOut])
async def get_profile_by_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get the company profile via project_id — resolves project → company → profile."""
    from app.models.project import Project
    project = await db.get(Project, project_id)
    if not project:
        raise NotFoundException("Project", str(project_id))
    result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.company_id == project.company_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise NotFoundException("CompanyProfile for project", str(project_id))
    return Response(data=CompanyProfileOut.model_validate(profile))


@router.post("", response_model=Response[CompanyProfileOut], status_code=status.HTTP_201_CREATED)
async def create_profile(body: CompanyProfileCreate, db: AsyncSession = Depends(get_db)):
    """Create a company profile."""
    company = await db.get(Company, body.company_id)
    if not company:
        raise NotFoundException("Company", str(body.company_id))

    existing = await db.execute(
        select(CompanyProfile).where(CompanyProfile.company_id == body.company_id)
    )
    if existing.scalar_one_or_none():
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail="Profile already exists for this company")

    profile = CompanyProfile(**body.model_dump())
    db.add(profile)
    await db.flush()
    await db.refresh(profile)
    return Response(data=CompanyProfileOut.model_validate(profile), message="Profile created")


@router.put("/{profile_id}", response_model=Response[CompanyProfileOut])
async def update_profile(
    profile_id: uuid.UUID, body: CompanyProfileUpdate, db: AsyncSession = Depends(get_db)
):
    """Update a company profile."""
    profile = await db.get(CompanyProfile, profile_id)
    if not profile:
        raise NotFoundException("CompanyProfile", str(profile_id))

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.flush()
    await db.refresh(profile)
    return Response(data=CompanyProfileOut.model_validate(profile), message="Profile updated")


@router.post("/generate", response_model=Response[CompanyProfileOut])
async def generate_company_analysis(
    body: CompanyAnalysisRequest, db: AsyncSession = Depends(get_db)
):
    """Trigger AI-powered company analysis and return a generated profile.

    In mock mode this returns a realistic placeholder profile.
    """
    company = await db.get(Company, body.company_id)
    if not company:
        raise NotFoundException("Company", str(body.company_id))

    if not body.force_regenerate:
        result = await db.execute(
            select(CompanyProfile).where(CompanyProfile.company_id == body.company_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return Response(
                data=CompanyProfileOut.model_validate(existing),
                message="Existing profile returned (use force_regenerate=true to regenerate)",
            )

    # Mock AI analysis output
    mock_profile = CompanyProfile(
        company_id=body.company_id,
        strengths="Strong market presence with established customer base; Robust technology infrastructure; Experienced leadership team; Diversified revenue streams",
        weaknesses="Limited digital transformation progress; Aging legacy systems; Talent retention challenges in key technical roles",
        market_position="Well-established player with approximately 15-20% market share in their core segment",
        key_products=f"{company.name}'s flagship product line; Professional services division; Cloud-based SaaS platform",
        competitors="Major industry competitors include MarketLeader Inc, TechRival Corp, and InnovateCo",
        recent_news="Recently announced expansion into new market segments; Partnership with leading technology vendors; Investment in AI and machine learning capabilities",
        culture="Collaborative and innovation-focused work environment with emphasis on professional development and work-life balance",
        financials="Strong revenue growth of 12% YoY; Healthy profit margins in the 18-22% range; Continued investment in R&D at 15% of revenue",
        raw_analysis=f"Mock analysis generated for {company.name} in the {company.industry or 'general'} sector.",
    )
    db.add(mock_profile)
    await db.flush()
    await db.refresh(mock_profile)
    return Response(data=CompanyProfileOut.model_validate(mock_profile), message="Analysis generated")


@router.delete("/{profile_id}", response_model=Response)
async def delete_profile(profile_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a company profile."""
    profile = await db.get(CompanyProfile, profile_id)
    if not profile:
        raise NotFoundException("CompanyProfile", str(profile_id))
    await db.delete(profile)
    return Response(message="Profile deleted")
