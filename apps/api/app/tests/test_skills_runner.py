"""Tests for Skills API — list, execute, execution history."""

import uuid

import pytest


class TestSkillsAPI:
    """Test Skill listing and execution endpoints."""

    @pytest.mark.asyncio
    async def test_list_skills(self, client):
        response = await client.get("/api/v1/skills")
        assert response.status_code == 200
        data = response.json()["data"]
        assert isinstance(data, list)
        # Should have at least the 5 built-in skills
        skill_ids = [s["skill_id"] for s in data]
        assert "company_analysis" in skill_ids
        assert "proposal_generation" in skill_ids
        assert "visual_prompt" in skill_ids
        assert "export" in skill_ids

    @pytest.mark.asyncio
    async def test_get_skill_by_id(self, client):
        response = await client.get("/api/v1/skills/company_analysis")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["skill_id"] == "company_analysis"
        assert data["name"] == "企业解析"
        assert "category" in data

    @pytest.mark.asyncio
    async def test_get_nonexistent_skill(self, client):
        response = await client.get("/api/v1/skills/nonexistent_skill")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_executions_empty(self, client):
        response = await client.get("/api/v1/skills/executions")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_execute_skill_missing_llm(self, client, sample_project_id):
        """Execute skill without LLM service — should return error gracefully."""
        response = await client.post(
            "/api/v1/skills/proposal_generation/execute",
            json={
                "input_data": {"project_id": str(sample_project_id)},
                "project_id": str(sample_project_id),
            },
        )
        # May succeed or fail depending on mock setup, but should not 500
        assert response.status_code in (200, 400, 422)
        if response.status_code == 200:
            data = response.json()["data"]
            assert "success" in data

    @pytest.mark.asyncio
    async def test_execute_skill_invalid_id(self, client):
        response = await client.post(
            "/api/v1/skills/nonexistent_skill/execute",
            json={"input_data": {}},
        )
        assert response.status_code == 404


class TestSkillsManifest:
    """Test that each built-in skill has proper manifest."""

    @pytest.mark.asyncio
    async def test_each_skill_has_required_fields(self, client):
        response = await client.get("/api/v1/skills")
        skills = response.json()["data"]
        for skill in skills:
            assert skill["skill_id"], f"Missing skill_id"
            assert skill["name"], f"Missing name for {skill['skill_id']}"
            assert skill["category"], f"Missing category for {skill['skill_id']}"
            assert skill.get("visibility") in ("internal", "public", None)
            # status may or may not be in the listing response
            if "status" in skill:
                assert skill["status"] in ("active", "disabled", "deprecated")
