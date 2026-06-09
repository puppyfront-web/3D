"""Tests for Templates API — prompt templates and proposal templates."""

import uuid

import pytest


class TestPromptTemplates:
    """Test prompt template CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_create_prompt_template(self, client):
        response = await client.post(
            "/api/v1/templates/prompts",
            json={
                "name": "Test Prompt",
                "description": "A test prompt template",
                "category": "generation",
                "template_text": "Generate a proposal for {project_name}",
                "variables": ["project_name"],
            },
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["name"] == "Test Prompt"
        assert data["category"] == "generation"
        return data["id"]

    @pytest.mark.asyncio
    async def test_list_prompt_templates(self, client):
        response = await client.get("/api/v1/templates/prompts")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_get_prompt_template(self, client):
        create_resp = await client.post(
            "/api/v1/templates/prompts",
            json={
                "name": "Get Test Prompt",
                "category": "visual",
                "template_text": "Create visual for {style}",
                "variables": ["style"],
            },
        )
        template_id = create_resp.json()["data"]["id"]

        response = await client.get(f"/api/v1/templates/prompts/{template_id}")
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Get Test Prompt"

    @pytest.mark.asyncio
    async def test_update_prompt_template(self, client):
        create_resp = await client.post(
            "/api/v1/templates/prompts",
            json={"name": "Before Update", "category": "generation", "template_text": "old text"},
        )
        template_id = create_resp.json()["data"]["id"]

        response = await client.put(
            f"/api/v1/templates/prompts/{template_id}",
            json={"name": "After Update", "template_text": "new text"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "After Update"
        assert response.json()["data"]["template_text"] == "new text"

    @pytest.mark.asyncio
    async def test_delete_prompt_template(self, client):
        create_resp = await client.post(
            "/api/v1/templates/prompts",
            json={"name": "To Delete", "category": "generation", "template_text": "text"},
        )
        template_id = create_resp.json()["data"]["id"]

        response = await client.delete(f"/api/v1/templates/prompts/{template_id}")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_filter_by_category(self, client):
        await client.post(
            "/api/v1/templates/prompts",
            json={"name": "Cat Test", "category": "analysis", "template_text": "text"},
        )
        response = await client.get("/api/v1/templates/prompts", params={"category": "analysis"})
        assert response.status_code == 200
        for item in response.json()["items"]:
            assert item["category"] == "analysis"


class TestProposalTemplates:
    """Test proposal template CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_create_proposal_template(self, client):
        response = await client.post(
            "/api/v1/templates/proposals",
            json={
                "name": "Test Proposal Template",
                "description": "A test proposal template",
                "category": "standard",
                "sections": {"chapters": ["需求理解", "企业解析"]},
            },
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["name"] == "Test Proposal Template"

    @pytest.mark.asyncio
    async def test_list_proposal_templates(self, client):
        response = await client.get("/api/v1/templates/proposals")
        assert response.status_code == 200
        assert "items" in response.json()

    @pytest.mark.asyncio
    async def test_update_proposal_template(self, client):
        create_resp = await client.post(
            "/api/v1/templates/proposals",
            json={"name": "Old Name", "category": "standard", "sections": {}},
        )
        template_id = create_resp.json()["data"]["id"]

        response = await client.put(
            f"/api/v1/templates/proposals/{template_id}",
            json={"name": "New Name"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "New Name"

    @pytest.mark.asyncio
    async def test_delete_proposal_template(self, client):
        create_resp = await client.post(
            "/api/v1/templates/proposals",
            json={"name": "Delete Me", "category": "standard", "sections": {}},
        )
        template_id = create_resp.json()["data"]["id"]

        response = await client.delete(f"/api/v1/templates/proposals/{template_id}")
        assert response.status_code == 200
