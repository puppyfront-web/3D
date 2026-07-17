"""OperationRun service tests (PRESALE_DELIVERY_SPEC §11.2 — minimal P2).

Covers the start / add_step / finish lifecycle the auto-fill wrapper uses.
Soft-fail semantics: a broken OperationRun write never breaks the main flow.
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.operation_run import OperationRun
from app.services.operation_run_service import operation_run_service


@pytest_asyncio.fixture
async def run_project_id(db_session) -> uuid.UUID:
    from app.models.project import Company, Project
    from app.models.user import Role, User

    role = Role(
        id=uuid.uuid4(),
        name=f"op_role_{uuid.uuid4().hex[:8]}",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(role)
    await db_session.flush()
    user = User(
        id=uuid.uuid4(),
        email=f"op_{uuid.uuid4().hex[:8]}@test.local",
        name="Op User",
        role_id=role.id,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.flush()
    company = Company(
        id=uuid.uuid4(),
        name=f"Op Co {uuid.uuid4().hex[:8]}",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(company)
    await db_session.flush()
    project = Project(
        id=uuid.uuid4(),
        name=f"Op Project {uuid.uuid4().hex[:8]}",
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
async def test_start_creates_running_run(db_session, run_project_id):
    run = await operation_run_service.start(
        db_session, run_project_id, "auto_fill"
    )
    await db_session.flush()
    assert run is not None
    assert run.status == "running"
    assert run.operation_type == "auto_fill"
    assert run.steps == []


@pytest.mark.asyncio
async def test_add_step_appends_to_steps(db_session, run_project_id):
    run = await operation_run_service.start(
        db_session, run_project_id, "auto_fill"
    )
    await db_session.flush()
    await operation_run_service.add_step(
        db_session, run, "web_search", "completed", extra={"hit_count": 3}
    )
    await operation_run_service.add_step(
        db_session, run, "canvas_fill", "completed"
    )
    await db_session.flush()
    assert len(run.steps) == 2
    assert run.steps[0]["step"] == "web_search"
    assert run.steps[0]["extra"]["hit_count"] == 3
    assert run.steps[1]["step"] == "canvas_fill"


@pytest.mark.asyncio
async def test_finish_marks_completed_with_ended_at(db_session, run_project_id):
    run = await operation_run_service.start(
        db_session, run_project_id, "auto_fill"
    )
    await db_session.flush()
    await operation_run_service.finish(db_session, run, status="completed")
    await db_session.flush()
    assert run.status == "completed"
    assert run.ended_at is not None


@pytest.mark.asyncio
async def test_finish_marks_failed_with_error(db_session, run_project_id):
    run = await operation_run_service.start(
        db_session, run_project_id, "auto_fill"
    )
    await db_session.flush()
    await operation_run_service.finish(
        db_session, run, status="failed", error="canvas_fill blew up"
    )
    await db_session.flush()
    assert run.status == "failed"
    assert run.error == "canvas_fill blew up"


@pytest.mark.asyncio
async def test_add_step_soft_fails_on_none_run(db_session):
    """Passing run=None must not raise (soft-fail contract)."""
    # Should be a no-op.
    await operation_run_service.add_step(db_session, None, "x", "y")
    await operation_run_service.finish(db_session, None)


@pytest.mark.asyncio
async def test_auto_fill_creates_operation_run_e2e(client, db_session):
    """The auto-fill wrapper writes an OperationRun row with ≥2 steps."""
    from app.tests.test_presale_main_flow import (
        _seed_admin_owner,
        _wizard_payload,
    )

    await _seed_admin_owner(db_session)
    suffix = uuid.uuid4().hex[:8]
    wiz = await client.post("/api/v1/projects/wizard", json=await _wizard_payload(suffix))
    project_id = wiz.json()["data"]["id"]
    conv_id = (
        (await client.get(f"/api/v1/projects/{project_id}/conversation"))
        .json()["data"]["id"]
    )
    chat = await client.post(
        f"/api/v1/conversations/{conv_id}/chat/stream",
        json={"message": "给测试企业做一个裸眼3D幕墙发布方案"},
    )
    assert chat.status_code == 200, chat.text

    await db_session.commit()
    runs = (
        await db_session.execute(
            select(OperationRun).where(
                OperationRun.project_id == uuid.UUID(project_id),
                OperationRun.operation_type == "auto_fill",
            )
        )
    ).scalars().all()
    assert len(runs) == 1, "auto-fill should create exactly one OperationRun"
    run = runs[0]
    assert run.status == "completed"
    # ≥2 steps: web_search + memory_write (canvas_fill / brief steps are
    # best-effort). The hard requirement is the run exists and is finalised.
    assert len(run.steps or []) >= 2
