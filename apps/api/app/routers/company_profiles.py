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
    """Trigger Skill-backed company analysis and return the saved profile."""
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

    from app.services.embedding_service import get_embedding_service
    from app.services.llm_service import get_llm_service
    from app.skills.base import SkillContext
    from app.skills.registry import SkillRegistry
    from app.skills.runner import SkillRunner

    registry = SkillRegistry.get_instance()
    registry.auto_register()
    runner = SkillRunner(registry=registry)
    result = await runner.run(
        "company_analysis",
        {
            "company_id": str(body.company_id),
            "additional_context": body.context or "",
        },
        SkillContext(
            db=db,
            llm_service=await get_llm_service(db),
            embedding_service=await get_embedding_service(db),
        ),
    )
    if not result.get("success"):
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=result.get("error") or "Analysis failed")

    profile_result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.company_id == body.company_id)
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise NotFoundException("CompanyProfile for company", str(body.company_id))
    return Response(data=CompanyProfileOut.model_validate(profile), message="Analysis generated")


@router.delete("/{profile_id}", response_model=Response)
async def delete_profile(profile_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a company profile."""
    profile = await db.get(CompanyProfile, profile_id)
    if not profile:
        raise NotFoundException("CompanyProfile", str(profile_id))
    await db.delete(profile)
    return Response(message="Profile deleted")
