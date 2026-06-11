"""Tests for Project API endpoints."""

import uuid

import pytest

from app.models.project import Company, Project
from app.models.user import Role, User


@pytest.mark.asyncio
async def test_list_projects_empty(client):
    """Test listing projects when none exist."""
    response = await client.get("/api/v1/projects")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_create_project(client, sample_company_id, sample_user_id):
    """Test creating a project via the API."""
    payload = {
        "name": "API Test Project",
        "description": "Created via test",
        "company_id": str(sample_company_id),
        "owner_id": str(sample_user_id),
        "status": "draft",
        "priority": "high",
    }
    response = await client.post("/api/v1/projects", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["name"] == "API Test Project"
    assert data["data"]["status"] == "draft"
    return data["data"]["id"]


@pytest.mark.asyncio
async def test_list_projects_after_create(client, sample_company_id, sample_user_id):
    """Test that created projects appear in the list."""
    # Create a project first
    payload = {
        "name": "List Test Project",
        "company_id": str(sample_company_id),
        "owner_id": str(sample_user_id),
    }
    await client.post("/api/v1/projects", json=payload)

    # List projects
    response = await client.get("/api/v1/projects")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    names = [p["name"] for p in data["items"]]
    assert "List Test Project" in names


@pytest.mark.asyncio
async def test_get_project_by_id(client, sample_company_id, sample_user_id):
    """Test retrieving a single project by ID."""
    # Create
    payload = {
        "name": "Get Test Project",
        "company_id": str(sample_company_id),
        "owner_id": str(sample_user_id),
    }
    create_response = await client.post("/api/v1/projects", json=payload)
    project_id = create_response.json()["data"]["id"]

    # Get
    response = await client.get(f"/api/v1/projects/{project_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["name"] == "Get Test Project"


@pytest.mark.asyncio
async def test_update_project(client, sample_company_id, sample_user_id):
    """Test updating a project."""
    # Create
    payload = {
        "name": "Update Test Project",
        "company_id": str(sample_company_id),
        "owner_id": str(sample_user_id),
    }
    create_response = await client.post("/api/v1/projects", json=payload)
    project_id = create_response.json()["data"]["id"]

    # Update
    update_payload = {"name": "Updated Project Name", "priority": "high"}
    response = await client.put(f"/api/v1/projects/{project_id}", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["name"] == "Updated Project Name"
    assert data["data"]["priority"] == "high"


@pytest.mark.asyncio
async def test_update_project_status(client, sample_company_id, sample_user_id):
    """Test updating a project's status."""
    payload = {
        "name": "Status Test Project",
        "company_id": str(sample_company_id),
        "owner_id": str(sample_user_id),
    }
    create_response = await client.post("/api/v1/projects", json=payload)
    project_id = create_response.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/projects/{project_id}/status",
        json={"status": "in_progress"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["status"] == "in_progress"


@pytest.mark.asyncio
async def test_delete_project(client, sample_company_id, sample_user_id):
    """Test deleting a project."""
    payload = {
        "name": "Delete Test Project",
        "company_id": str(sample_company_id),
        "owner_id": str(sample_user_id),
    }
    create_response = await client.post("/api/v1/projects", json=payload)
    project_id = create_response.json()["data"]["id"]

    response = await client.delete(f"/api/v1/projects/{project_id}")
    assert response.status_code == 200

    # Verify it's gone
    get_response = await client.get(f"/api/v1/projects/{project_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_get_nonexistent_project(client):
    """Test that requesting a non-existent project returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/projects/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_projects_pagination(client, sample_company_id, sample_user_id):
    """Test project list pagination."""
    # Create multiple projects
    for i in range(3):
        payload = {
            "name": f"Page Test Project {i}",
            "company_id": str(sample_company_id),
            "owner_id": str(sample_user_id),
        }
        await client.post("/api/v1/projects", json=payload)

    # Request page 1 with size 2
    response = await client.get("/api/v1/projects?page=1&page_size=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 2
    assert data["page"] == 1
    assert data["pageSize"] == 2


@pytest.mark.asyncio
async def test_create_project_wizard_chain(client, sample_user_id):
    """Wizard endpoint resolves owner + company and round-trips screen_info.

    Regression for the previously-broken create-project chain (§21 #1/#2):
    the frontend posts a nested camelCase payload; the endpoint must accept it,
    default the owner, create-or-get the company, and persist screen_info.
    """
    payload = {
        "step1": {
            "projectName": "智慧城市裸眼3D幕墙方案",
            "clientName": "深圳市光影科技有限公司",
            "industry": "智慧城市",
            "projectType": "3D可视化",
            "description": "户外裸眼3D媒体立面",
            "priority": "high",
            "dueDate": "2026-09-01",
        },
        "screen": {
            "screenType": "裸眼3D",
            "screenSize": "10m × 6m",
            "pitch": "P3.91",
            "resolution": "1920×1080",
            "installEnvironment": "户外",
            "viewingDistance": "10-20米",
            "mainViewpoint": "正面",
            "notes": "户外强光环境",
        },
    }
    response = await client.post("/api/v1/projects/wizard", json=payload)
    assert response.status_code == 201, response.text
    project = response.json()["data"]
    assert project["name"] == "智慧城市裸眼3D幕墙方案"
    assert project["status"] == "draft"
    assert project["priority"] == "high"
    # screen_info round-trips (top-level key camelCased by alias; nested keys
    # stay snake_case since it's a stored JSON dict)
    assert project["screenInfo"]["screen_type"] == "裸眼3D"
    assert project["screenInfo"]["pitch"] == "P3.91"
    assert project["screenInfo"]["install_environment"] == "户外"

    # Follow-up GET sees the persisted screen_info
    get_resp = await client.get(f"/api/v1/projects/{project['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["screenInfo"]["resolution"] == "1920×1080"


@pytest.mark.asyncio
async def test_create_project_wizard_idempotent_company(client, db_session, sample_user_id):
    """A second wizard call with the same client_name reuses the company."""
    base = {"step1": {"projectName": "项目", "clientName": "复用客户有限公司"}}
    r1 = await client.post(
        "/api/v1/projects/wizard",
        json={**base, "step1": {**base["step1"], "projectName": "项目A"}, "screen": {"screenType": "LED显示屏"}},
    )
    assert r1.status_code == 201, r1.text
    r2 = await client.post(
        "/api/v1/projects/wizard",
        json={**base, "step1": {**base["step1"], "projectName": "项目B"}, "screen": {"screenType": "小间距LED"}},
    )
    assert r2.status_code == 201, r2.text

    from app.models.project import Company, Project
    from sqlalchemy import select

    company = (
        await db_session.execute(select(Company).where(Company.name == "复用客户有限公司"))
    ).scalar_one()
    projects = (
        await db_session.execute(select(Project).where(Project.company_id == company.id))
    ).scalars().all()
    assert len(projects) == 2
