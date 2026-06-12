"""Tests for ConfigExportService — re-importable JSON serialization of config rows.

The export contract: a bare JSON array of snake_case dicts with auto-managed
columns (id/created_at/updated_at) and environment-specific project_id (Case)
stripped, so the output feeds straight back into POST /<menu>/import.
"""
import json
import uuid

import pytest
from sqlalchemy import select

from app.core.exceptions import NotFoundException
from app.services.config_export_service import ConfigExportService


@pytest.mark.asyncio
async def test_export_many_strips_managed_fields(db_session):
    """id/created_at/updated_at must not appear; name must."""
    from app.models.workflow import SOPWorkflow

    db_session.add(SOPWorkflow(name="WF1", description="d", version="1.0"))
    await db_session.flush()

    payload = await ConfigExportService.export_many(db_session, "sop_workflow")
    data = json.loads(payload)
    assert isinstance(data, list)
    assert len(data) == 1
    row = data[0]
    assert row["name"] == "WF1"
    for forbidden in ("id", "created_at", "updated_at", "project_id"):
        assert forbidden not in row, f"{forbidden} should be stripped"


@pytest.mark.asyncio
async def test_export_many_emits_snake_case_keys(db_session):
    """Keys are SQLAlchemy column names (snake_case), not the camelCase API alias."""
    from app.models.workflow import SOPWorkflow

    db_session.add(SOPWorkflow(name="Snake"))
    await db_session.flush()

    row = json.loads(await ConfigExportService.export_many(db_session, "sop_workflow"))[0]
    assert "is_active" in row  # not isActive — import needs snake_case
    assert "isActive" not in row


@pytest.mark.asyncio
async def test_export_one_missing_raises_404(db_session):
    """A nonexistent id -> NotFoundException (router maps to 404)."""
    with pytest.raises(NotFoundException):
        await ConfigExportService.export_one(db_session, "sop_workflow", uuid.uuid4())


@pytest.mark.asyncio
async def test_export_one_returns_single_element_array(db_session):
    """Single-row export is a 1-element array (re-importable as-is)."""
    from app.models.workflow import SOPWorkflow

    wf = SOPWorkflow(name="Solo")
    db_session.add(wf)
    await db_session.flush()

    data = json.loads(await ConfigExportService.export_one(db_session, "sop_workflow", wf.id))
    assert len(data) == 1
    assert data[0]["name"] == "Solo"


@pytest.mark.asyncio
async def test_export_case_strips_project_id(db_session, sample_project_id):
    """Case export must drop project_id (it's re-injected at import per target project)."""
    from app.models.case import Case

    db_session.add(Case(project_id=sample_project_id, title="Case T", client_name="Client C"))
    await db_session.flush()

    row = json.loads(await ConfigExportService.export_many(db_session, "case"))[0]
    assert "project_id" not in row
    assert row["title"] == "Case T"
    assert row["client_name"] == "Client C"
