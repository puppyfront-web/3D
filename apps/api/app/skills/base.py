"""Base classes for the Skill Runtime system."""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SkillManifest:
    """Metadata definition for a skill."""

    skill_id: str
    name: str
    description: str
    category: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    required_services: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    visibility: str = "internal"
    version: str = "1.0.0"


@dataclass
class SkillContext:
    """Runtime context injected by the SkillRunner."""

    project_id: Optional[str] = None
    user_id: Optional[str] = None
    db: Any = None  # AsyncSession — use Any to avoid circular imports
    llm_service: Any = None
    embedding_service: Any = None
    image_service: Any = None
    retrieval_service: Any = None


@dataclass
class SkillResult:
    """Structured output from a skill execution."""

    success: bool = True
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    used_cases: List[str] = field(default_factory=list)
    used_documents: List[str] = field(default_factory=list)
    used_chunks: List[str] = field(default_factory=list)
    missing_info: List[str] = field(default_factory=list)
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "used_cases": self.used_cases,
            "used_documents": self.used_documents,
            "used_chunks": self.used_chunks,
            "missing_info": self.missing_info,
            "duration_ms": self.duration_ms,
        }


class BaseSkill(ABC):
    """Abstract base class for all skills."""

    manifest: SkillManifest

    @abstractmethod
    async def execute(self, input_data: Dict[str, Any], context: SkillContext) -> SkillResult:
        """Execute the skill with validated input. Return structured output."""

    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input against manifest.input_schema required fields."""
        required = self.manifest.input_schema.get("required", [])
        return all(key in input_data for key in required)

    def get_manifest(self) -> SkillManifest:
        """Return the skill's manifest."""
        return self.manifest

    async def _load_prompt_template(self, context: SkillContext, category: str) -> str | None:
        """Load a prompt template from the database by category."""
        if context.db is None:
            return None
        from sqlalchemy import select
        from app.models.template import PromptTemplate

        result = await context.db.execute(
            select(PromptTemplate).where(PromptTemplate.category == category).limit(1)
        )
        template = result.scalar_one_or_none()
        return template.template_text if template else None

    def _assemble_prompt(
        self,
        default_prompt: str,
        db_template: str | None,
        variables: dict[str, str],
    ) -> str:
        """Assemble final prompt: substitute variables into default prompt (which
        always contains the framework / OUTPUT_SCHEMA), then append DB template as
        supplementary admin instructions if present.

        The default prompt is always the base — it defines the structural contract
        between the skill and the LLM. The DB template provides admin-configurable
        additional instructions that are appended, not replace.
        """
        base = default_prompt
        for key, value in variables.items():
            base = base.replace("{" + key + "}", value)

        if db_template:
            for key, value in variables.items():
                db_template = db_template.replace("{" + key + "}", value)
            unsubstituted = self._validate_template_variables(db_template, variables)
            if unsubstituted:
                logger.warning(
                    "Skill %s: DB template has unsubstituted variables: %s",
                    self.manifest.skill_id,
                    unsubstituted,
                )
            base += "\n\n--- 管理员补充指令 ---\n" + db_template

        return base

    @staticmethod
    def _validate_template_variables(
        text: str,
        provided_variables: dict[str, str],
    ) -> list[str]:
        """Check for unsubstituted {var} placeholders remaining in text.
        Returns list of variable names that remain unsubstituted."""
        remaining = re.findall(r"\{(\w+)\}", text)
        return [v for v in remaining if v not in provided_variables]
