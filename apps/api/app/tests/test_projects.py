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
