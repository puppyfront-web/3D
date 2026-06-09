"""Tests for SOP Workflows API — CRUD and import."""

import uuid

import pytest


class TestWorkflowCRUD:
    """Test SOP workflow CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_create_workflow(self, client):
        response = await client.post(
            "/api/v1/workflows",
            json={
                "name": "Test SOP Workflow",
                "description": "A test SOP",
                "version": "1.0",
                "steps": [
                    {"order": 1, "name": "企业信息采集", "description": "采集企业基础信息", "agent": "company_analysis"},
                    {"order": 2, "name": "策划案生成", "description": "生成策划案初稿", "agent": "proposal_generation"},
                ],
                "pipeline_stages": [
                    {"stage": "enterprise_understanding", "name": "企业理解", "description": "理解企业背景"},
                    {"stage": "proposal_creation", "name": "策划案生成", "description": "生成策划案"},
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["name"] == "Test SOP Workflow"
        assert data["version"] == "1.0"
        assert len(data["steps"]) == 2
        return data["id"]

    @pytest.mark.asyncio
    async def test_list_workflows(self, client):
        response = await client.get("/api/v1/workflows")
        assert response.status_code == 200
        assert "items" in response.json()

    @pytest.mark.asyncio
    async def test_get_workflow(self, client):
        create_resp = await client.post(
            "/api/v1/workflows",
            json={"name": "Get Test SOP", "version": "2.0", "steps": []},
        )
        wf_id = create_resp.json()["data"]["id"]

        response = await client.get(f"/api/v1/workflows/{wf_id}")
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Get Test SOP"

    @pytest.mark.asyncio
    async def test_update_workflow(self, client):
        create_resp = await client.post(
            "/api/v1/workflows",
            json={"name": "Before Update", "version": "1.0", "steps": []},
        )
        wf_id = create_resp.json()["data"]["id"]

        response = await client.put(
            f"/api/v1/workflows/{wf_id}",
            json={"name": "After Update", "version": "2.0"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "After Update"
        assert response.json()["data"]["version"] == "2.0"

    @pytest.mark.asyncio
    async def test_delete_workflow(self, client):
        create_resp = await client.post(
            "/api/v1/workflows",
            json={"name": "Delete SOP", "version": "1.0", "steps": []},
        )
        wf_id = create_resp.json()["data"]["id"]

        response = await client.delete(f"/api/v1/workflows/{wf_id}")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_filter_active_workflows(self, client):
        response = await client.get("/api/v1/workflows", params={"is_active": "true"})
        assert response.status_code == 200
        for item in response.json()["items"]:
            assert item["is_active"] is True

    @pytest.mark.asyncio
    async def test_get_nonexistent_workflow(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/workflows/{fake_id}")
        assert response.status_code == 404
