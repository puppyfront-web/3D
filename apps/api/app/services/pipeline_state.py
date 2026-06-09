"""Pipeline session state — stored in conversation metadata_json."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# Ordered stage definitions for the standard pipeline
STAGE_ORDER = [
    "company_analysis",
    "proposal_generation",
    "visual_generation",
    "export",
]

# Stages that pause for user confirmation after execution
PAUSE_STAGES = {"company_analysis", "proposal_generation", "visual_generation"}


@dataclass
class PipelineState:
    """Represents an in-progress SOP pipeline session."""

    status: str = "running"  # running | paused | completed | failed
    current_stage: str = "company_analysis"
    completed_stages: List[str] = field(default_factory=list)
    project_context: Dict[str, Any] = field(default_factory=dict)
    stage_outputs: Dict[str, Any] = field(default_factory=dict)
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ── Serialization ──

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline": {
                "status": self.status,
                "current_stage": self.current_stage,
                "completed_stages": self.completed_stages,
                "project_context": self.project_context,
                "stage_outputs": self.stage_outputs,
                "started_at": self.started_at,
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PipelineState:
        p = data.get("pipeline", data)
        return cls(
            status=p.get("status", "running"),
            current_stage=p.get("current_stage", "company_analysis"),
            completed_stages=p.get("completed_stages", []),
            project_context=p.get("project_context", {}),
            stage_outputs=p.get("stage_outputs", {}),
            started_at=p.get("started_at", ""),
        )

    # ── Helpers ──

    def next_stage(self) -> Optional[str]:
        """Return the next stage after current, or None if done."""
        try:
            idx = STAGE_ORDER.index(self.current_stage)
        except ValueError:
            return None
        next_idx = idx + 1
        if next_idx >= len(STAGE_ORDER):
            return None
        return STAGE_ORDER[next_idx]

    def advance(self) -> Optional[str]:
        """Mark current stage completed, advance to next. Returns new stage or None."""
        if self.current_stage not in self.completed_stages:
            self.completed_stages.append(self.current_stage)
        nxt = self.next_stage()
        if nxt is None:
            self.status = "completed"
            return None
        self.current_stage = nxt
        self.status = "running"
        return nxt

    def pause(self) -> None:
        """Pause pipeline, waiting for user confirmation."""
        self.status = "paused"

    def reset(self) -> None:
        """Reset pipeline to initial state."""
        self.status = "running"
        self.current_stage = "company_analysis"
        self.completed_stages = []
        self.stage_outputs = {}
