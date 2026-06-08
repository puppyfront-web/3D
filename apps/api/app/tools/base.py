"""Base classes for the Tool system.

Tools are the standardised data-access layer between Skills and the database.
Each Tool encapsulates ONE type of structured query (e.g. case search, SOP load,
rule query) so that Skills never import ORM models directly.

Pattern:
  Skill → ToolRegistry.get("case_search") → CaseSearchTool.execute(params) → DB

Mirrors the Skill system (skills/base.py) for consistency.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─── Manifest ───────────────────────────────────────────────────


@dataclass
class ToolManifest:
    """Metadata definition for a Tool."""

    tool_id: str
    name: str
    description: str
    category: str  # "retrieval" | "loader" | "validator" | "generator"
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)


# ─── Context ────────────────────────────────────────────────────


@dataclass
class ToolContext:
    """Runtime context injected when a Tool is executed.

    Deliberately minimal — Tools only receive what they need.
    """

    db: Any = None  # AsyncSession — use Any to avoid circular imports
    embedding_service: Any = None  # only for knowledge_search tool
    llm_service: Any = None  # only for tools that need LLM calls


# ─── Result ─────────────────────────────────────────────────────


@dataclass
class ToolResult:
    """Structured output from a Tool execution."""

    success: bool = True
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
        }


# ─── Base Tool ──────────────────────────────────────────────────


class BaseTool(ABC):
    """Abstract base class for all Tools."""

    manifest: ToolManifest

    @abstractmethod
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        """Execute the tool with the given parameters. Return structured result."""

    def get_manifest(self) -> ToolManifest:
        """Return the tool's manifest."""
        return self.manifest
