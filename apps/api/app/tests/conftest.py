"""Test fixtures — SQLite in-memory database for testing."""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base
from app.models import *  # noqa: F401,F403 — ensure all models are registered

# Use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///file::memory:?cache=shared&uri=true"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    future=True,
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    """Create all tables once for the test session.

    Also redirects the *production* session factory/engine in
    ``app.db.session`` onto the in-memory test engine. Several service paths
    (e.g. ``conversation_service._handle_skill_execution``) open their own
    session via ``async_session_factory`` to dodge SQLite write-lock
    contention — without this redirect they would hit the file-based
    ``dev.db`` (stale schema, no test isolation) instead of the test DB.
    Doing the swap at session scope means every code path, DI or otherwise,
    resolves to the same in-memory database.
    """
    from sqlalchemy import event

    import app.db.session as db_session_module

    @event.listens_for(test_engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Redirect production engine + session factory → test engine.
    # `get_db` still resolves through dependency_overrides in the `client`
    # fixture, but any `async with async_session_factory()` call site now
    # binds to the test engine too.
    db_session_module.engine = test_engine
    db_session_module.async_session_factory = TestSessionLocal

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(autouse=True)
async def _isolate_db_state():
    """Wipe all rows before AND after every test.

    Why: the test DB is a single shared in-memory SQLite (``cache=shared``).
    Some service paths (e.g. ``conversation_service._handle_skill_execution``)
    open their OWN session via ``async_session_factory`` and COMMIT writes to
    that shared DB — those commits survive the per-test ``db_session``
    rollback and leak into the next test (the root cause of
    ``test_list_projects_empty`` flakiness). Flushing every table around each
    test makes the suite order-independent regardless of which session a code
    path writes through.
    """
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    yield
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a fresh database session for each test."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an HTTP test client with the test database session injected.

    Also bypasses JWT auth: the test client has no access token, so we
    override ``get_current_user`` with a mock that returns a seeded admin
    user. Production still enforces auth — this override only affects tests.
    """
    from app.core.security import get_current_user
    from app.db.session import get_db
    from app.main import create_app
    from app.models.user import Role, User

    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Seed an admin user + role and return it from the auth dependency so
    # every protected endpoint sees an authenticated admin in tests.
    admin_role = Role(
        id=uuid.uuid4(),
        name="admin",
        description="Test admin role",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(admin_role)
    await db_session.flush()

    admin_user = User(
        id=uuid.uuid4(),
        email="test-admin@example.com",
        name="Test Admin",
        role_id=admin_role.id,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(admin_user)
    await db_session.flush()

    async def override_get_current_user():
        # Refresh role relationship so require_admin-style checks pass.
        await db_session.refresh(admin_user, ["role"])
        return admin_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_conversation(db_session: AsyncSession):
    """Create and return a Conversation row for lock tests."""
    from app.models.conversation import Conversation

    conv = Conversation(title="test conv", status="active")
    db_session.add(conv)
    await db_session.flush()
    return conv


@pytest_asyncio.fixture
async def sample_role_id(db_session: AsyncSession) -> uuid.UUID:
    """Create and return a sample role ID."""
    from app.models.user import Role

    role = Role(
        id=uuid.uuid4(),
        name="test_user",
        description="Test user role",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(role)
    await db_session.flush()
    return role.id


@pytest_asyncio.fixture
async def sample_user_id(db_session: AsyncSession, sample_role_id: uuid.UUID) -> uuid.UUID:
    """Create and return a sample user ID."""
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        name="Test User",
        role_id=sample_role_id,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.flush()
    return user.id


@pytest_asyncio.fixture
async def sample_company_id(db_session: AsyncSession) -> uuid.UUID:
    """Create and return a sample company ID."""
    from app.models.project import Company

    company = Company(
        id=uuid.uuid4(),
        name="Test Company",
        industry="Technology",
        website="https://test.example.com",
        description="A test company for unit tests",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(company)
    await db_session.flush()
    return company.id


@pytest_asyncio.fixture
async def sample_project_id(
    db_session: AsyncSession,
    sample_company_id: uuid.UUID,
    sample_user_id: uuid.UUID,
) -> uuid.UUID:
    """Create and return a sample project ID."""
    from app.models.project import Project

    project = Project(
        id=uuid.uuid4(),
        name="Test Project",
        description="A test project",
        company_id=sample_company_id,
        owner_id=sample_user_id,
        status="draft",
        priority="medium",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(project)
    await db_session.flush()
    return project.id
