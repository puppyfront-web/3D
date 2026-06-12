"""Router-level round-trip tests: export -> import is idempotent and respects the
conflict mode. This also establishes the HTTP multipart import test pattern
(no prior router-level import tests existed)."""
import json

import pytest


async def _create_workflow(client, name: str, version: str = "1.0") -> str:
    resp = await client.post(
        "/api/v1/workflows", json={"name": name, "version": version, "steps": []}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


@pytest.mark.asyncio
async def test_workflow_export_then_import_skip_is_idempotent(client):
    """Exporting existing workflows and re-importing with skip changes nothing."""
    await _create_workflow(client, "WF-A")
    await _create_workflow(client, "WF-B")

    exported = (await client.get("/api/v1/workflows/export")).json()
    assert len(exported) == 2
    assert {r["name"] for r in exported} == {"WF-A", "WF-B"}

    resp = await client.post(
        "/api/v1/workflows/import",
        params={"mode": "skip"},
        files={"file": ("workflows.json", json.dumps(exported).encode(), "application/json")},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["imported"] == 0
    assert data["skipped"] == 2

    # Still only two workflows — no duplicates created.
    total = (await client.get("/api/v1/workflows")).json()["total"]
    assert total == 2


@pytest.mark.asyncio
async def test_workflow_import_overwrite_updates_existing(client):
    """mode=overwrite updates fields on the matched row; id is preserved."""
    wf_id = await _create_workflow(client, "OverwriteMe", version="1.0")

    exported = (await client.get("/api/v1/workflows/export")).json()
    exported[0]["version"] = "9.9"  # mutate a field

    resp = await client.post(
        "/api/v1/workflows/import",
        params={"mode": "overwrite"},
        files={"file": ("workflows.json", json.dumps(exported).encode(), "application/json")},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["updated"] == 1

    got = (await client.get(f"/api/v1/workflows/{wf_id}")).json()["data"]
    assert got["version"] == "9.9"  # field overwritten, same id


@pytest.mark.asyncio
async def test_workflow_import_rename_creates_copy(client):
    """mode=rename inserts a suffixed copy; original is untouched."""
    await _create_workflow(client, "RenameMe")

    exported = (await client.get("/api/v1/workflows/export")).json()

    resp = await client.post(
        "/api/v1/workflows/import",
        params={"mode": "rename"},
        files={"file": ("workflows.json", json.dumps(exported).encode(), "application/json")},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["imported"] == 1

    names = {w["name"] for w in (await client.get("/api/v1/workflows")).json()["items"]}
    assert names == {"RenameMe", "RenameMe (副本)"}


@pytest.mark.asyncio
async def test_workflow_single_export_returns_one_element_array(client):
    """GET /{id}/export yields a 1-element array re-importable as-is."""
    wf_id = await _create_workflow(client, "Solo")

    exported = (await client.get(f"/api/v1/workflows/{wf_id}/export")).json()
    assert isinstance(exported, list) and len(exported) == 1
    assert exported[0]["name"] == "Solo"


@pytest.mark.asyncio
async def test_cases_export_import_roundtrip_with_project_id(client, sample_project_id):
    """Cases round-trip: export strips project_id; import re-injects it and skips
    on (title, client_name) match."""
    await client.post(
        "/api/v1/cases",
        json={"project_id": str(sample_project_id), "title": "Case X", "client_name": "Client Y"},
    )

    exported = (await client.get("/api/v1/cases/export")).json()
    assert exported[0]["title"] == "Case X"
    assert "project_id" not in exported[0]

    resp = await client.post(
        "/api/v1/cases/import",
        params={"project_id": str(sample_project_id), "mode": "skip"},
        files={"file": ("cases.json", json.dumps(exported).encode(), "application/json")},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["skipped"] == 1  # matched existing case


@pytest.mark.asyncio
async def test_import_invalid_mode_rejected(client):
    """mode must be skip|overwrite|rename — anything else is a 422."""
    resp = await client.post(
        "/api/v1/workflows/import",
        params={"mode": "bogus"},
        files={"file": ("w.json", b"[]", "application/json")},
    )
    assert resp.status_code == 422
