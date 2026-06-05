"""Agents router — delegates to Skill Runtime for company analysis,
proposal generation, and visual prompt generation."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.db.session import get_db
from app.models.project import Company, Project
from app.models.generation import GenerationOutput, GenerationTask
from app.schemas.common import Response
from app.schemas.generation import (
    ProposalGenerationRequest,
    VisualPromptRequest,
)
from app.services.llm_service import get_llm_service
from app.services.embedding_service import get_embedding_service
from app.services.image_service import get_image_service
from app.skills.base import SkillContext
from app.skills.registry import SkillRegistry
from app.skills.runner import SkillRunner

router = APIRouter(prefix="/agents", tags=["agents"])

# Use the shared registry (already auto-registered via skills router import)
_registry = SkillRegistry.get_instance()


def _make_context(
    db: AsyncSession,
    project_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> SkillContext:
    """Build a SkillContext with all services injected."""
    return SkillContext(
        project_id=project_id,
        user_id=user_id,
        db=db,
        llm_service=get_llm_service(),
        embedding_service=get_embedding_service(),
        image_service=get_image_service(),
    )


@router.post("/company-analysis/{company_id}", response_model=Response)
async def run_company_analysis(
    company_id: uuid.UUID,
    force_regenerate: bool = False,
    project_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    """Run the company analysis skill for a given company.

    Uses the Skill Runtime to execute the company_analysis skill
    with real LLM and RAG support.
    """
    company = await db.get(Company, company_id)
    if not company:
        raise NotFoundException("Company", str(company_id))

    # Find a project for context if not provided
    pid = str(project_id) if project_id else None
    if not pid:
        result = await db.execute(
            select(Project).limit(1)
        )
        fallback = result.scalar_one_or_none()
        if fallback:
            pid = str(fallback.id)

    context = _make_context(db, project_id=pid)
    runner = SkillRunner(registry=_registry)

    result = await runner.run(
        skill_id="company_analysis",
        input_data={
            "company_id": str(company_id),
        },
        context=context,
    )

    return Response(
        data=result,
        message="Company analysis completed" if result.get("success") else "Company analysis failed",
    )


@router.post("/proposal", response_model=Response)
async def run_proposal_generation(
    body: ProposalGenerationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run the proposal generation skill.

    Uses the Skill Runtime with real LLM, RAG retrieval, and context pack assembly.
    """
    project = await db.get(Project, body.project_id)
    if not project:
        raise NotFoundException("Project", str(body.project_id))

    context = _make_context(db, project_id=str(body.project_id))
    runner = SkillRunner(registry=_registry)

    result = await runner.run(
        skill_id="proposal_generation",
        input_data={
            "project_id": str(body.project_id),
        },
        context=context,
    )

    return Response(
        data=result,
        message="Proposal generated successfully" if result.get("success") else "Proposal generation failed",
    )


@router.post("/visual-prompt", response_model=Response)
async def run_visual_prompt_generation(
    body: VisualPromptRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run the visual creative skill pipeline.

    Generates visual strategy and prompts, then optionally generates images.
    """
    project = await db.get(Project, body.project_id)
    if not project:
        raise NotFoundException("Project", str(body.project_id))

    context = _make_context(db, project_id=str(body.project_id))
    runner = SkillRunner(registry=_registry)

    # Step 1: Generate visual prompt
    visual_result = await runner.run(
        skill_id="visual_prompt",
        input_data={
            "project_id": str(body.project_id),
            "style_preferences": body.style_preferences,
        },
        context=context,
    )

    # Step 2: Generate image if visual prompt succeeded
    image_result = None
    if visual_result.get("success") and visual_result.get("output", {}).get("positive_prompt"):
        positive_prompt = visual_result["output"]["positive_prompt"]
        negative_prompt = visual_result["output"].get("negative_prompt", "")

        image_result = await runner.run(
            skill_id="image_generation",
            input_data={
                "prompt": positive_prompt,
                "negative_prompt": negative_prompt,
                "project_id": str(body.project_id),
            },
            context=context,
        )

    return Response(
        data={
            "visual_prompt": visual_result,
            "image_generation": image_result,
        },
        message="Visual generation completed" if visual_result.get("success") else "Visual generation failed",
    )


@router.post("/pipeline/{project_id}", response_model=Response)
async def run_full_pipeline(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Run the full project pipeline: analysis -> proposal -> visual.

    Each step stores results and updates project status.
    Steps can be resumed if a previous step already completed.
    """
    project = await db.get(Project, project_id)
    if not project:
        raise NotFoundException("Project", str(project_id))

    context = _make_context(db, project_id=str(project_id))
    runner = SkillRunner(registry=_registry)
    results = {}

    # Step 1: Company Analysis (if not already done)
    if project.status in ("draft", "pending"):
        company_id = str(project.company_id)
        analysis = await runner.run(
            skill_id="company_analysis",
            input_data={"company_id": company_id},
            context=context,
        )
        results["company_analysis"] = analysis
        if not analysis.get("success"):
            return Response(data=results, message="Pipeline stopped at company analysis")
        project.status = "company_analysis"
        await db.flush()

    # Step 2: Proposal Generation (if analysis is done)
    if project.status in ("company_analysis", "in_progress"):
        proposal = await runner.run(
            skill_id="proposal_generation",
            input_data={"project_id": str(project_id)},
            context=context,
        )
        results["proposal_generation"] = proposal
        if not proposal.get("success"):
            return Response(data=results, message="Pipeline stopped at proposal generation")
        project.status = "proposal_draft"
        await db.flush()

    # Step 3: Visual Generation (if proposal is done)
    if project.status in ("proposal_draft",):
        visual = await runner.run(
            skill_id="visual_prompt",
            input_data={
                "project_id": str(project_id),
                "style_preferences": "科技感、专业、高冲击力",
            },
            context=context,
        )
        results["visual_prompt"] = visual

        if visual.get("success") and visual.get("output", {}).get("positive_prompt"):
            image = await runner.run(
                skill_id="image_generation",
                input_data={
                    "prompt": visual["output"]["positive_prompt"],
                    "negative_prompt": visual["output"].get("negative_prompt", ""),
                    "project_id": str(project_id),
                },
                context=context,
            )
            results["image_generation"] = image

        project.status = "visual_design"
        await db.flush()

    return Response(
        data=results,
        message=f"Pipeline completed. Project status: {project.status}",
    )
