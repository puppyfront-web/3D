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
    used_external_sources: List[Dict[str, Any]] = field(default_factory=list)
    external_search_summary: Optional[Dict[str, Any]] = None
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
            "used_external_sources": self.used_external_sources,
            "external_search_summary": self.external_search_summary,
            "missing_info": self.missing_info,
            "duration_ms": self.duration_ms,
        }


# Mapping from `SkillManifest.required_services` strings to concrete Tool IDs.
# Services mapped to None are NOT tools — they are injected at runtime via
# SkillContext (LLM / embedding / image / export services) rather than looked
# up in the ToolRegistry, so they are intentionally left unvalidated.
REQUIRED_SERVICE_TO_TOOL: Dict[str, Optional[str]] = {
    "knowledge.retrieve": "knowledge_search",
    "case_search": "case_search",
    "sop.load": "sop_load",
    "template.load": "template_load",
    "prompt_template.load": "prompt_template_load",
    "visual_style.match": "visual_style_match",
    "tech_rule.query": "tech_rule_query",
    "quality_rule.query": "quality_rule_query",
    "company_profile.load": "company_profile_load",
    "web.search": "web_search",
    "image.generate": "image_generate",
    # LLM/embedding/image services are NOT tools — they're injected via SkillContext
    "llm.generate": None,
    "llm.generate_json": None,
    "llm.generate_stream": None,
    "embedding.embed": None,
    "export.docx": None,
    "export.pdf": None,
    "export.pptx": None,
}


class BaseSkill(ABC):
    """Abstract base class for all skills."""

    manifest: SkillManifest

    @abstractmethod
    async def execute(self, input_data: Dict[str, Any], context: SkillContext) -> SkillResult:
        """Execute the skill with validated input. Return structured output."""

    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input against manifest.input_schema.

        Checks both key presence AND type (Defect #12: previously only checked
        key existence, letting wrong-typed values through to the LLM call).
        """
        schema = self.manifest.input_schema
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        # 1. Required keys present
        for key in required:
            if key not in input_data:
                return False

        # 2. Type check for keys that have a declared type in properties
        _json_type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }
        for key, value in input_data.items():
            prop = properties.get(key)
            if not prop or "type" not in prop:
                continue
            expected_type = prop["type"]
            # Determine the Python type(s) that match the JSON schema type
            py_types = []
            for py, json_type in _json_type_map.items():
                if json_type == expected_type:
                    py_types.append(py)
            # "number" matches both int and float in JSON schema
            if expected_type == "number" and int not in py_types:
                py_types.append(int)
            if py_types and not isinstance(value, tuple(py_types)):
                logger.warning(
                    "Skill %s: field '%s' expected type '%s' but got %s",
                    self.manifest.skill_id, key, expected_type, type(value).__name__,
                )
                return False
        return True

    def get_manifest(self) -> SkillManifest:
        """Return the skill's manifest."""
        return self.manifest

    @staticmethod
    def _tool_context(context: "SkillContext") -> "ToolContext":
        """Create a ToolContext from a SkillContext for Tool calls."""
        from app.tools.base import ToolContext
        return ToolContext(
            db=context.db,
            embedding_service=context.embedding_service,
            llm_service=context.llm_service,
        )

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
