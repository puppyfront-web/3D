"""Plan Executor — runs an ExecutionPlan step by step with SSE streaming.

Each step triggers a Skill execution, with context passing between steps.
Supports pausing for user confirmation and re-planning on failure.
"""

import json
import logging
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.services.execution_plan import ExecutionPlan, PlanStep

logger = logging.getLogger(__name__)

# Display names for known skill_ids
_STEP_DISPLAY_NAMES = {
    "company_analysis": "企业解析",
    "proposal_generation": "策划案生成",
    "visual_prompt": "视觉方案生成",
    "image_generation": "图片生成",
    "export": "方案导出",
    "case_retrieval": "案例检索",
    "proposal_agent": "策划案专家",
    "visual_concept_agent": "视觉创意专家",
}


async def execute_plan(
    plan: ExecutionPlan,
    context: "SkillContext",  # noqa: F821
    registry: "SkillRegistry",  # noqa: F821
) -> AsyncGenerator[Dict[str, Any], None]:
    """Execute an ExecutionPlan, yielding SSE-compatible events.

    Yields dicts with keys: type, data (matching the SSE chunk format).
    Caller is responsible for converting to SSE strings and saving messages.
    """
    from app.skills.runner import SkillRunner

    plan.status = "running"

    # Yield the plan overview so the frontend can render progress
    yield {
        "type": "plan_created",
        "data": {
            "plan_id": plan.plan_id,
            "domain": plan.domain,
            "project_type": plan.project_type,
            "steps": [
                {
                    "step_id": s.step_id,
                    "name": s.name or _STEP_DISPLAY_NAMES.get(s.skill_id, s.skill_id),
                    "status": s.status,
                }
                for s in plan.steps
            ],
        },
    }

    while plan.current_step_index < len(plan.steps):
        step = plan.steps[plan.current_step_index]

        # Skip steps whose condition is not met
        if plan.should_skip(step):
            step.status = "skipped"
            logger.info("PlanExecutor: skipping optional step %s", step.name)
            plan.current_step_index += 1
            continue

        # Skip already completed/failed/skipped steps
        if step.status in ("completed", "failed", "skipped"):
            plan.current_step_index += 1
            continue

        # Execute this step
        step.status = "running"
        step.started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        step_display = step.name or _STEP_DISPLAY_NAMES.get(step.skill_id, step.skill_id)
        yield {
            "type": "plan_step_start",
            "data": {
                "step_id": step.step_id,
                "skill_id": step.skill_id,
                "name": step_display,
            },
        }

        start_time = time.time()

        # Build input for this step
        input_data = _build_step_input(step, plan)

        # Agent-type steps: delegate to expert agents instead of skills
        if step.skill_id == "proposal_agent":
            async for event in _run_proposal_agent_step(plan, context, step, step_display):
                yield event
            if step.status == "completed" and step.pause_after:
                plan.pause()
                yield {
                    "type": "plan_paused",
                    "data": {
                        "step_id": step.step_id,
                        "name": step_display,
                        "output": plan.step_outputs.get("proposal_agent", {}),
                        "skill_id": step.skill_id,
                    },
                }
                return
            plan.current_step_index += 1
            continue

        if step.skill_id == "visual_concept_agent":
            async for event in _run_visual_concept_agent_step(plan, context, step, step_display):
                yield event
            if step.status == "completed" and step.pause_after:
                plan.pause()
                yield {
                    "type": "plan_paused",
                    "data": {
                        "step_id": step.step_id,
                        "name": step_display,
                        "output": plan.step_outputs.get("visual_concept_agent", {}),
                        "skill_id": step.skill_id,
                    },
                }
                return
            plan.current_step_index += 1
            continue

        # Standard skill execution
        runner = SkillRunner(registry)
        result = await runner.run(step.skill_id, input_data, context)

        elapsed = int(time.time() - start_time)

        if result.get("success"):
            output = result.get("output", {})
            plan.mark_step_completed(step.step_id, output)

            yield {
                "type": "plan_step_complete",
                "data": {
                    "step_id": step.step_id,
                    "skill_id": step.skill_id,
                    "name": step_display,
                    "status": "completed",
                    "duration": elapsed,
                    "output_summary": _summarize_output(step.skill_id, output),
                },
            }

            # Auto-chain visual_prompt → image_generation
            if step.skill_id == "visual_prompt" and output.get("positive_prompt"):
                collected_images = []
                for _ in range(2):
                    img_input = {
                        "prompt": output["positive_prompt"],
                        "negative_prompt": output.get("negative_prompt", ""),
                        "width": 1024,
                        "height": 768,
                    }
                    if context.project_id:
                        img_input["project_id"] = context.project_id
                    img_result = await runner.run("image_generation", img_input, context)
                    if img_result.get("success"):
                        url = img_result.get("output", {}).get("image_url")
                        if url:
                            collected_images.append({"url": url})
                if collected_images:
                    output["images"] = collected_images
                    output["image_url"] = collected_images[0]["url"]
                    plan.step_outputs["visual_prompt"] = output

            # Pause if needed
            if step.pause_after:
                plan.pause()
                yield {
                    "type": "plan_paused",
                    "data": {
                        "step_id": step.step_id,
                        "name": step_display,
                        "output": output,
                        "skill_id": step.skill_id,
                    },
                }
                return  # Stop execution, wait for user

        else:
            error_msg = result.get("error", "执行失败")
            plan.mark_step_failed(step.step_id, error_msg)

            yield {
                "type": "plan_step_failed",
                "data": {
                    "step_id": step.step_id,
                    "skill_id": step.skill_id,
                    "name": step_display,
                    "error": error_msg,
                },
            }

            # Check if we can replan
            if plan.replan_count < plan.max_replans:
                plan.replan_count += 1
                plan.status = "replanning"
                logger.info(
                    "PlanExecutor: step %s failed, replanning (attempt %d)",
                    step.name, plan.replan_count,
                )
                # For now: skip the failed step and continue
                # Future: call Re-planner to generate alternative steps
                plan.current_step_index += 1
                plan.status = "running"
            else:
                plan.status = "failed"
                return

        plan.current_step_index += 1

    # All steps done
    plan.status = "completed"
    yield {
        "type": "plan_completed",
        "data": {
            "plan_id": plan.plan_id,
            "domain": plan.domain,
            "completed_steps": len([s for s in plan.steps if s.status == "completed"]),
            "total_steps": len(plan.steps),
        },
    }


def _build_step_input(step: PlanStep, plan: ExecutionPlan) -> Dict[str, Any]:
    """Build skill input from plan context and previous step outputs."""
    user_msg = plan.context.get("user_message", "")
    company_name = plan.context.get("company_name", "")

    input_data: Dict[str, Any] = {
        "user_message": user_msg,
        "domain": plan.domain,
    }

    if step.skill_id == "company_analysis":
        input_data["company_info"] = user_msg
        input_data["company_name"] = company_name

    elif step.skill_id == "proposal_generation":
        company_output = plan.step_outputs.get("company_analysis", {})
        input_data["requirement_text"] = user_msg
        input_data["company_profile"] = company_output
        input_data["company_info"] = user_msg

    elif step.skill_id == "visual_prompt":
        proposal_output = plan.step_outputs.get("proposal_generation", {})
        company_output = plan.step_outputs.get("company_analysis", {})
        input_data["user_message"] = user_msg
        input_data["proposal_context"] = proposal_output
        input_data["visual_direction"] = company_output.get("recommended_visual_direction", "")

    elif step.skill_id == "export":
        proposal_output = plan.step_outputs.get("proposal_generation", {})
        task_id = proposal_output.get("output_id") or proposal_output.get("task_id")
        input_data["task_id"] = str(task_id) if task_id else ""
        input_data["format"] = "word"

    return input_data


def _summarize_output(skill_id: str, output: Dict[str, Any]) -> Dict[str, Any]:
    """Create a brief summary of skill output for SSE events."""
    summary: Dict[str, Any] = {}
    if skill_id == "company_analysis":
        missing = output.get("missing_info", [])
        analysis = output.get("analysis", output)
        if isinstance(analysis, dict):
            missing = missing or analysis.get("missing_info", [])
        summary["missing_count"] = len(missing) if isinstance(missing, list) else 0
    elif skill_id == "proposal_generation":
        summary["sections_count"] = len(output.get("sections_meta", []))
    elif skill_id in ("visual_prompt", "image_generation"):
        images = output.get("images", [])
        summary["images_count"] = len(images) if isinstance(images, list) else 0
    elif skill_id == "proposal_agent":
        summary["proposal_confirmed"] = bool(output)
    elif skill_id == "visual_concept_agent":
        summary["visual_confirmed"] = bool(output)
    return summary


# ---------------------------------------------------------------------------
# Agent-step execution helpers
# ---------------------------------------------------------------------------


async def _run_proposal_agent_step(
    plan: ExecutionPlan,
    context: "SkillContext",
    step: PlanStep,
    step_display: str,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Run ProposalAgent as a plan step — auto-completes to REVIEWING."""
    from app.agents.proposal import ProposalAgent, ProposalContext, RequirementInfo

    user_msg = plan.context.get("user_message", "")
    ctx = ProposalContext(
        domain=plan.domain,
        requirement=RequirementInfo(raw_input=user_msg),
    )

    agent = ProposalAgent()
    elapsed_start = time.time()

    # Collect all agent SSE chunks, forward as plan_step events
    chunks_data: List[Dict[str, Any]] = []
    async for chunk_str in agent.handle_message(
        user_msg, ctx, context.db if hasattr(context, "db") else None,
        project_id=context.project_id if hasattr(context, "project_id") else None,
    ):
        # Parse the SSE chunk and forward relevant events
        if chunk_str.startswith("data: "):
            try:
                chunk = json.loads(chunk_str[6:])
                chunks_data.append(chunk)
                # Forward structured events as plan step progress
                chunk_type = chunk.get("type", "")
                if chunk_type == "skill_progress":
                    yield {
                        "type": "plan_step_progress",
                        "data": {
                            "step_id": step.step_id,
                            "skill_id": step.skill_id,
                            "name": step_display,
                            "sub_progress": chunk.get("data", {}),
                        },
                    }
                elif chunk_type in ("content_block_start", "content_block_data", "content_block_end"):
                    yield {"type": chunk_type, "data": chunk.get("data", {})}
            except json.JSONDecodeError:
                pass

    # Agent finished — store output
    elapsed = int(time.time() - elapsed_start)
    step.status = "completed"
    step.completed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    output = ctx.to_dict()
    plan.mark_step_completed(step.step_id, output)

    yield {
        "type": "plan_step_complete",
        "data": {
            "step_id": step.step_id,
            "skill_id": step.skill_id,
            "name": step_display,
            "status": "completed",
            "duration": elapsed,
            "output_summary": _summarize_output("proposal_agent", output),
        },
    }


async def _run_visual_concept_agent_step(
    plan: ExecutionPlan,
    context: "SkillContext",
    step: PlanStep,
    step_display: str,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Run VisualConceptAgent as a plan step, pre-populated from proposal output."""
    from app.agents.visual_concept import VisualConceptAgent, VisualConceptContext, VisualRequirement

    proposal_data = plan.step_outputs.get("proposal_agent", {})
    handoff = proposal_data.get("output_for_next_agent") or {}

    # Build visual context from proposal handoff
    ctx = VisualConceptContext()
    if handoff:
        ctx.requirement = VisualRequirement(
            raw_input=handoff.get("visual_direction", ""),
            scene=handoff.get("scene"),
            visual_style=handoff.get("visual_style"),
            brand_or_theme=handoff.get("brand_or_theme"),
            target_audience=handoff.get("target_audience"),
            key_elements=handoff.get("key_elements", []),
        )
    else:
        user_msg = plan.context.get("user_message", "")
        ctx.requirement = VisualRequirement(raw_input=user_msg)

    # Auto-create initial node since requirement is pre-filled
    ctx.create_initial_node()

    agent = VisualConceptAgent()
    elapsed_start = time.time()

    async for chunk_str in agent.handle_message(
        ctx.requirement.raw_input, ctx,
        context.db if hasattr(context, "db") else None,
        project_id=context.project_id if hasattr(context, "project_id") else None,
    ):
        if chunk_str.startswith("data: "):
            try:
                chunk = json.loads(chunk_str[6:])
                chunk_type = chunk.get("type", "")
                if chunk_type == "skill_progress":
                    yield {
                        "type": "plan_step_progress",
                        "data": {
                            "step_id": step.step_id,
                            "skill_id": step.skill_id,
                            "name": step_display,
                            "sub_progress": chunk.get("data", {}),
                        },
                    }
                elif chunk_type in (
                    "visual_strategy", "visual_result",
                    "quality_check", "action_buttons",
                    "content_block_start", "content_block_data", "content_block_end",
                ):
                    yield {"type": chunk_type, "data": chunk.get("data", {})}
            except json.JSONDecodeError:
                pass

    elapsed = int(time.time() - elapsed_start)
    step.status = "completed"
    step.completed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    output = ctx.to_dict()
    plan.mark_step_completed(step.step_id, output)

    yield {
        "type": "plan_step_complete",
        "data": {
            "step_id": step.step_id,
            "skill_id": step.skill_id,
            "name": step_display,
            "status": "completed",
            "duration": elapsed,
            "output_summary": _summarize_output("visual_concept_agent", output),
        },
    }
