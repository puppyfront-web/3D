"""Tests for database model creation and relationships."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models.case import Case
from app.models.company_profile import CompanyProfile
from app.models.document import Document, DocumentChunk
from app.models.feedback import Feedback
from app.models.generation import GenerationOutput, GenerationTask
from app.models.project import Company, Project
from app.models.rule import QualityRule, TechnicalRule
from app.models.template import PromptTemplate, ProposalTemplate
from app.models.user import Role, User
from app.models.visual import VisualStyle
from app.models.workflow import SOPWorkflow


@pytest.mark.asyncio
async def test_create_role(db_session):
    """Test creating a Role."""
    role = Role(
        id=uuid.uuid4(),
        name="admin_test",
        description="Test admin role",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(role)
    await db_session.flush()

    result = await db_session.execute(select(Role).where(Role.name == "admin_test"))
    fetched = result.scalar_one()
    assert fetched.name == "admin_test"
    assert fetched.description == "Test admin role"


@pytest.mark.asyncio
async def test_create_user_with_role(db_session, sample_role_id):
    """Test creating a User with a role relationship."""
    user = User(
        id=uuid.uuid4(),
        email="model_test@example.com",
        name="Model Test User",
        role_id=sample_role_id,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.flush()

    result = await db_session.execute(select(User).where(User.email == "model_test@example.com"))
    fetched = result.scalar_one()
    assert fetched.name == "Model Test User"
    assert fetched.role_id == sample_role_id
    assert fetched.is_active is True


@pytest.mark.asyncio
async def test_create_company(db_session):
    """Test creating a Company."""
    company = Company(
        id=uuid.uuid4(),
        name="Model Test Corp",
        industry="Finance",
        description="Test company for model tests",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(company)
    await db_session.flush()

    result = await db_session.execute(select(Company).where(Company.name == "Model Test Corp"))
    fetched = result.scalar_one()
    assert fetched.industry == "Finance"


@pytest.mark.asyncio
async def test_create_project(db_session, sample_company_id, sample_user_id):
    """Test creating a Project linked to a company and owner."""
    project = Project(
        id=uuid.uuid4(),
        name="Model Test Project",
        company_id=sample_company_id,
        owner_id=sample_user_id,
        status="draft",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(project)
    await db_session.flush()

    result = await db_session.execute(select(Project).where(Project.name == "Model Test Project"))
    fetched = result.scalar_one()
    assert fetched.company_id == sample_company_id
    assert fetched.status == "draft"


@pytest.mark.asyncio
async def test_create_case(db_session, sample_project_id):
    """Test creating a Case linked to a project."""
    case = Case(
        id=uuid.uuid4(),
        project_id=sample_project_id,
        title="Model Test Case",
        client_name="Test Client",
        industry="Healthcare",
        challenge="Test challenge description",
        solution="Test solution description",
        results="Test results",
        quality_score=85.0,
        is_published=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(case)
    await db_session.flush()

    result = await db_session.execute(select(Case).where(Case.title == "Model Test Case"))
    fetched = result.scalar_one()
    assert fetched.quality_score == 85.0
    assert fetched.is_published is True


@pytest.mark.asyncio
async def test_create_document(db_session, sample_project_id):
    """Test creating a Document."""
    doc = Document(
        id=uuid.uuid4(),
        project_id=sample_project_id,
        filename="test_doc.pdf",
        original_filename="Test Doc.pdf",
        content_type="application/pdf",
        file_size=1024,
        file_path="/tmp/test_doc.pdf",
        status="uploaded",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(doc)
    await db_session.flush()

    result = await db_session.execute(select(Document).where(Document.filename == "test_doc.pdf"))
    fetched = result.scalar_one()
    assert fetched.file_size == 1024
    assert fetched.status == "uploaded"


@pytest.mark.asyncio
async def test_create_prompt_template(db_session):
    """Test creating a PromptTemplate."""
    template = PromptTemplate(
        id=uuid.uuid4(),
        name="Test Prompt Template",
        category="test",
        template_text="Hello {name}, this is a test.",
        variables=["name"],
        is_default=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(template)
    await db_session.flush()

    result = await db_session.execute(
        select(PromptTemplate).where(PromptTemplate.name == "Test Prompt Template")
    )
    fetched = result.scalar_one()
    assert fetched.category == "test"
    assert "name" in fetched.variables


@pytest.mark.asyncio
async def test_create_visual_style(db_session):
    """Test creating a VisualStyle."""
    style = VisualStyle(
        id=uuid.uuid4(),
        name="Test Style",
        primary_color="#FF0000",
        secondary_color="#00FF00",
        accent_color="#0000FF",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(style)
    await db_session.flush()

    result = await db_session.execute(select(VisualStyle).where(VisualStyle.name == "Test Style"))
    fetched = result.scalar_one()
    assert fetched.primary_color == "#FF0000"


@pytest.mark.asyncio
async def test_create_generation_task_and_output(db_session, sample_project_id):
    """Test creating a GenerationTask with an output."""
    task = GenerationTask(
        id=uuid.uuid4(),
        project_id=sample_project_id,
        type="proposal",
        status="completed",
        model_used="mock-v1",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(task)
    await db_session.flush()

    output = GenerationOutput(
        id=uuid.uuid4(),
        task_id=task.id,
        content_type="text/markdown",
        content="# Test Proposal\n\nContent here.",
        used_cases=[str(uuid.uuid4())],
        used_documents=[],
        used_chunks=[],
        used_sop_version="1.0",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(output)
    await db_session.flush()

    result = await db_session.execute(
        select(GenerationOutput).where(GenerationOutput.task_id == task.id)
    )
    fetched = result.scalar_one()
    assert fetched.content_type == "text/markdown"
    assert len(fetched.used_cases) == 1
