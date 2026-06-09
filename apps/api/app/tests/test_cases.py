"""Tests for Case CRUD API endpoints."""

import uuid

import pytest


@pytest.mark.asyncio
async def test_create_case(client, sample_project_id):
    """Test creating a case study."""
    payload = {
        "project_id": str(sample_project_id),
        "title": "Test Case Study",
        "client_name": "Test Client Corp",
        "industry": "Finance",
        "challenge": "Outdated systems causing delays",
        "solution": "Cloud migration with microservices",
        "results": "50% faster processing",
        "technologies": "AWS, Kubernetes, Python",
        "duration": "6 months",
        "team_size": 8,
        "budget_range": "$500K - $700K",
        "is_published": True,
    }
    response = await client.post("/api/v1/cases", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["title"] == "Test Case Study"
    assert data["data"]["qualityScore"] is None
    return data["data"]["id"]


@pytest.mark.asyncio
async def test_list_cases(client, sample_project_id):
    """Test listing case studies."""
    # Create a case first
    payload = {
        "project_id": str(sample_project_id),
        "title": "List Test Case",
        "client_name": "List Client",
    }
    await client.post("/api/v1/cases", json=payload)

    response = await client.get("/api/v1/cases")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_list_cases_by_project(client, sample_project_id):
    """Test filtering cases by project."""
    payload = {
        "project_id": str(sample_project_id),
        "title": "Filtered Case",
        "client_name": "Filter Client",
    }
    await client.post("/api/v1/cases", json=payload)

    response = await client.get(f"/api/v1/cases?project_id={sample_project_id}")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["projectId"] == str(sample_project_id)


@pytest.mark.asyncio
async def test_update_case(client, sample_project_id):
    """Test updating a case study."""
    payload = {
        "project_id": str(sample_project_id),
        "title": "Update Test Case",
        "client_name": "Update Client",
    }
    create_resp = await client.post("/api/v1/cases", json=payload)
    case_id = create_resp.json()["data"]["id"]

    update_payload = {
        "title": "Updated Case Title",
        "results": "Excellent results achieved",
        "is_published": True,
    }
    response = await client.put(f"/api/v1/cases/{case_id}", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["title"] == "Updated Case Title"
    assert data["data"]["isPublished"] is True


@pytest.mark.asyncio
async def test_update_quality_score(client, sample_project_id):
    """Test updating a case's quality score."""
    payload = {
        "project_id": str(sample_project_id),
        "title": "Quality Score Test",
        "client_name": "Score Client",
    }
    create_resp = await client.post("/api/v1/cases", json=payload)
    case_id = create_resp.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/cases/{case_id}/quality-score",
        json={"case_id": case_id, "score": 92.5},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["qualityScore"] == 92.5


@pytest.mark.asyncio
async def test_delete_case(client, sample_project_id):
    """Test deleting a case study."""
    payload = {
        "project_id": str(sample_project_id),
        "title": "Delete Test Case",
        "client_name": "Delete Client",
    }
    create_resp = await client.post("/api/v1/cases", json=payload)
    case_id = create_resp.json()["data"]["id"]

    response = await client.delete(f"/api/v1/cases/{case_id}")
    assert response.status_code == 200

    # Verify deletion
    get_resp = await client.get(f"/api/v1/cases/{case_id}")
    assert get_resp.status_code == 404
