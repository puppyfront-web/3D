"""Planner — generates ExecutionPlan based on business domain.

Strategy:
1. SOP-driven (preferred): Load matching SOP from DB, convert to ExecutionPlan
2. LLM fallback: When no SOP matches, use LLM to generate plan dynamically
"""

import json
import logging
from typing import Any, Dict, Optional

from app.services.execution_plan import (
    ExecutionPlan,
    PlanStep,
    create_plan_for_domain,
)

logger = logging.getLogger(__name__)

# Domain keywords for inferring the business domain from user message
_DOMAIN_KEYWORDS: Dict[str, list[str]] = {
    "exhibition": [
        "展厅", "展陈", "展馆", "博物馆", "规划馆", "科技馆",
        "党建馆", "企业展厅", "展项", "展台",
    ],
    "culture_tourism": [
        "文旅", "夜游", "沉浸式体验", "光影秀", "景区",
        "灯光秀", "投影秀", "夜游灯光", "主题公园",
    ],
    "multimedia": [
        "互动装置", "数字沙盘", "AR", "VR", "互动桌面",
        "滑轨屏", "球幕", "体感交互",
    ],
    "curtain_wall": [
        "幕墙", "LED", "裸眼3D", "媒体立面", "3D展示",
        "户外大屏", "广告屏",
    ],
}


def infer_domain(message: str) -> str:
    """Infer the business domain from user message using keyword matching.

    Returns the domain with the most keyword hits, or "curtain_wall" as default.
    """
    scores: Dict[str, int] = {}
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in message)
        if score > 0:
            scores[domain] = score

    if scores:
        return max(scores, key=scores.get)  # type: ignore[arg-type]
    return "curtain_wall"


async def create_plan(
    user_message: str,
    company_name: str = "",
    db=None,
    sop_loader=None,
) -> ExecutionPlan:
    """Create an execution plan, preferring SOP-driven approach.

    Args:
        user_message: The user's request text
        company_name: Extracted company name
        db: Optional database session for SOP lookup
        sop_loader: Optional async callable that loads SOP by domain
    """
    domain = infer_domain(user_message)

    # Strategy 1: Try SOP-driven plan from database
    if db and sop_loader:
        try:
            sop = await sop_loader(domain, db)
            if sop:
                plan = _sop_to_plan(sop, domain, user_message, company_name)
                logger.info(
                    "Planner: SOP-driven plan for domain=%s, %d steps",
                    domain, len(plan.steps),
                )
                return plan
        except Exception as e:
            logger.warning("SOP-driven planning failed: %s, using template", e)

    # Strategy 2: Template-based plan (default)
    plan = create_plan_for_domain(domain, user_message, company_name)
    logger.info(
        "Planner: template plan for domain=%s, %d steps",
        domain, len(plan.steps),
    )
    return plan


def _sop_to_plan(
    sop: Dict[str, Any],
    domain: str,
    user_message: str,
    company_name: str,
) -> ExecutionPlan:
    """Convert an SOP workflow from DB into an ExecutionPlan."""
    steps_data = sop.get("steps", [])
    pipeline_stages = sop.get("pipeline_stages", [])

    steps = []
    for i, stage in enumerate(pipeline_stages if pipeline_stages else steps_data):
        step = PlanStep(
            step_id=str(i),
            skill_id=stage.get("skill_id", stage.get("stage", "")),
            name=stage.get("name", ""),
            description=stage.get("description", ""),
            depends_on=[str(i - 1)] if i > 0 else [],
            pause_after=stage.get("pause_after", i < len(pipeline_stages) - 1),
            optional=stage.get("optional", False),
            condition=stage.get("condition"),
        )
        steps.append(step)

    return ExecutionPlan(
        domain=domain,
        project_type=sop.get("workflow_type", domain),
        steps=steps,
        context={"user_message": user_message, "company_name": company_name},
    )


async def default_sop_loader(domain: str, db) -> Optional[Dict[str, Any]]:
    """Default SOP loader: queries the database for a matching SOP workflow."""
    try:
        from sqlalchemy import select
        from app.models.workflow import SOPWorkflow

        # Try exact domain match first, then fallback to generic
        for match_type in [domain, "generic"]:
            result = await db.execute(
                select(SOPWorkflow)
                .where(
                    SOPWorkflow.workflow_type == match_type,
                    SOPWorkflow.status == "active",
                )
                .order_by(SOPWorkflow.version.desc())
                .limit(1)
            )
            sop = result.scalar_one_or_none()
            if sop:
                return {
                    "name": sop.name,
                    "workflow_type": sop.workflow_type,
                    "steps": sop.steps if isinstance(sop.steps, list) else json.loads(sop.steps or "[]"),
                    "pipeline_stages": sop.pipeline_stages if isinstance(sop.pipeline_stages, list) else json.loads(sop.pipeline_stages or "[]"),
                }
    except Exception as e:
        logger.warning("SOP DB lookup failed: %s", e)
    return None
