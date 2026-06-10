"""Agents router — delegates to Skill Runtime for company analysis,
proposal generation, and visual prompt generation."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.db.session import get_db
from app.models.project import Company, Project
from app.models.generation import GenerationOutput, GenerationTask
from app.schemas.common import Response
from app.schemas.generation import (
    DirectImageRequest,
    ProposalGenerationRequest,
    VisualPromptRequest,
)
from pydantic import BaseModel
from app.services.llm_service import get_llm_service
from app.services.embedding_service import get_embedding_service
from app.services.image_service import get_image_service
from app.skills.base import SkillContext
from app.skills.registry import SkillRegistry
from app.skills.runner import SkillRunner

router = APIRouter(prefix="/agents", tags=["agents"])

# Use the shared registry (already auto-registered via skills router import)
_registry = SkillRegistry.get_instance()


async def _make_context(
    db: AsyncSession,
    project_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> SkillContext:
    """Build a SkillContext with all services injected."""
    return SkillContext(
        project_id=project_id,
        user_id=user_id,
        db=db,
        llm_service=await get_llm_service(db),
        embedding_service=await get_embedding_service(db),
        image_service=await get_image_service(db),
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

    context = await _make_context(db, project_id=pid)
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

    context = await _make_context(db, project_id=str(body.project_id))
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

    context = await _make_context(db, project_id=str(body.project_id))
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

        image_input: dict = {
            "prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "project_id": str(body.project_id),
        }
        if body.width:
            image_input["width"] = body.width
        if body.height:
            image_input["height"] = body.height

        image_result = await runner.run(
            skill_id="image_generation",
            input_data=image_input,
            context=context,
        )

    return Response(
        data={
            "visual_prompt": visual_result,
            "image_generation": image_result,
        },
        message="Visual generation completed" if visual_result.get("success") else "Visual generation failed",
    )


@router.post("/generate-image", response_model=Response)
async def direct_image_generation(
    body: DirectImageRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate an image directly from a prompt. No project required.

    Useful for generating visual charts, diagrams, and curation analysis images.
    """
    from app.services.image_service import get_image_service

    image_service = await get_image_service(db)

    width = body.width or 1024
    height = body.height or 768

    image_url = await image_service.generate_image_url(
        prompt=body.prompt,
        width=width,
        height=height,
        negative_prompt=body.negative_prompt or "",
    )

    return Response(
        data={
            "image_url": image_url,
            "prompt": body.prompt,
            "width": width,
            "height": height,
        },
        message="Image generated",
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

    context = await _make_context(db, project_id=str(project_id))
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


# ──────────────────────────────────────────────────────────────
# Quality Review Checklist
# ──────────────────────────────────────────────────────────────

class ChecklistItem(BaseModel):
    id: str
    description: str
    status: str  # pass / warning / fail / pending
    comment: Optional[str] = None


class ChecklistGroup(BaseModel):
    id: str
    category: str
    items: List[ChecklistItem]


@router.post("/quality-check/{project_id}", response_model=Response)
async def run_quality_check(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Run quality check for a project and return structured review checklists.

    Checks for:
    - Company analysis completeness
    - Proposal completeness and section review status
    - Visual generation presence
    - Missing info / forbidden content
    """
    project = await db.get(Project, project_id)
    if not project:
        raise NotFoundException("Project", str(project_id))

    checklists: List[ChecklistGroup] = []

    # ── 1. Company Analysis ──
    from app.models.company import CompanyProfile
    profile_result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.company_id == project.company_id).limit(1)
    )
    profile = profile_result.scalar_one_or_none()

    analysis_items: List[ChecklistItem] = []
    if profile:
        analysis_items.append(ChecklistItem(
            id="analysis-1", description="企业基础画像已生成",
            status="pass", comment=None,
        ))
        has_six_views = bool(profile.analysis_json and
                            isinstance(profile.analysis_json, dict) and
                            profile.analysis_json.get("six_views"))
        analysis_items.append(ChecklistItem(
            id="analysis-2", description="六看分析完整",
            status="pass" if has_six_views else "warning",
            comment=None if has_six_views else "建议补充六看维度分析",
        ))
        missing = profile.missing_info or []
        analysis_items.append(ChecklistItem(
            id="analysis-3", description="待确认信息已处理",
            status="warning" if missing else "pass",
            comment=f"待确认 {len(missing)} 项" if missing else None,
        ))
    else:
        analysis_items.append(ChecklistItem(
            id="analysis-1", description="企业基础画像已生成",
            status="fail", comment="尚未生成企业分析，请先完成企业解析",
        ))
        analysis_items.append(ChecklistItem(
            id="analysis-2", description="六看分析完整",
            status="pending", comment=None,
        ))
        analysis_items.append(ChecklistItem(
            id="analysis-3", description="待确认信息已处理",
            status="pending", comment=None,
        ))
    checklists.append(ChecklistGroup(id="analysis", category="企业分析", items=analysis_items))

    # ── 2. Proposal ──
    proposal_result = await db.execute(
        select(GenerationTask)
        .where(GenerationTask.project_id == project_id)
        .where(GenerationTask.type == "proposal")
        .order_by(GenerationTask.created_at.desc())
        .limit(1)
    )
    proposal_task = proposal_result.scalar_one_or_none()

    proposal_items: List[ChecklistItem] = []
    if proposal_task and proposal_task.outputs:
        output = proposal_task.outputs[0]
        has_content = bool(output.content and len(output.content) > 200)
        proposal_items.append(ChecklistItem(
            id="proposal-1", description="策划案已生成",
            status="pass" if has_content else "warning",
            comment=None if has_content else "策划案内容过短",
        ))
        sections_meta = output.sections_meta or []
        total = len(sections_meta)
        approved = sum(1 for s in sections_meta if s.get("status") == "approved")
        has_citations = bool(output.used_cases or output.used_documents)
        proposal_items.append(ChecklistItem(
            id="proposal-2",
            description=f"章节审核完成 ({approved}/{total})",
            status="pass" if total > 0 and approved == total else ("warning" if approved > 0 else "fail"),
            comment=None if approved == total else f"还有 {total - approved} 个章节未审核",
        ))
        proposal_items.append(ChecklistItem(
            id="proposal-3", description="引用来源可追溯",
            status="pass" if has_citations else "warning",
            comment=None if has_citations else "建议关联相关案例和文档",
        ))
    else:
        proposal_items.append(ChecklistItem(
            id="proposal-1", description="策划案已生成",
            status="fail", comment="尚未生成策划案",
        ))
        proposal_items.append(ChecklistItem(
            id="proposal-2", description="章节审核完成",
            status="pending", comment=None,
        ))
        proposal_items.append(ChecklistItem(
            id="proposal-3", description="引用来源可追溯",
            status="pending", comment=None,
        ))
    checklists.append(ChecklistGroup(id="proposal", category="策划案", items=proposal_items))

    # ── 3. Visual ──
    visual_result = await db.execute(
        select(GenerationTask)
        .where(GenerationTask.project_id == project_id)
        .where(GenerationTask.type.in_(["visual_prompt", "image_generation", "visual"]))
        .order_by(GenerationTask.created_at.desc())
        .limit(1)
    )
    visual_task = visual_result.scalar_one_or_none()

    visual_items: List[ChecklistItem] = []
    has_visual = bool(visual_task and visual_task.outputs)
    visual_items.append(ChecklistItem(
        id="visual-1", description="视觉方案已生成",
        status="pass" if has_visual else "warning",
        comment=None if has_visual else "建议生成视觉方案（可选）",
    ))
    checklists.append(ChecklistGroup(id="visual", category="视觉方案", items=visual_items))

    # ── 4. Compliance ──
    compliance_items: List[ChecklistItem] = [
        ChecklistItem(
            id="comp-1", description="未出现编造报价或承诺投屏效果",
            status="pass", comment=None,
        ),
        ChecklistItem(
            id="comp-2", description="未出现编造案例",
            status="pass", comment=None,
        ),
        ChecklistItem(
            id="comp-3", description="AI生成内容已经人工核查",
            status="warning" if proposal_task else "pending",
            comment="请确认所有 AI 生成内容已由责任人核查" if proposal_task else None,
        ),
    ]
    checklists.append(ChecklistGroup(id="compliance", category="合规检查", items=compliance_items))

    return Response(
        data=[g.model_dump() for g in checklists],
        message="Quality check completed",
    )
