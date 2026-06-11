"""Execution Plan — dynamic, domain-aware plan for multi-skill orchestration.

Replaces the fixed 4-stage PipelineState with a flexible plan that adapts
to different business domains (curtain wall, exhibition, culture tourism, etc.).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class PlanStep:
    """A single step in an execution plan."""

    step_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    skill_id: str = ""
    name: str = ""                    # Display name (e.g. "企业解析")
    description: str = ""
    depends_on: List[str] = field(default_factory=list)   # step_ids this depends on
    pause_after: bool = False         # Pause for user confirmation after execution
    optional: bool = False            # Can be skipped if condition not met
    condition: Optional[str] = None   # Python-like expression, e.g. "domain == 'exhibition'"

    status: str = "pending"           # pending | running | completed | failed | skipped
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "depends_on": self.depends_on,
            "pause_after": self.pause_after,
            "optional": self.optional,
            "condition": self.condition,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PlanStep:
        return cls(
            step_id=data.get("step_id", str(uuid.uuid4())[:8]),
            skill_id=data.get("skill_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            depends_on=data.get("depends_on", []),
            pause_after=data.get("pause_after", False),
            optional=data.get("optional", False),
            condition=data.get("condition"),
            status=data.get("status", "pending"),
            output=data.get("output"),
            error=data.get("error"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )


@dataclass
class ExecutionPlan:
    """A dynamic execution plan that adapts to the business domain."""

    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    domain: str = ""                  # curtain_wall | exhibition | culture_tourism | multimedia
    project_type: str = ""            # Finer-grained type (e.g. "enterprise_showroom")

    steps: List[PlanStep] = field(default_factory=list)
    step_outputs: Dict[str, Any] = field(default_factory=dict)  # step_id → output

    status: str = "draft"             # draft | running | paused | completed | failed | replanning
    current_step_index: int = 0
    context: Dict[str, Any] = field(default_factory=dict)  # user_message, company_name, etc.

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    replan_count: int = 0
    max_replans: int = 2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_plan": {
                "plan_id": self.plan_id,
                "domain": self.domain,
                "project_type": self.project_type,
                "steps": [s.to_dict() for s in self.steps],
                "step_outputs": self.step_outputs,
                "status": self.status,
                "current_step_index": self.current_step_index,
                "context": self.context,
                "created_at": self.created_at,
                "replan_count": self.replan_count,
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutionPlan:
        ep = data.get("execution_plan", data)
        plan = cls(
            plan_id=ep.get("plan_id", str(uuid.uuid4())),
            domain=ep.get("domain", ""),
            project_type=ep.get("project_type", ""),
            step_outputs=ep.get("step_outputs", {}),
            status=ep.get("status", "draft"),
            current_step_index=ep.get("current_step_index", 0),
            context=ep.get("context", {}),
            created_at=ep.get("created_at", ""),
            replan_count=ep.get("replan_count", 0),
        )
        for s in ep.get("steps", []):
            plan.steps.append(PlanStep.from_dict(s))
        return plan

    # ── Helpers ──

    def current_step(self) -> Optional[PlanStep]:
        """Return the current step to execute."""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    def advance(self) -> Optional[PlanStep]:
        """Move to next pending step. Returns the next step or None if done."""
        self.current_step_index += 1
        while self.current_step_index < len(self.steps):
            step = self.steps[self.current_step_index]
            if step.status == "pending":
                return step
            self.current_step_index += 1
        self.status = "completed"
        return None

    def pause(self) -> None:
        self.status = "paused"

    def mark_step_completed(self, step_id: str, output: Dict[str, Any]) -> None:
        """Mark a step as completed and store its output."""
        for step in self.steps:
            if step.step_id == step_id:
                step.status = "completed"
                step.output = output
                step.completed_at = datetime.now(timezone.utc).isoformat()
                self.step_outputs[step.skill_id] = output
                break

    def mark_step_failed(self, step_id: str, error: str) -> None:
        for step in self.steps:
            if step.step_id == step_id:
                step.status = "failed"
                step.error = error
                step.completed_at = datetime.now(timezone.utc).isoformat()
                break

    def should_skip(self, step: PlanStep) -> bool:
        """Check if a step should be skipped based on its condition."""
        if not step.condition:
            return False
        try:
            # Simple condition evaluation with domain context
            local_vars = {
                "domain": self.domain,
                "project_type": self.project_type,
                "context": self.context,
            }
            return not bool(eval(step.condition, {"__builtins__": {}}, local_vars))
        except Exception:
            return step.optional  # If condition can't be evaluated, skip only if optional


# ── Plan templates for each domain ──

def create_plan_for_domain(
    domain: str,
    user_message: str = "",
    company_name: str = "",
) -> ExecutionPlan:
    """Create a standard execution plan for a given domain.

    All domains now use the 3-step expert-agent pipeline:
      proposal_agent → visual_concept_agent → export
    """
    domain_labels = {
        "curtain_wall": ("幕墙/LED", "3D幕墙/裸眼3D/LED媒体立面"),
        "exhibition": ("展厅/展陈", "企业展厅/博物馆/规划馆"),
        "culture_tourism": ("文旅/夜游", "文旅夜游/沉浸式体验/光影秀"),
        "multimedia": ("多媒体互动", "互动装置/数字沙盘/AR/VR"),
    }
    label, desc = domain_labels.get(domain, ("综合", "数字视觉展示"))

    return ExecutionPlan(
        domain=domain,
        project_type=domain,
        context={"user_message": user_message, "company_name": company_name},
        steps=[
            PlanStep(
                skill_id="proposal_agent",
                name=f"策划案专家（{label}）",
                description=f"企业解析 + RAG检索 + 策划案生成（{desc}）",
                pause_after=True,
            ),
            PlanStep(
                skill_id="visual_concept_agent",
                name="视觉创意专家",
                description="基于策划案生成视觉概念图（多轮交互）",
                depends_on=["proposal_agent"],
                pause_after=True,
            ),
            PlanStep(
                skill_id="export",
                name="方案导出",
                description="导出 Word/PDF 文档",
                depends_on=["visual_concept_agent"],
            ),
        ],
    )
