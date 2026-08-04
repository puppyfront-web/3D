"""ProjectMemory + ConversationState model CRUD tests (PRESALE_DELIVERY_SPEC §7.2).

Covers the upsert semantics the memory service relies on: insert-on-first,
update-on-conflict via the natural-key UNIQUE constraint. The service-layer
build_canvas_digest / inject logic is exercised in the presale main-flow E2E
(test_presale_main_flow.py) — these tests stay at the model/CRUD level so a
regression in the constraint or column shape surfaces in isolation.
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.project_memory import ConversationState, ProjectMemory


@pytest_asyncio.fixture
async def memory_project_id(db_session) -> uuid.UUID:
    """A project row to hang memory rows off (FK target)."""
    from app.models.project import Company, Project
    from app.models.user import Role, User

    role = Role(
        id=uuid.uuid4(),
        name=f"mem_role_{uuid.uuid4().hex[:8]}",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(role)
    await db_session.flush()
    user = User(
        id=uuid.uuid4(),
        email=f"mem_{uuid.uuid4().hex[:8]}@test.local",
        name="Mem User",
        role_id=role.id,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.flush()
    company = Company(
        id=uuid.uuid4(),
        name=f"Mem Co {uuid.uuid4().hex[:8]}",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(company)
    await db_session.flush()
    project = Project(
        id=uuid.uuid4(),
        name=f"Mem Project {uuid.uuid4().hex[:8]}",
        company_id=company.id,
        owner_id=user.id,
        status="draft",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(project)
    await db_session.flush()
    return project.id


@pytest.mark.asyncio
async def test_project_memory_insert_and_read(db_session, memory_project_id):
    """A ProjectMemory row round-trips through the session."""
    mem = ProjectMemory(
        project_id=memory_project_id,
        memory_type="canvas_digest",
        memory_json={"boards": [{"key": "company_intro"}], "missing_info": []},
    )
    db_session.add(mem)
    await db_session.flush()

    result = await db_session.execute(
        select(ProjectMemory).where(
            ProjectMemory.project_id == memory_project_id,
            ProjectMemory.memory_type == "canvas_digest",
        )
    )
    fetched = result.scalar_one()
    assert fetched.memory_json["boards"][0]["key"] == "company_intro"
    assert fetched.updated_at is not None


@pytest.mark.asyncio
async def test_project_memory_unique_per_type(db_session, memory_project_id):
    """Two rows with the same (project_id, memory_type) violate the constraint."""
    db_session.add(
        ProjectMemory(
            project_id=memory_project_id,
            memory_type="canvas_digest",
            memory_json={"v": 1},
        )
    )
    await db_session.flush()
    db_session.add(
        ProjectMemory(
            project_id=memory_project_id,
            memory_type="canvas_digest",
            memory_json={"v": 2},
        )
    )
    # SQLite doesn't enforce UNIQUE on flush alone — commit to trip it. Postgres
    # enforces on flush; either way the violation surfaces.
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_project_memory_distinct_types_coexist(db_session, memory_project_id):
    """Different memory_types for the same project are independent rows."""
    db_session.add(
        ProjectMemory(
            project_id=memory_project_id,
            memory_type="canvas_digest",
            memory_json={"boards": []},
        )
    )
    db_session.add(
        ProjectMemory(
            project_id=memory_project_id,
            memory_type="confirmed_facts",
            memory_json={"budget": "50万"},
        )
    )
    await db_session.flush()

    result = await db_session.execute(
        select(ProjectMemory).where(ProjectMemory.project_id == memory_project_id)
    )
    rows = result.scalars().all()
    assert len(rows) == 2
    assert {m.memory_type for m in rows} == {"canvas_digest", "confirmed_facts"}


@pytest.mark.asyncio
async def test_conversation_state_insert_and_read(db_session, memory_project_id):
    """A ConversationState row round-trips; thread_id is optional."""
    from app.models.conversation import Conversation

    conv = Conversation(
        id=uuid.uuid4(),
        title="mem conv",
        status="active",
        project_id=memory_project_id,
    )
    db_session.add(conv)
    await db_session.flush()

    state = ConversationState(
        conversation_id=conv.id,
        thread_id=None,
        state_key="last_web_hits",
        state_json={"hits": [], "summary": "ok"},
    )
    db_session.add(state)
    await db_session.flush()

    result = await db_session.execute(
        select(ConversationState).where(
            ConversationState.conversation_id == conv.id,
            ConversationState.state_key == "last_web_hits",
        )
    )
    fetched = result.scalar_one()
    assert fetched.state_json["summary"] == "ok"
    assert fetched.thread_id is None


@pytest.mark.asyncio
async def test_conversation_state_unique_per_key(db_session, memory_project_id):
    """Duplicate (conversation_id, thread_id, state_key) violates the constraint.

    Note: when thread_id is NULL, SQL NULL-distinctness means two rows DON'T
    conflict — the service layer handles NULL-thread dedup via an explicit
    upsert query. Here we set thread_id to exercise the constraint path.
    """
    from app.models.conversation import Conversation, ConversationThread

    conv = Conversation(
        id=uuid.uuid4(),
        title="mem conv",
        status="active",
        project_id=memory_project_id,
    )
    db_session.add(conv)
    await db_session.flush()
    thread = ConversationThread(
        id=uuid.uuid4(),
        conversation_id=conv.id,
        scope_type="project",
    )
    db_session.add(thread)
    await db_session.flush()

    db_session.add(
        ConversationState(
            conversation_id=conv.id,
            thread_id=thread.id,
            state_key="last_web_hits",
            state_json={"v": 1},
        )
    )
    await db_session.commit()
    db_session.add(
        ConversationState(
            conversation_id=conv.id,
            thread_id=thread.id,
            state_key="last_web_hits",
            state_json={"v": 2},
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


# ─── Service-layer tests (PRESALE_DELIVERY_SPEC §7.2) ──────────────────────


@pytest.mark.asyncio
async def test_upsert_project_memory_inserts_then_updates(db_session, memory_project_id):
    """Upsert on a fresh key inserts; a second call updates in place."""
    from app.services.project_memory_service import project_memory_service

    await project_memory_service.upsert_project_memory(
        db_session, memory_project_id, "canvas_digest", {"v": 1}
    )
    await db_session.flush()

    await project_memory_service.upsert_project_memory(
        db_session, memory_project_id, "canvas_digest", {"v": 2, "boards": []}
    )
    await db_session.flush()

    result = await db_session.execute(
        select(ProjectMemory).where(
            ProjectMemory.project_id == memory_project_id,
            ProjectMemory.memory_type == "canvas_digest",
        )
    )
    rows = result.scalars().all()
    assert len(rows) == 1, "upsert must not duplicate rows"
    assert rows[0].memory_json == {"v": 2, "boards": []}


@pytest.mark.asyncio
async def test_get_project_memory_returns_none_when_missing(db_session, memory_project_id):
    from app.services.project_memory_service import project_memory_service

    got = await project_memory_service.get_project_memory(
        db_session, memory_project_id, "never_set"
    )
    assert got is None


@pytest.mark.asyncio
async def test_upsert_conversation_state_null_thread_dedup(db_session, memory_project_id):
    """Two upserts with thread_id=None update the same row (NULL-safe dedup)."""
    from app.models.conversation import Conversation
    from app.services.project_memory_service import project_memory_service

    conv = Conversation(
        id=uuid.uuid4(),
        title="state conv",
        status="active",
        project_id=memory_project_id,
    )
    db_session.add(conv)
    await db_session.flush()

    await project_memory_service.upsert_conversation_state(
        db_session, conv.id, "last_web_hits", {"hits": ["a"]}
    )
    await db_session.flush()
    await project_memory_service.upsert_conversation_state(
        db_session, conv.id, "last_web_hits", {"hits": ["a", "b"]}
    )
    await db_session.flush()

    result = await db_session.execute(
        select(ConversationState).where(
            ConversationState.conversation_id == conv.id,
            ConversationState.state_key == "last_web_hits",
        )
    )
    rows = result.scalars().all()
    assert len(rows) == 1, "NULL-thread dedup must keep one row"
    assert rows[0].state_json == {"hits": ["a", "b"]}


@pytest.mark.asyncio
async def test_build_canvas_digest_returns_empty_for_empty_canvas(
    db_session, memory_project_id
):
    """A project with a canvas but no filled nodes → empty boards + missing_info."""
    from app.services.canvas_service import canvas_service
    from app.services.project_memory_service import project_memory_service

    # Bootstrap V1 (default topology, all nodes draft / empty planning).
    await canvas_service.ensure_initial_version(db_session, memory_project_id)
    await db_session.flush()

    digest = await project_memory_service.build_canvas_digest(
        db_session, memory_project_id
    )
    assert "boards" in digest
    assert isinstance(digest.get("missing_info"), list)
    assert digest.get("last_web_search") is None
    # No filled nodes yet → boards empty.
    assert digest["boards"] == []

