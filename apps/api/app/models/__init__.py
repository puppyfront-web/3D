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
    "Feedback",
]
