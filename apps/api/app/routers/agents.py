"""Agents router — company analysis, proposal generation, visual prompt generation."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.db.session import get_db
from app.models.case import Case
from app.models.company_profile import CompanyProfile
from app.models.generation import GenerationOutput, GenerationTask
from app.models.project import Company, Project
from app.models.template import PromptTemplate
from app.models.workflow import SOPWorkflow
from app.schemas.common import Response
from app.schemas.generation import (
    ProposalGenerationRequest,
    VisualPromptRequest,
)

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/company-analysis/{company_id}", response_model=Response)
async def run_company_analysis(
    company_id: uuid.UUID,
    force_regenerate: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Run the company analysis agent for a given company.

    Returns a mock analysis result including strengths, weaknesses, and market insights.
    """
    company = await db.get(Company, company_id)
    if not company:
        raise NotFoundException("Company", str(company_id))

    # Create a generation task
    task = GenerationTask(
        project_id=uuid.uuid4(),  # Standalone analysis — no project
        type="company_analysis",
        status="running",
        prompt_used=f"Analyze company: {company.name}",
        model_used="mock-v1",
        started_at=datetime.now(timezone.utc),
    )
    # We need a real project — find or use the first one
    result = await db.execute(select(Project).limit(1))
    fallback_project = result.scalar_one_or_none()
    if fallback_project:
        task.project_id = fallback_project.id

    db.add(task)
    await db.flush()

    # Mock analysis output
    analysis = {
        "company_name": company.name,
        "industry": company.industry,
        "strengths": [
            "Strong brand recognition in core market segments",
            "Established customer base with high retention rates",
            "Diversified product and service portfolio",
            "Experienced leadership team with deep industry knowledge",
            "Robust technology infrastructure supporting current operations",
        ],
        "weaknesses": [
            "Limited digital transformation progress compared to competitors",
            "Aging legacy systems increasing maintenance costs",
            "Talent retention challenges in key technical and leadership roles",
        ],
        "market_position": "Well-established mid-market player with approximately 15-20% market share in primary segments. Recognized for quality and reliability.",
        "key_products": [
            f"{company.name} Core Platform",
            f"{company.name} Professional Services",
            f"{company.name} Analytics Suite",
        ],
        "competitors": [
            "MarketLeader Corp",
            "InnovateTech Inc",
            "GlobalSolutions Group",
        ],
        "recent_news": [
            "Announced strategic partnership with leading cloud provider",
            "Opened new regional office to expand market coverage",
            "Launched sustainability initiative targeting carbon neutrality by 2030",
        ],
        "culture": "Innovation-driven culture with emphasis on collaboration and continuous improvement. Strong commitment to employee development and work-life balance.",
        "financials": {
            "revenue_trend": "Growing 12-15% annually",
            "profitability": "Healthy margins in the 18-22% range",
            "rd_investment": "Approximately 15% of revenue allocated to R&D",
        },
        "opportunities": [
            "Digital transformation consulting market growing at 18% CAGR",
            "Increasing demand for AI/ML integration services",
            "Expansion into adjacent vertical markets",
        ],
        "threats": [
            "Increasing competition from cloud-native startups",
            "Rapid technology evolution requiring constant upskilling",
            "Economic uncertainty impacting client budgets",
        ],
    }

    import json
    output = GenerationOutput(
        task_id=task.id,
        content_type="application/json",
        content=json.dumps(analysis, indent=2),
        used_cases=[],
        used_documents=[],
        used_chunks=[],
        used_sop_version="1.0",
    )
    db.add(output)

    task.status = "completed"
    task.completed_at = datetime.now(timezone.utc)
    await db.flush()

    return Response(
        data={
            "task_id": str(task.id),
            "output_id": str(output.id),
            "analysis": analysis,
        },
        message="Company analysis completed",
    )


@router.post("/proposal", response_model=Response)
async def run_proposal_generation(
    body: ProposalGenerationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run the proposal generation agent pipeline.

    Creates a generation task and returns a mock proposal with realistic content.
    """
    project = await db.get(Project, body.project_id)
    if not project:
        raise NotFoundException("Project", str(body.project_id))

    company = await db.get(Company, project.company_id)

    # Gather related cases
    cases_result = await db.execute(
        select(Case).where(Case.project_id == body.project_id).limit(3)
    )
    cases = cases_result.scalars().all()

    # Create generation task
    task = GenerationTask(
        project_id=body.project_id,
        type="proposal",
        status="running",
        prompt_used=f"Generate proposal for {project.name}",
        model_used="mock-v1",
        started_at=datetime.now(timezone.utc),
    )
    db.add(task)
    await db.flush()

    # Build mock proposal
    company_name = company.name if company else "Client"
    industry = company.industry if company else "Technology"

    case_studies_section = ""
    used_case_ids = []
    for c in cases:
        case_studies_section += f"""
### {c.title}

**Client:** {c.client_name}
**Challenge:** {c.challenge}
**Solution:** {c.solution}
**Results:** {c.results}

---
"""
        used_case_ids.append(str(c.id))

    proposal_content = f"""# {project.name}

## Executive Summary

This proposal outlines a comprehensive solution for {company_name}, addressing their strategic needs in the {industry} sector. Our approach combines proven methodologies with innovative technologies to deliver measurable business outcomes.

## Understanding of Requirements

Based on our thorough analysis of {company_name}'s needs, we have identified the following key requirements:

1. **Modernization of Core Systems** — Upgrading legacy infrastructure to support future growth
2. **Enhanced Data Analytics** — Implementing advanced analytics for data-driven decision making
3. **Improved Customer Experience** — Creating seamless omnichannel experiences
4. **Operational Efficiency** — Streamlining processes through automation and optimization
5. **Scalability** — Building a platform that grows with the business

## Proposed Solution

Our proposed solution leverages a cloud-native architecture built on microservices principles, ensuring flexibility, scalability, and resilience.

### Architecture Overview
- **Cloud Platform:** Multi-cloud strategy with primary deployment on AWS/Azure
- **Data Layer:** Modern data lakehouse architecture with real-time streaming capabilities
- **Application Layer:** Containerized microservices with API-first design
- **AI/ML Integration:** Embedded intelligence for predictive analytics and automation
- **Security:** Zero-trust security model with end-to-end encryption

## Relevant Case Studies

{case_studies_section if case_studies_section else "No prior case studies available for this project."}

## Implementation Approach

### Phase 1: Discovery & Planning (Weeks 1-4)
- Stakeholder interviews and requirements validation
- Technical architecture design
- Project plan and resource allocation

### Phase 2: Foundation (Weeks 5-12)
- Infrastructure setup and CI/CD pipeline configuration
- Core platform development
- Data migration planning and preparation

### Phase 3: Development (Weeks 13-24)
- Iterative development in 2-week sprints
- Regular demos and feedback cycles
- Integration testing and quality assurance

### Phase 4: Deployment & Optimization (Weeks 25-30)
- Phased rollout with blue-green deployments
- Performance monitoring and optimization
- Knowledge transfer and documentation

## Team Structure

| Role | Count | Experience |
|------|-------|------------|
| Project Manager | 1 | 10+ years |
| Solution Architect | 1 | 12+ years |
| Senior Developers | 4 | 8+ years average |
| DevOps Engineer | 2 | 6+ years average |
| QA Lead | 1 | 7+ years |
| UX Designer | 1 | 5+ years |

## Investment Summary

| Category | Estimate |
|----------|----------|
| Discovery & Planning | $80,000 - $120,000 |
| Development | $400,000 - $600,000 |
| Infrastructure | $60,000 - $100,000 |
| Testing & QA | $80,000 - $120,000 |
| Project Management | $80,000 - $100,000 |
| **Total Investment** | **$700,000 - $1,040,000** |

## Success Metrics

1. System uptime > 99.9%
2. API response time < 200ms
3. Customer satisfaction score > 90%
4. Processing speed improvement > 40%
5. Time to market reduction > 50%

## Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Scope creep | Medium | High | Change management process |
| Integration complexity | Medium | Medium | Early proof of concept |
| Resource availability | Low | High | Cross-trained team members |
| Performance issues | Low | Medium | Load testing from sprint 1 |

## Next Steps

1. Schedule kickoff meeting with key stakeholders
2. Finalize scope and priorities
3. Execute master services agreement
4. Begin Phase 1 discovery activities

---

*This proposal is valid for 90 days from the date of issuance.*
"""

    output = GenerationOutput(
        task_id=task.id,
        content_type="text/markdown",
        content=proposal_content,
        used_cases=used_case_ids,
        used_documents=[],
        used_chunks=[],
        used_sop_version="1.2",
    )
    db.add(output)

    task.status = "completed"
    task.completed_at = datetime.now(timezone.utc)
    await db.flush()

    return Response(
        data={
            "task_id": str(task.id),
            "output_id": str(output.id),
            "content_type": output.content_type,
            "content": proposal_content,
            "used_cases": used_case_ids,
            "used_documents": [],
            "used_chunks": [],
            "used_sop_version": "1.2",
        },
        message="Proposal generated successfully",
    )


@router.post("/visual-prompt", response_model=Response)
async def run_visual_prompt_generation(
    body: VisualPromptRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run the visual creative agent to generate design prompts.

    Returns mock visual design recommendations.
    """
    project = await db.get(Project, body.project_id)
    if not project:
        raise NotFoundException("Project", str(body.project_id))

    company = await db.get(Company, project.company_id)
    company_name = company.name if company else "Client"
    industry = company.industry if company else "Technology"

    visual_prompt = {
        "project_name": project.name,
        "company_name": company_name,
        "industry": industry,
        "color_palette": {
            "primary": "#1a73e8",
            "secondary": "#4285f4",
            "accent": "#34a853",
            "background": "#ffffff",
            "text": "#202124",
            "light_gray": "#f8f9fa",
        },
        "typography": {
            "headings": {
                "font": "Inter",
                "weights": [700, 800],
                "sizes": ["2.5rem (H1)", "2rem (H2)", "1.5rem (H3)"],
            },
            "body": {
                "font": "Inter",
                "weights": [400, 500],
                "size": "1rem (16px)",
                "line_height": "1.6",
            },
        },
        "layout_guidelines": {
            "grid": "12-column grid with 24px gutters",
            "max_width": "1200px",
            "margins": "80px (desktop), 24px (mobile)",
            "spacing_scale": "8px base unit (8, 16, 24, 32, 48, 64)",
        },
        "visual_elements": [
            "Clean geometric shapes and subtle gradients",
            "Data visualization with consistent chart styling",
            "Icon set: Outlined style, 2px stroke weight",
            "Photography: Professional, bright, with blue undertones",
            "Illustrations: Flat design with isometric perspectives",
        ],
        "slide_design": {
            "title_slide": "Full-bleed background image with gradient overlay, large heading, subtle animation",
            "content_slide": "Two-column layout with heading, bullet points, and supporting visual",
            "data_slide": "Dashboard-style layout with charts, KPIs, and key metrics highlighted",
            "case_study": "Card-based layout with image, challenge/solution/results structure",
            "closing_slide": "Minimal design with call-to-action and contact information",
        },
        "style_preferences": body.style_preferences or "Modern, professional, clean",
        "target_audience": body.target_audience or f"{industry} sector decision makers",
    }

    task = GenerationTask(
        project_id=body.project_id,
        type="visual_prompt",
        status="completed",
        prompt_used=f"Generate visual prompt for {project.name}",
        model_used="mock-v1",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )

    # Find a project to attach the task to
    db.add(task)
    await db.flush()

    import json
    output = GenerationOutput(
        task_id=task.id,
        content_type="application/json",
        content=json.dumps(visual_prompt, indent=2),
        used_cases=[],
        used_documents=[],
        used_chunks=[],
        used_sop_version="1.0",
    )
    db.add(output)
    await db.flush()

    return Response(
        data={
            "task_id": str(task.id),
            "output_id": str(output.id),
            "visual_prompt": visual_prompt,
        },
        message="Visual prompt generated successfully",
    )
