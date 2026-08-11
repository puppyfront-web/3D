"""SQLAlchemy models — re-export every model so that Alembic and the
metadata registry pick them all up."""

from app.models.user import Role, User
from app.models.project import Company, Project
from app.models.company_profile import CompanyProfile
from app.models.document import Document, DocumentChunk
from app.models.case import Case
from app.models.template import PromptTemplate, ProposalTemplate
from app.models.workflow import SOPWorkflow
from app.models.visual import VisualStyle
from app.models.rule import QualityRule, TechnicalRule
from app.models.generation import GenerationOutput, GenerationTask
from app.models.retrieval import RetrievalLog
from app.models.feedback import Feedback
from app.models.skill import Skill, SkillExecution
from app.models.conversation import Conversation, ConversationThread, Message
from app.models.conversation_lock import ConversationLock
from app.models.project_memory import ConversationState, ProjectMemory
from app.models.operation_run import OperationRun
from app.models.app_setting import AppSetting
from app.models.industry_material import IndustryMaterial
from app.models.talking_point import TalkingPoint
from app.models.pricing_experience import PricingExperience
from app.models.eval import EvalCase, EvalRun, EvalSet
from app.models.knowledge_asset_revision import KnowledgeAssetRevision
from app.models.canvas import (
    Canvas,
    CanvasEdge,
    CanvasGroup,
    CanvasNode,
    NodeSource,
    ProjectVersion,
)

__all__ = [
    "User",
    "Role",
    "Company",
    "Project",
    "CompanyProfile",
    "Document",
    "DocumentChunk",
    "Case",
    "PromptTemplate",
    "ProposalTemplate",
    "SOPWorkflow",
    "VisualStyle",
    "TechnicalRule",
    "QualityRule",
    "GenerationTask",
    "GenerationOutput",
    "RetrievalLog",
    "EvalSet",
    "EvalCase",
    "EvalRun",
    "Feedback",
    "Skill",
    "SkillExecution",
    "Conversation",
    "ConversationThread",
    "Message",
    "ConversationLock",
    # Project + conversation memory (PRESALE_DELIVERY_SPEC §7.2)
    "ProjectMemory",
    "ConversationState",
    # Operation-level observability parent (PRESALE_DELIVERY_SPEC §11.2)
    "OperationRun",
    "AppSetting",
    # Internal knowledge bases (PRD §12)
    "IndustryMaterial",
    "TalkingPoint",
    "PricingExperience",
    # Version history for knowledge base assets (PRD §23.4.9)
    "KnowledgeAssetRevision",
    # Infinite-canvas workspace (snapshot version model)
    "ProjectVersion",
    "Canvas",
    "CanvasGroup",
    "CanvasNode",
    "CanvasEdge",
    "NodeSource",
]
